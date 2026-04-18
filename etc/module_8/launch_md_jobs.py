import pandas as pd
import os
import shutil
import pathlib
import subprocess
import time
from pdbfixer import PDBFixer
from openmm.app import PDBFile
from utils.parse_nvidia_smi import find_available_gpus
# from utils.utils import run_command # This function is not used for the parallel part

MODULE_PATH = pathlib.Path(__file__).parent.resolve()
BASH = shutil.which("bash") or "/usr/bin/bash"
RUN_MD = f'{MODULE_PATH}/run_md.sh'


def launch_md_jobs(wd, score_csv, docked_dir, receptor_path, config_path, threads, num_md_mols, ):
    final_df = pd.read_csv(score_csv)

    # --- Receptor preparation (this part remains unchanged) ---
    print("--- Preparing receptor PDB for MD ---")
    fixer = PDBFixer(filename=receptor_path)
    fixer.findMissingResidues()
    chains = list(fixer.topology.chains())
    keys = fixer.missingResidues.keys()
    for key in list(keys):
        chain = chains[key[0]]
        if key[1] == 0 or key[1] == len(list(chain.residues())):
            print("ok")
            del fixer.missingResidues[key]
    fixer.findNonstandardResidues() 
    fixer.replaceNonstandardResidues() 
    fixer.removeHeterogens(keepWater=False) 
    fixer.findMissingAtoms() 
    fixer.addMissingAtoms() 
    fixer.addMissingHydrogens(7.0)

    md_receptor = f'{wd}/receptor_md.pdb'
    PDBFile.writeFile(fixer.topology, fixer.positions, open(md_receptor,'w'))
    print("--- Receptor preparation complete ---\n")

    gpu_array = find_available_gpus(num_gpus=threads)
    
    # This list will act as our worker pool, storing (process, gpu_index, ligand, log_file)
    running_procs = []

    # Loop through all molecules to be run
    for i in range(num_md_mols):
        
        gpu_idx_to_use = -1

        # If the pool is full, poll all running processes until one finishes
        if len(running_procs) >= threads:
            while True:
                finished_proc_index = -1
                # Check each running process to see if it has finished
                for idx, (proc, gpu_idx, ligand, log_file) in enumerate(running_procs):
                    if proc.poll() is not None: # This check is non-blocking
                        print(f"--- Job for '{ligand}' on GPU slot {gpu_idx} completed. Slot is now free. ---")
                        if proc.returncode != 0:
                             print(f"Warning: Job for '{ligand}' failed with exit code {proc.returncode}. Check logs.")
                        log_file.close() # Close the log file for the finished process
                        finished_proc_index = idx
                        break # Exit the inner for loop
                
                # If a process was found to have finished
                if finished_proc_index != -1:
                    # Remove it from the list and reuse its GPU index
                    _ , gpu_idx_to_use, _ , _ = running_procs.pop(finished_proc_index)
                    break # Exit the while loop to launch the next job
                else:
                    # If no process has finished, wait a moment to avoid high CPU usage
                    time.sleep(1)
                
        else:
            # If the pool is not full, use the next available GPU index
            gpu_idx_to_use = len(running_procs)
        
        # --- Prepare and launch the new job ---
        ligand = final_df.iloc[i]['ligand']
        docked_pdbqt = f'{docked_dir}/{ligand}_out.pdbqt'
        assert os.path.exists(docked_pdbqt)
        job_wd = f'{wd}/{ligand}'
        os.makedirs(job_wd, exist_ok=True)

        for file in os.listdir(config_path):
            shutil.copy(f'{config_path}/{file}', job_wd)
            
        node_id, cuda_id = gpu_array[gpu_idx_to_use].split(':')
        ssh_host = f"gpu{node_id}"

        cmd = [
            'ssh', ssh_host,
            f"cd {job_wd} && "
            f"{BASH} {RUN_MD} {md_receptor} {docked_pdbqt} {cuda_id}"
        ]
        
        print(f"--> Launching job for '{ligand}' on GPU slot {gpu_idx_to_use} ({ssh_host}:{cuda_id})...")
        
        log_file = open(f"{job_wd}/md_run.log", "w")
        
        process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        
        # Add the new process and its full info to our pool
        running_procs.append((process, gpu_idx_to_use, ligand, log_file))

    # After the loop, wait for any remaining jobs to complete
    print("\n--- All jobs have been launched. Waiting for the final set of jobs to complete... ---")
    for proc, gpu_idx, ligand, log in running_procs:
        proc.wait()
        log.close()
        print(f"Final job for '{ligand}' on GPU slot {gpu_idx} has completed.")
        if proc.returncode != 0:
             print(f"Warning: Job for '{ligand}' failed with exit code {proc.returncode}.")

    print("\nAll MD jobs have been processed successfully.")