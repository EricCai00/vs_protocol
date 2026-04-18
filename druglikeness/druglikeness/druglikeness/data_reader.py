import numpy as np
import pandas as pd
from transformers import AutoTokenizer
from datasets import Dataset
from rdkit.Chem.Scaffolds import MurckoScaffold

pretrained_path = '/public/home/caiyi/eric_github/generaldl/weights/chemberta'


def smi2scaffold(smi):
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(smiles=smi, includeChirality=True)
    except:
        return smi


def read_data(data, config):
    smiles_col = config.smiles_col
    split_group_col = config.split_group_col

    if isinstance(data, str):
        data = pd.read_csv(data)
        targets = data[[config.target_col]].values.tolist()
        targets = np.array(targets).reshape(-1,1).astype(np.float32)
    elif isinstance(data, list):
        data = pd.DataFrame(data, columns=['smiles'])
        targets = np.full((len(data), 1), np.nan)
    else:
        raise ValueError('Unknown data type: {}'.format(type(data)))
    
    data_dict = {'target': targets}
    if smiles_col in data.columns:
        data_dict['smiles'] = data[smiles_col].tolist()
        if 'scaffold' in data.columns:
            data_dict['scaffolds'] = data['scaffold'].to_list()
        else:
            data_dict['scaffolds'] = data[smiles_col].map(smi2scaffold).tolist()
    else:
        data_dict['smiles'] = None
        data_dict['scaffolds'] = None

    if split_group_col in data.columns:
        data_dict['group'] = data[split_group_col].tolist()
    elif split_group_col == 'scaffold':
        data_dict['group'] = data_dict['scaffolds']
    else:
        data_dict['group'] = None

    data_dict['is_pair_data'] = False
    return data_dict


def read_pair_data(data, config):
    smiles_col_0 = config.get('smiles_col_0', 'smiles_i')
    smiles_col_1 = config.get('smiles_col_1', 'smiles_j')
    split_group_col = config.split_group_col

    if isinstance(data, str):
        data = pd.read_csv(data)
    else:
        raise ValueError('Unknown data type: {}'.format(type(data)))

    targets = data[[config.target_col]].values.tolist()
    targets = np.array(targets).reshape(-1,1).astype(np.float32)
    
    data_dict = {'target': targets}
    if smiles_col_0 in data.columns:
        data_dict['smiles_0'] = data[smiles_col_0].tolist()
        data_dict['scaffolds'] = data[smiles_col_0].map(smi2scaffold).tolist()
    else:
        data_dict['smiles_0'] = None
        data_dict['scaffolds'] = None
    
    if smiles_col_1 in data.columns:
        data_dict['smiles_1'] = data[smiles_col_1].tolist()
    else:
        data_dict['smiles_1'] = None
        data_dict['scaffolds'] = None

    if split_group_col in data.columns:
        data_dict['group'] = data[split_group_col].tolist()
    elif split_group_col == 'scaffold':
        data_dict['group'] = data_dict['scaffolds']
    else:
        data_dict['group'] = None

    data_dict['is_pair_data'] = True
    return data_dict
    

def init_data(data_sources, config):
    is_pair_data = config.is_pair_data
    assert len(data_sources) == len(is_pair_data)

    data_list = []
    for i, data_path in enumerate(data_sources):
        print(f'Loading dataset {i}')
        if is_pair_data[i]:
            data_list.append(read_pair_data(data_path, config))
        else:
            data_list.append(read_data(data_path, config))

    for i, data_block in enumerate(data_list):
        tokenizer = AutoTokenizer.from_pretrained(pretrained_path)
        tokenize_function = lambda examples: tokenizer(examples['smiles'], padding='max_length', truncation=True, max_length=300)

        if is_pair_data[i]:
            data_dict_0 = {'smiles': data_block['smiles_0'], 'label': data_block['target']}
            dataset_0 = Dataset.from_dict(data_dict_0).with_format('torch')
            dataset_0 = dataset_0.map(tokenize_function, batched=True)
            input_ids_0 = dataset_0['input_ids']
            attention_mask_0 = dataset_0['attention_mask']
            feature_list_0 = []
            for j in range(len(dataset_0['input_ids'])):
                feature_list_0.append({'input_ids': input_ids_0[j] , 
                                       'attention_mask': attention_mask_0[j]})

            data_dict_1 = {'smiles': data_block['smiles_1'], 'label': data_block['target']}
            dataset_1 = Dataset.from_dict(data_dict_1).with_format('torch')
            dataset_1 = dataset_1.map(tokenize_function, batched=True)
            input_ids_1 = dataset_1['input_ids']
            attention_mask_1 = dataset_1['attention_mask']
            feature_list_1 = []
            for j in range(len(dataset_1['input_ids'])):
                feature_list_1.append({'input_ids': input_ids_1[j], 
                                       'attention_mask': attention_mask_1[j]})
            data_block['features'] = list(zip(feature_list_0, feature_list_1))
        else:
            data_dict = {'smiles': data_block['smiles'], 'label': data_block['target']}
            dataset = Dataset.from_dict(data_dict).with_format('torch')
            
            dataset = dataset.map(tokenize_function, batched=True)
            input_ids = dataset['input_ids']
            attention_mask = dataset['attention_mask']
            feature_list = []
            for j in range(len(dataset['input_ids'])):
                feature_list.append({'input_ids': input_ids[j], 
                                     'attention_mask': attention_mask[j]})
            data_block['features'] = feature_list
    return data_list
