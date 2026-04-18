#!/usr/bin/env python3

import math
import argparse
from multiprocessing import Pool
from rdkit import Chem
from tqdm import tqdm
from rdkit import RDLogger
import sys

# Silence RDKit warnings
lg = RDLogger.logger()
lg.setLevel(RDLogger.ERROR)


def _filter_chunk(lines):
    """
    Process a chunk of SMILES lines, filtering out invalid or multi-component molecules.
    Returns a list of valid "smi name" strings.
    """
    valid = []
    for line in tqdm(lines, leave=False):
        parts = line.strip().split()
        if len(parts) != 2:
            # skip malformed lines
            print('molformed line:', line)
            continue
        smi, name = parts
        if '.' in smi:
            # skip multi-component molecules
            continue
        # parse
        mol = Chem.MolFromSmiles(smi)
        if not mol:
            print(line)
            continue
        valid.append(f"{Chem.MolToSmiles(mol)} {name}")
    return valid


def library_preprocess(input_path, output_path, threads=1):
    """
    Reads input file of "smi name" lines, filters invalid or multi-component SMILES,
    and writes valid lines to output. Supports multithreading.
    """
    with open(input_path) as f:
        lines = f.read().splitlines()

    # split lines into roughly equal chunks
    if threads < 1:
        threads = 1
    split_size = math.ceil(len(lines) / threads)
    chunks = [lines[i * split_size:(i + 1) * split_size] for i in range(threads)]

    # process in parallel
    if threads == 1:
        results = [_filter_chunk(chunks[0])]
    else:
        with Pool(threads) as pool:
            results = pool.map(_filter_chunk, chunks)
            pool.close()

    # combine and write
    with open(output_path, 'w') as fo:
        for sublist in results:
            for entry in sublist:
                fo.write(entry + "\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Filter SMILES file for valid single-component molecules with multithreading support"
    )
    parser.add_argument('-i', '--input', required=True, help='Input SMILES file ("smi name" per line)')
    parser.add_argument('-o', '--output', required=True, help='Output file for filtered lines')
    parser.add_argument('-t', '--threads', type=int, default=1, help='Number of worker processes')
    args = parser.parse_args()

    try:
        library_preprocess(args.input, args.output, args.threads)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
