#!/public/home/caiyi/software/miniconda3/bin/python

import argparse
import os
import subprocess
import sys
from pathlib import Path
import shlex
import threading
import pty

from utils.parse_pbsstat import calculate_node_distribution

DEFAULT_OBABEL_EXE = "/public/home/caiyi/software/miniconda3/bin/obabel"
DEFAULT_PYTHON2_EXE = "/public/home/caiyi/software/miniconda3/envs/python2/bin/python2"
DEFAULT_PREPARE_LIGAND4_SCRIPT = "/public/home/caiyi/software/miniconda3/envs/python2/bin/prepare_ligand4.py"

def stream_text_pipe(pipe, output_stream):
    """Reads and prints text lines from a pipe."""
    try:
        for line in iter(pipe.readline, ''):
            output_stream.write(line)
            output_stream.flush()
    except Exception:
        pass
    finally:
        if pipe and not pipe.closed:
            pipe.close()

def stream_pty_master_fd_raw(fd_master, output_stream):
    """Reads raw bytes from PTY master fd and prints them with filtering."""
    try:
        encoding = getattr(sys.stderr, 'encoding', None) or 'utf-8'
        buffer = ""
        last_progress = ""
        
        while True:
            chunk = os.read(fd_master, 1024)
            if not chunk:
                break
            
            text = chunk.decode(encoding, errors='replace')
            buffer += text
            
            # 处理完整的行
            while '\n' in buffer or '\r' in buffer:
                # 优先按\n分割，其次按\r
                if '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                else:
                    line, buffer = buffer.split('\r', 1)
                
                # 过滤掉冗长的分子信息输出，只保留进度条
                # 保留包含ETA、百分比、时间估计的行（GNU parallel的进度条）
                if any(marker in line for marker in ['ETA:', '%', 'sec', 'Computers', 'Sockets']):
                    # 移除ANSI转义序列
                    import re
                    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    clean_line = re.sub(r'\x1b\[7m', '', clean_line)
                    
                    # 只显示进度百分比行，避免重复
                    if '%' in clean_line and clean_line != last_progress:
                        output_stream.write(clean_line + '\n')
                        output_stream.flush()
                        last_progress = clean_line
                elif 'Error' in line or 'Warning' in line or 'error' in line.lower():
                    # 保留错误和警告信息
                    output_stream.write(line + '\n')
                    output_stream.flush()
                # 其他详细的分子信息行都忽略
            
    except OSError:
        pass
    except Exception:
        pass

def distributed_prepare_ligand(input, output_dir, threads, force, verbose, blocked_nodes):
    obabel_exe_path = os.getenv("OBABEL", DEFAULT_OBABEL_EXE)
    python2_exe_path = os.getenv("PYTHON2", DEFAULT_PYTHON2_EXE)
    prepare_ligand4_script_path = os.getenv("PREPARE_LIGAND4", DEFAULT_PREPARE_LIGAND4_SCRIPT)

    for tool_path, tool_name in [(obabel_exe_path, "OBABEL"), (python2_exe_path, "PYTHON2"), (prepare_ligand4_script_path, "PREPARE_LIGAND4")]:
        if not Path(tool_path).is_file():
            print(f"Error: {tool_name} executable/script not found at '{tool_path}'.", file=sys.stderr)
            sys.exit(1)

    input_file_abs = Path(input).resolve()
    output_dir_abs = Path(output_dir).resolve()

    if not input_file_abs.is_file():
        print(f"Error: Input file not found: {input_file_abs}", file=sys.stderr)
        sys.exit(1)

    work_dir_abs = output_dir_abs.parent
    base_filename_no_ext = input_file_abs.stem
    mol2_dir = work_dir_abs / f"{base_filename_no_ext}_mol2"

    for dir_path, dir_name_desc in [(mol2_dir, "Temporary MOL2 directory"), (output_dir_abs, "Final PDBQT output directory")]:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
        elif os.listdir(str(dir_path)) and not force:
            print(f"Error: {dir_name_desc} '{dir_path}' is not empty! Use -f to force.", file=sys.stderr)
            sys.exit(1)

    if verbose:
        print(f"Requesting cluster status to allocate {threads} task slots...", flush=True)

    job_slots_per_node, error_msg = calculate_node_distribution(n_jobs_or_mode=threads, verbose=verbose, blocked_nodes=blocked_nodes)
    print('job_slots_per_node', job_slots_per_node)

    if error_msg:
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    if job_slots_per_node is None or not isinstance(job_slots_per_node, dict):
        print("Error: Cluster allocation function did not return a valid dictionary.", file=sys.stderr)
        sys.exit(1)

    node_order_for_S_arg = ['node1', 'node2', 'node3', 'gpu1', 'gpu2']
    s_args_list = []
    active_nodes_for_distrib = False
    for node_name in node_order_for_S_arg:
        slots = job_slots_per_node.get(node_name, 0)
        if slots > 0:
            active_nodes_for_distrib = True
        s_args_list.append(f"{slots}/{node_name}")
    parallel_S_arg_str = ",".join(s_args_list)

    if not active_nodes_for_distrib and verbose:
        print("Warning: No available processing slots on specified nodes. Check parse_pbsstat output.", file=sys.stderr)

    if verbose:
        print(f"GNU Parallel -S argument: {parallel_S_arg_str}", flush=True)

    sq_obabel_exe = shlex.quote(obabel_exe_path)
    sq_python2_exe = shlex.quote(python2_exe_path)
    sq_prepare_ligand4_script = shlex.quote(prepare_ligand4_script_path)
    sq_mol2_target_subdir_path = shlex.quote(str(mol2_dir))
    sq_pdbqt_target_dir_path = shlex.quote(str(output_dir_abs))

    parallel_command_block = f"""
    LINE={{}}
    zinc=${{LINE##* }}
    _base_name="{base_filename_no_ext}" 
    _mol2_dir={sq_mol2_target_subdir_path}  
    _pdbqt_dir={sq_pdbqt_target_dir_path} 
    # _obabel_outfile_fullpath="${{_mol2_dir}}/${{_base_name}}_${{zinc}}.mol2"
    _obabel_outfile_fullpath="${{_mol2_dir}}/${{zinc}}.mol2"
    # _preplig_infile_relative="${{_base_name}}_${{zinc}}.mol2" 
    _preplig_infile_relative="${{zinc}}.mol2" 
    # _preplig_outfile_fullpath="${{_pdbqt_dir}}/${{_base_name}}_${{zinc}}.pdbqt"
    _preplig_outfile_fullpath="${{_pdbqt_dir}}/${{zinc}}.pdbqt"
    timeout 5m {sq_obabel_exe} -:"$LINE" -omol2 -O "${{_obabel_outfile_fullpath}}" --gen3d > /dev/null 2>&1
    cd "${{_mol2_dir}}" 
    {sq_python2_exe} {sq_prepare_ligand4_script} -l "${{_preplig_infile_relative}}" -o "${{_preplig_outfile_fullpath}}"
    """

    cmd_list_for_parallel = [
        'parallel',
        '-S', parallel_S_arg_str,
        '--linebuffer', 
        '--bar',        
        parallel_command_block 
    ]

    if verbose:
        print(f"\nExecuting: parallel -S {parallel_S_arg_str} --linebuffer --bar \\", flush=True)
        print(f"  '{parallel_command_block.strip()}' \\", flush=True)
        print(f"  < {input_file_abs}\n", flush=True)

    master_stderr_fd, slave_stderr_fd = pty.openpty()
    process = None
    actual_slave_stderr_fd_to_close = slave_stderr_fd

    try:
        with open(input_file_abs, 'rb') as infile_for_parallel_stdin_bytes:
            process = subprocess.Popen(
                cmd_list_for_parallel,
                stdin=infile_for_parallel_stdin_bytes,
                stdout=subprocess.PIPE,
                stderr=actual_slave_stderr_fd_to_close,
                bufsize=0
            )
        os.close(actual_slave_stderr_fd_to_close)
        actual_slave_stderr_fd_to_close = -1

        stdout_thread = threading.Thread(target=stream_pty_master_fd_raw, args=(process.stdout.fileno(), sys.stdout))
        stderr_thread = threading.Thread(target=stream_pty_master_fd_raw, args=(master_stderr_fd, sys.stderr))

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        return_code = process.wait()

        if return_code != 0:
            print(f"\nError: GNU parallel command finished with failure count: {return_code}", file=sys.stderr, flush=True)
        else:
            print("\nGNU parallel batch processing completed successfully.", flush=True)

    except FileNotFoundError:
        print("Error: GNU parallel command not found. Please ensure it's installed and in your PATH.", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"Error during GNU parallel execution: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    finally:
        if actual_slave_stderr_fd_to_close != -1:
            try: os.close(actual_slave_stderr_fd_to_close)
            except OSError: pass
        try: os.close(master_stderr_fd)
        except OSError: pass

        if process and process.poll() is None: 
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass

    print(f"Temporary MOL2 files are located at: {mol2_dir}", flush=True)
    print(f"Final PDBQT files are located at: {output_dir_abs}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare ligands using GNU parallel. Input SMILES file and output PDBQT files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Input SMILES file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for PDBQT files.")
    parser.add_argument("-t", "--threads", type=int, required=True, help="Total number of threads or job slots to request.")
    parser.add_argument("-f", "--force", action="store_true", help="Continue even if output directories are not empty.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    
    args = parser.parse_args()

    distributed_prepare_ligand(args.input, args.output_dir, args.threads, args.force, args.verbose)
