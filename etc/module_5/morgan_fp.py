#!/usr/bin/env python3
import os
import glob
import argparse
import multiprocessing
from functools import partial
from datetime import datetime
from rdkit import Chem
import rdkit
from rdkit import DataStructs

def _compute_morgan_fp(smiles, mol_id, nbits=1024, radius=2):
    from rdkit.Chem import AllChem
    """
    Computes the Morgan fingerprint for a single SMILES string.
    
    Returns a tuple of (mol_id, fingerprint_object).
    Returns None if the SMILES string cannot be parsed.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"Warning: Could not parse SMILES '{smiles}' for ID '{mol_id}'. Skipping.")
        return None

    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=nbits, useChirality=True)
    return (mol_id, fp)

def generate_fps(smiles_folder_path, input_suffix, output_fps_path,
                 tot_process=4, nbits=1024, radius=2):
    """
    1. Scans all files ending with `input_suffix` in `smiles_folder_path`.
       Assumes each line has the format: SMILES <whitespace> ID
    2. Computes Morgan (ECFP) fingerprints for each molecule in parallel.
    3. Writes all results to a standard FPS file at `output_fps_path`,
       adhering to the ChemFP format specification.
    """
    # 1) Collect all (smiles, ID) pairs
    smiles_list = []
    search_pattern = os.path.join(smiles_folder_path, f'*{input_suffix}')
    for txt_file in glob.glob(search_pattern):
        with open(txt_file, 'r') as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                smi, mid = parts[0], parts[1]
                smiles_list.append((smi, mid))

    if not smiles_list:
        print(f"ERROR: No valid SMILES lines found in '{smiles_folder_path}' with suffix '{input_suffix}'")
        return

    # 2) Compute fingerprints in parallel
    pool = multiprocessing.Pool(min(multiprocessing.cpu_count(), tot_process))
    func = partial(_compute_morgan_fp, nbits=nbits, radius=radius)
    results = pool.starmap(func, smiles_list)
    pool.close()
    pool.join()

    # 3) Filter out failed computations and format the output lines
    fps_lines = []
    for item in results:
        if item is None:  # SMILES could not be parsed
            continue
        mol_id, fp_obj = item
        # Convert the fingerprint object to a hex string for FPS format
        hex_fp = DataStructs.BitVectToFPSText(fp_obj)
        # CORRECT FORMAT: fingerprint<tab>id
        fps_lines.append(f"{hex_fp}\t{mol_id}")

    if not fps_lines:
        print("ERROR: No valid fingerprints could be generated.")
        return

    # 4) Write all results to the output file with the corrected header
    out_dir = os.path.dirname(output_fps_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_fps_path, 'w') as fout:
        # Write a compliant header
        fout.write("#FPS1\n")
        fout.write(f"#num_bits={nbits}\n")
        fout.write(f"#type=RDKit-Morgan radius={radius} nbits={nbits}\n")
        fout.write(f"#software=RDKit/{rdkit.__version__}\n")
        fout.write(f"#date={datetime.utcnow().isoformat(timespec='seconds')}\n")
        
        # Write the records
        for line in fps_lines:
            fout.write(line + "\n")

    print(f"Finished generating FPS file -> '{output_fps_path}' ({len(fps_lines)} molecules).")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate Morgan fingerprints from SMILES files in parallel and output in ChemFP's FPS format."
    )
    parser.add_argument(
        '-sfp', '--smile_folder_path',
        required=True,
        help="Folder containing SMILES text files. Each line should be: SMILES<whitespace>ID"
    )
    parser.add_argument(
        '-o', '--output_fps',
        required=True,
        help="Path for the output FPS file (e.g., /path/to/output.fps)"
    )
    parser.add_argument(
        '-sf', '--suffix',
        help="Suffix for input smiles files (default: .smi)",
        default='.smi'
    )
    parser.add_argument(
        '-tp', '--tot_process',
        type=int,
        default=4,
        help="Number of parallel processes to use (default: 4)"
    )
    parser.add_argument(
        '--nbits',
        type=int,
        default=1024,
        help="Length of the Morgan fingerprint (default: 1024)"
    )
    parser.add_argument(
        '--radius',
        type=int,
        default=2,
        help="Radius of the Morgan fingerprint (default: 2)"
    )
    args = parser.parse_args()

    generate_fps(
        smiles_folder_path=os.path.expanduser(args.smile_folder_path),
        input_suffix=args.suffix,
        output_fps_path=os.path.expanduser(args.output_fps),
        tot_process=args.tot_process,
        nbits=args.nbits,
        radius=args.radius
    )
