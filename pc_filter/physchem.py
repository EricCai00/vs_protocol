#!/public/home/caiyi/software/miniconda3/envs/python39/bin/python

from tqdm import tqdm
import math
from multiprocessing import Pool
import pandas as pd
import argparse
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, Lipinski, rdMolDescriptors
from rdkit.Contrib.SA_Score import sascorer
from functools import partial
import collections

# from PyBioMed.PyMolecule import constitution, molproperty

from rdkit import RDLogger
lg = RDLogger.logger()
lg.setLevel(RDLogger.ERROR)

def get_max_ring_size(mol: Chem.Mol) -> int:
    ring_info = mol.GetRingInfo()
    atom_rings = ring_info.AtomRings()
    if not atom_rings:
        return 0
    max_ring_size = max(len(ring) for ring in atom_rings)
    return max_ring_size


def calculate_split_(lines, set_):
    d = {}
    if set_ not in ['all', 'ro5', 'phychem', 'medchem']:
        raise Exception(f'Wrong value {set_} for `set_`')

    if set_ in ['all', 'ro5', 'phychem']:
        # constitution
        # constitution_list = ['naccr', 'ndonr']
        # for label in constitution_list:
        #     d[label] = constitution._constitutional[label]
        d['nHA'] = Lipinski.NumHAcceptors
        d['nHD'] = Lipinski.NumHDonors

        # molproperty
        # d['LogP'] = molproperty.CalculateMolLogP
        d['LogP'] = Crippen.MolLogP

        # additional
        d['MW'] = Descriptors.MolWt
        # d['nRotbond'] = constitution.CalculateRotationBondNumber
        d['nRot'] = Lipinski.NumRotatableBonds
    
    if set_ in ['all', 'psychem']:
        d['nRing'] = rdMolDescriptors.CalcNumRings
        d['MaxRing'] = get_max_ring_size
        d['nStereo'] = rdMolDescriptors.CalcNumAtomStereoCenters
        d['TPSA'] = Descriptors.TPSA

    if set_ in ['all', 'medchem']:
        d['SAscore'] = sascorer.calculateScore
        d['QED'] = Descriptors.qed

    name2des = collections.OrderedDict()
    for line in tqdm(lines):
        smi, name = line.split()
        try:
            mol = Chem.MolFromSmiles(smi)
            des = {}
            for label, func in d.items():
                des[label] = func(mol)
            name2des[name] = des
        except:
            name2des[name] = {}
            print('Error on: ' + smi + ' ' + name + '\n')
            with open('err.txt', 'a') as f:
                f.write(smi + ' ' + name + '\n')
    return name2des


def calc_physchem(input_, output, set_='all', threads=1):
    with open(input_) as f:
        lines = f.read().splitlines()
    split_len = math.ceil(len(lines) / threads)
    line_splits = [lines[i * split_len: (i+1) * split_len] for i in range(threads)]

    calculate_split = partial(calculate_split_, set_=set_)
    with Pool(threads) as pool:
        out_list = pool.map(calculate_split, line_splits)
    pool.close()

    df_list = [pd.DataFrame(name2des).T for name2des in out_list]

    df = pd.concat(df_list)
    df.index.name = 'name'
    df.to_csv(output)


if __name__ == '__main__':
    usage = 'physicochemical.py --input <smi_file> --output <csv_file> --threads 20'

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-t', '--threads', default=1, type=int)
    args = parser.parse_args()

    calc_physchem(args.input, args.output, args.threads)
