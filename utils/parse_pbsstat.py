#!/usr/bin/env python3
# File: parse_pbsstat.py (Refactored)

import sys
import subprocess

# --- Constants ---
# Node performance, can be adjusted here or passed as an argument if needed

# Fallback if ncpu_dict or load_dict doesn't get a node from pbsstat that's in PERF_DICT
DEFAULT_LOAD = 0.0  # Assuming 0 load if not found
DEFAULT_NCPU = 0    # Assuming 0 CPU if not found

def _run_local_ssh_command(ssh_host, remote_command_str, verbose=False):
    """Helper to run SSH command and capture output."""
    ssh_command_list = ['ssh', ssh_host, remote_command_str]
    if verbose:
        print(f"Executing via SSH to {ssh_host}: {remote_command_str}", flush=True, file=sys.stderr)
    try:
        process = subprocess.run(
            ssh_command_list,
            capture_output=True,
            text=True,
            check=False  # Don't raise an exception for non-zero exit codes
        )
        if verbose and process.stderr:
             print(f"SSH Stderr: {process.stderr.strip()}", flush=True, file=sys.stderr)
        return process.stdout, process.stderr, process.returncode
    except Exception as e:
        if verbose:
            print(f"Exception running SSH command to {ssh_host}: {e}", file=sys.stderr, flush=True)
        return None, str(e), -1

def calculate_node_distribution(
    n_jobs_or_mode,
    ssh_host='master',
    pbsstat_cmd_on_remote='/etc/parakou/bin/pbsstat',
    torque_bin_path='/opt/torque/bin',
    perf_dict_override=None,
    verbose=False,
    blocked_nodes=''
):
    """
    Fetches PBS node status, calculates available power, and determines job distribution.

    Args:
        n_jobs_or_mode: Integer total number of jobs to distribute, or the string 'best'
                        to find the node with maximum available power.
        ssh_host: The host to SSH into to run pbsstat.
        pbsstat_cmd_on_remote: The pbsstat command on the remote host.
        torque_bin_path: Path to be prepended to PATH for finding pbsstat.
        perf_dict_override: Optional dictionary to override internal PERF_DICT.
        verbose: Boolean for verbose output during execution.

    Returns:
        A tuple: (result_data, error_message_str)
        - If n_jobs_or_mode is an integer (number of jobs):
            result_data is a dictionary like {'node1': slots, 'node2': slots, ...}
            error_message_str is None on success, or a string on failure.
        - If n_jobs_or_mode is 'best':
            result_data is the name of the best node (string).
            error_message_str is None on success, or a string on failure.
        - Returns (None, error_message_str) if pbsstat call fails or critical parsing error.
    """
    PERF_DICT = {'node1': 2.5, 'node2': 2.5, 'node3': 2.5, 'gpu1': 2.3, 'gpu2': 1.8}

    if blocked_nodes:
        blocked_nodes_list = blocked_nodes.split(',')
        for node in blocked_nodes_list:
            PERF_DICT.pop(node)

    current_perf_dict = perf_dict_override if perf_dict_override else PERF_DICT
    expected_nodes = set(current_perf_dict.keys())

    remote_command_to_run = f'export PATH={torque_bin_path}:$PATH; {pbsstat_cmd_on_remote}'
    stdout, stderr_ssh, returncode = _run_local_ssh_command(ssh_host, remote_command_to_run, verbose)

    if returncode != 0:
        err_msg = (f"Failed to execute pbsstat via SSH on '{ssh_host}'. RC: {returncode}. "
                   f"Stderr from SSH: {stderr_ssh.strip()}")
        return None, err_msg

    lines = stdout.splitlines()
    load_dict = {}
    ncpu_dict = {}

    for line_content in lines[2:]:  # Skip header lines
        if line_content.startswith('|') and line_content[1] != ' ':
            raw_parts = line_content.split('|')
            # User's original parsing: node=raw_parts[1], ncpu=raw_parts[3], load_raw=raw_parts[4]
            # Then load = load_raw[1:-3].strip()
            if len(raw_parts) < 5: # Need at least up to the raw load column
                if verbose: print(f"Skipping malformed pbsstat line (too few parts): {line_content}", file=sys.stderr)
                continue

            node_name = raw_parts[1].strip()

            if node_name not in expected_nodes:
                if verbose: print(f"Skipping node '{node_name}' not in perf_dict.", file=sys.stderr)
                continue
            
            try:
                ncpu_str = raw_parts[3].strip()
                load_str_column_content = raw_parts[4] # Content of the 4th column (0-indexed part 4)

                # Mimic original parsing: load = line[4][1:-3].strip()
                # This implies the content of column 4 might be like " 0.12* "
                # The slicing [1:-3] for a string " 0.12* " would give "0.12* "
                # Then .strip() gives "0.12*"
                if len(load_str_column_content) >= 4: # Need at least 1 char + content + 3 chars
                    load_str_processed = load_str_column_content[1:-3].strip()
                else: # Fallback if string too short for the specific slice
                    load_str_processed = load_str_column_content.strip()
                
                if load_str_processed.endswith('*'):
                    load_val = float(load_str_processed[:-1])
                else:
                    load_val = float(load_str_processed)
                
                ncpu_val = int(ncpu_str)

                load_dict[node_name] = load_val
                ncpu_dict[node_name] = ncpu_val
            except (ValueError, IndexError) as e:
                if verbose:
                    print(f"Warning: Could not parse line details for node {node_name}: '{line_content}'. Error: {e}", file=sys.stderr)
                # If parsing fails for a node, it won't be in load_dict/ncpu_dict, handled below.
                continue
    
    # Ensure all expected nodes have entries, defaulting if not found in pbsstat output
    for node in expected_nodes:
        if node not in load_dict:
            if verbose: print(f"Node '{node}' from perf_dict not found in pbsstat output. Applying defaults.", file=sys.stderr)
            load_dict[node] = DEFAULT_LOAD
            ncpu_dict[node] = DEFAULT_NCPU

    avail_power_dict = {}
    for node_key in current_perf_dict: # Iterate using perf_dict keys for consistent order if needed
        # ncpu_dict.get() and load_dict.get() provide safety if a node was somehow missed
        avail_power = max(
            (ncpu_dict.get(node_key, DEFAULT_NCPU) * 1.5 - load_dict.get(node_key, DEFAULT_LOAD)) * current_perf_dict[node_key],
            0
        )
        avail_power_dict[node_key] = avail_power

    if n_jobs_or_mode == 'best':
        if not avail_power_dict:
            return None, "No nodes found or available power is zero for all."
        best_node = max(avail_power_dict, key=avail_power_dict.get) if avail_power_dict else None
        if best_node is None and verbose:
            return None, "Could not determine best node (avail_power_dict is empty)."
        return best_node, None

    try:
        num_jobs_to_distribute = int(n_jobs_or_mode)
        if num_jobs_to_distribute < 0:
             return None, f"num_jobs must be a non-negative integer, got {num_jobs_to_distribute}"
    except ValueError:
        return None, f"Invalid n_jobs_or_mode: '{n_jobs_or_mode}'. Must be an integer or 'best'."

    distrib_slots_dict = {}
    total_avail_power = sum(avail_power_dict.values())

    if total_avail_power == 0:
        if verbose: print("Warning: Total available power is 0. Assigning 0 slots to all nodes.", file=sys.stderr)
        for node_key in current_perf_dict:
            distrib_slots_dict[node_key] = 0
        return distrib_slots_dict, None # Return dict with all zeros

    for node_key in current_perf_dict: # Iterate using perf_dict keys for consistent order
        # Empirical ratio from original script
        raw_slots = (num_jobs_to_distribute / total_avail_power * avail_power_dict[node_key] / 0.6) if total_avail_power > 0 else 0
        distrib_slots_dict[node_key] = round(raw_slots)
    
    return distrib_slots_dict, None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <num_jobs | 'best'> [-v|--verbose]", file=sys.stderr)
        sys.exit(1)

    jobs_arg_cli = sys.argv[1]
    verbose_cli = "-v" in sys.argv[2:] or "--verbose" in sys.argv[2:]
    
    mode_cli = None
    if jobs_arg_cli.lower() == 'best':
        mode_cli = 'best'
    else:
        try:
            mode_cli = int(jobs_arg_cli)
            if mode_cli < 0:
                print("Error: num_jobs must be a non-negative integer.", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print(f"Error: Invalid argument '{jobs_arg_cli}'. Must be an integer (num_jobs) or 'best'.", file=sys.stderr)
            sys.exit(1)

    # You can override ssh_host etc. here if you expose them as CLI arguments too
    # For now, using defaults from the function signature
    result, error_msg_cli = calculate_node_distribution(mode_cli, verbose=verbose_cli)

    if error_msg_cli:
        print(f"Error: {error_msg_cli}", file=sys.stderr)
        sys.exit(1)
    
    if result is None: # Should be caught by error_msg_cli
        print("Error: Function returned None without an error message.", file=sys.stderr)
        sys.exit(1)

    if mode_cli == 'best':
        print(result)  # Prints the best node name
    else:
        output_counts = []
        for node_name_key in result.keys(): 
            output_counts.append(str(result[node_name_key]))
        print(" ".join(output_counts))