#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility for serially counting hydrogen bonds between a receptor and multiple ligands using PyMOL.

This script calculates two metrics for each ligand:
1. The total number of hydrogen bonds formed with the entire receptor.
2. The number of hydrogen bonds formed specifically with a user-defined set of key residues.

This module can be imported and used programmatically:

    from hbond_analyzer import run_hbond_analysis
    
    run_hbond_analysis(
        receptor_path="receptor.pdbqt",
        ligand_dir="ligands/",
        output_path="results.csv",
        key_residue_ids=['57', '67', '59', '82', '133', '136'],
        cutoff=3.5
    )

Or executed as a script from the command line:

    python hbond_analyzer.py \\
        --receptor /path/to/receptor.pdbqt \\
        --ligand-dir /path/to/ligands/ \\
        --key-residues 57,67,59,82,133,136 \\
        --output results.csv

Requirements:
  - PyMOL Python modules available in your environment (e.g., via `conda install -c schrodinger pymol-bundle`).
  - tqdm (`pip install tqdm`) for the progress bar.
"""

import argparse
import sys
import os
import glob
import csv
from tqdm import tqdm

# Attempt to import PyMOL and provide a helpful error message if it fails.
try:
    from pymol import cmd
except ImportError:
    sys.stderr.write("Error: PyMOL module not found.\n")
    sys.stderr.write("Please ensure PyMOL is installed and its Python modules are in your environment.\n")
    sys.stderr.write("For Conda, you can use: 'conda install -c schrodinger pymol-bundle'\n")
    sys.exit(1)


def run_hbond_analysis(receptor_path: str, ligand_dir: str, output_path: str, key_residue_ids: list, cutoff: float = 3.5):
    """
    Analyzes hydrogen bonds for a batch of ligands against a receptor.

    Args:
        receptor_path (str): The file path for the receptor structure (PDBQT, PDB, etc.).
        ligand_dir (str): The directory path containing ligand structure files.
        output_path (str): The file path for the output CSV results.
        key_residue_ids (list): A list of strings, where each string is a residue ID
                                for targeted H-bond counting.
        cutoff (float, optional): The distance cutoff in Angstroms for H-bond detection. 
                                  Defaults to 3.5.
    """
    print("--- Starting Hydrogen Bond Analysis ---")

    # --- 1. Initialization and Validation ---
    cmd.reinitialize()

    print(f"Loading receptor from: {receptor_path}")
    if not os.path.isfile(receptor_path):
        print(f"Error: Receptor file not found at '{receptor_path}'.")
        sys.exit(1)
    cmd.load(receptor_path, 'receptor')
    cmd.alter("receptor", "ID = index")

    # Create a set of integer residue IDs for fast lookups, matching the user's snippet.
    try:
        print(key_residue_ids)
        key_residue_ids_set = {int(i) for i in key_residue_ids}
        print(f"Key residues for targeted analysis: {', '.join(key_residue_ids)}")
    except ValueError:
        print("Error: Key residues must be integers.")
        sys.exit(1)

    # Find all ligand files in the specified directory.
    if not os.path.isdir(ligand_dir):
        print(f"Error: Ligand directory not found at '{ligand_dir}'.")
        sys.exit(1)
    ligand_files = sorted(glob.glob(os.path.join(ligand_dir, "*")))
    ligand_files = [f for f in ligand_files if os.path.isfile(f) and not f.startswith('.')]

    if not ligand_files:
        print(f"Warning: No ligand files found in '{ligand_dir}'.")
        return

    # --- 2. Main Processing Loop ---
    all_results = []
    print(f"\nProcessing {len(ligand_files)} ligands...")
    
    for ligand_file in tqdm(ligand_files, desc="Analyzing Ligands"):
        # remove '_out.pdbqt'
        ligand_name = os.path.basename(ligand_file)[:-10]
        ligand_path = os.path.join(ligand_dir, ligand_file)
        assert os.path.isfile(ligand_path)
        cmd.load(ligand_path, 'ligand')
        cmd.alter("ligand", "ID = index")

        # OPTIMIZATION: Calculate all H-bonds once.
        total_hb_pairs = cmd.find_pairs(
            selection1="receptor and donor", selection2="ligand and acceptor",
            cutoff=cutoff, mode=1) + cmd.find_pairs(
            selection1="receptor and acceptor", selection2="ligand and donor",
            cutoff=cutoff, mode=1)
        total_hbond_count = len(total_hb_pairs)

        # OPTIMIZATION: Filter the full list in Python instead of running find_pairs again.
        key_hbond_count = 0
        atom_to_resi_cache = {}  # Cache atom ID -> resi lookups for this ligand.

        for pair in total_hb_pairs:
            # The pair is structured as: (('receptor', atom_id), ('ligand', atom_id))
            receptor_part = None
            if pair[0][0] == 'receptor':
                receptor_part = pair[0]
            elif pair[1][0] == 'receptor':
                receptor_part = pair[1]
            
            if receptor_part:
                receptor_atom_id = receptor_part[1]
                resi = None
                
                # Check cache first to minimize calls to PyMOL
                if receptor_atom_id in atom_to_resi_cache:
                    resi = atom_to_resi_cache[receptor_atom_id]
                else:
                    # If not cached, query PyMOL for the residue ID and cache it.
                    atom_info = []
                    cmd.iterate(f"id {receptor_atom_id} and receptor", "atom_info.append(resi)", space={'atom_info': atom_info})
                    if atom_info:
                        resi = atom_info[0]
                        atom_to_resi_cache[receptor_atom_id] = resi
                
                # Check if the found residue ID is one of the key residues.
                # Convert `resi` string to int for comparison, as per the working snippet.
                if resi and int(resi) in key_residue_ids_set:
                    key_hbond_count += 1

        all_results.append({
            'ligand_name': ligand_name,
            'total_hbonds': total_hbond_count,
            'key_residue_hbonds': key_hbond_count
        })

        # Clean up the ligand to prepare for the next iteration
        cmd.delete("ligand")

    # Final cleanup of the PyMOL session
    cmd.delete("all")
    print("\nAnalysis complete.")

    # --- 3. Write Results to CSV ---
    if not all_results:
        print("No results to write.")
        return

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    header = ['ligand_name', 'total_hbonds', 'key_residue_hbonds']
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_results)
    
    print(f"Results for {len(all_results)} ligands have been written to: {output_path}")


def main():
    """
    Main function to parse command-line arguments and run the analysis.
    """
    parser = argparse.ArgumentParser(
        description="Serially count hydrogen bonds between a receptor and multiple ligands using PyMOL.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-r", "--receptor",
        required=True,
        help="Path to the receptor structure file (e.g., PDBQT, PDB)."
    )
    parser.add_argument(
        "-d", "--ligand-dir",
        required=True,
        help="Directory containing the ligand structure files."
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path for the output CSV file to store results."
    )
    parser.add_argument(
        "-k", "--key_residues",
        required=True,
        help="Comma-separated list of key residue IDs for targeted H-bond counting.\n"
             "Example: 57,67,59,82,133,136"
    )
    parser.add_argument(
        "-c", "--cutoff",
        type=float,
        default=3.5,
        help="Distance cutoff in Angstroms for H-bond detection (default: 3.5)."
    )
    args = parser.parse_args()

    # Convert the comma-separated string of residue IDs into a list of strings
    key_residue_id_list = [item.strip() for item in args.key_residues.split(',')]

    # Run the main analysis function with the parsed arguments
    run_hbond_analysis(
        receptor_path=args.receptor,
        ligand_dir=args.ligand_dir,
        output_path=args.output,
        key_residue_ids=key_residue_id_list,
        cutoff=args.cutoff
    )

if __name__ == '__main__':
    main()
