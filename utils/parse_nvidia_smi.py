#!/usr/bin/env python3
"""
Module: parse_nvidia_smi.py

This module provides functions to fetch GPU usage and memory stats from remote hosts via SSH,
then replicate the original script’s logic to identify and sort available GPUs per-host, matching the exact behavior.
It can be used both as a library and a CLI tool.
"""
import sys
import subprocess
from typing import Dict, List, Tuple, Optional

# --- Constants ---
MIN_FREE_MEM_MB = 10000
MAX_UTIL_PERCENT = 70
SSH_HOSTS = ["gpu1", "gpu2"]
TOTAL_MEM_MB = 24576


def _run_ssh_command(host: str, command: str, verbose: bool = False) -> Tuple[str, str, int]:
    cmd = ["ssh", host, command]
    if verbose:
        print(f"Executing SSH command on {host}: {command}", file=sys.stderr)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return out, err, proc.returncode


def parse_nvidia_outputs(outs: List[str]) -> Tuple[Dict[str,int], Dict[str,int]]:
    """
    Replicate original parsing: enumerate each host's GPUs by index and extract mem/util.
    outs: list of stdout strings, in order corresponding to SSH_HOSTS.
    Returns global memory_dict and usage_dict.
    """
    memory_dict: Dict[str,int] = {}
    usage_dict: Dict[str,int] = {}

    for host_idx, output in enumerate(outs, start=1):
        idx = 0
        for line in output.splitlines():
            if 'W' in line and '%' in line:
                parts = line.split()
                try:
                    mem = int(parts[-7][:-3])
                    util = int(parts[-3][:-1])
                except (ValueError, IndexError):
                    continue
                gpu_id = f"{host_idx}:{idx}"
                memory_dict[gpu_id] = mem
                usage_dict[gpu_id] = util
                idx += 1
    return memory_dict, usage_dict


def find_available_gpus(num_gpus: int, verbose: bool = False) -> List[str]:
    # Fetch raw outputs
    outs = []
    for host in SSH_HOSTS:
        out, err, rc = _run_ssh_command(host, "nvidia-smi", verbose)
        if rc != 0 and verbose:
            print(f"SSH fetch failed on {host}", file=sys.stderr)
        outs.append(out)

    memory_dict, usage_dict = parse_nvidia_outputs(outs)

    # Build avail_list1 and avail_list2 exactly as original
    avail_list1: List[Tuple[str,int]] = []
    # host1 has indices from max down to 0; determine count by keys
    max_idx1 = max((int(k.split(':')[1]) for k in memory_dict if k.startswith('1:')), default=-1)
    for i in range(max_idx1, -1, -1):
        gpu_id = f'1:{i}'
        if (TOTAL_MEM_MB - memory_dict.get(gpu_id,0) > MIN_FREE_MEM_MB) and (usage_dict.get(gpu_id,100) < MAX_UTIL_PERCENT):
            avail_list1.append((gpu_id, usage_dict[gpu_id]))
    avail_list1.sort(key=lambda x: x[1])

    avail_list2: List[Tuple[str,int]] = []
    max_idx2 = max((int(k.split(':')[1]) for k in memory_dict if k.startswith('2:')), default=-1)
    for i in range(max_idx2, -1, -1):
        gpu_id = f'2:{i}'
        if (TOTAL_MEM_MB - memory_dict.get(gpu_id,0) > MIN_FREE_MEM_MB) and (usage_dict.get(gpu_id,100) < MAX_UTIL_PERCENT):
            avail_list2.append((gpu_id, usage_dict[gpu_id]))
    avail_list2.sort(key=lambda x: x[1])

    # combined = avail_list1 + avail_list2
    combined = avail_list2 + avail_list1
    num = min(len(combined), num_gpus)
    return [gpu for gpu,_ in combined[:num]]


def parse_args() -> int:
    if len(sys.argv)!=2:
        print(f"Usage: {sys.argv[0]} <num_gpus>")
        sys.exit(1)
    try:
        v = int(sys.argv[1]); assert v>=0
        return v
    except:
        print("Error: <num_gpus> must be a non-negative integer.")
        sys.exit(1)


if __name__=='__main__':
    requested = parse_args()
    results = find_available_gpus(requested, verbose=True)
    for gid in results:
        print(gid)
