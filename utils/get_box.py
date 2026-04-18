#!/public/home/caiyi/software/miniconda3/bin/python

import os
import argparse
import prody
from rdkit import Chem
import numpy as np
import shutil

def get_box_mol2(mol2_path, extend=10, min_size=20):
    mol = Chem.MolFromMol2File(mol2_path, sanitize=True)
    conf = mol.GetConformer()
    coords = np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])
    x_list, y_list, z_list = coords[:,0], coords[:,1], coords[:,2]
    center = lambda x: (np.max(x) + np.min(x)) / 2
    size = lambda x: np.max(x) - np.min(x)
    box_size = lambda x_list: max(size(x_list) + extend, min_size)
    
    center_coords = [round(center(axis), 4) for axis in [x_list, y_list, z_list]]
    box_sizes = [round(box_size(axis), 4) for axis in [x_list, y_list, z_list]]
    return center_coords, box_sizes

def gen_config_mol2(mol2_path, receptor_path, output_dir, prefix, extend=10, min_size=20):
    center, box = get_box_mol2(mol2_path, extend=extend, min_size=min_size)
    with open(os.path.join(output_dir, f"{prefix}_config.txt"), 'w') as f:
        f.write(f'center_x = {center[0]}\n')
        f.write(f'center_y = {center[1]}\n')
        f.write(f'center_z = {center[2]}\n')
        f.write(f'size_x = {box[0]}\n')
        f.write(f'size_y = {box[1]}\n')
        f.write(f'size_z = {box[2]}\n')
    shutil.copy(receptor_path, os.path.join(output_dir, f"{prefix}_clean.pdb"))

# Function to extract the ligand information
def extract_ligand(input_file, output_dir=None, prefix=None, chain='all', min_box_size=20, extend=10, ligand_name=None, max_peptide_len=1, verbose=False):
    get_key = lambda atom: f'{atom.getChid()}_{atom.getResnum()}_{atom.getResname()}'

    def has_carbon(atom_list):
        has = False
        for atom in atom_list:
            if atom.getElement() == 'C':
                has = True
                break
        return has

    def get_box_prody(atom_list, extend=0, min_size=0):
        center = lambda x: (max(x) + min(x)) / 2
        size = lambda x: max(x) - min(x)
        x_list, y_list, z_list = [], [], []
        for atom in atom_list:
            coords = atom.getCoords()
            x_list.append(coords[0])
            y_list.append(coords[1])
            z_list.append(coords[2])
        center_coords = [round(center(l), 4) for l in [x_list, y_list, z_list]]
        box_size = lambda x_list: max(size(x_list) + extend, min_size)
        box_sizes = [round(box_size(l), 4) for l in [x_list, y_list, z_list]]
        return center_coords, box_sizes

    dirname = os.path.abspath(os.path.dirname(input_file))
    basename = os.path.basename(input_file)
    if not output_dir:
        output_dir = dirname

    prefix = basename.split(".")[0] if not prefix else prefix
    output_pdb = f'{output_dir}/{prefix}_clean.pdb'
    output_config = f'{output_dir}/{prefix}_config.txt'
    output_log = f'{output_dir}/ligand_extract_log.txt'

    if len(input_file) == 4:
        input_file = input_file.lower()
    atoms = prody.parsePDB(input_file)
    atoms.setAltlocs(' ')
    if chain != 'all':
        atoms = atoms.select(f'chain {chain}')
    ligand_atoms = atoms.select('(hetero or nucleoside or nucleobase) and (not water)')
    nucleotide_atoms = atoms.select('nucleotide')
    nucleotide_serials = set(atom.getSerial() for atom in nucleotide_atoms) if nucleotide_atoms else set()

    ligand_res = {}
    if ligand_atoms:
        for atom in ligand_atoms:
            key = get_key(atom)
            if key not in ligand_res:
                ligand_res[key] = [atom]
            else:
                ligand_res[key].append(atom)

    # Read SEQRES, HET, and MODRES
    with open(input_file + '.pdb.gz', 'r') if len(input_file) == 4 else open(input_file) as f:
        lines = map(lambda x: x.decode(), f.read().splitlines()) if len(input_file) == 4 else f.read().splitlines()

    chain_res, het_res, modres = [], [], []
    chain_seq = {}
    for line in lines:
        if line.startswith('SEQRES'):
            chain_id = line[11]
            line_res = line[19:].split()
            if chain_id not in chain_seq:
                chain_seq[chain_id] = line_res
            else:
                chain_seq[chain_id].extend(line_res)
            chain_res.extend(line_res)

        if line.startswith('MODRES'):
            resname = line[12:15]
            chain_id = line[16]
            resnum = line[17:22].strip()
            modres.append((chain_id, resnum, resname))
        if line.startswith('HET '):
            resname = line[7:10]
            chain_id = line[12]
            resnum = line[13:17].strip()
            het_res.append((chain_id, resnum, resname))
    chain_res = set(chain_res)

    chain_seq_len = {}
    for chid, seq in chain_seq.items():
        if seq[-1] == 'NH2':
            seq.pop()
        chain_seq_len[chid] = len(seq)

    # Add peptide ligands
    for chid, chain_len in chain_seq_len.items():
        if 0 < chain_len <= max_peptide_len:
            key = f'{chid}_LEN{chain_len}_PEP'
            resname_str = ' '.join(set(chain_seq[chid]))
            ligand_res[key] = list(atoms.select(f'chain {chid} resname {resname_str}'))

    # Remove inorganic ions, nonstd AA, and nonstd nucleotides
    for key in list(ligand_res):
        res_name = key.split('_')[-1]
        if not has_carbon(ligand_res[key]) or res_name in chain_res:
            del ligand_res[key]

    # Add ligand atoms
    for res in het_res:
        chain, resnum, resname = res
        key = f'{chain}_{resnum}_{resname}'
        aa_atoms = atoms.select(f'protein chain {chain} resnum {resnum}')
        if res not in modres and aa_atoms:
            ligand_res[key] = list(aa_atoms)
        nucl_atoms = atoms.select(f'nucleotide chain {chain} resnum {resnum}')
        if nucl_atoms:
            ligand_res[key] = list(nucl_atoms)

    ligand_atom_num = []
    ligand_stats = {}
    for key in ligand_res:
        atom_num = len(ligand_res[key])
        ligand_atom_num.append((key, atom_num))
        resname = key.split('_')[-1]
        if resname not in ligand_stats:
            ligand_stats[resname] = {'num': 0}
        ligand_stats[resname]['num'] += 1
        ligand_stats[resname]['atom_num'] = atom_num

    if ligand_atom_num:
        print('\nligand_name\tnum_atoms\tcenter')
        protein_center, _ = get_box_prody(atoms)
        for key, num in ligand_atom_num:
            c, _ = get_box_prody(ligand_res[key])
            print(f'{key}\t\t{num}\t{tuple(map(lambda x: round(x, 3), c))}')

        if ligand_name:
            for key, num in ligand_atom_num:
                if key.endswith(ligand_name):
                    sel_key = key
                    break
        else:
            sel_key = sorted(ligand_atom_num, key=lambda x: x[1], reverse=True)[0][0]

        center_coords, box_size = get_box_prody(ligand_res[sel_key], extend=extend, min_size=min_box_size)
        print('\nSelected ligand:', sel_key)
        print('Num of atoms:', len(ligand_res[sel_key]))
        print('Center:', center_coords)
        print('Box size:', box_size)

        with open(output_config, 'w') as f:
            f.write(f'center_x = {center_coords[0]}\n')
            f.write(f'center_y = {center_coords[1]}\n')
            f.write(f'center_z = {center_coords[2]}\n')
            f.write(f'size_x = {box_size[0]}\n')
            f.write(f'size_y = {box_size[1]}\n')
            f.write(f'size_z = {box_size[2]}\n')

    else:
        print('\nNo ligand')

    if not os.path.exists(output_log):
        with open(output_log, 'w') as f:
            f.write(f'name\tchain\t#ligands\t#type of ligands\tselected ligand\tall ligands\n')

    sel_ligand_str = f'{sel_key}({len(ligand_res[sel_key])})' if ligand_atom_num else ''
    ligand_str = ''
    for ligand_name, ligand_dict in ligand_stats.items():
        if ligand_str:
            ligand_str += '; '
        ligand_str += f'{ligand_name}({ligand_dict["atom_num"]},{ligand_dict["num"]})'

    with open(output_log, 'a') as f:
        f.write(f'{input_file}\t{chain}\t{len(ligand_atom_num)}\t{len(ligand_stats)}\t{sel_ligand_str}\t{ligand_str}\n')

    sel_str = f'resname {" ".join(chain_res)}'
    for key, num in ligand_atom_num:
        chain, resnum, resname = key.split('_')
        if resname != 'PEP':
            sel_str += f' not resnum {resnum}'
        else:
            sel_str += f' not chain {chain}'

    prody.writePDB(output_pdb, atoms.select(sel_str))


# Main entry point for the command line
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract ligands and generate configuration for docking.')
    parser.add_argument('-i', '--input_file', required=True)
    parser.add_argument('-o', '--output_dir')
    parser.add_argument('-pf', '--prefix')
    parser.add_argument('-c', '--chain', default='all')
    parser.add_argument('-s', '--min_box_size', type=float, default=20)
    parser.add_argument('-e', '--extend', type=float, default=10)
    parser.add_argument('-n', '--ligand_name', default=None)
    parser.add_argument('-p', '--max_peptide_len', type=int, default=1)
    args = parser.parse_args()

    extract_ligand(
        input_file=args.input_file,
        output_dir=args.output_dir,
        prefix=args.prefix,
        chain=args.chain,
        min_box_size=args.min_box_size,
        extend=args.extend,
        ligand_name=args.ligand_name,
        max_peptide_len=args.max_peptide_len
    )
