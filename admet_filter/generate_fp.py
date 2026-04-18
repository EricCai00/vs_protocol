#!/public/home/caiyi/software/miniconda3/envs/python39/bin/python

import math
import os
from multiprocessing import Pool
from tqdm import tqdm
import numpy as np
import h5py
import argparse
from functools import partial


fp_size = {'maccs': 166, 'maccs_full': 167, 'erg': 441, 'pubchem': 881, 'morgan': 1024, 
        'ecfp2_2048': 2048, 'ecfp4_1024': 1024, 'ecfp4_2048': 2048, 'ecfp6_2048': 2048}
continuous_fps = {'erg'}


def generate_fp_(lines, fp_type):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    GetErGFingerprint = partial(AllChem.GetErGFingerprint, fuzzIncrement=0.3, maxPath=21, minPath=1)
    GetMorganFingerprint = partial(AllChem.GetMorganFingerprintAsBitVect, radius=2, nBits=1024, useChirality=True)
    GetECFP2_2048 = partial(AllChem.GetMorganFingerprintAsBitVect, radius=1, nBits=2048)
    GetECFP4_2048 = partial(AllChem.GetMorganFingerprintAsBitVect, radius=2, nBits=2048)
    GetECFP4_1024 = partial(AllChem.GetMorganFingerprintAsBitVect, radius=2, nBits=1024)
    GetECFP6_2048 = partial(AllChem.GetMorganFingerprintAsBitVect, radius=3, nBits=2048)

    type_mapping = {'maccs_full': AllChem.GetMACCSKeysFingerprint, 'erg': GetErGFingerprint, 
                    'morgan': GetMorganFingerprint, 'ecfp2_2048': GetECFP2_2048, 
                    'ecfp4_1024': GetECFP4_1024, 'ecfp4_2048': GetECFP4_2048, 'ecfp6_2048': GetECFP6_2048}
    
    get_fp = type_mapping[fp_type]

    dtype = np.uint8
    if fp_type in continuous_fps:
        dtype = np.float16

    array = np.zeros((len(lines), fp_size[fp_type]), dtype=dtype)
    zincs = []
    smiles = []
    num = 0
    for line in tqdm(lines):
        smi, zinc = line.split()
        try:
            mol = Chem.MolFromSmiles(smi)
            # smiles.append(smi)
            fp = get_fp(mol)
            array[num] = fp
            num += 1
            zincs.append(bytes(zinc, encoding='utf-8'))
        except:
            print(f'Error on: {smi}')

    # assert i == len(array) - 1
    array = array[:num, :]
    return array, zincs, smiles


def batch_generate_fp(input_, output, fp_type, threads):
    if os.path.exists(output):
        # raise Exception('Output flie already exists!')
        print('Output flie already exists!')
        return

    with open(input_, encoding='utf-8') as f:
        lines = f.read().splitlines()

    split_len = math.ceil(len(lines) / threads)
    line_splits = [lines[int(i * split_len): int((i+1) * split_len)] for i in range(threads)]

    generate_fp = partial(generate_fp_, fp_type=fp_type)

    with Pool(threads) as pool:
        out_list = pool.map(generate_fp, line_splits)

    with h5py.File(output, 'w') as f:
        array = []
        zincs = []
        smiles = []
        for i in range(threads):
            array.append(out_list[i][0])
            zincs.extend(out_list[i][1])
            smiles.extend(out_list[i][2])
        f['array'] = np.concatenate(array)
        f['name'] = np.array(zincs, dtype=bytes)
        # f['smiles'] = smiles


if __name__ == '__main__':  
    usage = 'gen_fp.py -i <smi_file> -o <output_path> -fp <pubchem/erg/maccs/morgan> [-t <int>]'

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-fp', '--fp_type', required=True)
    parser.add_argument('-t', '--threads', type=int, default=1)
    args = parser.parse_args()

    batch_generate_fp(args.input, args.output, args.fp_type, args.threads)
