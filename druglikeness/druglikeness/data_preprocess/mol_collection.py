import random
import copy
from tqdm import tqdm
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.Chem import AllChem
from rdkit import DataStructs
from rdkit.Chem import MACCSkeys
import numpy as np
from typing import List
from collections import Counter
import pickle


class Mol:
    def __init__(self, smiles, label, name=None, _repr='smiles', store_mol=True, 
                 store_scaffold=False, chiral_scaffold=True) -> None:
        self.smiles = smiles
        self.store_mol = False
        self.store_mol_name = False if name is None else True
        self.store_scaffold = False
        self.store_inchikey = False
        self.store_molwt = False
        self.store_feature = False
        if store_mol:
            self.store_mol = True
            try:
                self.mol = Chem.MolFromSmiles(smiles)
                if self.mol is None:
                    print(f'Generate mol failed for: {smiles}')
            except:
                print(f'Generate mol failed for: {smiles}')
                self.mol = None
        self.label = label
        self.name = name
        self._repr = _repr
        if store_scaffold:
            self.generate_scaffold(chiral_scaffold)
        # self.inchikey = Chem.MolToInchiKey(self.mol)

    def generate_scaffold(self, chiral_scaffold):
        self.scaffold = MurckoScaffold.MurckoScaffoldSmiles(
            smiles=self.smiles, includeChirality=chiral_scaffold)
        self.store_scaffold = True
        
    def update_str(self):
        self.smiles = Chem.MolToSmiles(self.mol)
        self.inchikey = Chem.MolToInchiKey(self.mol)
        self.store_inchikey = True

    def update_mol(self, new_mol, update_str=True):
        self.mol = new_mol
        if update_str:
            self.update_str()
    
    def update_feature(self, feature):
        self.feature = feature
        self.store_feature = True

    def add_h(self):
        self.mol = Chem.AddHs(self.mol)

    def __repr__(self) -> str:
        return getattr(self, self._repr)


class MolPair:
    def __init__(self, data_0: Mol, data_1: Mol, label: int):
        self.data_0 = data_0
        self.data_1 = data_1
        self.label = label


class MolCollection:
    def __init__(self, data_source=None, name=None, source_format=None, smiles_col='smiles', 
                 label_col='label', name_col=None, label=None, multilabel=False, excluded_cols=None,
                 store_mol=False):
        self.data_list: List[Mol] = []
        self.name = name
        self.store_mol = store_mol
        self.store_mol_name = False
        self.store_scaffold = False
        self.store_inchikey = False
        self.store_molwt = False
        self.store_feature = False
        self.all_h = False
        self.multilabel = multilabel
        # Columns that are not labels (used in multi-label tasks)
        excluded_cols = ['smiles', 'SMILES', 'mol_id'] if excluded_cols is None else excluded_cols
        
        if type(data_source) is str:
            if data_source.endswith('.csv') or source_format == 'csv':
                if name_col:
                    self.store_mol_name = True
                self._load_csv(data_source, smiles_col, label_col, name_col, default_label=label, 
                              multilabel=multilabel, excluded_cols=excluded_cols, store_mol=store_mol)
            elif data_source.endswith('.smi') or source_format == 'smi':
                self.store_mol_name = True
                self._load_smi(data_source, label, delim=' ')
            elif source_format == 'txt':
                self._load_txt(data_source, label)
            else:
                raise Exception('Unsupported data source')
        elif type(data_source) is list:
            if len(data_source) > 0:
                if all([type(data) is str for data in data_source]):
                    self.data_list = [Mol(smiles, label, _repr='smiles',
                                          store_mol=self.store_mol, 
                                          store_scaffold=self.store_scaffold) for smiles in data_source]
                elif all([type(data) is Mol for data in data_source]):
                    self.data_list = data_source
                    self.update_flags()
                elif all([type(data) is MolCollection for data in data_source]):
                    self.build_from_blocks(block_list=data_source)
                else:
                    print(type(data_source[0]))
                    raise Exception('Unsupported data type')
        elif data_source is None:
            pass
        else:
            raise Exception('Unsupported data type')

    def build_from_blocks(self, block_list: List['MolCollection']):
        for block in block_list:
            # self.data_list.extend(block.data_list)
            self.data_list.extend(copy.deepcopy(block.data_list))
        
        self.update_flags()
        if len(set([block.all_h for block in block_list])) > 1:
            raise Exception('Inconsistent hydrogen types among blocks')
        
        self.multilabel = False
        block_multilabel = [block.multilabel for block in block_list]
        assert len(set(block_multilabel)) <= 1
        if True in block_multilabel:
            self.multilabel = True
            block_label_names = [tuple(block.label_names) for block in block_list]
            assert len(set(block_label_names)) <= 1
            self.label_names = block_list[0].label_names
    
    def update_flags(self):
        self.store_mol = all([data.store_mol for data in self.data_list]) if len(self) > 0 else False
        self.store_mol_name = all([data.store_mol_name for data in self.data_list]) if len(self) > 0 else False
        self.store_scaffold = all([data.store_scaffold for data in self.data_list]) if len(self) > 0 else False
        self.store_inchikey = all([data.store_inchikey for data in self.data_list]) if len(self) > 0 else False
        self.store_molwt = all([data.store_molwt for data in self.data_list]) if len(self) > 0 else False
        self.store_feature = all([data.store_feature for data in self.data_list]) if len(self) > 0 else False

    def _load_csv(self, file_path, smiles_col, label_col, name_col=None, 
                 default_label=None, multilabel=False, excluded_cols=[], store_mol=True):
        df = pd.read_csv(file_path)
        # iterator = tqdm(df.iterrows()) if store_mol else df.iterrows()
        iterator = tqdm(df.iterrows())
        if not multilabel:
            if label_col:
                if name_col:
                    for _, row in iterator:
                        self.data_list.append(Mol(row[smiles_col], row[label_col], 
                                                        row[name_col], store_mol=store_mol))
                else:
                    for _, row in iterator:
                        self.data_list.append(Mol(row[smiles_col], row[label_col], store_mol=store_mol))
            else:
                print(f'INFO: Using label {default_label} since not providing label_col')
                if name_col:
                    for _, row in iterator:
                        self.data_list.append(Mol(row[smiles_col], default_label, 
                                                        row[name_col], store_mol=store_mol))
                else:
                    for _, row in iterator:
                        self.data_list.append(Mol(row[smiles_col], default_label, store_mol=store_mol))
        else:
            label_cols = [col for col in df.columns if col not in excluded_cols]
            if name_col:
                for _, row in iterator:
                    self.data_list.append(Mol(row[smiles_col], np.array(row[label_cols]), 
                                                    row[name_col], store_mol=store_mol))
            else:
                for _, row in iterator:
                    self.data_list.append(Mol(row[smiles_col], np.array(row[label_cols]), store_mol=store_mol))
            self.label_names = label_cols
            
    def _load_smi(self, file_path, label, delim=' '):
        with open(file_path) as f:
            lines = f.read().splitlines()
        for line in lines:
            smi, name = line.split(delim)
            self.data_list.append(Mol(smi, label, name))
    
    def _load_txt(self, file_path, label):
        with open(file_path) as f:
            lines = f.read().splitlines()
        for smi in lines:
            self.data_list.append(Mol(smi, label))

    def to_df(self, smiles_col='smiles', label_col='label', name_col='name', include_scaffold=False):
        data_list = []
        if include_scaffold and not self.store_scaffold:
            self.generate_scaffold(chiral_scaffold=True, use_tqdm=True)

        if not self.multilabel:
            for data in self.data_list:
                row = {}
                if self.store_mol_name:
                    row.update({name_col: data.name})
                row.update({smiles_col: data.smiles, label_col: data.label})
                if include_scaffold:
                    row.update({'scaffold': data.scaffold})
                data_list.append(row)
        else:
            n_labels = len(self.label_names)
            for data in self.data_list:
                row = {}
                if self.store_mol_name:
                    row.update({name_col: data.name})
                row.update({smiles_col: data.smiles})
                if include_scaffold:
                    row.update({'scaffold': data.scaffold})
                label_dict = {self.label_names[i]: data.label[i] for i in range(n_labels)}
                row.update(label_dict)
                data_list.append(row)
        return pd.DataFrame(data_list)

    def to_csv(self, file_path, smiles_col='smiles', label_col='label', name_col='name', include_scaffold=False):
        df = self.to_df(smiles_col, label_col, name_col, include_scaffold)
        df.to_csv(file_path, index=False)
    
    def to_smi(self, file_path):
        smi_list = self.get_smiles_list()
        if self.store_mol_name:
            name_list = self.get_name_list()
        else:
            name_list = [i for i in range(1, len(self)+1)]
        assert len(name_list) == len(smi_list)
        with open(file_path, 'w') as f:
            for i in range(len(self)):
                f.write(f'{smi_list[i]} {name_list[i]}\n')
    
    def to_txt(self, file_path):
        smi_list = self.get_smiles_list()
        with open(file_path, 'w') as f:
            for i in range(len(smi_list)):
                f.write(f'{smi_list[i]}\n')

    def get_smiles_list(self):
        return [data.smiles for data in self.data_list]
    
    def get_inchikey_list(self):
        if not self.store_inchikey:
            self.update_str()
        return [data.inchikey for data in self.data_list]
    
    def get_label_array(self):
        return np.array([data.label for data in self.data_list])

    def get_feature_array(self):
        return np.array([data.feature for data in self.data_list])
    
    def get_name_list(self):
        return [data.name for data in self.data_list]

    def get_by_name(self, mol_name):
        if not self.store_mol_name:
            raise Exception('Not storing mol names')
        name_list = self.get_name_list()
        idx = name_list.index(mol_name)
        return self[idx]
    
    def get_by_smiles(self, smiles):
        smiles_list = self.get_smiles_list()
        idx = smiles_list.index(smiles)
        return self[idx]

    def get_by_inchikey(self, key):
        key_list = self.get_inchikey_list()
        idx = key_list.index(key)
        return self[idx]
    
    def shuffle(self, seed=42):
        # When seed=0, sometimes the blocks are shuffled separately??
        random.seed(seed)
        random.shuffle(self.data_list)
    
    def generate_scaffold(self, chiral_scaffold=True, use_tqdm=True):
        print('Generating Murcko scaffold')
        iterator = tqdm(self.data_list) if use_tqdm else self.data_list
        for data in iterator:
            data.generate_scaffold(chiral_scaffold=chiral_scaffold)
        self.store_scaffold = True
    
    def get_scaffold_list(self):
        if not self.store_scaffold:
            self.generate_scaffold(chiral_scaffold=True, use_tqdm=True)
        return [data.scaffold for data in self.data_list]

    def update_str(self):
        for data in tqdm(self.data_list):
            data.update_str()
        self.store_inchikey = True
    
    def calculate_molwt(self):
        for data in self.data_list:
            data.molwt = Descriptors.MolWt(data.mol)
            data.store_molwt = True
        self.store_molwt = True
    
    def add_h(self):
        for data in self.data_list:
            data.add_h()
        self.all_h = True

    def _get_str_sets(self, external_dataset: 'MolCollection', based_on='smiles'):
        print('Caution: Should conduct preprocess before this! Otherwise it\'ll be inaccurate!')
        if based_on == 'smiles':
            external_set = set(external_dataset.get_smiles_list())
            internal_set = set(self.get_smiles_list())
        elif 'inchikey' in based_on:
            external_set = set(external_dataset.get_inchikey_list())
            internal_set = set(self.get_inchikey_list())
            if based_on == 'inchikey_layer1':
                external_set = set([key.split('-')[0] for key in external_set])
                internal_set = set([key.split('-')[0] for key in internal_set])
            elif based_on == 'inchikey_layer1-2':
                external_set = set([key[:-2] for key in external_set])
                internal_set = set([key[:-2] for key in internal_set])
        return internal_set, external_set

    def get_intersection(self, external_dataset: 'MolCollection', based_on='smiles'):
        internal_set, external_set = self._get_str_sets(external_dataset, based_on)
        return internal_set.intersection(external_set)

    def get_difference(self, external_dataset: 'MolCollection', based_on='smiles'):
        internal_set, external_set = self._get_str_sets(external_dataset, based_on)
        return internal_set.difference(external_set)
    
    def remove_intersection(self, external_dataset):
        external_smiles = set(external_dataset.get_smiles_list())
        new_list = []
        for data in self.data_list:
            if not data.smiles in external_smiles:
                new_list.append(data)
        self.data_list = new_list
    
    def get_scaffold_intersection(self, external_dataset: 'MolCollection'):
        external_scaffold = set(external_dataset.get_scaffold_list())
        return set(self.get_scaffold_list()).intersection(external_scaffold)

    def get_scaffold_stats(self, top=None):
        counter = Counter(self.get_scaffold_list())
        return counter.most_common(top)
    
    def get_label_stats(self, return_type='proportion'):
        label_list = self.get_label_array()
        if not self.multilabel:
            stats = {}
            counter = Counter(label_list)
            for i in range(2):
                if return_type == 'proportion':
                    stats[i] = round(counter[i] / len(self), 3)
                elif return_type == 'count':
                    stats[i] = counter[i]
                else:
                    raise Exception(f'Unknown return_type {return_type}')
            return stats
        else:
            raise NotImplementedError
    
    def get_simi_matrix(self, external_dataset: 'MolCollection', fp='ecfp'):
        smiles_list_1 = self.get_smiles_list()
        smiles_list_2 = external_dataset.get_smiles_list()
        
        if fp == 'ecfp':
            fps_1 = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(smiles), 2) 
                    for smiles in tqdm(smiles_list_1, desc='Dataset 1')]
            fps_2 = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(smiles), 2) 
                    for smiles in tqdm(smiles_list_2, desc='Dataset 2')]
        elif fp == 'maccs':
            fps_1 = [MACCSkeys.GenMACCSKeys(Chem.MolFromSmiles(smiles)) 
                    for smiles in tqdm(smiles_list_1, desc="Dataset 1")]
            fps_2 = [MACCSkeys.GenMACCSKeys(Chem.MolFromSmiles(smiles)) 
                    for smiles in tqdm(smiles_list_2, desc="Dataset 2")]

        simi_matrix = np.zeros((len(fps_1), len(fps_2)))
        
        for i, fp1 in tqdm(enumerate(fps_1)):
            similarities = DataStructs.BulkTanimotoSimilarity(fp1, fps_2)
            simi_matrix[i, :] = similarities
        
        return simi_matrix

    def get_max_similarity(self, external_dataset: 'MolCollection', return_type='similarity'):
        smiles_list_1 = self.get_smiles_list()
        smiles_list_2 = external_dataset.get_smiles_list()
        fps_1 = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(smiles), 2) 
                 for smiles in smiles_list_1]
        fps_2 = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(smiles), 2) 
                 for smiles in smiles_list_2]

        max_similarities = []
        most_similar_idx = []
        most_similar_smi = []        
        for i, fp1 in enumerate(fps_1):
            similarities = DataStructs.BulkTanimotoSimilarity(fp1, fps_2)
            max_sim = max(similarities)
            max_similarities.append(max_sim)
            max_sim_idx = similarities.index(max_sim)
            max_sim_smiles = smiles_list_2[max_sim_idx]
            most_similar_idx.append((i, max_sim_idx))
            most_similar_smi.append((i, max_sim_smiles))
        if return_type == 'similarity':
            return max_similarities
        elif return_type == 'index':
            return most_similar_idx
        elif return_type == 'smiles':
            return most_similar_smi
        else:
            raise Exception(f'Unknown return_type {return_type}')
            
    def __len__(self):
        return len(self.data_list)
    
    def __getitem__(self, idx):
        if type(idx) is int:
            return self.data_list[idx]
        elif type(idx) is slice:
            new_dataset = MolCollection(self.data_list[idx], name=f'{self.name}_slice{idx.start}:{idx.stop}')
            return new_dataset
        elif type(idx) is np.ndarray or type(idx) is list:
            if len(idx) > 0:
                sel_data = [self[int(i)] for i in idx]
                return MolCollection(sel_data, name=f'{self.name}_idx{idx[0]}...{idx[-1]}')
            else:
                return MolCollection([], name=f'{self.name}_empty_idx')
        else:
            raise Exception(f'Unsupported slice type {type(idx)}')
    
    def __repr__(self) -> str:
        return f'<Data Set "{self.name}" with {len(self)} Data Points>'

    def __add__(self, other: 'MolCollection') -> 'MolCollection':
        return MolCollection([self, other], name=f'{self.name}+{other.name}')


class MolPairCollection:
    def __init__(self, data_source=None, name=None, smiles_col_0='smiles_i', smiles_col_1='smiles_j',
                 label_col='label', name_col_0=None, name_col_1=None, store_mol=True):
        self.data_list: List[MolPair] = []
        self.name = name
        self.store_mol = store_mol
        self.store_mol_name = False
        self.store_molwt = False
        self.store_inchikey = False

        if type(data_source) is str:
            if data_source.endswith('.csv'):
                if name_col_0 and name_col_1:
                    self.store_mol_name = True
                self._load_csv(data_source, smiles_col_0, smiles_col_1, label_col, name_col_0, name_col_1, store_mol)
        elif type(data_source) is list:
            if len(data_source) > 0:
                if all([type(data) is MolPair for data in data_source]):
                    self.data_list = data_source
                    self.update_flags()
                elif all([type(data) is MolPairCollection for data in data_source]):
                    self.build_from_blocks(block_list=data_source)
                else:
                    print(type(data_source[0]))
                    raise Exception('Unsupported data type')
        elif data_source is None:
            pass
        else:
            raise Exception('Unsupported data type')

    def _load_csv(self, file_path, smiles_col_0, smiles_col_1, label_col, name_col_0=None, name_col_1=None, 
                  store_mol=True):
        df = pd.read_csv(file_path)
        if name_col_0 and name_col_1:
            for _, row in df.iterrows():
                data_0 = Mol(smiles=row[smiles_col_0], label=np.nan, name=row[name_col_0], store_mol=store_mol)
                data_1 = Mol(smiles=row[smiles_col_1], label=np.nan, name=row[name_col_1], store_mol=store_mol)
                self.data_list.append(MolPair(data_0, data_1, label=row[label_col]))
        else:
            for _, row in df.iterrows():
                data_0 = Mol(smiles=row[smiles_col_0], label=np.nan, store_mol=store_mol)
                data_1 = Mol(smiles=row[smiles_col_1], label=np.nan, store_mol=store_mol)
                self.data_list.append(MolPair(data_0, data_1, label=row[label_col]))

    def build_from_blocks(self, block_list: List['MolPairCollection']):
        for block in block_list:
            # self.data_list.extend(block.data_list)
            self.data_list.extend(copy.deepcopy(block.data_list))
        self.update_flags()
    
    def update_flags(self):
        self.store_mol = all([data_pair.data_0.store_mol and data_pair.data_1.store_mol 
                              for data_pair in self.data_list]) if len(self) > 0 else False
        
        self.store_mol_name = all([data_pair.data_0.store_mol_name and data_pair.data_1.store_mol_name 
                                   for data_pair in self.data_list]) if len(self) > 0 else False
        # self.store_scaffold = all([data.store_scaffold for data in self.data_list]) if len(self) > 0 else False
        self.store_inchikey = all([data_pair.data_0.store_inchikey and data_pair.data_1.store_inchikey 
                                   for data_pair in self.data_list]) if len(self) > 0 else False
        self.store_molwt = all([data_pair.data_0.store_molwt and data_pair.data_1.store_molwt 
                                for data_pair in self.data_list]) if len(self) > 0 else False
        # self.store_feature = all([data.store_feature for data in self.data_list]) if len(self) > 0 else False

    def to_df(self, smiles_col_0='smiles_i', smiles_col_1='smiles_j', label_col='label',
              name_col_0='name_i', name_col_1='name_j'):
        data_list = []
        if self.store_mol_name:
            for data_pair in self.data_list:
                data_0 = data_pair.data_0
                data_1 = data_pair.data_1
                data_list.append({name_col_0: data_0.name, smiles_col_0: data_0.smiles, 
                                  name_col_1: data_1.name, smiles_col_1: data_1.smiles, 
                                  label_col: data_pair.label})
        else:
            for data_pair in self.data_list:
                data_0 = data_pair.data_0
                data_1 = data_pair.data_1
                data_list.append({smiles_col_0: data_0.smiles, smiles_col_1: data_1.smiles, 
                                  label_col: data_pair.label})
        return pd.DataFrame(data_list)
    
    def to_separate_dfs(self, smiles_col='smiles', label_col='label', name_col='name'):
        data_list_0 = []
        data_list_1 = []
        if self.store_mol_name:
            for data_pair in self.data_list:
                data_0 = data_pair.data_0
                data_1 = data_pair.data_1
                data_list_0.append({name_col: data_0.name, smiles_col: data_0.smiles, label_col: data_pair.label ^ 1})
                data_list_1.append({name_col: data_1.name, smiles_col: data_1.smiles, label_col: data_pair.label})
        else:
            for data_pair in self.data_list:
                data_0 = data_pair.data_0
                data_1 = data_pair.data_1
                data_list_0.append({smiles_col: data_0.smiles, label_col: data_pair.label ^ 1})
                data_list_1.append({smiles_col: data_1.smiles, label_col: data_pair.label})
        return pd.DataFrame(data_list_0), pd.DataFrame(data_list_1)

    def to_csv(self, file_path, smiles_col_0='smiles_i', smiles_col_1='smiles_j', 
            label_col='label', name_col_0='name_i', name_col_1='name_j'):
        df = self.to_df(smiles_col_0, smiles_col_1, label_col, name_col_0, name_col_1)
        df.to_csv(file_path, index=False)
    
    def to_separate_csvs(self, file_path_prefix, smiles_col='smiles', label_col='label', name_col='name'):
        df_0, df_1 = self.to_separate_dfs(smiles_col, label_col, name_col)
        df_0.to_csv(f'{file_path_prefix}_i.csv', index=False)
        df_1.to_csv(f'{file_path_prefix}_j.csv', index=False)

    def update_str(self):
        for data_pair in tqdm(self.data_list):
            data_pair.data_0.update_str()
            data_pair.data_1.update_str()
        self.store_inchikey = True

    def calculate_molwt(self):
        for data_pair in self.data_list:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            data_0.molwt = Descriptors.MolWt(data_0.mol)
            data_1.molwt = Descriptors.MolWt(data_1.mol)
            data_0.store_molwt = True
            data_1.store_molwt = True
        self.store_molwt = True
    
    def __len__(self):
        return len(self.data_list)
    
    def __add__(self, other: 'MolPairCollection') -> 'MolPairCollection':
        return MolPairCollection([self, other], name=f'{self.name}+{other.name}')
