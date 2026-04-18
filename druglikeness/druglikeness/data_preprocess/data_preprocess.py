from tqdm import tqdm
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem import SaltRemover
from rdkit.DataStructs import TanimotoSimilarity
import numpy as np
from .mol_collection import MolCollection, MolPairCollection

lg = RDLogger.logger()
lg.setLevel(RDLogger.WARNING)

default_clean = ['rdkit_cleanup_and_isotope', 'rdkit_remove_frag', 'remove_inorganic_frag', 'remove_mixture',
                 'mol_weight_1000', 'num_atom_6', 'oboyle_neutralize', 'canonicalize_tautomer']

def oboyle_neutralize(mol):
    pattern = Chem.MolFromSmarts("[+1!h0!$([*]~[-1,-2,-3,-4]),-1!$([*]~[+1,+2,+3,+4])]")
    at_matches = mol.GetSubstructMatches(pattern)
    at_matches_list = [y[0] for y in at_matches]
    if len(at_matches_list) > 0:
        for at_idx in at_matches_list:
            atom = mol.GetAtomWithIdx(at_idx)
            chg = atom.GetFormalCharge()
            hcount = atom.GetTotalNumHs()
            atom.SetFormalCharge(0)
            atom.SetNumExplicitHs(hcount - chg)
            atom.UpdatePropertyCache()
    return mol

def is_organic(mol):
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 6:
            return True
    return False


class DataProcessor:
    def __init__(self, clean_steps=None):
        self.clean_steps = default_clean if clean_steps is None else clean_steps

    def preprocess(self, dataset: MolCollection, use_tqdm=True):
        original_len = len(dataset)
        print(f'Original data set length: {original_len}')
        self.remove_none_mol(dataset)
        print(f'Data set length after removing None mol: {len(dataset)}')
        for process_step in self.clean_steps:
            process_fn = getattr(self, process_step)
            process_fn(dataset, use_tqdm=use_tqdm)
        dataset.update_str()
        print(f'Data set length after preprocessing: {len(dataset)}')
        print(f'{original_len - len(dataset)} data points removed in preprocessing')
    
    def remove_none_mol(self, dataset: MolCollection):
        if not dataset.store_mol:
            for data in dataset.data_list:
                data.update_mol(Chem.MolFromSmiles(data.smiles))
            dataset.store_mol = True

        new_list = []
        for data in dataset.data_list:
            if data.mol is not None:
                new_list.append(data)
        dataset.data_list = new_list
    
    def remove_nan_feature(self, dataset: MolCollection):
        if not dataset.store_feature:
            raise Exception('Not storing features!')
        
        new_list = []
        ori_len = len(dataset)
        for data in dataset.data_list:
            if not np.isnan(data.feature).any():
                new_list.append(data)
        dataset.data_list = new_list
        print(f'Removed {ori_len - len(dataset)} data points which contains NaN features')

    def get_nan_feature_mask(self, dataset: MolCollection):
        if not dataset.store_feature:
            raise Exception('Not storing features!')
        
        mask = []
        for data in dataset.data_list:
            if not np.isnan(data.feature).any():
                mask.append(1)
            else:
                mask.append(0)
        return np.array(mask)

    def deduplicate(self, dataset: MolCollection, based_on='smiles', ambiguity_handling=None):
        label_dict = {}
        idx_dict = {}
        old_list = dataset.data_list
        print(f'Data set length before deduplication: {len(old_list)}')
        for i, data in enumerate(old_list):
            data_repr = getattr(data, based_on)
            if data_repr not in label_dict:
                label_dict[data_repr] = []
                idx_dict[data_repr] = []
            label_dict[data_repr].append(data.label)
            idx_dict[data_repr].append(i)
        
        new_list = []
        if not dataset.multilabel:
            for key, labels in label_dict.items():
                labels = np.nan_to_num(labels, nan=-1)
                if len(set(labels)) == 1:
                    new_list.append(old_list[idx_dict[key][0]])
                else:
                    print('ambiguity occurs in:', key)
                    print('labels:', set(labels))
                    print('ambiguity handling:', ambiguity_handling)
                    if ambiguity_handling in ['remove_positive', 'remove_negative']:
                        assert set(labels) == set([0, 1])
                    kept_label = None

                    if ambiguity_handling is None:
                        raise Exception('Encountered ambiguity but not handling')
                    elif ambiguity_handling == 'keep_first':
                        new_list.append(old_list[idx_dict[key][0]])
                    elif ambiguity_handling == 'keep_all':
                        new_list.extend(old_list[idx_dict[key]])
                    elif ambiguity_handling == 'mean':
                        mean_data = old_list[idx_dict[key][0]]
                        mean_data.label = np.mean(labels)
                        new_list.append(mean_data)
                    elif ambiguity_handling == 'remove_positive':
                        kept_label = 0
                    elif ambiguity_handling == 'remove_negative':
                        kept_label = 1
                    elif ambiguity_handling == 'remove_all':
                        continue
                    else:
                        raise Exception('Unknown ambiguity handling method')
                    for j, label in enumerate(labels):
                        if label == kept_label:
                            new_list.append(old_list[idx_dict[key][j]])
                            break
                # else:
                #     raise Exception('Unexpected number of classes for the label')
        else:
            for key, labels in label_dict.items():
                labels = np.nan_to_num(labels, nan=-1)
                all_equal = all(np.array_equal(labels[0], arr) for arr in labels[1:])
                if all_equal:
                    new_list.append(old_list[idx_dict[key][0]])
                else:
                    print('ambiguity occurs in', key)
                    if ambiguity_handling is None:
                        raise Exception('Encountered ambiguity but not handling')
                    elif ambiguity_handling in ['remove_positive', 'remove_negative']:
                        raise Exception('Unsupported ambiguity handling method for multi-label dataset')
                    elif ambiguity_handling == 'remove_both':
                        continue
                    else:
                        raise Exception('Unknown ambiguity handling method')

        dataset.data_list = new_list
        print(f'Data set length after deduplication: {len(new_list)}')
        print(f'{len(old_list) - len(new_list)} data points removed in deduplication')
    
    def remove_ambiguity(self, dataset: MolCollection, removed_class=1, threshold=0.8):
        if removed_class == 1:
            kept_class = 0
        elif removed_class == 0:
            kept_class = 1
        else:
            raise Exception(f'Unexpected class label {removed_class}')
        kept_class_fps = [AllChem.GetMorganFingerprintAsBitVect(data.mol, 2, nBits=2048) 
                          for data in dataset.data_list if data.label == kept_class]
        original_length = len(dataset.data_list)
        def is_similar(mol):
            if mol is None:
                return False
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
            for kept_fp in kept_class_fps:
                if TanimotoSimilarity(fp, kept_fp) > threshold:
                    return True
            return False
        
        dataset.data_list = [data for data in dataset.data_list 
                          if not (data.label == removed_class and is_similar(data.mol))]
        removed_count = original_length - len(dataset.data_list)
        print(f"Removed {removed_count} data points in class {removed_class} similar (Tanimoto>{threshold}) "
              f"to class {kept_class} to prevent ambiguity")
        
    def molvs_validate(self, dataset: MolCollection):
        validator = rdMolStandardize.MolVSValidation()
        for data in dataset.data_list:
            result = validator.validate(data.mol)
            if result:
                for info in result:
                    print(f'{info} in {data.smiles}')

    ## Data preprocessing functions
    def rdkit_cleanup(self, dataset: MolCollection, use_tqdm=True):
        print('Cleaning up molecules (Sanitize, Remove Hs, Disconnect metal, '
              'Correct functional groups, Recombine charges, Reionize)')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            data.update_mol(rdMolStandardize.Cleanup(data.mol), update_str=False)
    
    def rdkit_cleanup_and_isotope(self, dataset: MolCollection, use_tqdm=True):
        print('Cleaning up molecules (Sanitize, Remove Hs, Disconnect metal, Correct functional groups, '
              'Recombine charges, Reionize), and Removing Isotopic labels')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            data.update_mol(rdMolStandardize.IsotopeParent(data.mol), update_str=False)

    def rdkit_remove_frag(self, dataset: MolCollection, use_tqdm=True):
        print('Removing fragments accroding to rdkit list')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            data.update_mol(rdMolStandardize.RemoveFragments(data.mol), update_str=False)

    def remove_salt(self, dataset: MolCollection, use_tqdm=True):
        print('Removing salts fragments accroding to rdkit list')
        remover = SaltRemover.SaltRemover()
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            data.update_mol(remover.StripMol(data.mol, dontRemoveEverything=True), 
                            update_str=False)
    
    def canonicalize_smiles(self, dataset: MolCollection, use_tqdm=True):
        print('Canonicalizing smiles')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            data.smiles = Chem.MolToSmiles(data.mol)
    
    def oboyle_neutralize(self, dataset: MolCollection, use_tqdm=True):
        print('Neutralizing molecules using O\'Boyle\'s code')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data in iterator:
            try:
                data.update_mol(oboyle_neutralize(data.mol), update_str=False)
            except:
                data.mol = None
        self.remove_none_mol(dataset)
        
    def rdkit_uncharge(self, dataset: MolCollection, use_tqdm=True):
        print('Neutralizing molecules using rdMolStandardize.Uncharger')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        uncharger = rdMolStandardize.Uncharger()
        for data in iterator:
            data.update_mol(uncharger.uncharge(data.mol), update_str=False)

    def remove_inorganic(self, dataset: MolCollection, use_tqdm=True):
        print('Removing inorganic molecules')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data in iterator:
            if is_organic(data.mol):
                new_list.append(data)
        dataset.data_list = new_list
    
    def remove_inorganic_frag(self, dataset: MolCollection, use_tqdm=True):
        print('Removing inorganic fragments in mixtures and removing inorganic compounds')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data in iterator:
            frags = Chem.GetMolFrags(data.mol, asMols=True)
            new_frags = []
            for frag in frags:
                if is_organic(frag):
                    new_frags.append(frag)
            new_mol = None
            for frag in new_frags:
                if new_mol is None:
                    new_mol = frag
                else:
                    new_mol = Chem.CombineMols(new_mol, frag)
            data.mol = new_mol
            if new_mol is not None:
                new_list.append(data)
        dataset.data_list = new_list

    def keep_largest_frag(self, dataset: MolCollection, use_tqdm=True):
        print('Keep only the largest fragment in a mixture')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        chooser = rdMolStandardize.LargestFragmentChooser()
        for data in iterator:
            data.update_mol(chooser.choose(data.mol), update_str=False)

    def remove_mixture(self, dataset: MolCollection, use_tqdm=True):
        print('Removing mixtures and Removing duplicated frags if the molecule is not mixture')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data in iterator:
            frags = Chem.GetMolFrags(data.mol, asMols=True)
            if len(frags) == 1:
                new_list.append(data)
            else:
                frag_smi = [Chem.MolToSmiles(frag) for frag in frags]
                if len(set(frag_smi)) == 1:
                    data.mol = frags[0]
                    new_list.append(data)

        dataset.data_list = new_list
    
    def canonicalize_tautomer(self, dataset: MolCollection, use_tqdm=True):
        print('Canonicalizing tautomer')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        tautomer_enumerator = rdMolStandardize.TautomerEnumerator()
        tautomer_enumerator.SetRemoveBondStereo(False)
        tautomer_enumerator.SetRemoveSp3Stereo(False)
        tautomer_enumerator.SetReassignStereo(False)
        for data in iterator:
            data.update_mol(tautomer_enumerator.Canonicalize(data.mol), update_str=False)
            # data.update_mol(rdMolStandardize.CanonicalTautomer(data.mol), update_str=False)
    
    def mol_weight_1000(self, dataset: MolCollection, use_tqdm=False):
        print('Removing molecules with mol weight larger than 1000')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        if not dataset.store_molwt:
            dataset.calculate_molwt()
        new_list = []
        for data in iterator:
            if data.molwt <= 1000:
                new_list.append(data)
        dataset.data_list = new_list
    
    def num_atom_6(self, dataset: MolCollection, use_tqdm=False):
        print('Removing molecules with less than 6 atoms')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data in iterator:
            mol_all_h = Chem.AddHs(data.mol)
            if mol_all_h.GetNumAtoms() >= 6:
                new_list.append(data)
        dataset.data_list = new_list


class PairDataProcessor:
    def __init__(self, clean_steps=None):
        self.clean_steps = default_clean if clean_steps is None else clean_steps

    def preprocess(self, dataset: MolPairCollection, use_tqdm=True):
        original_len = len(dataset)
        print(f'Original data set length: {original_len}')
        self.remove_none_mol(dataset)
        print(f'Data set length after removing None mol: {len(dataset)}')
        for process_step in self.clean_steps:
            process_fn = getattr(self, process_step)
            process_fn(dataset, use_tqdm=use_tqdm)
        dataset.update_str()
        print(f'Data set length after preprocessing: {len(dataset)}')
        print(f'{original_len - len(dataset)} data points removed in preprocessing')
    
    def remove_none_mol(self, dataset: MolPairCollection):
        if not dataset.store_mol:
            for data_pair in dataset.data_list:
                data_0 = data_pair.data_0
                data_1 = data_pair.data_1
                data_0.update_mol(Chem.MolFromSmiles(data_0.smiles))
                data_1.update_mol(Chem.MolFromSmiles(data_1.smiles))
            dataset.store_mol = True

        new_list = []
        for data_pair in dataset.data_list:
            if data_pair.data_0.mol is not None and \
                data_pair.data_1.mol is not None:
                new_list.append(data_pair)
        dataset.data_list = new_list
    
    def rdkit_cleanup_and_isotope(self, dataset: MolPairCollection, use_tqdm=True):
        print('Cleaning up molecules (Sanitize, Remove Hs, Disconnect metal, Correct functional groups, '
              'Recombine charges, Reionize), and Removing Isotopic labels')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            data_0.update_mol(rdMolStandardize.IsotopeParent(data_0.mol), update_str=False)
            data_1.update_mol(rdMolStandardize.IsotopeParent(data_1.mol), update_str=False)
    
    def rdkit_remove_frag(self, dataset: MolPairCollection, use_tqdm=True):
        print('Removing fragments accroding to rdkit list')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            data_0.update_mol(rdMolStandardize.RemoveFragments(data_0.mol), update_str=False)
            data_1.update_mol(rdMolStandardize.RemoveFragments(data_1.mol), update_str=False)
    
    def remove_inorganic_frag(self, dataset: MolPairCollection, use_tqdm=True):
        print('Removing inorganic fragments in mixtures and removing inorganic compounds')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        def remove_frag(mol):
            frags = Chem.GetMolFrags(mol, asMols=True)
            new_frags = []
            for frag in frags:
                if is_organic(frag):
                    new_frags.append(frag)
            new_mol = None
            for frag in new_frags:
                if new_mol is None:
                    new_mol = frag
                else:
                    new_mol = Chem.CombineMols(new_mol, frag)
            return new_mol

        new_list = []
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            data_0.mol = remove_frag(data_0.mol)
            data_1.mol = remove_frag(data_1.mol)
            if data_0.mol is not None and data_1.mol is not None:
                new_list.append(data_pair)
        dataset.data_list = new_list

    def remove_mixture(self, dataset: MolPairCollection, use_tqdm=True):
        print('Removing mixtures and Removing duplicated frags if the molecule is not mixture')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            frags_0 = Chem.GetMolFrags(data_0.mol, asMols=True)
            frags_1 = Chem.GetMolFrags(data_1.mol, asMols=True)
            if len(frags_0) == 1 and len(frags_1) == 1:
                new_list.append(data_pair)
            else:
                frag_smi_0 = [Chem.MolToSmiles(frag) for frag in frags_0]
                frag_smi_1 = [Chem.MolToSmiles(frag) for frag in frags_1]
                if len(set(frag_smi_0)) == 1 and len(set(frag_smi_1)) == 1:
                    data_0.mol = frags_0[0]
                    data_1.mol = frags_1[0]
                    new_list.append(data_pair)

        dataset.data_list = new_list

    def mol_weight_1000(self, dataset: MolPairCollection, use_tqdm=False):
        print('Removing molecules with mol weight larger than 1000')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        if not dataset.store_molwt:
            dataset.calculate_molwt()
        new_list = []
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            if data_0.molwt <= 1000 and data_1.molwt <= 1000:
                new_list.append(data_pair)
        dataset.data_list = new_list
    
    def num_atom_6(self, dataset: MolPairCollection, use_tqdm=False):
        print('Removing molecules with less than 6 atoms')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        new_list = []
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            mol_all_h_0 = Chem.AddHs(data_0.mol)
            mol_all_h_1 = Chem.AddHs(data_1.mol)
            if mol_all_h_0.GetNumAtoms() >= 6 and mol_all_h_1.GetNumAtoms() >= 6:
                new_list.append(data_pair)
        dataset.data_list = new_list
    
    def oboyle_neutralize(self, dataset: MolPairCollection, use_tqdm=True):
        print('Neutralizing molecules using O\'Boyle\'s code')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            try:
                data_0.update_mol(oboyle_neutralize(data_0.mol), update_str=False)
            except:
                print(f'Error on {data_0} when oboyle_neutralize')
                data_0.mol = None
        
            try:
                data_1.update_mol(oboyle_neutralize(data_1.mol), update_str=False)
            except:
                print(f'Error on {data_1} when oboyle_neutralize')
                data_1.mol = None
        self.remove_none_mol(dataset)
    
    def canonicalize_tautomer(self, dataset: MolPairCollection, use_tqdm=True):
        print('Canonicalizing tautomer')
        iterator = tqdm(dataset.data_list) if use_tqdm else dataset.data_list
        tautomer_enumerator = rdMolStandardize.TautomerEnumerator()
        tautomer_enumerator.SetRemoveBondStereo(False)
        tautomer_enumerator.SetRemoveSp3Stereo(False)
        tautomer_enumerator.SetReassignStereo(False)
        for data_pair in iterator:
            data_0 = data_pair.data_0
            data_1 = data_pair.data_1
            data_0.update_mol(tautomer_enumerator.Canonicalize(data_0.mol), update_str=False)
            data_1.update_mol(tautomer_enumerator.Canonicalize(data_1.mol), update_str=False)
