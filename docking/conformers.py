#!/usr/bin/env python3
import os
import math
from multiprocessing import Pool
from functools import partial
from tqdm import tqdm
from rdkit import Chem

def generate_conformers_chunk(lines, output_dir, num_confs=20, num_threads=0):
    from rdkit.Chem import rdDistGeom
    from rdkit.Chem import AllChem

    for line in tqdm(lines):
        try:
            smi, name = line.split()
            mol = Chem.MolFromSmiles(smi)
            mol = Chem.AddHs(mol)
            params = rdDistGeom.ETKDGv3()
            params.numThreads = num_threads  # 内部 RDKit 多线程
            cids = rdDistGeom.EmbedMultipleConfs(
                mol, numConfs=num_confs, params=params
            )
            _ = AllChem.MMFFOptimizeMoleculeConfs(
                mol, numThreads=num_threads, mmffVariant='MMFF94s'
            )
            for cid in cids:
                filename = os.path.join(output_dir, f"{name}_conf_{cid}.pdb")
                Chem.MolToPDBFile(mol, filename, confId=cid)
        except Exception as e:
            print(f"Error on line: {line} | {e}")

def batch_generate_conformers(smi_path, output_dir, num_confs=20, num_threads=1, rdkit_threads=0):
    os.makedirs(output_dir, exist_ok=True)

    with open(smi_path) as f:
        lines = f.read().splitlines()

    split_len = math.ceil(len(lines) / num_threads)
    line_splits = [
        lines[i * split_len : (i + 1) * split_len] for i in range(num_threads)
    ]

    worker = partial(
        generate_conformers_chunk,
        output_dir=output_dir,
        num_confs=num_confs,
        num_threads=rdkit_threads,  # 内层 RDKit 线程数
    )

    with Pool(num_threads) as pool:
        pool.map(worker, line_splits)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate conformers with multiprocessing")
    parser.add_argument("-i", "--input", required=True, help="SMI file path")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("-n", "--num_confs", type=int, default=20, help="Number of conformers per molecule")
    parser.add_argument("-t", "--threads", type=int, default=1, help="Number of processes for outer multiprocessing")
    parser.add_argument("-rt", "--rdkit_threads", type=int, default=0, help="Threads used by RDKit internally")
    args = parser.parse_args()

    batch_generate_conformers(
        smi_path=args.input,
        output_dir=args.output,
        num_confs=args.num_confs,
        num_threads=args.threads,
        rdkit_threads=args.rdkit_threads
    )
