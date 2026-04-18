import shutil
import os
import numpy as np
import time
from tqdm import tqdm
import torch
from torch import nn
from torch.utils.data import DataLoader
from torch.optim import Adam
from transformers.optimization import get_linear_schedule_with_warmup

from . import data_reader
from . import utils
from . import dataset
from . import model


class TrainRunner(utils.Runner):

    def __init__(self, args):
        super().__init__(args)
        config = self.config
        config.update(args, ignore_none=True)

        log_save_path, config.model_save_dir = self.init_output_dir()
        self.logger = utils.set_logger(log_save_path, debug=args.debug)

        self.init_torch()
        self.data = data_reader.init_data(config.data_paths, config)
        if config.model_name == 'generaldl':
            self.model_class = model.GeneralDL
            self.cal_metric = utils.cal_generaldl_metric
        elif config.model_name == 'specdl':
            self.model_class = model.SpecDL
            self.cal_metric = utils.cal_specdl_metric
        else:
            raise ValueError('Unknown model: {}'.format(config.model_name))

    def init_output_dir(self):
        config = self.config
        exp_name = config.exp_name

        exp_path = f'{config.exp_parent_path}/{exp_name}'
        model_save_dir = exp_path
        log_save_path = f'{exp_path}/log.txt'
        config_save_path = f'{exp_path}/config.yaml'
        if not self.args.override and os.path.exists(exp_path):
            raise Exception(f'Experiment {exp_name} already exists! Use -or for overriding!')
        
        output_dirs = [config.exp_parent_path, exp_path, model_save_dir]
        for dir_ in output_dirs:
            os.makedirs(dir_, exist_ok=True)
        if os.path.abspath(self.args.config_path) != os.path.abspath(config_save_path):
            shutil.copy(self.args.config_path, config_save_path)
        return log_save_path, model_save_dir
    
    def init_model(self):
        config = self.config
        freeze_layers = config.freeze_layers
        freeze_layers_reversed = config.freeze_layers_reversed
        model = self.model_class(config).to(self.device)
        if isinstance(freeze_layers, str):
            freeze_layers = freeze_layers.replace(' ', '').split(',')
        if isinstance(freeze_layers, list):
            for layer_name, layer_param in model.named_parameters():
                should_freeze = any(layer_name.startswith(freeze_layer) for freeze_layer in freeze_layers)
                layer_param.requires_grad = not (freeze_layers_reversed ^ should_freeze)
                if freeze_layers_reversed ^ should_freeze:
                    self.logger.info(f'Freezing {layer_name}')
        return model

    def run_cv_train(self):
        data = self.data
        num_tasks = len(data)
        config = self.config
        X = [np.asarray(data[i]['features']) for i in range(num_tasks)]
        y = [np.asarray(data[i]['target']) for i in range(num_tasks)]
        group = [data[i]['group'] for i in range(num_tasks)]

        self.cv_idx = dataset.split_cv(X, y, group, config)
        for fold, idx_list in enumerate(self.cv_idx):
            self.logger.info(f'----------- Start training fold {fold} ---------------')
            train_subsets, valid_subsets = [], []
            for i, (tr_idx, te_idx) in enumerate(idx_list):
                train_subsets.append(dataset.SubDataset(X[i][tr_idx], y[i][tr_idx], i))
                valid_subsets.append(dataset.SubDataset(X[i][te_idx], y[i][te_idx], i))
            train_set = dataset.MultipleDataset(train_subsets, config)
            valid_set = dataset.MultipleDataset(valid_subsets, config)
            self.run_fold_train(train_set, valid_set, fold)
    
    def run_fold_train(self, train_set, valid_set, fold):
        config = self.config
        max_epochs = config.max_epochs
        model = self.init_model()
        train_loader = self.resample_and_load_dataset(train_set)
        num_training_steps = len(train_loader) * max_epochs
        num_warmup_steps = int(num_training_steps * config.warmup_ratio)
        optimizer = Adam(model.parameters(), lr=float(config.learning_rate), eps=1e-6)
        scheduler = get_linear_schedule_with_warmup(
            optimizer, num_warmup_steps=num_warmup_steps, num_training_steps=num_training_steps)
        scaler = torch.cuda.amp.GradScaler()

        wait = 0
        max_metric = float('-inf')
        for epoch in range(max_epochs):
            model = model.train()
            start_time = time.time()
            prog_bar = tqdm(total=len(train_loader), dynamic_ncols=True,
                             leave=False, position=0, desc='Train', ncols=5)
            train_loss = []
            for i, batch in enumerate(train_loader):
                batch = {k: v.to(self.device) for k, v in batch.items()}
                optimizer.zero_grad()
                with torch.cuda.amp.autocast():
                    outputs = model(**batch)
                    loss = outputs['loss']
                train_loss.append(float(loss.data))

                prog_bar.set_postfix(
                    Epoch="Epoch {}/{}".format(epoch+1, max_epochs),
                    loss="{:.04f}".format(float(sum(train_loss) / (i + 1))),
                    lr="{:.04f}".format(float(optimizer.param_groups[0]['lr'])))
                prog_bar.update()

                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), config.max_norm)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()

            prog_bar.close()
            mean_train_loss = np.mean(train_loss)

            val_loss, metric = self.validate(model, valid_set, epoch)
            end_time = time.time()
            mean_val_loss = np.mean(val_loss)
            message = 'Epoch [{}/{}] train_loss: {:.4f}, val_loss: {:.4f}, val_auc: {}, lr: {:.6f}, {:.1f}s'.format(
                epoch + 1, config.max_epochs, mean_train_loss, mean_val_loss, metric, 
                optimizer.param_groups[0]['lr'], (end_time - start_time))
            self.logger.info(message)
            end_training, max_metric, wait = self.determine_ending(np.mean(metric), max_metric, wait)
            if wait == 0:
                saved_dict = {'model_state_dict': model.state_dict(), 'epoch': epoch+1}
                torch.save(saved_dict, f'{config.model_save_dir}/model_{fold}.pth')

            if end_training:
                self.logger.warning(f'Early stopping at epoch: {epoch + 1}')
                break

            train_loader = self.resample_and_load_dataset(train_set)
    
    def determine_ending(self, metric, max_metric, wait):
        end_training = False
        if metric >= max_metric:
            max_metric = metric
            wait = 0
        elif metric <= max_metric:
            wait += 1
            if wait >= self.config.patience:
                end_training = True
        return end_training, max_metric, wait

    def validate(self, model: nn.Module, valid_set: dataset.MultipleDataset, epoch: int):
        config = self.config
        valid_set_lens = [len(subset) for subset in valid_set.subset_list]
        valid_sampler = dataset.MultiDatasetPredictSampler(dataset_lens=valid_set_lens)
        valid_loader = DataLoader(dataset=valid_set, batch_size=config.batch_size,
            shuffle=False, collate_fn=valid_set.collate_fn, sampler=valid_sampler)
        
        model = model.eval()
        prog_bar = tqdm(total=len(valid_loader), dynamic_ncols=True,
                        position=0, leave=False, desc='val', ncols=5)
        val_loss = []
        val_preds = []
        val_reals = []
        for i, batch in enumerate(valid_loader):
            batch = {k: v.to(self.device) for k, v in batch.items()}
            with torch.no_grad():
                outputs = model(**batch, return_pred=True)
                loss = outputs['loss']
                val_pred = outputs['predict'].cpu().numpy()
                val_loss.append(float(loss.data))
            val_preds.append(val_pred)
            val_reals.append(batch['target'].cpu().numpy())
            
            prog_bar.set_postfix(
                Epoch="Epoch {}/{}".format(epoch+1, config.max_epochs),
                loss="{:.04f}".format(float(np.sum(val_loss) / (i + 1))))
            prog_bar.update()
        val_preds = np.concatenate(val_preds)
        val_reals = np.concatenate(val_reals)
        metric = self.cal_metric(val_reals, val_preds)
        return val_loss, metric

    def resample_and_load_dataset(self, train_set):
        config = self.config
        logger = self.logger
        dataset_lens = []
        new_subset_list = []
        for i, subset in enumerate(train_set.subset_list):
            new_subset = subset
            if config.do_resample[i]:
                num_each_class = config.resample_target_size[i] // 2
                pos_prop = subset.label.sum() / len(subset)
                less_prop = pos_prop if pos_prop < 0.5 else 1 - pos_prop
                less_class = 1 if pos_prop < 0.5 else 0
                less_idx = np.where(subset.label == less_class)[0]
                more_idx = np.where(subset.label != less_class)[0]

                if num_each_class > len(more_idx):
                    num_each_class = len(more_idx)
                    logger.warning(f'Warning: Target re-sampling size exceeds max possible size, re-set to {num_each_class*2}')

                oversample_fold = num_each_class // len(less_idx)
                oversample_remainder = num_each_class % len(less_idx)
                oversampled_less_idx = np.repeat(less_idx, oversample_fold)
                oversampled_less_idx = np.concatenate([oversampled_less_idx,
                    np.random.choice(less_idx, oversample_remainder, replace=False)])
                downsampled_more_idx = np.random.choice(more_idx, num_each_class, replace=False)
                new_idx = np.concatenate([oversampled_less_idx, downsampled_more_idx])

                resampled_data = [subset.feature[i] for i in new_idx]
                resampled_labels = [subset.label[i] for i in new_idx]
                new_subset = dataset.SubDataset(resampled_data, resampled_labels, subset_idx=i)
                logger.info(f'Re-sampled on dataset {i}')
                logger.info(f'Dataset size after resampling {len(new_idx)}')
                logger.info(f'Less class ({less_class}) proportion before resampling: {less_prop}')
                logger.info(f'Less class ({less_class}) proportion after resampling: {len(oversampled_less_idx)/len(new_idx)}')

            new_subset_list.append(new_subset)
            dataset_lens.append(len(new_subset))

        new_multi_set = dataset.MultipleDataset(new_subset_list, config)
        train_sampler = dataset.MultiDatasetTrainSampler(dataset_lens=dataset_lens, 
                                                         num_iters=config.num_iters,
                                                         dataset_weights=config.dataset_weights)
        train_dataloader = DataLoader(dataset=new_multi_set, batch_size=config.batch_size,
                                      collate_fn=new_multi_set.collate_fn, drop_last=False, sampler=train_sampler)
        return train_dataloader
