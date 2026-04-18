import numpy as np
import torch
from torch.utils.data import Dataset, Sampler
from itertools import cycle
from sklearn.model_selection import GroupKFold, KFold


def split_cv(data, target, group, config):
    if config.split_method == 'scaffold':
        splitter = GroupKFold(n_splits=config.kfold)
    elif config.split_method == 'random':
        splitter = KFold(n_splits=config.kfold, shuffle=True)

    assert len(data) == len(target) == len(group)
    output = []
    for i, X in enumerate(data):
        y = target[i]
        grp = group[i]
        output.append(list(splitter.split(X, y, grp)))
    
    return list(zip(*output))


class MultiDatasetPredictSampler(Sampler):
    def __init__(self, dataset_lens):
        self.dataset_lens = dataset_lens
        self.num_datasets = len(dataset_lens)
        self.total_samples = sum(dataset_lens)
        print('Eval Dataset Lengths:', dataset_lens)
        print('Eval Total Samples:', self.total_samples)

    def __iter__(self):
        for dataset_idx in range(self.num_datasets):
            for sample_idx in range(self.dataset_lens[dataset_idx]):
                yield dataset_idx, sample_idx

    def __len__(self):
        return self.total_samples

class MultiDatasetTrainSampler(Sampler):
    def __init__(self, dataset_lens, num_iters=None, dataset_weights=None):
        self.dataset_lens = dataset_lens
        self.num_datasets = len(dataset_lens)
        self.num_iters = num_iters
        self.dataset_weights = dataset_weights

        if self.dataset_weights is None:
            self.dataset_weights = np.ones(self.num_datasets) / self.num_datasets
        else:
            self.dataset_weights = np.array(self.dataset_weights, dtype=float)
            self.dataset_weights /= self.dataset_weights.sum()

        self.num_iters = int(np.mean(dataset_lens) * self.num_datasets) \
            if num_iters is None else num_iters
        print('Dataset Lengths:', dataset_lens)
        print('Num Iterations per Epoch:', self.num_iters)

    def __iter__(self):
        dataset_iter = cycle(np.random.choice(self.num_datasets, self.num_iters, 
                                               p=self.dataset_weights))
        iterators = [cycle(np.random.permutation(range(self.dataset_lens[i]))) 
                     for i in range(self.num_datasets)]
        for _ in range(self.num_iters):
            dataset_idx = next(dataset_iter)
            iterator = iterators[dataset_idx]
            yield dataset_idx, next(iterator)

    def __len__(self):
        return self.num_iters


class MultipleDataset(Dataset):
    def __init__(self, subset_list, config):
        self.subset_list = subset_list
        self.num_subset = len(subset_list)
        self.subset_lens = [len(subset) for subset in subset_list]
        self.num_tasks = config.num_tasks
    
    def __len__(self):
        return sum(len(dataset) for dataset in self.subset_list)

    def __getitem__(self, index):
        subset_idx, data_idx = index
        return self.subset_list[subset_idx][data_idx]

    def collate_fn(self, samples):
        batch = {}
        subset_idx_list = []
        input_ids, attention_mask = [], []
        label = np.full((len(samples), self.num_tasks), np.nan)
        for i, s in enumerate(samples):
            subset_idx = s[2]
            subset_idx_list.append(subset_idx)
            label[i][subset_idx] = s[1]
            if type(s[0]) is dict:
                input_ids.append(s[0]['input_ids'])
                attention_mask.append(s[0]['attention_mask'])
            else:
                for j in range(2):
                    input_ids.append(s[0][j]['input_ids'])
                    attention_mask.append(s[0][j]['attention_mask'])
        
        batch['input_ids'] = torch.stack(input_ids)
        batch['attention_mask'] = torch.stack(attention_mask)
        batch['subset'] = torch.tensor(subset_idx_list)
        batch['target'] = torch.tensor(label)
        return batch


class SubDataset(Dataset):
    def __init__(self, feature, label, subset_idx):
        self.feature = feature
        self.label: np.ndarray = label
        self.subset_idx = subset_idx
    
    def __len__(self):
        return len(self.feature)
    
    def __getitem__(self, idx):
        return self.feature[idx], self.label[idx], self.subset_idx
