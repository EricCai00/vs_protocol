from glob import glob
import os
import sys
import argparse
sys.path.append('/public/home/caiyi/eric_github/vs_protocol')

from module_4.distributed_unidock import distributed_unidock
from module_4.extract_vina_score import extract_scores
from utils.get_box import extract_ligand
from utils.utils import run_command

# if __name__ == '__main__':
#     # sys.path.append('/public/home/caiyi/eric_github/vs_protocol/module_4')
    
#     from module_4.distributed_unidock import distributed_unidock
#     from extract_ligand import extract_ligand
# else:
#     from module_4.distributed_unidock import distributed_unidock
#     from extract_ligand import extract_ligand

PREPARE_RECEPTOR = '/public/home/caiyi/install/bin/prepare_receptor'


def run_off_targets(targets_dir, pdbqt_dir, wd, smi_path, dock_threads=4, extract_threads=40):
    list_path = f'{wd}/list.txt'
    receptors_dir = f'{wd}/targets'
    os.makedirs(receptors_dir, exist_ok=True)

    for target_pdb in glob(f'{targets_dir}/*.pdb'):
        extract_ligand(input_file=target_pdb, output_dir=receptors_dir)

        receptor_name = os.path.basename(target_pdb)[:-4]
        clean_pdb = receptor_name + '_clean.pdb'
        receptor_pdbqt = clean_pdb + 'qt'
        config_path = receptor_name + '_config.txt'
        run_command([PREPARE_RECEPTOR,
                    '-r', f'{receptors_dir}/{clean_pdb}',
                    '-o', f'{receptors_dir}/{receptor_pdbqt}',
                    '-A', 'hydrogen'])
        if not os.path.exists(f'{wd}/{receptor_name}_pdbqt'):
            os.symlink(pdbqt_dir, f'{wd}/{receptor_name}_pdbqt', target_is_directory=True)

        names = []
        with open(smi_path) as f:
            lines = f.read().splitlines()
            for line in lines:
                smi, name = line.split()
                names.append(name)

        # print(lib_path, lines)
        with open(list_path, 'w') as fo:
            for name in names:
                try:
                    assert os.path.isfile(f'{pdbqt_dir}/{name}.pdbqt')
                    fo.write(f'{name}.pdbqt\n')
                except:
                    print(f'Warning: File {name}.pdbqt does not exists.')

        distributed_unidock(
            config=f'{receptors_dir}/{config_path}',
            receptor=f'{receptors_dir}/{receptor_pdbqt}',
            wd=wd,
            name=receptor_name,
            threads=dock_threads,
            search_mode='fast',
            list_file=list_path
        )

        extract_scores(
            name=receptor_name,
            docked_dir=f'{wd}/{receptor_name}_docked',
            output_dir=wd,
            threads=extract_threads
        )

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-t', '--target_dir', required=True)
    parser.add_argument('-d', '--working_dir', required=True)
    parser.add_argument('-s', '--smi_path', required=True)
    args = parser.parse_args()

    run_off_targets(targets_dir=args.target_dir, wd=args.working_dir, smi_path=args.smi_path)
