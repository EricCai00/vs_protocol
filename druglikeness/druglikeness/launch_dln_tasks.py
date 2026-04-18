#!/public/home/caiyi/software/miniconda3/bin/python
import argparse
import subprocess
import sys
import os
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from utils.parse_nvidia_smi import find_available_gpus
else:
    from utils.parse_nvidia_smi import find_available_gpus

PREDICT_DLN = '/public/home/caiyi/eric_github/vs_protocol/module_3/druglikeness/predict.py'
WEIGHTS_DIR = '/public/home/caiyi/eric_github/vs_protocol/weights/druglikeness'
PYTHON3 = "/public/home/caiyi/software/miniconda3/bin/python"
# Remove SPLIT_SCRIPT constant since we use the Python function directly


def launch_dln_tasks(
    input_smi: Path,
    output_dir: str,
    gpu_array,
    verbose: bool = False
):
    procs = []
    model_names = ['generaldl', 'specdl-ftt', 'specdl-zinc', 'specdl-cm', 'specdl-cp']
    actual_gpus = [gpu_array[0], gpu_array[0], gpu_array[1], gpu_array[1], gpu_array[2]]

    for idx, gpu_id in enumerate(actual_gpus):
        node_id, cuda_id = gpu_id.split(':')
        ssh_host = f"gpu{node_id}"
        cmd = [
            'ssh', ssh_host,
            f"CUDA_VISIBLE_DEVICES={cuda_id} {PYTHON3} {PREDICT_DLN}"
            f" -i {input_smi}"
            f" -m {WEIGHTS_DIR}/{model_names[idx]}"
            f" -o {output_dir}/druglikeness_{model_names[idx]}.csv"
        ]
        print(cmd)
        if verbose:
            print(f"Launching on {ssh_host} (GPU {cuda_id}):", ' '.join(cmd), file=sys.stderr)
        proc = subprocess.Popen(cmd)
        procs.append(proc)

    for p in procs:
        p.wait()
        if p.returncode != 0:
            print(f"UniDock exited with code {p.returncode}", file=sys.stderr)


def distributed_dln_pred(
    input_smi: str,
    output_dir: str,
    verbose: bool = False
):
    gpu_array = find_available_gpus(3, verbose=verbose)

    print(f"Predicting druglikeness on 3 GPU(s): {gpu_array}")
    launch_dln_tasks(
        input_smi, output_dir, gpu_array, verbose
    )
    print("All druglikeness tasks completed.")    


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Distributed UniDock: split inputs & dispatch via SSH across GPUs",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-i', '--input_smi', required=True, help='UniDock config file (PDBQT)')
    parser.add_argument('-o', '--output_dir', required=True, help='Receptor PDBQT file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    distributed_dln_pred(
        input_smi=args.input_smi,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
