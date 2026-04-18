#!/usr/bin/env python3
import os
import sys
import shutil
import yaml
import pathlib
import pandas as pd
import numpy as np
import prody
import time

from utils.utils import run_command, zscore_sigmoid
from utils.get_box import extract_ligand, gen_config_mol2
from utils.library_preprocess import library_preprocess

from pc_filter.physchem import calc_physchem

from admet_filter.admetlab_prepare import admetlab_prepare
from admet_filter.admetlab_score import admetlab_score

from druglikeness.druglikeness.launch_dln_tasks import distributed_dln_pred

from docking.conformers import batch_generate_conformers
from docking.distributed_prepare_ligand import distributed_prepare_ligand
from docking.distributed_prepare_ligand_pdb import distributed_prepare_ligand_pdb
from docking.distributed_unidock import distributed_unidock
from docking.extract_vina_score import extract_scores
from docking.hbond_plip import count_hbonds_batch as count_hbonds_plip
from docking.hbond_pymol import run_hbond_analysis as count_hbonds_pymol

# --- Global Paths ---
PREPARE_RECEPTOR = '/public/home/caiyi/install/bin/prepare_receptor'
BASH = shutil.which("bash") or "/usr/bin/bash"

REPO_PATH = pathlib.Path(__file__).parent.resolve()
ADMETLAB_PREDICT = f'{REPO_PATH}/admet_filter/admetlab_predict.py'

MODULE_ORDER = [
    "library",          # 0: 库预处理
    "receptor",         # 1: 受体准备
    "physicochemical",  # 2: 理化性质筛选
    "admet",            # 3: ADMET筛选
    "druglikeness",     # 4: 类药性预测
    "prepare_ligand",   # 5: 分子准备
    "docking",          # 6: 分子对接
    "result",           # 7: 结果分析
]


def load_config(config_path):
    with open(os.path.expanduser(config_path)) as f:
        return yaml.safe_load(f)


def should_run(module_name, start_module):
    return MODULE_ORDER.index(module_name) >= MODULE_ORDER.index(start_module)


def filter_library(current_library, filtered_library, sel_names):
    with open(current_library) as f:
        lines = f.read().splitlines()
    with open(filtered_library, 'w') as fo:
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                smi, name = parts[0], parts[1]
                if name in sel_names:
                    fo.write(f'{smi} {name}\n')
    return filtered_library


def main():
    if len(sys.argv) != 2:
        print("Usage: python vs_protocol.py /path/to/config.yaml")
        sys.exit(1)

    config = load_config(sys.argv[1])
    working_dir = os.path.expanduser(config['working_directory'])
    project_name = config['project_name']
    start_module = config.get('start_module', MODULE_ORDER[0])
    receptor_pdb = os.path.expanduser(config['receptor_pdb'])
    ref_ligand_file = config.get('ref_ligand_file', '')
    if ref_ligand_file:
        ref_ligand_file = os.path.expanduser(ref_ligand_file)
    library_smi = os.path.expanduser(config.get('library_smiles', ''))
    current_library = library_smi

    project_dir = os.path.join(working_dir, project_name)
    receptor_dir = os.path.join(project_dir, 'receptor')
    os.makedirs(receptor_dir, exist_ok=True)
    clean_pdb = os.path.join(receptor_dir, f"{project_name}_clean.pdb")
    receptor_pdbqt = os.path.join(receptor_dir, f"{project_name}_clean.pdbqt")

    # ==================== MODULE 0: Library Preprocessing ====================
    config_library = config.get('library', {})
    if config_library.get('active', False):
        print("-------------------- MODULE 0: Library Preprocessing --------------------")
        processed_library = os.path.join(project_dir, 'library_preprocessed.smi')
        library_preprocess(current_library, processed_library,
                           threads=config_library.get('threads', 60))
        current_library = processed_library
    else:
        print("SKIPPING MODULE 0: Library Preprocessing.")

    # ==================== MODULE 1: Receptor Preparation ====================
    config_receptor = config.get('receptor', {})
    if should_run('receptor', start_module) and config_receptor.get('active', False):
        print("-------------------- MODULE 1: Receptor Preparation --------------------")
        if ref_ligand_file:
            gen_config_mol2(
                mol2_path=ref_ligand_file,
                receptor_path=receptor_pdb,
                output_dir=receptor_dir,
                prefix=project_name
            )
        else:
            extract_ligand(
                input_file=receptor_pdb,
                output_dir=receptor_dir,
                prefix=project_name
            )
        run_command([
            PREPARE_RECEPTOR,
            '-r', clean_pdb,
            '-o', receptor_pdbqt,
            '-A', 'hydrogens'
        ], step_name='Prepare Receptor')
    else:
        print("SKIPPING MODULE 1: Receptor Preparation.")

    # ==================== MODULE 2: Physicochemical Screening ====================
    config_pc = config.get('physicochemical', {})
    pc_dir = os.path.join(project_dir, 'physicochemical')
    if should_run('physicochemical', start_module) and config_pc.get('active', False):
        print("-------------------- MODULE 2: Physicochemical Screening --------------------")
        os.makedirs(pc_dir, exist_ok=True)
        physchem_file = f'{pc_dir}/physchem.csv'
        if config_pc.get('perform_phychem_predict', False):
            calc_physchem(
                input_=current_library,
                output=physchem_file,
                set_='all',
                threads=config_pc.get('threads', 60)
            )

        if config_pc.get('perform_phychem_filter', False):
            physchem_df = pd.read_csv(physchem_file)
            phychem_array = np.array([
                np.logical_and(physchem_df['MW'] >= float(config_pc['mw_lower']),
                               physchem_df['MW'] <= float(config_pc['mw_upper'])),
                np.logical_and(physchem_df['LogP'] >= float(config_pc['logp_lower']),
                               physchem_df['LogP'] <= float(config_pc['logp_upper'])),
                np.logical_and(physchem_df['nHA'] >= float(config_pc['nha_lower']),
                               physchem_df['nHA'] <= float(config_pc['nha_upper'])),
                physchem_df['nHD'] <= float(config_pc['nhd_upper']),
                physchem_df['nRot'] <= float(config_pc['nrot_upper']),
                physchem_df['nRing'] <= float(config_pc['nring_upper']),
                physchem_df['MaxRing'] <= float(config_pc['maxring_upper']),
                physchem_df['nStereo'] <= float(config_pc['nstereo_upper']),
                physchem_df['TPSA'] <= float(config_pc['tpsa_upper']),
                physchem_df['QED'] >= float(config_pc['qed_lower']),
                physchem_df['SAscore'] <= float(config_pc['sascore_upper'])
            ])
            prop_count = phychem_array.shape[0]
            sel_names = set(
                physchem_df[phychem_array.mean(0) >= config_pc['count_lower'] / prop_count]['name']
            )
            current_library = filter_library(
                current_library,
                f'{pc_dir}/library_filtered_phychem.smi',
                sel_names
            )
    else:
        print("SKIPPING MODULE 2: Physicochemical Screening.")

    # ==================== MODULE 3: ADMET Screening ====================
    config_admet = config.get('admet', {})
    admet_dir = os.path.join(project_dir, 'admet')
    if should_run('admet', start_module) and config_admet.get('active', False):
        print("-------------------- MODULE 3: ADMET Screening --------------------")
        os.makedirs(admet_dir, exist_ok=True)
        if config_admet.get('perform_admet_prepare', False):
            print("\n-------- ADMET: Prepare FPs & descriptors --------")
            admetlab_prepare(
                input_=current_library,
                wd=admet_dir,
                suffix=project_name,
                threads=config_admet.get('admet_prepare_threads', 60)
            )
            current_library = os.path.join(admet_dir, f'admetlab_input_{project_name}.smi')
        if config_admet.get('perform_admet_predict', False):
            print("\n-------- ADMET: Predicting --------")
            run_command([
                ADMETLAB_PREDICT,
                '-i', admet_dir,
                '-o', admet_dir,
                '-t', str(config_admet.get('admet_predict_threads', 30)),
                '-c', str(config_admet.get('admet_predict_chunk', 100000)),
                '-sf', project_name
            ])
        admet_result_file = f'{admet_dir}/admetlab_results_{project_name}.csv'
        admet_score_file = f'{admet_dir}/admetlab_score_{project_name}.csv'
        if config_admet.get('perform_admet_score', False):
            print("\n-------- ADMET: Calculating score --------")
            admetlab_score(
                input_=admet_result_file,
                output=admet_score_file,
                name_field='name',
                keep_nan=True
            )
        if config_admet.get('perform_admet_filter', False):
            print("\n-------- ADMET: Filtering --------")
            admet_score_df = pd.read_csv(admet_score_file)
            admet_result_df = pd.read_csv(admet_result_file)
            name_sets = []
            name_sets.append(set(admet_score_df[
                admet_score_df['score'] >= float(config_admet['admet_score_lower'])
            ]['name']))
            endpoints = ['HIA', 'F (20%)', 'F (30%)', 'VD', 'VD', 'CL', 'CL',
                         'Caco-2', 'hERG', 'H-HT', 'Ames', 'CYP2D6-Substrate', 'Pgp-substrate']
            threshold_names = ['hia_upper', 'f20_upper', 'f30_upper', 'vd_lower', 'vd_upper',
                                'cl_lower', 'cl_upper', 'caco2_lower', 'herg_upper', 'hht_upper',
                                'ames_upper', 'cyp2d6_sub_upper', 'pgp_sub_upper']
            for i, threshold_name in enumerate(threshold_names):
                threshold_type = threshold_name.split('_')[-1]
                if threshold_type == 'lower':
                    name_sets.append(set(admet_result_df[
                        admet_result_df[endpoints[i]] >= float(config_admet[threshold_name])
                    ]['name']))
                elif threshold_type == 'upper':
                    name_sets.append(set(admet_result_df[
                        admet_result_df[endpoints[i]] <= float(config_admet[threshold_name])
                    ]['name']))
                else:
                    raise Exception('Wrong threshold type')
            sel_names = set.intersection(*name_sets)
            current_library = filter_library(
                current_library,
                f'{admet_dir}/library_filtered_admet.smi',
                sel_names
            )
    else:
        print("SKIPPING MODULE 3: ADMET Screening.")

    # ==================== MODULE 4: Druglikeness Screening ====================
    config_dln = config.get('druglikeness', {})
    dln_dir = os.path.join(project_dir, 'druglikeness')
    if should_run('druglikeness', start_module) and config_dln.get('active', False):
        print("-------------------- MODULE 4: Druglikeness Screening --------------------")
        os.makedirs(dln_dir, exist_ok=True)
        if config_dln.get('perform_dln_pred', False):
            print("-------- Druglikeness: Prediction --------")
            distributed_dln_pred(input_smi=current_library, output_dir=dln_dir)

        if config_dln.get('perform_dln_filter', False):
            print("-------- Druglikeness: Filtering --------")
            smi_list, name_list = [], []
            with open(current_library) as f:
                for line in f.read().splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        smi_list.append(parts[0])
                        name_list.append(parts[1])
            df = pd.DataFrame({'name': name_list, 'smiles': smi_list})
            model_names = ['generaldl', 'specdl-ftt', 'specdl-zinc', 'specdl-cm', 'specdl-cp']
            for model in model_names:
                df_dln = pd.read_csv(f'{dln_dir}/druglikeness_{model}.csv')
                assert len(df_dln) == len(df)
                df[model] = df_dln['prediction']
            df['gt_0.5_count'] = (df[model_names] > 0.5).sum(axis=1)
            df_filtered = df[df['gt_0.5_count'] >= config_dln.get('dln_count_lower', 3)]
            sel_names = set(df_filtered.name)
            current_library = filter_library(
                current_library,
                f'{dln_dir}/library_filtered_druglikeness.smi',
                sel_names
            )
    else:
        print("SKIPPING MODULE 4: Druglikeness Screening.")

    # ==================== MODULE 5: Molecular Preparation ====================
    config_prep = config.get('prepare_ligand', {})
    prep_dir = os.path.join(project_dir, 'prepare_ligand')
    ligand_pdbqt_dir = os.path.join(prep_dir, f'{project_name}_pdbqt')
    if should_run('prepare_ligand', start_module) and config_prep.get('active', False):
        print("-------------------- MODULE 5: Molecular Preparation --------------------")
        os.makedirs(prep_dir, exist_ok=True)
        os.makedirs(ligand_pdbqt_dir, exist_ok=True)
        dock_strategy = config_prep.get('dock_strategy', 'single')
        if config_prep.get('perform_prepare', False):
            if dock_strategy == 'single':
                print(f"Preparing ligands: {current_library} → {ligand_pdbqt_dir}")
                distributed_prepare_ligand(
                    input=current_library,
                    output_dir=ligand_pdbqt_dir,
                    threads=config_prep.get('prepare_threads', 90),
                    force=True,
                    verbose=config_prep.get('verbose', False),
                    blocked_nodes=config_prep.get('blocked_nodes', '')
                )
            elif dock_strategy == 'repeated':
                conformer_dir = os.path.join(prep_dir, f'{project_name}_conformers')
                print(f"Generating conformers: {current_library} → {conformer_dir}")
                batch_generate_conformers(
                    smi_path=current_library,
                    output_dir=conformer_dir,
                    num_confs=config_prep.get('num_conformers', 1),
                    num_threads=config_prep.get('gen_conf_threads', 10),
                    rdkit_threads=config_prep.get('rdkit_threads', 0)
                )
                print(f"Preparing ligands from PDB: {conformer_dir} → {ligand_pdbqt_dir}")
                distributed_prepare_ligand_pdb(
                    input_dir=conformer_dir,
                    output_dir=ligand_pdbqt_dir,
                    threads=config_prep.get('prepare_threads', 90),
                    force=True,
                    verbose=config_prep.get('verbose', False),
                    blocked_nodes=config_prep.get('blocked_nodes', '')
                )
            else:
                raise Exception(f"Invalid dock_strategy: {dock_strategy}")
        else:
            print('Skipping preparing molecules.')
    else:
        print("SKIPPING MODULE 5: Molecular Preparation.")

    # ==================== MODULE 6: Molecular Docking ====================
    config_dock = config.get('docking', {})
    dock_dir = os.path.join(project_dir, 'docking')
    docked_dir = os.path.join(dock_dir, f"{project_name}_docked{config_dock.get('output_suffix', '')}")
    if should_run('docking', start_module) and config_dock.get('active', False):
        print("-------------------- MODULE 6: Molecular Docking --------------------")
        os.makedirs(dock_dir, exist_ok=True)

        if config_dock.get('perform_dock', False):
            print("-------- Docking: Running Uni-Dock --------")
            dock_config_file = os.path.join(receptor_dir, f"{project_name}_config.txt") \
                if config_dock.get('config_file', 'auto') == 'auto' else config_dock['config_file']
            distributed_unidock(
                config=dock_config_file,
                receptor=receptor_pdbqt,
                wd=dock_dir,
                name=project_name,
                threads=config_dock.get('dock_threads', 4),
                search_mode=config_dock.get('search_mode', 'fast'),
                list_file=config_dock.get('list_file', None),
                suffix=config_dock.get('output_suffix', ''),
                verbose=config_dock.get('verbose', False)
            )
        else:
            print('Skipping docking.')

        if config_dock.get('perform_extract', False):
            print("-------- Docking: Extract scores --------")
            extract_scores(
                name=project_name,
                docked_dir=docked_dir,
                output_dir=dock_dir,
                threads=config_dock.get('extract_threads', 40),
                suffix=config_dock.get('output_suffix', '')
            )
            score_path = os.path.join(dock_dir, project_name + '_dock_scores.txt')
            print(f"Vina scores saved to {score_path}")
        else:
            print('Skipping extracting scores.')

        if config_dock.get('perform_hbond', False):
            method = config_dock.get('method', 'pymol')
            hbond_file = os.path.join(dock_dir, 'hbond_counts.csv')
            key_residues_str = config_dock.get('key_residues', '')
            key_residue_ids = [r.strip() for r in key_residues_str.split(',') if r.strip()]

            receptor_prody = prody.parsePDB(clean_pdb).getHierView()
            chain = 'A'
            key_residue_names = []
            for res_id in key_residue_ids:
                res_name = receptor_prody.getResidue(chain, int(res_id)).getResname()
                key_residue_names.append(f'{res_name}{res_id}')

            print(f"\n-------- Docking: H-bond analysis ({method.upper()}) --------")
            if method == 'plip':
                complex_dir = os.path.join(project_dir, f'{project_name}_complexes')
                os.makedirs(complex_dir, exist_ok=True)
                count_hbonds_plip(
                    receptor_pdb=receptor_pdb,
                    ligand_dir=docked_dir,
                    complex_dir=complex_dir,
                    threads=config_dock.get('hbond_threads', 40),
                    output=hbond_file
                )
            elif method == 'pymol':
                count_hbonds_pymol(
                    receptor_path=receptor_pdbqt,
                    ligand_dir=docked_dir,
                    output_path=hbond_file,
                    key_residue_ids=key_residue_ids,
                    cutoff=config_dock.get('cutoff', 3.5),
                )
            else:
                raise Exception(f"Unsupported hbond method: {method}")

            if config_dock.get('perform_residue_filter', False):
                print(f"\n-------- Docking: Key residue filtering --------")
                hbond_df = pd.read_csv(hbond_file)
                name2smi = {}
                with open(current_library) as f:
                    for line in f.read().splitlines():
                        parts = line.split()
                        if len(parts) >= 2:
                            name2smi[parts[1]] = parts[0]
                filtered_lib = os.path.join(dock_dir, 'library_filtered_key_residues.smi')
                with open(filtered_lib, 'w') as f:
                    for ligand_name in hbond_df[hbond_df['key_residue_hbonds'] > 0]['ligand_name']:
                        smi = name2smi.get(ligand_name, '')
                        if smi:
                            f.write(f'{smi} {ligand_name}\n')
                print(f'Filtering library using key residues {key_residue_names}')
                print(f'Saved filtered library in {filtered_lib}')
                current_library = filtered_lib
        else:
            print('Skipping H-bond analysis.')
    else:
        print("SKIPPING MODULE 6: Molecular Docking.")

    # ==================== MODULE 7: Result Analysis ====================
    config_result = config.get('result', {})
    if should_run('result', start_module) and config_result.get('active', False):
        print("-------------------- MODULE 7: Result Analysis --------------------")
        print("Result analysis - not implemented yet.")
    else:
        print("SKIPPING MODULE 7: Result Analysis.")


if __name__ == "__main__":
    if not BASH or not os.path.exists(BASH):
        print(f"Error: Bash interpreter not found at '{BASH}'. Please verify BASH path.")
        sys.exit(1)
    main()
