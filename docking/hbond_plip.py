#!/usr/bin/env python3
"""
Utility for merging receptor + ligand folders into complexes and counting hydrogen bonds
using PLIP, with optional multithreading.

This module can be imported and used programmatically:

    from hbond_counter_plip import count_hbonds_batch
    results = count_hbonds_batch(
        receptor_pdb="receptor/2rku.pdb",
        ligand_dir="ligands/",
        out_dir="complexes/",
        threads=4
    )

Or executed as a script:

    python hbond_counter_plip.py \
        --receptor receptor/2rku.pdb \
        --ligand-dir ligands/ \
        --complex-dir complexes/ \
        --threads 8 \
        --output results.csv

Requirements:
  - plip (`pip install plip-analysis`)
  - biopython (`pip install biopython`)
"""
import argparse
import os
import glob
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from plip.structure.preparation import PDBComplex
from Bio import PDB

def merge_receptor_ligand(receptor_pdb: str, ligand_pdbqt: str, output_pdb: str):
    """Extract first conformation from ligand_pdbqt and merge into receptor_pdb, save as output_pdb."""
    # parse receptor
    parser = PDB.PDBParser(QUIET=True)
    receptor = parser.get_structure('R', receptor_pdb)
    # make a copy
    merged = receptor.copy()
    # create ligand chain
    ligand_chain = PDB.Chain.Chain('L')
    # read first MODEL from pdbqt
    atoms = []
    with open(ligand_pdbqt) as f:
        in_model = False
        for line in f:
            if line.startswith('MODEL'):
                in_model = True; continue
            if line.startswith('ENDMDL'):
                break
            if in_model and (line.startswith('ATOM') or line.startswith('HETATM')):
                atoms.append(line)
    # build one residue
    res_id = ('H_LIG', 1, ' ')
    residue = PDB.Residue.Residue(res_id, 'LIG', ' ')
    ligand_chain.add(residue)
    atom_serial = 1
    for l in atoms:
        name = l[12:16].strip()
        coords = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        element = l[76:78].strip() or name[0]
        atom = PDB.Atom.Atom(f"{name}_{atom_serial}", coords, 0.0, 1.0, ' ', f"{name}_{atom_serial}", atom_serial, element)
        residue.add(atom)
        atom_serial += 1
    # add ligand chain to first model
    merged[0].add(ligand_chain)
    # save
    io = PDB.PDBIO()
    io.set_structure(merged)
    io.save(output_pdb)

def count_hbonds(complex_pdb: str) -> int:
    """Use PLIP to analyze complex_pdb and return unique H-bond count."""
    c = PDBComplex()
    c.load_pdb(complex_pdb)
    c.analyze()
    seen = set()
    total = 0
    for site in c.interaction_sets.values():
        for h in site.hbonds_ldon + site.hbonds_pdon:
            pair = frozenset((h.d_orig_idx, h.a_orig_idx))
            if pair not in seen:
                seen.add(pair)
                total += 1
    return total

def process_ligand(receptor_pdb: str, ligand_file: str, complex_dir: str) -> tuple:
    """Merge receptor+ligand, run PLIP, return (ligand_name, hbond_count)."""
    base = os.path.splitext(os.path.basename(ligand_file))[0]
    out_pdb = os.path.join(complex_dir, f"{base}_complex.pdb")
    merge_receptor_ligand(receptor_pdb, ligand_file, out_pdb)
    try:
        n = count_hbonds(out_pdb)
    except Exception as e:
        print(f"[ERROR] {base}: {e}")
        n = -1
    return base, n

def count_hbonds_batch(receptor_pdb: str, ligand_dir: str, complex_dir: str,
                       threads: int = 4, output=None) -> dict:
    """
    For each ligand in ligand_dir:
      1) merge with receptor_pdb into complex_dir
      2) count PLIP H-bonds in parallel
    Returns dict { ligand_base: hbond_count }
    """
    os.makedirs(complex_dir, exist_ok=True)
    ligands = sorted(glob.glob(os.path.join(ligand_dir, "*.pdbqt")))
    results = {}
    with ThreadPoolExecutor(max_workers=threads) as exe:
        futs = {exe.submit(process_ligand, receptor_pdb, lig, complex_dir): lig for lig in ligands}
        for fut in as_completed(futs):
            name, count = fut.result()
            results[name] = count
    print(f"Processed {len(ligands)} ligands into {complex_dir} using {threads} threads.")
    
    if output:
        with open(args.output, "w", newline="") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(["ligand", "hbond_count"])
            for name, cnt in sorted(res.items()):
                writer.writerow([name, cnt])
        print(f"Results written to {args.output}")
    else:
        for name, cnt in sorted(res.items()):
            print(f"{name}\t{cnt}")
    return results

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Merge receptor+ligands into complexes and count H-bonds via PLIP"
    )
    p.add_argument("-r", "--receptor", required=True,
                   help="Path to receptor PDB file")
    p.add_argument("-d", "--ligand-dir", required=True,
                   help="Directory with ligand PDBQT files")
    p.add_argument("-c", "--complex-dir", required=True,
                   help="Directory to write merged complex PDBs")
    p.add_argument("-t", "--threads", type=int, default=4,
                   help="Number of threads (default: 4)")
    p.add_argument("-o", "--output", default=None,
                   help="CSV file for output (ligand,hbond_count)")
    args = p.parse_args()

    res = count_hbonds_batch(
        receptor_pdb=args.receptor,
        ligand_dir=args.ligand_dir,
        complex_dir=args.complex_dir,
        threads=args.threads,
        output=args.output
    )


