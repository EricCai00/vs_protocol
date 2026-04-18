#!/usr/bin/env python3
import os
import sys
import argparse
import pandas as pd
import numpy as np
import requests
import subprocess
from pathlib import Path
from multiprocessing import Pool
from Bio import PDB
from vina import Vina

def download_from_alphafold(pdb_id: str, save_path: str) -> bool:
    """
    如果本地无 PDB 文件，尝试从 AlphaFold 下载 (UniProt ID 格式)。
    返回 True 表示成功下载或已存在；False 表示下载失败。
    """
    if os.path.exists(save_path):
        return True
    url = f"https://alphafold.ebi.ac.uk/files/{pdb_id}.pdb"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            Path(save_path).write_bytes(resp.content)
            print(f"[Download] 成功从 AlphaFold 下载: {pdb_id}")
            return True
        else:
            print(f"[Download] AlphaFold HTTP {resp.status_code} for {pdb_id}")
            return False
    except Exception as e:
        print(f"[Download] 异常下载 {pdb_id}: {e}")
        return False

def compute_pocket_center_size(pdb_path: str, start_res: int, end_res: int, margin: float = 5.0):
    """
    解析 PDB，提取指定残基区间 (inclusive) 的所有原子坐标，计算中心 (mean) 和尺寸 (ptp + margin)。
    返回 (center_list, size_list)。若未找到任何原子则抛 ValueError。
    """
    parser = PDB.PDBParser(QUIET=True)
    structure = parser.get_structure(os.path.basename(pdb_path), pdb_path)
    coords = []
    for model in structure:
        for chain in model:
            for residue in chain:
                resnum = residue.id[1]
                if start_res <= resnum <= end_res:
                    for atom in residue:
                        coords.append(atom.get_coord())
    if not coords:
        raise ValueError(f"No atoms found in residues {start_res}-{end_res} of {pdb_path}")
    arr = np.array(coords)
    center = arr.mean(axis=0)
    size = np.ptp(arr, axis=0) + margin
    return center.tolist(), size.tolist()

def prepare_receptor(pdb_path: str, receptor_pdbqt: str, python2: str, prepare_script: str):
    """
    调用 prepare_receptor4.py 生成 receptor.pdbqt。
    若命令返回非零则抛 RuntimeError。
    """
    cmd = f"{python2} {prepare_script} -r {pdb_path} -o {receptor_pdbqt}"
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        stderr = res.stderr.decode().strip() if res.stderr else ""
        raise RuntimeError(f"prepare_receptor 失败: {cmd}\n{stderr}")

def run_docking_for_one(pdb_id: str,
                       pdb_path: str,
                       start_res: int,
                       end_res: int,
                       ligand_dir: str,
                       out_dir: str,
                       python2: str,
                       prepare_script: str,
                       margin: float = 5.0,
                       exhaustiveness: int = 32,
                       n_poses: int = 9) -> list:
    """
    对单个蛋白 与 ligand_dir 下所有 .pdbqt 配体做对接。
    返回含多个 dict 的列表：{pdb_name, ligand_name, pose, affinity, rmsd_lb, rmsd_ub}
    """
    os.makedirs(out_dir, exist_ok=True)
    results = []
    if not os.path.exists(pdb_path):
        if not download_from_alphafold(pdb_id, pdb_path):
            print(f"[Warning] 无法获取 PDB {pdb_id}, 跳过")
            return results

    receptor_pdbqt = os.path.join(out_dir, f"{pdb_id}_receptor.pdbqt")
    try:
        prepare_receptor(pdb_path, receptor_pdbqt, python2, prepare_script)
    except Exception as e:
        print(f"[Error] {pdb_id} prepare_receptor 失败: {e}")
        return results

    try:
        center, size = compute_pocket_center_size(pdb_path, start_res, end_res, margin=margin)
    except Exception as e:
        print(f"[Error] {pdb_id} 计算口袋中心/大小失败: {e}")
        return results

    ligand_files = [f for f in os.listdir(ligand_dir) if f.endswith('.pdbqt')]
    for ligand_file in ligand_files:
        ligand_name = os.path.splitext(ligand_file)[0]
        ligand_path = os.path.join(ligand_dir, ligand_file)
        try:
            v = Vina(sf_name='vina')
            v.set_receptor(receptor_pdbqt)
            v.set_ligand_from_file(ligand_path)
            v.compute_vina_maps(center=center, box_size=size)
            v.dock(exhaustiveness=exhaustiveness, n_poses=n_poses)
            docked_path = os.path.join(out_dir, f"{pdb_id}_{ligand_name}_docked.pdbqt")
            v.write_poses(docked_path, n_poses=n_poses, overwrite=True)
            with open(docked_path, 'r') as fin:
                pose_idx = 0
                for line in fin:
                    if line.startswith("REMARK VINA RESULT:"):
                        parts = line.strip().split()
                        try:
                            affinity = float(parts[3])
                            rmsd_lb = float(parts[4])
                            rmsd_ub = float(parts[5])
                            pose_idx += 1
                            results.append({
                                'pdb_name': pdb_id,
                                'ligand_name': ligand_name,
                                'pose': pose_idx,
                                'affinity': affinity,
                                'rmsd_lb': rmsd_lb,
                                'rmsd_ub': rmsd_ub
                            })
                        except:
                            continue
            print(f"[Docking] {pdb_id} vs {ligand_name} 完成, 得到 {n_poses} 份结果")
        except Exception as e:
            print(f"[Error] {pdb_id} 对接 {ligand_name} 失败: {e}")
            continue
    return results

def off_target_screen(ligand_dir: str,
                      off_target_list: pd.DataFrame,
                      all_pdb_base: str,
                      out_base: str,
                      python2: str,
                      prepare_script: str,
                      margin: float,
                      exhaustiveness: int,
                      n_poses: int,
                      processes: int) -> pd.DataFrame:
    """
    脱靶预测：对 off_target_list 中的每个 pdb 做对接，返回合并 DataFrame。
    off_target_list: DataFrame，需含 'pdb_name','start_res','end_res' 列。
    """
    records = []
    def worker(row):
        pdb = str(row['pdb_name'])
        try:
            start = int(row['start_res']); end = int(row['end_res'])
        except:
            print(f"[Warning] off-target 列 start_res/end_res 无效: {row}")
            return []
        pdb_path = os.path.join(all_pdb_base, pdb + '.pdb')
        out_dir = os.path.join(out_base, pdb)
        return run_docking_for_one(
            pdb_id=pdb,
            pdb_path=pdb_path,
            start_res=start,
            end_res=end,
            ligand_dir=ligand_dir,
            out_dir=out_dir,
            python2=python2,
            prepare_script=prepare_script,
            margin=margin,
            exhaustiveness=exhaustiveness,
            n_poses=n_poses
        )

    os.makedirs(out_base, exist_ok=True)
    tasks = [row for _, row in off_target_list.iterrows()]
    if processes > 1:
        with Pool(processes=processes) as pool:
            all_lists = pool.map(worker, tasks)
    else:
        all_lists = [worker(row) for row in tasks]
    for sub in all_lists:
        records.extend(sub or [])

    if records:
        return pd.DataFrame(records)
    else:
        return pd.DataFrame(columns=['pdb_name','ligand_name','pose','affinity','rmsd_lb','rmsd_ub'])

def run_off_targets(off_targets_csv: str,
                    ligand_dir: str,
                    all_pdb_path: str,
                    out_root: str,
                    python2: str,
                    prepare_script: str,
                    margin: float,
                    exhaustiveness: int,
                    n_poses: int,
                    processes: int) -> None:
    """
    对脱靶目标列表做对接，并将结果写入 offtarget_results.csv
    """
    off_df = pd.read_csv(off_targets_csv)
    result_df = off_target_screen(
        ligand_dir=ligand_dir,
        off_target_list=off_df,
        all_pdb_base=all_pdb_path,
        out_base=os.path.join(out_root, 'offtarget'),
        python2=python2,
        prepare_script=prepare_script,
        margin=margin,
        exhaustiveness=exhaustiveness,
        n_poses=n_poses,
        processes=processes
    )
    off_file = os.path.join(out_root, 'offtarget_results.csv')
    if not result_df.empty:
        result_df.to_csv(off_file, index=False)
        print(f"[Result] 脱靶对接结果保存: {off_file}")
    else:
        print("[Result] 未生成任何脱靶对接结果")
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='脱靶蛋白对接预测')
    parser.add_argument('-i', '--off_targets', type=str, required=True,
                        help='脱靶蛋白列表 CSV，含列: pdb_name, start_res, end_res')
    parser.add_argument('-l', '--ligand_dir', type=str, required=True,
                        help='配体文件夹，含 .pdbqt 文件')
    parser.add_argument('--all_pdb_path', type=str, required=True,
                        help='本地 PDB 存储根目录')
    parser.add_argument('-o', '--output', type=str, required=True,
                        help='输出根目录')
    parser.add_argument('--python2', type=str, required=True,
                        help='Python2 可执行文件路径')
    parser.add_argument('--prepare_script', type=str, required=True,
                        help='prepare_receptor4.py 脚本路径')
    parser.add_argument('--processes', type=int, default=1,
                        help='并行进程数')
    parser.add_argument('--margin', type=float, default=5.0,
                        help='口袋尺寸 margin')
    parser.add_argument('--exhaustiveness', type=int, default=32,
                        help='Vina exhaustiveness')
    parser.add_argument('--n_poses', type=int, default=9,
                        help='Vina 输出 pose 数量')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    run_off_targets(
        off_targets_csv=args.off_targets,
        ligand_dir=args.ligand_dir,
        all_pdb_path=args.all_pdb_path,
        out_root=args.output,
        python2=args.python2,
        prepare_script=args.prepare_script,
        margin=args.margin,
        exhaustiveness=args.exhaustiveness,
        n_poses=args.n_poses,
        processes=args.processes
    )
