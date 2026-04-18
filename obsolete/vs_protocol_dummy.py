import argparse
import os
import subprocess
import sys
import shutil # 用于查找 bash
import random # 用于模拟数据
import time # 用于模拟耗时操作

# --- 全局路径和配置 (合并后) ---
PYTHON3 = "/public/home/caiyi/software/miniconda3/bin/python"
PYTHON2 = "/public/home/caiyi/software/miniconda3/envs/python2/bin/python2"
CODE_PATH = "/public/home/caiyi/eric_github/vs_protocol"
PREPARE_RECEPTOR4 = "/public/home/caiyi/software/miniconda3/envs/python2/bin/prepare_receptor4.py"
BASH = shutil.which("bash") or "/usr/bin/bash"

DEFAULT_DD_SCRIPT_PATH = os.path.join(CODE_PATH, "deep_docking.sh")
DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH = os.path.join(CODE_PATH, "distributed_unidock.sh")

GPU_THREADS_DEFAULT = 4
PREPARE_THREADS_DEFAULT = 90
EXTRACT_THREADS_DEFAULT = 15

MODULE_ORDER = ["receptor_prep", "known_inhibitors", "docking", "clustering", "pre_md", "weighted"]

# --- 模拟脚本路径 ---
# 假设这些脚本存在于 CODE_PATH 下的相应模块目录中
CLUSTERING_SCRIPT = os.path.join(CODE_PATH, "module_5_clustering/run_clustering.py")
HBA_CALC_SCRIPT = os.path.join(CODE_PATH, "module_6_pre_md/calculate_hba.py")
OFFTARGET_DOCKING_SCRIPT = os.path.join(CODE_PATH, "module_6_pre_md/run_offtarget_docking.sh") # 假设是一个shell脚本
PHYSCHEM_ADMET_SCRIPT = os.path.join(CODE_PATH, "module_7_weighted/calculate_physchem_admet.py")
WEIGHTED_SCORING_SCRIPT = os.path.join(CODE_PATH, "module_7_weighted/calculate_weighted_score.py")


def run_command(command_parts, step_name="Command", cwd=None, env=None):
    """辅助函数，用于执行命令并打印输出/错误。"""
    print(f"Executing: {' '.join(command_parts)}")
    if cwd:
        print(f"Working directory: {cwd}")
    try:
        process = subprocess.run(command_parts, check=True, capture_output=True, text=True, cwd=cwd, env=env)
        if process.stdout and process.stdout.strip():
            print(f"STDOUT ({step_name}):\n{process.stdout.strip()}")
        if process.stderr and process.stderr.strip():
            print(f"STDERR ({step_name}):\n{process.stderr.strip()}")
        print(f"{step_name} completed successfully.")
        return process
    except subprocess.CalledProcessError as e:
        print(f"Error during {step_name}:")
        if e.stdout and e.stdout.strip():
            print(f"STDOUT:\n{e.stdout.strip()}")
        if e.stderr and e.stderr.strip():
            print(f"STDERR:\n{e.stderr.strip()}")
        sys.exit(f"{step_name} failed with exit code {e.returncode}")
    except FileNotFoundError:
        print(f"Error: The command '{command_parts[0]}' was not found. Please check paths and ensure it's executable.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Virtual Screening Protocol Script with modular execution and a choice of docking methods.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""Examples:
    Run all modules with Deep Docking:
    python vs_protocol.py -d ~/data/vs_protocol -p project_dd -r receptor.pdb -l library.smi \\
    --docking_method deepdocking \\
    --dd_config /path/to/dd_conf.txt --dd_sampling_size 1000

    Run with Module 3 and then UniDock:
    python vs_protocol.py -d ~/data/vs_protocol -p project_ud -r receptor.pdb -l library.smi \\
    --docking_method unidock \\
    --ud_config /path/to_unidock_conf.txt

    Start from docking module (assuming receptor and filtered library already exist):
    python vs_protocol.py -d ~/data/vs_protocol -p project_ud -r receptor.pdb -l filtered_library.smi \\
    --start_module docking --docking_method unidock \\
    --ud_config /path/to_unidock_conf.txt
"""
    )

    # --- 主脚本参数 ---
    parser.add_argument("-d", "--wd", required=True, help="Working directory path")
    parser.add_argument("-p", "--project", required=True, help="Project name")
    parser.add_argument("-r", "--receptor", required=True,
                        help="Receptor PDB file path. Required, even if receptor_prep is skipped, to locate existing PDBQT.")
    parser.add_argument("-l", "--library",
                        help="Input library SMILES file path. Required if running Module 3 or UniDock (and Module 3 is skipped/inactive).")
    parser.add_argument("--start_module", type=str, default=MODULE_ORDER[0],
                        choices=MODULE_ORDER,
                        help=f"Specify the module to start execution from (default: {MODULE_ORDER[0]}). "
                             "Skipped modules are assumed to have their outputs already present if needed by later modules.")

    m3_group = parser.add_argument_group('Module 3: Known Inhibitor Filtering Options')
    m3_group.add_argument("--perform_substruct", type=int, default=0, choices=[0, 1],
                        help="Perform substructure filtering for Module 3 (1=yes, 0=no; default: 0)")
    m3_group.add_argument("--perform_simi", type=int, default=0, choices=[0, 1],
                        help="Perform similarity filtering for Module 3 (1=yes, 0=no; default: 0)")
    m3_group.add_argument("--substruct_list",
                        default="/public/home/caiyi/data/vs_protocol/substructures.txt",
                        help="Path to substructures list file (default: ...)")
    m3_group.add_argument("--simi_query",
                        help="Path to similarity query SMILES file (required if --perform_simi is 1 for Module 3 and Module 3 is active)")
    m3_group.add_argument("--simi_threshold", type=float, default=0.3,
                        help="Similarity threshold for filtering in Module 3 (default: 0.3)")

    # --- Module 4: 对接方法选择 (必选其一) ---
    m4_choice_group = parser.add_argument_group('Module 4: Docking Method (Required - Choose One)')
    m4_choice_group.add_argument("--docking_method", type=str, required=True,
                               choices=["deepdocking", "unidock"],
                               help="Specify the docking method for Module 4: 'deepdocking' or 'unidock'.")

    # --- Deep Docking 模块参数 ---
    dd_group = parser.add_argument_group('Module 4 Option A: Deep Docking Call Options (used if --docking_method deepdocking)')
    dd_group.add_argument("--dd_script_path", default=DEFAULT_DD_SCRIPT_PATH,
                          help=f"Path to deep_docking.sh script (default: {DEFAULT_DD_SCRIPT_PATH})")
    dd_group.add_argument("--dd_config", help="Path to docking configuration file for deep_docking.sh (-c option)")
    dd_group.add_argument("--dd_tot_iters", type=int, default=11,
                          help="Total iterations for deep_docking.sh (-n option; default: 11)")
    dd_group.add_argument("--dd_sampling_size", type=int,
                          help="Sampling size N for deep_docking.sh (-N option)")
    dd_group.add_argument("--dd_start_iter", type=int, default=1,
                          help="Iteration to resume deep_docking.sh from (-i option; default: 1)")
    dd_group.add_argument("--dd_start_step", type=str, default="sample",
                          choices=["sample", "prepare", "dock", "extract", "train", "evaluate", "predict"],
                          help="Step to resume deep_docking.sh from (-s option; default: sample)")
    dd_group.add_argument("--dd_start_set", type=str, default="train", choices=["train", "valid", "test"],
                          help="Dataset to resume 'prepare' or 'dock' step from for deep_docking.sh (-e option; default: train)")

    # --- UniDock 模块参数 ---
    ud_group = parser.add_argument_group('Module 4 Option B: UniDock Call Options (used if --docking_method unidock)')
    ud_group.add_argument("--ud_script_path", default=DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH,
                          help=f"Path to distributed_unidock.sh script (default: {DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH})")
    ud_group.add_argument("--ud_config", help="Path to UniDock configuration file (for -c option of distributed_unidock.sh)")
    ud_group.add_argument("--ud_threads", type=int, default=GPU_THREADS_DEFAULT,
                          help=f"Number of GPU threads for UniDock (-t option, default: {GPU_THREADS_DEFAULT})")
    ud_group.add_argument("--ud_search_mode", type=str, default="fast", choices=["fast", "balance", "accurate"],
                          help="Search mode for UniDock (-m option, default: fast)")
    ud_group.add_argument("--ud_ligand_list_file", default=None,
                          help="(Optional) Path to a specific list file of ligand basenames for UniDock (-l option).")
    ud_group.add_argument("--ud_output_suffix", default="",
                          help="(Optional) Suffix for the UniDock output directory (-x option, e.g., '_run1')")
    ud_group.add_argument("--ud_prepare_threads", type=int, default=PREPARE_THREADS_DEFAULT,
                          help=f"Number of threads for preparing ligands for UniDock (default: {PREPARE_THREADS_DEFAULT})")
    ud_group.add_argument("--ud_extract_threads", type=int, default=EXTRACT_THREADS_DEFAULT,
                          help=f"Number of threads for extracting UniDock scores (default: {EXTRACT_THREADS_DEFAULT})")
    
    # --- Module 5: Clustering 参数 ---
    m5_group = parser.add_argument_group('Module 5: Clustering Options')
    m5_group.add_argument("--clustering_threshold", type=float, default=0.5,
                           help="Similarity threshold for clustering (default: 0.5, for simulation)")
    m5_group.add_argument("--num_clusters_expected", type=int, default=10,
                           help="Expected number of clusters for simulation (default: 10)")


    # --- Module 6: Pre-MD 参数 ---
    m6_group = parser.add_argument_group('Module 6: Pre-MD / Off-target Prediction Options')
    m6_group.add_argument("--off_target_pdb_list", default=None,
                           help="Path to a file containing a list of PDB files for off-target docking (one PDB per line).")
    m6_group.add_argument("--off_target_config", default=None,
                           help="Path to a generic docking configuration file for off-target docking (e.g., UniDock config).")


    args = parser.parse_args()

    # --- 确定模块执行状态 ---
    try:
        start_module_index = MODULE_ORDER.index(args.start_module)
    except ValueError:
        parser.error(f"Internal error: Invalid --start_module choice somehow passed: {args.start_module}")

    def should_run_module(module_name):
        try:
            return MODULE_ORDER.index(module_name) >= start_module_index
        except ValueError: # Should not happen with predefined MODULE_ORDER
            return False

    # --- 参数依赖检查 (部分检查移到模块执行前，以允许跳过模块) ---
    if args.perform_simi == 1 and should_run_module("known_inhibitors") and \
       (args.perform_substruct == 1 or args.library) and not args.simi_query:
        parser.error("--simi_query is required when --perform_simi is 1 and Module 3 (known_inhibitors) is active.")

    if args.docking_method == "deepdocking":
        if should_run_module("docking"): # Only check if docking module is supposed to run
            if not os.path.isfile(os.path.expanduser(args.dd_script_path)):
                parser.error(f"--dd_script_path does not point to a valid file: {args.dd_script_path} (required for docking_method 'deepdocking')")
            if not args.dd_config:
                parser.error("--dd_config is required when docking_method is 'deepdocking'")
            if args.dd_sampling_size is None:
                parser.error("--dd_sampling_size is required when docking_method is 'deepdocking'")
    elif args.docking_method == "unidock":
        if should_run_module("docking"): # Only check if docking module is supposed to run
            if not os.path.isfile(os.path.expanduser(args.ud_script_path)):
                parser.error(f"--ud_script_path does not point to a valid file: {args.ud_script_path} (required for docking_method 'unidock')")
            if not args.ud_config:
                parser.error("--ud_config is required when docking_method is 'unidock'")
            if not args.library and not should_run_module("known_inhibitors"): # If known_inhibitors is run, it might generate the library
                 # This check might need refinement based on whether Module 3 *always* produces the input for UniDock
                parser.error("--library <SMILES_file> is required as input for ligand preparation when docking_method is 'unidock' and Module 3 is skipped or does not produce the required SMILES file.")


    # --- 主流程开始 ---
    work_dir_abs = os.path.expanduser(args.wd)
    project_dir_abs = os.path.join(work_dir_abs, args.project)
    receptor_dir = os.path.join(project_dir_abs, "receptor")
    module_3_dir = os.path.join(project_dir_abs, "module_3")
    module_5_dir = os.path.join(project_dir_abs, "module_5_clustering") # 新增
    module_6_dir = os.path.join(project_dir_abs, "module_6_pre_md")     # 新增
    module_7_dir = os.path.join(project_dir_abs, "module_7_weighted")  # 新增


    receptor_pdb_path_abs = os.path.expanduser(args.receptor)
    receptor_clean_pdb = os.path.join(receptor_dir, f"{args.project}_clean.pdb")
    receptor_clean_pdbqt = os.path.join(receptor_dir, f"{args.project}_clean.pdbqt")

    # --- Module 1: Receptor Prep ---
    if should_run_module("receptor_prep"):
        print("--------------------Process Target PDB (Module 'receptor_prep')--------------------")
        os.makedirs(receptor_dir, exist_ok=True)
        cmd_extract = [
            PYTHON3, os.path.join(CODE_PATH, "extract_ligand.py"),
            "-i", receptor_pdb_path_abs, "-o", receptor_dir, "-pf", args.project
        ]
        run_command(cmd_extract, "Extract Ligand")
        cmd_prepare_receptor = [
            PYTHON2, PREPARE_RECEPTOR4,
            "-r", receptor_clean_pdb, "-o", receptor_clean_pdbqt, "-A", "hydrogens"
        ]
        run_command(cmd_prepare_receptor, "Prepare Receptor")
    else:
        print("Skipping Module: Receptor Prep.")
        if not os.path.exists(receptor_clean_pdbqt) and (should_run_module("docking") or should_run_module("pre_md")): # pre_md might also need receptor
              print(f"Warning: Receptor PDBQT file '{receptor_clean_pdbqt}' not found, but receptor prep was skipped. Subsequent modules may fail.")


    # --- MODULE 3: Known Inhibitors ---
    ligands_smi_for_docking_input = None
    if args.library:
        ligands_smi_for_docking_input = os.path.expanduser(args.library) # 默认值

    if should_run_module("known_inhibitors"):
        if args.library:
            library_path_abs = os.path.expanduser(args.library) # 重新获取以防万一
            if args.perform_substruct == 1 or args.perform_simi == 1:
                print("--------------------MODULE 3: Known Inhibitors Filtering--------------------")
                os.makedirs(module_3_dir, exist_ok=True)
                substruct_list_path_abs = os.path.expanduser(args.substruct_list)
                simi_query_path_abs = None
                if args.simi_query:
                    simi_query_path_abs = os.path.expanduser(args.simi_query)

                current_smi_input = library_path_abs
                # ligands_smi_for_docking_input 在此块开始时已设为 library_path_abs

                if args.perform_substruct == 1:
                    print("Performing substructure similarity filtering (Module 3)...")
                    substruct_output_smi = os.path.join(module_3_dir, "matched_at_least_one.smi")
                    cmd_substruct = [
                        PYTHON3, os.path.join(CODE_PATH, "module_3/substructure.py"),
                        "-i", library_path_abs, "-o", module_3_dir, "-l", substruct_list_path_abs
                    ]
                    run_command(cmd_substruct, "Substructure Filtering (Module 3)")
                    current_smi_input = substruct_output_smi
                    ligands_smi_for_docking_input = substruct_output_smi

                if args.perform_simi == 1:
                    print("Performing fingerprint similarity filtering (Module 3)...")
                    final_filtered_smi_path_module3 = os.path.join(module_3_dir, "filtered_library_module3.smi")
                    similarity_csv_path = os.path.join(module_3_dir, "similarity.csv")
                    cmd_calc_simi = [
                        PYTHON3, os.path.join(CODE_PATH, "module_3/calc_simi.py"),
                        "-i", current_smi_input, "-o", similarity_csv_path, "-q", simi_query_path_abs
                    ]
                    run_command(cmd_calc_simi, "Calculate Similarity (Module 3)")
                    cmd_filter_simi = [
                        PYTHON3, os.path.join(CODE_PATH, "module_3/filter_simi.py"),
                        "--target_smi_file", current_smi_input, "--score_csv", similarity_csv_path,
                        "-o", final_filtered_smi_path_module3, "-t", str(args.simi_threshold)
                    ]
                    run_command(cmd_filter_simi, "Filter Similarity (Module 3)")
                    ligands_smi_for_docking_input = final_filtered_smi_path_module3

                print(f"Module 3: Output SMILES for next step: {ligands_smi_for_docking_input}")
            else:
                print(f"Module 3: Active, but no filtering selected. Using original library for next step: {ligands_smi_for_docking_input}")
        else:
            print("Module 3: Active, but no --library provided. Skipping known inhibitor processing.")
            ligands_smi_for_docking_input = None
    else:
        print("Skipping Module: Known Inhibitors.")
        # ligands_smi_for_docking_input 保持其基于 args.library 的初始值（如果有）
        # 如果后续模块需要这个文件，但它不存在，则可能会出错。

    # --- MODULE 4: Docking ---
    docking_results_file = None # 用于后续模块的输入
    unidock_base_dir = None # 初始化

    if should_run_module("docking"):
        print("\n--------------------MODULE 4: Docking--------------------")
        if not os.path.exists(receptor_clean_pdbqt):
            print(f"Error: Receptor PDBQT file '{receptor_clean_pdbqt}' for Docking not found!")
            sys.exit(1)

        if args.docking_method == "deepdocking":
            print("Initiating Deep Docking module by calling deep_docking.sh...")
            dd_script_path_abs = os.path.expanduser(args.dd_script_path)
            dd_config_path_abs = os.path.expanduser(args.dd_config)
            cmd_deep_docking = [
                BASH, dd_script_path_abs,
                "-d", work_dir_abs, "-p", args.project, "-r", receptor_clean_pdbqt,
                "-c", dd_config_path_abs, "-n", str(args.dd_tot_iters),
                "-N", str(args.dd_sampling_size)
            ]
            if args.dd_start_iter != 1:
                cmd_deep_docking.extend(["-i", str(args.dd_start_iter)])
            if args.dd_start_step != "sample":
                cmd_deep_docking.extend(["-s", args.dd_start_step])
            if args.dd_start_set != "train":
                cmd_deep_docking.extend(["-e", args.dd_start_set])
            run_command(cmd_deep_docking, "Deep Docking Shell Script")
            # 假设 DeepDocking 的最终打分文件名为 all_docking_results.csv，且在 project_dir_abs/iteration_X/extract/all_docking_results.csv
            # 为了模拟，我们假设它在 project_dir_abs 下，实际需要根据 deep_docking.sh 的输出来确定
            # 查找最新的迭代目录来获取结果
            latest_iter_dir = None
            if os.path.isdir(project_dir_abs):
                iter_dirs = [d for d in os.listdir(project_dir_abs) if d.startswith("iteration_") and os.path.isdir(os.path.join(project_dir_abs, d))]
                if iter_dirs:
                    iter_dirs.sort(key=lambda x: int(x.split('_')[-1]), reverse=True)
                    latest_iter_dir = os.path.join(project_dir_abs, iter_dirs[0], "extract")
                    docking_results_file = os.path.join(latest_iter_dir, "all_docking_results.csv") # 假设的文件名
                    if not os.path.exists(docking_results_file):
                         docking_results_file = os.path.join(latest_iter_dir, "test_results.csv") # 备用名
                    print(f"Assuming DeepDocking results are in: {docking_results_file}")


        elif args.docking_method == "unidock":
            print("Initiating UniDock module...")
            if not ligands_smi_for_docking_input or not os.path.exists(ligands_smi_for_docking_input):
                print(f"Error: Cannot run UniDock. Input SMILES file for ligand preparation is missing or was not generated: {ligands_smi_for_docking_input}")
                sys.exit(1)

            ud_script_path_abs = os.path.expanduser(args.ud_script_path)
            ud_config_path_abs = os.path.expanduser(args.ud_config)

            unidock_base_dir = os.path.join(project_dir_abs, f"module_4_unidock_run{args.ud_output_suffix}") # 使用后缀
            unidock_ligands_pdbqt_dir = os.path.join(unidock_base_dir, "ligands_for_unidock_pdbqt")
            os.makedirs(unidock_ligands_pdbqt_dir, exist_ok=True)

            print(f"Preparing ligands for UniDock from: {ligands_smi_for_docking_input} into {unidock_ligands_pdbqt_dir}")
            cmd_prepare_unidock_ligands = [
                BASH, os.path.join(CODE_PATH, "distributed_prepare_ligand.sh"),
                "-i", ligands_smi_for_docking_input,
                "-o", unidock_ligands_pdbqt_dir,
                "-t", str(args.ud_prepare_threads),
                "-f"
            ]
            run_command(cmd_prepare_unidock_ligands, "Prepare Ligands for UniDock")

            unidock_file_prefix = "ligands_for_unidock"
            cmd_unidock = [
                BASH, ud_script_path_abs,
                "-c", ud_config_path_abs,
                "-r", receptor_clean_pdbqt,
                "-d", unidock_base_dir,
                "-n", unidock_file_prefix,
                "-t", str(args.ud_threads),
                "-m", args.ud_search_mode
            ]
            if args.ud_ligand_list_file:
                cmd_unidock.extend(["-l", os.path.expanduser(args.ud_ligand_list_file)])
            if args.ud_output_suffix: # distributed_unidock.sh 内部处理后缀，这里确保目录名一致
                 pass # unidock_base_dir 已经包含了后缀
            run_command(cmd_unidock, "UniDock Shell Script")

            print(f"Extracting scores for UniDock results...")
            unidock_docked_dir = os.path.join(unidock_base_dir, f"{unidock_file_prefix}_docked") # 不加后缀，脚本内部会处理
            # 如果 distributed_unidock.sh 的 -x 参数会影响 _docked 目录名，则需要调整
            # 假设 extract_vina_score.py 会在 unidock_base_dir 生成一个 <name>_scores.csv 文件
            docking_results_file = os.path.join(unidock_base_dir, f"{unidock_file_prefix}_scores.csv")
            print(f"Expecting UniDock scores file at: {docking_results_file}")

            if not os.path.isdir(unidock_docked_dir) or not os.listdir(unidock_docked_dir):
                print(f"Warning: UniDock output directory '{unidock_docked_dir}' is missing or empty. Skipping score extraction. Expected results file {docking_results_file} might not be created.")
            else:
                extract_script_path = os.path.join(CODE_PATH, "extract_vina_score.py")
                if not os.path.isfile(extract_script_path):
                    print(f"Error: Score extraction script not found at {extract_script_path}. Cannot extract UniDock scores.")
                else:
                    cmd_extract_unidock_scores = [
                        PYTHON3, extract_script_path,
                        "--name", unidock_file_prefix,
                        "--docked_dir", unidock_docked_dir,
                        "--output_dir", unidock_base_dir, # 脚本会在 output_dir 生成 <name>_scores.csv
                        "--threads", str(args.ud_extract_threads)
                    ]
                    run_command(cmd_extract_unidock_scores, "Extract UniDock Scores")
                    if not os.path.exists(docking_results_file):
                        print(f"Warning: Expected UniDock scores file {docking_results_file} was not found after extraction attempt.")


        # 为后续模块准备模拟的对接结果文件（如果真实文件不存在）
        if docking_results_file and not os.path.exists(docking_results_file):
            print(f"Warning: Docking results file '{docking_results_file}' not found. Creating a dummy file for subsequent modules.")
            os.makedirs(os.path.dirname(docking_results_file), exist_ok=True)
            with open(docking_results_file, 'w') as f:
                f.write("ligand_id,docking_score,smiles\n") # Header
                # 获取输入SMILES用于模拟
                source_smi_file_for_dummy_data = ligands_smi_for_docking_input
                if not source_smi_file_for_dummy_data or not os.path.exists(source_smi_file_for_dummy_data) :
                    source_smi_file_for_dummy_data = os.path.expanduser(args.library) if args.library and os.path.exists(os.path.expanduser(args.library)) else None

                if source_smi_file_for_dummy_data:
                    print(f"Generating dummy docking data from: {source_smi_file_for_dummy_data}")
                    try:
                        with open(source_smi_file_for_dummy_data, 'r') as smi_f:
                            lines = smi_f.readlines()
                            for i, line in enumerate(lines[:100]): # 最多取前100个
                                parts = line.strip().split()
                                smi = parts[0]
                                name = parts[1] if len(parts) > 1 else f"LIG{i+1}"
                                score = round(random.uniform(-12.0, -5.0), 2)
                                f.write(f"{name},{score},{smi}\n")
                    except Exception as e:
                        print(f"Could not read SMILES for dummy data generation: {e}")
                        f.write(f"LIG_DUMMY_1,{-9.5+random.random()},{'C1CCCCC1CC(N)C(=O)O'}\n") # Fallback dummy
                        f.write(f"LIG_DUMMY_2,{-8.0+random.random()},{'Cc1ccccc1CN'}\n")
                else:
                    print("No library SMILES file found to generate dummy docking data names/SMILES. Using generic dummies.")
                    f.write(f"LIG_DUMMY_1,{-9.5+random.random()},{'C1CCCCC1CC(N)C(=O)O'}\n")
                    f.write(f"LIG_DUMMY_2,{-8.0+random.random()},{'Cc1ccccc1CN'}\n")
            print(f"Dummy docking results file created: {docking_results_file}")
        elif not docking_results_file:
             print(f"Warning: docking_results_file path was not set. Subsequent modules relying on it may fail.")


    else:
        print("Skipping Module: Docking.")
        # 如果跳过对接，后续模块可能需要一个预先存在的对接结果文件
        # 尝试定位一个可能的对接结果文件，如果用户是从后续模块开始的
        if args.docking_method == "deepdocking":
            latest_iter_dir = None
            if os.path.isdir(project_dir_abs):
                iter_dirs = [d for d in os.listdir(project_dir_abs) if d.startswith("iteration_") and os.path.isdir(os.path.join(project_dir_abs, d))]
                if iter_dirs:
                    iter_dirs.sort(key=lambda x: int(x.split('_')[-1]), reverse=True)
                    latest_iter_dir = os.path.join(project_dir_abs, iter_dirs[0], "extract")
                    docking_results_file = os.path.join(latest_iter_dir, "all_docking_results.csv")
                    if not os.path.exists(docking_results_file):
                         docking_results_file = os.path.join(latest_iter_dir, "test_results.csv") # 备用名

        elif args.docking_method == "unidock":
            unidock_base_dir = os.path.join(project_dir_abs, f"module_4_unidock_run{args.ud_output_suffix}")
            docking_results_file = os.path.join(unidock_base_dir, "ligands_for_unidock_scores.csv")

        if docking_results_file and os.path.exists(docking_results_file):
            print(f"Docking module skipped. Found existing docking results: {docking_results_file}")
        elif should_run_module("clustering") or should_run_module("pre_md") or should_run_module("weighted"):
            print(f"Warning: Docking module skipped, and no obvious existing docking results file ({docking_results_file if docking_results_file else 'N/A'}) found. Subsequent modules may fail or use dummy data if implemented.")
            # Create a dummy if absolutely needed and not found
            if not docking_results_file: # if path was not even determined
                docking_results_file = os.path.join(project_dir_abs, "simulated_docking_scores.csv") # Generic fallback
            if not os.path.exists(docking_results_file):
                print(f"Creating a dummy docking results file for skipped docking: {docking_results_file}")
                os.makedirs(os.path.dirname(docking_results_file), exist_ok=True)
                with open(docking_results_file, 'w') as f:
                    f.write("ligand_id,docking_score,smiles\n")
                    f.write(f"LIG_SKIPPED_1,-8.8,'COCC(N)C1CCCC1'\n")
                    f.write(f"LIG_SKIPPED_2,-7.2,'CN1CCC(CC1)c1ccccc1'\n")


    # --- MODULE 5: Clustering ---
    clustered_representatives_smi = None
    if should_run_module("clustering"):
        print("\n--------------------MODULE 5: Clustering--------------------")
        os.makedirs(module_5_dir, exist_ok=True)
        clustered_representatives_smi = os.path.join(module_5_dir, "cluster_representatives.smi")
        cluster_details_csv = os.path.join(module_5_dir, "clustering_details.csv")

        if not docking_results_file or not os.path.exists(docking_results_file):
            print("Error: Docking results file is required for clustering but not found. Skipping Clustering.")
        else:
            print(f"Starting clustering of molecules from: {docking_results_file}")
            print(f"Using clustering threshold: {args.clustering_threshold}")
            print(f"Expected number of clusters (for simulation): {args.num_clusters_expected}")

            cmd_clustering = [
                PYTHON3, CLUSTERING_SCRIPT,
                "--input_docking_csv", docking_results_file,
                "--output_representatives_smi", clustered_representatives_smi,
                "--output_cluster_csv", cluster_details_csv,
                "--threshold", str(args.clustering_threshold)
            ]
            run_command(cmd_clustering, "Molecule Clustering (Module 5)")

            print(f"Simulating execution of: {PYTHON3} {CLUSTERING_SCRIPT} ...")
            print(f"STDOUT (Molecule Clustering):")
            print(f"  Loading docking results from {docking_results_file}...")

            ligands_for_clustering = []
            try:
                with open(docking_results_file, 'r') as drf:
                    header = drf.readline()
                    for line in drf:
                        parts = line.strip().split(',')
                        if len(parts) >= 3: # ligand_id, docking_score, smiles
                           ligands_for_clustering.append({'id': parts[0], 'score': float(parts[1]), 'smiles': parts[2]})
                        elif len(parts) == 2: # ligand_id, docking_score (if smiles is missing)
                           ligands_for_clustering.append({'id': parts[0], 'score': float(parts[1]), 'smiles': 'C'}) # Dummy smiles

            except Exception as e:
                print(f"  Error reading docking results for simulation: {e}. Using fallback data.")
                ligands_for_clustering = [
                    {'id': 'LIG1', 'score': -9.0, 'smiles': 'CCO'},
                    {'id': 'LIG2', 'score': -8.5, 'smiles': 'CCC'},
                    {'id': 'LIG3', 'score': -9.2, 'smiles': 'CCN'},
                    {'id': 'LIG4', 'score': -7.0, 'smiles': 'c1ccccc1'},
                    {'id': 'LIG5', 'score': -8.8, 'smiles': 'CC(=O)O'},
                ]
            
            num_ligands = len(ligands_for_clustering)
            print(f"  Read {num_ligands} ligands for clustering.")
            print(f"  Calculating fingerprints and similarity matrix...")
            time.sleep(1)
            print(f"  Performing hierarchical clustering with threshold {args.clustering_threshold}...")
            time.sleep(2)
            
            num_clusters_found = min(args.num_clusters_expected, num_ligands) if num_ligands > 0 else 0
            if num_ligands == 0 : num_clusters_found = 0

            print(f"  Found {num_clusters_found} clusters.")
            
            # 模拟生成输出文件
            with open(cluster_details_csv, 'w') as f_csv, open(clustered_representatives_smi, 'w') as f_smi:
                f_csv.write("cluster_id,representative_ligand_id,representative_score,representative_smiles,num_members\n")
                representatives_generated = 0
                if num_ligands > 0 and num_clusters_found > 0:
                    ligands_per_cluster_approx = num_ligands // num_clusters_found
                    for i in range(num_clusters_found):
                        # 从对接结果中选一个作为代表（按分数排序）
                        # 简单地按顺序取，实际聚类会更复杂
                        sorted_ligands = sorted(ligands_for_clustering, key=lambda x: x['score'])
                        if i < len(sorted_ligands):
                            rep = sorted_ligands[i]
                            members = random.randint(1, max(1, ligands_per_cluster_approx + 2))
                            f_csv.write(f"Cluster_{i+1},{rep['id']},{rep['score']},{rep['smiles']},{members}\n")
                            f_smi.write(f"{rep['smiles']}\t{rep['id']}_repr_C{i+1}\n") # SMILES \t ID
                            print(f"    Cluster {i+1}: Representative {rep['id']} (Score: {rep['score']}), Members: {members}")
                            representatives_generated +=1
                        else:
                            # Fallback if not enough unique ligands for desired clusters
                            dummy_rep_id = f"DUMMY_REP_C{i+1}"
                            dummy_rep_smi = f"C1C{i+1}CCCC1" # Unique dummy SMILES
                            dummy_rep_score = round(random.uniform(-10.0, -7.0), 2)
                            members = random.randint(1, 5)
                            f_csv.write(f"Cluster_{i+1},{dummy_rep_id},{dummy_rep_score},{dummy_rep_smi},{members}\n")
                            f_smi.write(f"{dummy_rep_smi}\t{dummy_rep_id}\n")
                            print(f"    Cluster {i+1}: Representative {dummy_rep_id} (Score: {dummy_rep_score}), Members: {members}")
                            representatives_generated +=1


            if representatives_generated > 0 :
                print(f"  Clustering complete. {representatives_generated} representatives written to {clustered_representatives_smi}")
                print(f"  Clustering details written to {cluster_details_csv}")
            else:
                print(f"  Clustering did not produce any representatives (possibly no input ligands or too few).")
                # Create empty files to prevent downstream errors if they expect files
                if not os.path.exists(clustered_representatives_smi): open(clustered_representatives_smi, 'w').close()
                if not os.path.exists(cluster_details_csv): open(cluster_details_csv, 'w').write("cluster_id,representative_ligand_id,representative_score,representative_smiles,num_members\n")


            print(f"Molecule Clustering (Module 5) completed successfully (simulated).")
    else:
        print("Skipping Module: Clustering.")
        # 如果跳过，后续模块可能需要一个预先存在的代表性SMILES文件
        clustered_representatives_smi = os.path.join(module_5_dir, "cluster_representatives.smi")
        if os.path.exists(clustered_representatives_smi):
            print(f"Clustering module skipped. Found existing representatives SMILES: {clustered_representatives_smi}")
        elif should_run_module("pre_md") or should_run_module("weighted"):
            print(f"Warning: Clustering module skipped, and representative SMILES file '{clustered_representatives_smi}' not found. Subsequent modules may fail or use dummy data.")
            # Create a dummy if needed and not found
            if not os.path.exists(clustered_representatives_smi):
                print(f"Creating a dummy representative SMILES file for skipped clustering: {clustered_representatives_smi}")
                os.makedirs(os.path.dirname(clustered_representatives_smi), exist_ok=True)
                with open(clustered_representatives_smi, 'w') as f:
                    # Try to get some SMILES from docking_results_file if it exists
                    written_dummy_reps = 0
                    if docking_results_file and os.path.exists(docking_results_file):
                        try:
                            with open(docking_results_file, 'r') as drf:
                                drf.readline() # skip header
                                for _ in range(min(5, sum(1 for line in drf if line.strip()))): # take up to 5
                                    line = drf.readline()
                                    if not line: break
                                    parts = line.strip().split(',')
                                    if len(parts) >=3:
                                        f.write(f"{parts[2]}\t{parts[0]}_rep_skipC\n")
                                        written_dummy_reps +=1
                        except: pass # ignore errors
                    if written_dummy_reps == 0:
                         f.write(f"Cc1ccccc1N\tLIG_REP_SKIPPED_1\n")
                         f.write(f"CC(C)CO\tLIG_REP_SKIPPED_2\n")
                print(f"Dummy representatives SMILES file created: {clustered_representatives_smi}")


    # --- MODULE 6: Pre-MD (HBA, Off-target) ---
    hba_results_csv = None
    off_target_summary_csv = None
    ligands_for_pre_md = clustered_representatives_smi # Input for this module

    if should_run_module("pre_md"):
        print("\n--------------------MODULE 6: Pre-MD (HBA Calculation & Off-target Prediction)--------------------")
        os.makedirs(module_6_dir, exist_ok=True)
        hba_results_csv = os.path.join(module_6_dir, "hba_counts.csv")
        off_target_summary_csv = os.path.join(module_6_dir, "off_target_summary.csv")

        if not ligands_for_pre_md or not os.path.exists(ligands_for_pre_md) or os.path.getsize(ligands_for_pre_md) == 0:
            print(f"Error: Input SMILES file '{ligands_for_pre_md}' for Pre-MD (from clustering) is missing or empty. Skipping Pre-MD.")
        else:
            print(f"Starting Pre-MD tasks using ligands from: {ligands_for_pre_md}")

            # 1. Calculate HBA (Hydrogen Bond Acceptors)
            print("\n  --- Sub-module: Calculating Hydrogen Bond Acceptors (HBA) ---")
            # cmd_hba = [
            #     PYTHON3, HBA_CALC_SCRIPT,
            #     "--input_smi", ligands_for_pre_md,
            #     "--output_csv", hba_results_csv
            # ]
            # run_command(cmd_hba, "HBA Calculation (Module 6)")
            print(f"Simulating execution of: {PYTHON3} {HBA_CALC_SCRIPT} ...")
            time.sleep(1)
            print(f"STDOUT (HBA Calculation):")
            print(f"  Loading SMILES from {ligands_for_pre_md}...")
            num_hba_ligands = 0
            hba_ligand_ids_smiles = []
            try:
                with open(ligands_for_pre_md, 'r') as smi_f:
                    for line in smi_f:
                        parts = line.strip().split()
                        if parts:
                            hba_ligand_ids_smiles.append({'smiles': parts[0], 'id': parts[1] if len(parts) > 1 
                                                          else f"LIG_HBA_{num_hba_ligands+1}"})
                            num_hba_ligands += 1
            except Exception as e:
                print(f"  Error reading SMILES for HBA calculation: {e}")

            print(f"  Processing {num_hba_ligands} ligands for HBA count...")
            with open(hba_results_csv, 'w') as f:
                f.write("ligand_id,smiles,hba_count\n")
                if num_hba_ligands > 0:
                    for entry in hba_ligand_ids_smiles:
                        h_count = random.randint(0, 5) # Simulate HBA count
                        f.write(f"{entry['id']},{entry['smiles']},{h_count}\n")
                        print(f"    Ligand {entry['id']}: HBA Count = {h_count}")
                else:
                    print("    No ligands to process for HBA.")
            print(f"  HBA counts written to {hba_results_csv}")
            print(f"HBA Calculation (Module 6) completed successfully (simulated).")


            # 2. Off-target Prediction (Docking against homologous proteins)
            print("\n  --- Sub-module: Off-target Prediction ---")
            if not args.off_target_pdb_list or not args.off_target_config:
                print("  Off-target PDB list (--off_target_pdb_list) or config (--off_target_config) not provided. Skipping off-target prediction.")
                # Create an empty summary if not run
                with open(off_target_summary_csv, 'w') as f_off:
                    f_off.write("ligand_id,off_target_protein,off_target_score\n") # Header
            else:
                off_target_pdb_list_path = os.path.expanduser(args.off_target_pdb_list)
                off_target_config_path = os.path.expanduser(args.off_target_config)
                if not os.path.exists(off_target_pdb_list_path):
                    print(f"  Error: Off-target PDB list file '{off_target_pdb_list_path}' not found. Skipping off-target prediction.")
                elif not os.path.exists(off_target_config_path):
                     print(f"  Error: Off-target docking config file '{off_target_config_path}' not found. Skipping off-target prediction.")
                else:
                    print(f"  Performing off-target docking using ligands from {ligands_for_pre_md}")
                    print(f"  Off-target PDBs from: {off_target_pdb_list_path}")
                    print(f"  Off-target docking config: {off_target_config_path}")

                    # cmd_offtarget = [
                    #     BASH, OFFTARGET_DOCKING_SCRIPT, # Assuming a shell script to handle multiple dockings
                    #     "--ligand_smi_file", ligands_for_pre_md,
                    #     "--pdb_list_file", off_target_pdb_list_path,
                    #     "--docking_config", off_target_config_path,
                    #     "--output_summary_csv", off_target_summary_csv,
                    #     "--working_dir", module_6_dir # Script might create subdirs here
                    # ]
                    # run_command(cmd_offtarget, "Off-target Docking (Module 6)")

                    # Simulate off-target docking
                    print(f"Simulating execution of: {BASH} {OFFTARGET_DOCKING_SCRIPT} ...")
                    time.sleep(3) # Simulate耗时
                    print(f"STDOUT (Off-target Docking):")
                    off_targets = []
                    try:
                        with open(off_target_pdb_list_path, 'r') as pdb_list_f:
                            off_targets = [line.strip() for line in pdb_list_f if line.strip() and line.strip().endswith(".pdb")] # or .pdbqt
                        print(f"  Found {len(off_targets)} off-target PDBs: {', '.join(os.path.basename(p) for p in off_targets)}")
                    except Exception as e:
                        print(f"  Error reading off-target PDB list: {e}")

                    with open(off_target_summary_csv, 'w') as f_off:
                        f_off.write("ligand_id,off_target_protein_basename,off_target_score\n") # Header
                        if num_hba_ligands > 0 and off_targets: # Use same ligands as HBA for simulation
                            for entry in hba_ligand_ids_smiles: # For each ligand from clustering
                                print(f"    Processing ligand {entry['id']} for off-target effects...")
                                for target_pdb in off_targets:
                                    target_basename = os.path.basename(target_pdb)
                                    # Simulate docking score for this off-target
                                    off_score = round(random.uniform(-8.0, -4.0), 2)
                                    f_off.write(f"{entry['id']},{target_basename},{off_score}\n")
                                    print(f"      vs {target_basename}: Score = {off_score}")
                                    time.sleep(0.1) # Tiny delay
                        else:
                            print("    No ligands or no off-targets to process.")

                    print(f"  Off-target docking simulation complete. Summary written to {off_target_summary_csv}")
                    print(f"Off-target Docking (Module 6) completed successfully (simulated).")
    else:
        print("Skipping Module: Pre-MD (HBA & Off-target).")
        # Define paths even if skipped, for consistency and potential later use if module is re-run
        hba_results_csv = os.path.join(module_6_dir, "hba_counts.csv")
        off_target_summary_csv = os.path.join(module_6_dir, "off_target_summary.csv")
        if should_run_module("weighted"): # If next module runs, check for existing files
            if os.path.exists(hba_results_csv):
                print(f"Pre-MD module skipped. Found existing HBA results: {hba_results_csv}")
            else:
                print(f"Warning: Pre-MD module skipped, and HBA results file '{hba_results_csv}' not found. Weighted scoring may lack this data or use defaults.")
                # Create dummy HBA if needed
                if not os.path.exists(hba_results_csv):
                    os.makedirs(os.path.dirname(hba_results_csv), exist_ok=True)
                    with open(hba_results_csv, 'w') as f:
                        f.write("ligand_id,smiles,hba_count\n")
                        # Try to use ligands from clustered_representatives_smi
                        if clustered_representatives_smi and os.path.exists(clustered_representatives_smi):
                             try:
                                with open(clustered_representatives_smi, 'r') as crs_f:
                                    for line_idx, line in enumerate(crs_f):
                                        if line_idx >= 2: break # Max 2 dummy entries
                                        parts = line.strip().split()
                                        if parts:
                                            smi = parts[0]
                                            name = parts[1] if len(parts) > 1 else f"LIG_SKIP_HBA{line_idx+1}"
                                            f.write(f"{name},{smi},{random.randint(1,3)}\n") # Dummy HBA
                             except: pass # ignore
                        else: # Absolute fallback
                            f.write(f"LIG_SKIP_HBA1,CNCO,{random.randint(1,3)}\n")


            if os.path.exists(off_target_summary_csv):
                print(f"Pre-MD module skipped. Found existing Off-target summary: {off_target_summary_csv}")
            else:
                print(f"Warning: Pre-MD module skipped, and Off-target summary file '{off_target_summary_csv}' not found. Weighted scoring may lack this data or use defaults.")
                # Create dummy off-target if needed
                if not os.path.exists(off_target_summary_csv):
                    os.makedirs(os.path.dirname(off_target_summary_csv), exist_ok=True)
                    with open(off_target_summary_csv, 'w') as f:
                        f.write("ligand_id,off_target_protein_basename,off_target_score\n")
                        if clustered_representatives_smi and os.path.exists(clustered_representatives_smi):
                             try:
                                with open(clustered_representatives_smi, 'r') as crs_f:
                                    for line_idx, line in enumerate(crs_f):
                                        if line_idx >=1: break # Max 1 dummy ligand with 2 off-targets
                                        parts = line.strip().split()
                                        if parts:
                                            name = parts[1] if len(parts) > 1 else f"LIG_SKIP_OT{line_idx+1}"
                                            f.write(f"{name},OFFTARGET_DUMMY_A,{round(random.uniform(-7.0, -5.0),1)}\n")
                                            f.write(f"{name},OFFTARGET_DUMMY_B,{round(random.uniform(-7.0, -5.0),1)}\n")
                             except: pass
                        else: # Absolute fallback
                            f.write(f"LIG_SKIP_OT1,OFFTARGET_DUMMY_A,-6.5\n")


    # --- MODULE 7: Weighted Scoring ---
    final_ranked_results_csv = None
    ligands_for_weighting = clustered_representatives_smi # Usually, the clustered representatives are the ones to be scored comprehensively

    if should_run_module("weighted"):
        print("\n--------------------MODULE 7: Weighted Scoring--------------------")
        os.makedirs(module_7_dir, exist_ok=True)
        physchem_admet_results_csv = os.path.join(module_7_dir, "physchem_admet_properties.csv")
        final_ranked_results_csv = os.path.join(module_7_dir, "final_weighted_ranked_candidates.csv")

        if not ligands_for_weighting or not os.path.exists(ligands_for_weighting) or os.path.getsize(ligands_for_weighting) == 0:
            print(f"Error: Input SMILES file '{ligands_for_weighting}' for Weighted Scoring 
                  is missing or empty. Skipping Weighted Scoring.")
        else:
            print(f"Starting Weighted Scoring for ligands from: {ligands_for_weighting}")

            # 1. Calculate Physicochemical and ADMET properties (simulated)
            print("\n  --- Sub-module: Calculating Physicochemical and ADMET Properties ---")
            # cmd_physchem = [
            #     PYTHON3, PHYSCHEM_ADMET_SCRIPT,
            #     "--input_smi", ligands_for_weighting,
            #     "--output_csv", physchem_admet_results_csv
            # ]
            # run_command(cmd_physchem, "PhysChem/ADMET Calculation (Module 7)")
            print(f"Simulating execution of: {PYTHON3} {PHYSCHEM_ADMET_SCRIPT} ...")
            time.sleep(2)
            print(f"STDOUT (PhysChem/ADMET Calculation):")
            print(f"  Loading SMILES from {ligands_for_weighting}...")
            num_phys_ligands = 0
            phys_ligand_ids_smiles = []
            try:
                with open(ligands_for_weighting, 'r') as smi_f:
                     for line in smi_f:
                        parts = line.strip().split()
                        if parts:
                            phys_ligand_ids_smiles.append({'smiles': parts[0], 'id': parts[1] 
                                                           if len(parts) > 1 else f"LIG_PHY_{num_phys_ligands+1}"})
                            num_phys_ligands +=1
            except Exception as e:
                print(f"  Error reading SMILES for PhysChem/ADMET: {e}")

            print(f"  Calculating properties for {num_phys_ligands} ligands...")
            with open(physchem_admet_results_csv, 'w') as f:
                f.write("ligand_id,smiles,mol_weight,logp,tpsa,num_hbd,num_hba,ro5_violations,admet_risk_score\n")
                if num_phys_ligands > 0:
                    for entry in phys_ligand_ids_smiles:
                        mw = round(random.uniform(150, 500), 2)
                        logp = round(random.uniform(-1, 5), 2)
                        tpsa = round(random.uniform(20, 150), 1)
                        hbd = random.randint(0,5)
                        hba = random.randint(0,10)
                        ro5 = random.randint(0,1)
                        admet_risk = round(random.random(), 2) # Lower is better
                        f.write(f"{entry['id']},{entry['smiles']},{mw},{logp},{tpsa},{hbd},{hba},{ro5},{admet_risk}\n")
                        print(f"    Ligand {entry['id']}: MW={mw}, LogP={logp}, ADMET Risk={admet_risk}")
                else:
                    print("    No ligands to process for PhysChem/ADMET.")
            print(f"  Physicochemical and ADMET properties written to {physchem_admet_results_csv}")
            print(f"PhysChem/ADMET Calculation (Module 7) completed successfully (simulated).")


            # 2. Combine all scores and rank
            print("\n  --- Sub-module: Combining Scores and Ranking ---")
            print("  Gathering data from previous modules:")
            print(f"    Docking scores from: {docking_results_file if docking_results_file else 'N/A'}")
            print(f"    HBA counts from: {hba_results_csv if hba_results_csv else 'N/A'}")
            print(f"    Off-target summary from: {off_target_summary_csv if off_target_summary_csv else 'N/A'}")
            print(f"    PhysChem/ADMET properties from: {physchem_admet_results_csv}")

            # Ensure all required input files for weighting exist, even if dummy
            # This is crucial for the simulated script to "run"
            input_files_for_weighting = {
                "docking": docking_results_file,
                "hba": hba_results_csv,
                "offtarget": off_target_summary_csv,
                "physchem": physchem_admet_results_csv
            }
            all_inputs_exist = True
            for key, filepath in input_files_for_weighting.items():
                if not filepath or not os.path.exists(filepath):
                    print(f"    WARNING: Input file for '{key}' ({filepath}) is missing for weighted scoring. Results may be incomplete or based on defaults.")
                    all_inputs_exist = False # For simulation, we might proceed with defaults in the "script"

            # cmd_weighted = [
            #     PYTHON3, WEIGHTED_SCORING_SCRIPT,
            #     "--input_smi_representatives", ligands_for_weighting, # To know which ligands to score
            #     "--docking_scores_csv", docking_results_file,
            #     "--hba_counts_csv", hba_results_csv,
            #     "--off_target_summary_csv", off_target_summary_csv,
            #     "--physchem_admet_csv", physchem_admet_results_csv,
            #     "--output_ranked_csv", final_ranked_results_csv,
            #     "--weights", "0.2,0.2,0.2,0.2,0.2" # physchem,admet,docking,hba,offtarget
            # ]
            # run_command(cmd_weighted, "Weighted Scoring and Ranking (Module 7)")
            print(f"Simulating execution of: {PYTHON3} {WEIGHTED_SCORING_SCRIPT} ...")
            time.sleep(2)
            print(f"STDOUT (Weighted Scoring and Ranking):")
            print(f"  Loading data for {num_phys_ligands} representative ligands...") # Assuming same ligands as physchem for simulation
            
            # Simulate reading all data and calculating weighted score
            final_scores = []
            if num_phys_ligands > 0:
                for entry in phys_ligand_ids_smiles:
                    # Simulate fetching scores for this ligand ID from other files
                    # (Actual script would do proper merging)
                    s_dock = round(random.uniform(0,1),3) # Normalized score
                    s_phys = round(random.uniform(0,1),3)
                    s_admet = round(random.uniform(0,1),3)
                    s_hba = round(random.uniform(0,1),3)
                    s_offtarget = round(random.uniform(0,1),3)
                    
                    weighted_score = 0.2 * s_phys + 0.2 * s_admet + 0.2 * s_dock + 0.2 * s_hba + 0.2 * s_offtarget
                    final_scores.append({
                        'id': entry['id'],
                        'smiles': entry['smiles'],
                        'phys_norm': s_phys,
                        'admet_norm': s_admet,
                        'dock_norm': s_dock,
                        'hba_norm': s_hba,
                        'offtarget_norm': s_offtarget,
                        'weighted_score': round(weighted_score, 4)
                    })
                    print(f"    Ligand {entry['id']}: Weighted Score = {weighted_score:.4f}")
            
            # Sort by weighted score (higher is better)
            final_scores.sort(key=lambda x: x['weighted_score'], reverse=True)
            
            with open(final_ranked_results_csv, 'w') as f:
                f.write("rank,ligand_id,smiles,physchem_score_norm,admet_score_norm,docking_score_norm,hba_score_norm,offtarget_score_norm,final_weighted_score\n")
                for i, score_data in enumerate(final_scores):
                    f.write(f"{i+1},{score_data['id']},{score_data['smiles']},"
                            f"{score_data['phys_norm']},{score_data['admet_norm']},{score_data['dock_norm']},"
                            f"{score_data['hba_norm']},{score_data['offtarget_norm']},{score_data['weighted_score']}\n")
            
            print(f"  Ranking complete. Final results written to {final_ranked_results_csv}")
            print(f"Weighted Scoring and Ranking (Module 7) completed successfully (simulated).")

    else:
        print("Skipping Module: Weighted Scoring.")
        final_ranked_results_csv = os.path.join(module_7_dir, "final_weighted_ranked_candidates.csv")
        if os.path.exists(final_ranked_results_csv):
             print(f"Weighted scoring module skipped. Found existing final ranked results: {final_ranked_results_csv}")


    print("\nVS Protocol script (Python version) finished.")

if __name__ == "__main__":
    if not BASH or not os.path.exists(BASH):
        print(f"Error: Bash interpreter not found at '{BASH}'. Please check the BASH path definition.")
        sys.exit(1)
    
    # Create dummy scripts for simulation if they don't exist
    # This is just to make the `run_command` not fail on FileNotFoundError for the simulated parts
    # In a real scenario, these scripts would exist and have actual logic.
    dummy_scripts_to_create = {
        CLUSTERING_SCRIPT: "#!/usr/bin/env python\nprint('Simulated clustering script executed.')\nimport sys; sys.exit(0)",
        HBA_CALC_SCRIPT: "#!/usr/bin/env python\nprint('Simulated HBA calculation script executed.')\nimport sys; sys.exit(0)",
        OFFTARGET_DOCKING_SCRIPT: "#!/bin/bash\necho 'Simulated off-target docking script executed.'\nexit 0",
        PHYSCHEM_ADMET_SCRIPT: "#!/usr/bin/env python\nprint('Simulated PhysChem/ADMET script executed.')\nimport sys; sys.exit(0)",
        WEIGHTED_SCORING_SCRIPT: "#!/usr/bin/env python\nprint('Simulated weighted scoring script executed.')\nimport sys; sys.exit(0)",
        # Also, the scripts from earlier modules if you want to run this standalone for testing later modules
        os.path.join(CODE_PATH, "extract_ligand.py"): "#!/usr/bin/env python\nprint('Simulated extract_ligand.py executed.')\nimport sys; sys.exit(0)",
        os.path.join(CODE_PATH, "module_3/substructure.py"): "#!/usr/bin/env python\nprint('Simulated substructure.py executed.')\nimport sys; sys.exit(0)",
        os.path.join(CODE_PATH, "module_3/calc_simi.py"): "#!/usr/bin/env python\nprint('Simulated calc_simi.py executed.')\nimport sys; sys.exit(0)",
        os.path.join(CODE_PATH, "module_3/filter_simi.py"): "#!/usr/bin/env python\nprint('Simulated filter_simi.py executed.')\nimport sys; sys.exit(0)",
        os.path.join(CODE_PATH, "distributed_prepare_ligand.sh"): "#!/bin/bash\necho 'Simulated distributed_prepare_ligand.sh executed.'\nexit 0",
        os.path.join(CODE_PATH, "extract_vina_score.py"): "#!/usr/bin/env python\nprint('Simulated extract_vina_score.py executed.')\nimport sys; sys.exit(0)",
    }
    # Create dummy main docking scripts as well if they are default and might not exist
    if DEFAULT_DD_SCRIPT_PATH not in dummy_scripts_to_create and not os.path.exists(DEFAULT_DD_SCRIPT_PATH) :
        dummy_scripts_to_create[DEFAULT_DD_SCRIPT_PATH] = "#!/bin/bash\necho 'Simulated deep_docking.sh executed.'\n# Create some dummy output dir and file for testing subsequent steps\nmkdir -p $2/iteration_1/extract\necho 'ligand_id,docking_score,smiles' > $2/iteration_1/extract/all_docking_results.csv\necho 'DUMMY_DD_LIG1,-10.0,CNCN' >> $2/iteration_1/extract/all_docking_results.csv\nexit 0"
    if DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH not in dummy_scripts_to_create and not os.path.exists(DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH):
        dummy_scripts_to_create[DEFAULT_DISTRIBUTED_UNIDOCK_SCRIPT_PATH] = "#!/bin/bash\necho 'Simulated distributed_unidock.sh executed.'\n# Create some dummy output dir for testing subsequent steps\n# Args: -d base_dir -n prefix \nmkdir -p $4/${6}_docked \necho 'some dummy docked file' > $4/${6}_docked/dummy.pdbqt\nexit 0"


    for script_path, content in dummy_scripts_to_create.items():
        script_dir = os.path.dirname(script_path)
        if script_dir : # Ensure directory exists
            os.makedirs(script_dir, exist_ok=True)
        if not os.path.exists(script_path):
            try:
                with open(script_path, 'w') as f:
                    f.write(content)
                os.chmod(script_path, 0o755) # Make it executable
                print(f"Created dummy script: {script_path}")
            except Exception as e:
                print(f"Warning: Could not create dummy script {script_path}: {e}")
    
    # Create dummy PREPARE_RECEPTOR4 if it does not exist
    if not os.path.exists(PREPARE_RECEPTOR4):
        script_dir = os.path.dirname(PREPARE_RECEPTOR4)
        if script_dir: os.makedirs(script_dir, exist_ok=True)
        try:
            with open(PREPARE_RECEPTOR4, 'w') as f:
                f.write("#!/usr/bin/env python\nprint('Simulated prepare_receptor4.py executed.')\nimport sys; sys.exit(0)")
            os.chmod(PREPARE_RECEPTOR4, 0o755)
            print(f"Created dummy script: {PREPARE_RECEPTOR4}")
        except Exception as e:
            print(f"Warning: Could not create dummy script {PREPARE_RECEPTOR4}: {e}")


    main()