#!/public/home/caiyi/software/miniconda3/bin/python
"""
distributed_unidock.py

Python wrapper to split ligand lists and dispatch UniDock jobs over multiple GPUs via SSH.
Can be used as a script or imported as a module.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.parse_nvidia_smi import find_available_gpus
    from split_pdbqt_list import split_pdbqt_list
else:
    from utils.parse_nvidia_smi import find_available_gpus
    from .split_pdbqt_list import split_pdbqt_list

UNIDOCK = "/public/home/caiyi/software/miniconda3/envs/unidock/bin/unidock"
CODE_PATH = "/public/home/caiyi/eric_github/vs_protocol"
PYTHON3 = "/public/home/caiyi/software/miniconda3/bin/python"
# Remove SPLIT_SCRIPT constant since we use the Python function directly


def run_split_list(
    wd: Path,
    name: str,
    threads: int,
    list_file: Path = None,
    verbose: bool = False
):
    """
    Split the ligand list into multiple chunks using the split_pdbqt_list module
    """
    if verbose:
        print(f"Splitting list into {threads} parts using split_pdbqt_list", file=sys.stderr)
    split_pdbqt_list(
        working_dir=wd,
        prefix=name,
        num_splits=threads,
        list_path=list_file
    )


def launch_unidock_tasks(
    wd: Path,
    name: str,
    receptor: Path,
    config: Path,
    gpu_array,
    search_mode: str,
    suffix: str,
    verbose: bool = False
):
    dock_dir = wd / f"{name}_docked{suffix}"
    pdbqt_dir = wd / f"{name}_pdbqt"
    procs = []
    
    print(f"Starting UniDock on {len(gpu_array)} GPU(s)...")

    for idx, gpu_id in enumerate(gpu_array):
        node_id, cuda_id = gpu_id.split(':')
        split_file = wd / f"{name}_list_split" / f"{name}_list_split_{idx:02d}.txt"
        ssh_host = f"gpu{node_id}"
        cmd = [
            'ssh', ssh_host,
            f"cd {pdbqt_dir} && "
            f"CUDA_VISIBLE_DEVICES={cuda_id} {UNIDOCK}"
            f" --receptor {receptor}"
            f" --ligand_index {split_file}"
            f" --config {config}"
            f" --dir {dock_dir}"
            f" --verbosity 0"            
            f" --search_mode {search_mode}"
        ]
        if verbose:
            print(f"Launching on {ssh_host} (GPU {cuda_id}):", ' '.join(cmd), file=sys.stderr)
        proc = subprocess.Popen(cmd)
        procs.append(proc)

    for p in procs:
        p.wait()
        if p.returncode != 0:
            print(f"UniDock exited with code {p.returncode}", file=sys.stderr)


def distributed_unidock(
    config: str,
    receptor: str,
    wd: str,
    name: str,
    threads: int,
    search_mode: str,
    list_file: str = None,
    suffix: str = "",
    verbose: bool = False
):
    """
    Core function to split and distribute UniDock jobs.

    Args:
      config:      path to UniDock config file
      receptor:    path to receptor PDBQT
      wd:          working directory
      name:        ligand list prefix
      threads:     number of GPU slots to request
      search_mode: either 'fast' or 'balance'
      list_file:   optional existing list of ligands
      suffix:      optional suffix for output dir
      verbose:     if True, print each command
    """
    config = Path(config).resolve()
    receptor = Path(receptor).resolve()
    wd = Path(wd).resolve()

    # create output dir
    dock_dir = wd / f"{name}_docked{suffix}"
    dock_dir.mkdir(parents=True, exist_ok=True)

    # pick GPUs
    if verbose:
        print(f"Selecting up to {threads} GPUs...", file=sys.stderr)
    gpu_array = find_available_gpus(threads, verbose=verbose)
    if verbose:
        print(f"GPUs selected: {gpu_array}", file=sys.stderr)

    # split list
    actual = len(gpu_array)
    run_split_list(
        wd,
        name,
        actual,
        Path(list_file).resolve() if list_file else None,
        verbose
    )

    # launch
    print(f"Running UniDock on {actual} GPU(s): {gpu_array}")
    launch_unidock_tasks(
        wd, name, receptor, config, gpu_array, search_mode, suffix, verbose
    )
    print("All UniDock tasks completed.")    


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Distributed UniDock: split inputs & dispatch via SSH across GPUs",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-c', '--config', required=True, help='UniDock config file (PDBQT)')
    parser.add_argument('-r', '--receptor', required=True, help='Receptor PDBQT file')
    parser.add_argument('-d', '--wd', required=True, help='Working directory')
    parser.add_argument('-n', '--name', required=True, help='Prefix for ligand list')
    parser.add_argument('-t', '--threads', type=int, required=True, help='Number of GPU slots')
    parser.add_argument('-m', '--search_mode',
                        choices=['fast', 'balance'], required=True,
                        help='UniDock search mode')
    parser.add_argument('-l', '--list', help='Optional ligand-list file')
    parser.add_argument('-x', '--suffix', default='', help='Suffix for output dir name')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    distributed_unidock(
        config=args.config,
        receptor=args.receptor,
        wd=args.wd,
        name=args.name,
        threads=args.threads,
        search_mode=args.search_mode,
        list_file=args.list,
        suffix=args.suffix,
        verbose=args.verbose,
    )
