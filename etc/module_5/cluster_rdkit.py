#!/usr/bin/env python3
import os
import sys
import argparse
from tqdm import tqdm
from rdkit import DataStructs
from rdkit.DataStructs import TanimotoSimilarity, BulkTanimotoSimilarity
from rdkit.ML.Cluster import Butina

def run_clustering(fingerprint_file, threshold, output_dir):
    """
    使用 RDKit 对预先计算好的指纹文件进行 Taylor-Butina 聚类。
    1. 从文件加载指纹 (hex string) 和 ID。
    2. 计算距离矩阵。
    3. 运行 Taylor-Butina 聚类。
    4. 将聚类代表写入 'cluster_representatives.txt'。
    5. 将详细的聚类信息写入 'clusters_detailed.txt'。
    """
    os.makedirs(output_dir, exist_ok=True)
    dist_threshold = 1 - threshold

    # 1. 从文件直接加载指纹和 ID (不再从 SMILES 生成)
    print(f"Loading fingerprints from: {fingerprint_file}")
    fps, ids = [], []
    try:
        with open(fingerprint_file, 'r') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                
                parts = line.split()
                if len(parts) != 2:
                    print(f"WARNING: Skipping malformed line #{i}: '{line}'")
                    continue
                
                hex_string, mol_id = parts
                
                bv = DataStructs.CreateFromFPSText(hex_string)
                fps.append(bv)
                ids.append(mol_id)

    except FileNotFoundError:
        sys.stderr.write(f"ERROR: Input file not found at '{fingerprint_file}'\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"ERROR: Failed to process file '{fingerprint_file}': {e}\n")
        sys.exit(1)

    if not fps:
        sys.stderr.write("ERROR: No valid fingerprints were loaded from the input file.\n")
        sys.exit(1)
        
    num_fps = len(fps)
    print(f"Loaded {num_fps} fingerprints.")

    # 2. 计算距离矩阵
    print("Calculating distance matrix...")
    dists = []
    for i in tqdm(range(num_fps)):
        sims = BulkTanimotoSimilarity(fps[i], fps[i+1:])
        dists.extend([1 - s for s in sims])

    # 3. 执行 Taylor-Butina 聚类
    print(f"Performing Taylor–Butina clustering (distance_threshold = {dist_threshold:.2f}) ...")
    clusters = Butina.ClusterData(dists, num_fps, dist_threshold, isDistData=True)

    # 4. 按簇大小对结果进行排序
    sorted_clusters = sorted(clusters, key=len, reverse=True)

    # --- BLOCK 1: 写入聚类代表 ---
    reps_out = os.path.join(output_dir, 'cluster_representatives.txt')
    try:
        with open(reps_out, 'w') as f_out:
            for cluster in sorted_clusters:
                centroid_idx = cluster[0]
                f_out.write(ids[centroid_idx] + "\n")
        print(f"Saved {len(sorted_clusters)} representatives to: {reps_out}")
    except Exception as e:
        sys.stderr.write(f"ERROR: Could not write representatives file: {e}\n")
        sys.exit(1)

    # --- BLOCK 2: 写入详细的聚类信息 ---
    detailed_out = os.path.join(output_dir, 'clusters_detailed.txt')
    try:
        with open(detailed_out, 'w') as f_out:
            f_out.write(f"# Detailed cluster information from Taylor-Butina clustering\n")
            f_out.write(f"# Tanimoto threshold = {threshold}\n")
            f_out.write("# Format: Member_ID  Similarity_to_Centroid\n\n")

            for i, cluster in enumerate(sorted_clusters):
                cluster_size = len(cluster)
                centroid_idx = cluster[0]
                centroid_id = ids[centroid_idx]
                centroid_fp = fps[centroid_idx]

                f_out.write(f"--- Cluster {i+1} (size: {cluster_size}, centroid: {centroid_id}) ---\n")
                
                f_out.write(f"{centroid_id}\t1.0000\t(centroid)\n")

                members_with_scores = []
                for member_idx in cluster[1:]:
                    score = TanimotoSimilarity(centroid_fp, fps[member_idx])
                    members_with_scores.append((ids[member_idx], score))
                
                sorted_members = sorted(members_with_scores, key=lambda x: x[1], reverse=True)
                
                for member_id, score in sorted_members:
                    f_out.write(f"{member_id}\t{score:.4f}\n")
                
                f_out.write("\n")

        print(f"Saved {len(sorted_clusters)} clusters to: {detailed_out}")
    except Exception as e:
        sys.stderr.write(f"ERROR: Could not write detailed clusters file: {e}\n")
        sys.exit(1)

    print("\nClustering complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Cluster a pre-computed fingerprint file using Taylor–Butina with RDKit."
    )
    parser.add_argument(
        '-f', '--fingerprint_file',
        required=True,
        help="Path to a fingerprint file. Each line: 'Hex_Fingerprint Molecule_ID'"
    )
    parser.add_argument(
        '-t', '--threshold',
        type=float,
        default=0.80,
        help="Tanimoto similarity threshold (default: 0.80)"
    )
    parser.add_argument(
        '-o', '--output_dir',
        required=True,
        help="Directory where output files will be written"
    )
    args = parser.parse_args()

    run_clustering(
        fingerprint_file=args.fingerprint_file,
        threshold=args.threshold,
        output_dir=args.output_dir
    )
