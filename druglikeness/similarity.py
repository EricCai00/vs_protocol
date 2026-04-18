#!/usr/bin/env python3
import os
import sys
import csv
import math
import argparse
from rdkit import Chem
from rdkit import DataStructs
from multiprocessing import Pool
import tqdm

# -----------------------------------------------------------------------------
# Global cache for sharing query fingerprints during parallel processing
ARGS_CONFIG = None
QUERY_FINGERPRINTS_DATA = None
# -----------------------------------------------------------------------------

def calculate_similarity_chunk(target_chunk):
    from rdkit.Chem import AllChem
    """
    target_chunk: list of tuples (idx, smi, name)
    """
    global ARGS_CONFIG, QUERY_FINGERPRINTS_DATA
    results = []
    if not target_chunk or not QUERY_FINGERPRINTS_DATA:
        return results

    query_fps = [item["fingerprint"] for item in QUERY_FINGERPRINTS_DATA]
    radius = ARGS_CONFIG['radius']

    for idx, smi, name in target_chunk:
        try:
            mol = Chem.MolFromSmiles(smi)
            fp = AllChem.GetMorganFingerprint(mol, radius=radius) if mol else None
        except Exception:
            fp = None

        if fp is None:
            scores = [None] * len(query_fps)
        else:
            scores = [DataStructs.TanimotoSimilarity(fp, qfp) for qfp in query_fps]

        results.append((idx, name, scores))
    return results

def calculate_similarities(input_smi, query_smi_file, output_csv, num_threads, radius):
    from rdkit.Chem import AllChem
    global ARGS_CONFIG, QUERY_FINGERPRINTS_DATA
    ARGS_CONFIG = {'num_threads': num_threads, 'radius': radius}

    # 1. Reading query SMILES and generate FPs
    print(f"Reading query SMILES from: {query_smi_file}")
    query_list = []
    with open(query_smi_file) as f:
        for ln, line in enumerate(f, 1):
            tokens = line.strip().split()
            if not tokens:
                continue
            smi = tokens[0]
            query_list.append((ln, smi))

    fps_data = []
    for idx, smi in query_list:
        mol = Chem.MolFromSmiles(smi)
        if mol:
            try:
                fp = AllChem.GetMorganFingerprint(mol, radius=radius)
                fps_data.append({"original_index": idx-1, "smi": smi, "fingerprint": fp})
            except Exception:
                print(f"Warning: failed to fingerprint query '{smi}' (line {idx})")
        else:
            print(f"Warning: invalid query SMILES '{smi}' (line {idx})")
    if not fps_data:
        print("No valid query fingerprints; exiting.")
        sys.exit(1)
    QUERY_FINGERPRINTS_DATA = fps_data
    print(f"Generated {len(fps_data)} query fingerprints.")

    # 2. Read target SMILES and names
    print(f"Reading target SMILES from: {input_smi}")
    targets = []
    with open(input_smi) as f:
        for idx, line in enumerate(f):
            tokens = line.strip().split()
            if not tokens:
                continue
            smi = tokens[0]
            name = tokens[1] if len(tokens) > 1 else f"mol_{idx+1}"
            targets.append((idx, smi, name))
    if not targets:
        print("No targets found; exiting.")
        sys.exit(1)

    num_targets = len(targets)
    threads = min(num_threads, num_targets)
    chunk_size = math.ceil(num_targets / threads)
    splits = [targets[i*chunk_size:(i+1)*chunk_size] for i in range(threads)]

    # 3. Calculating similarities
    print(f"Calculating similarities using {threads} threads...")
    with Pool(threads) as pool:
        all_chunks = list(tqdm.tqdm(
            pool.imap_unordered(calculate_similarity_chunk, splits),
            total=len(splits),
            desc="Similarity calculation"
        ))

    # 4. Summarize results
    # Prepare containers
    names = [None] * num_targets
    matrix = [[None]*len(fps_data) for _ in range(num_targets)]
    # Fill names and scores
    for chunk in all_chunks:
        for idx, name, scores in chunk:
            names[idx] = name
            matrix[idx] = scores

    # 5. Write CSV with names
    print(f"Writing similarity matrix to {output_csv}")
    header = ['Name'] + [f"Query_line_{item['original_index']+1}" for item in fps_data]
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for name, row in zip(names, matrix):
            writer.writerow([name] + [f"{s:.3f}" if s is not None else "N/A" for s in row])

    print("Similarity calculation complete.")


def calculate_average_scores(score_list_str):
    values = []
    for s in score_list_str:
        try:
            values.append(float(s))
        except ValueError:
            continue
    return (sum(values)/len(values)) if values else None


def filter_average_similarity(score_csv, input_smi, output_smi, threshold):
    # 1. 读取 target SMILES 和名称
    print(f"Reading target SMILES from: {input_smi}")
    smiles = []
    names = []
    with open(input_smi) as f:
        for line in f:
            tokens = line.strip().split()
            if not tokens:
                continue
            smiles.append(tokens[0])
            names.append(tokens[1] if len(tokens)>1 else f"mol_{len(smiles)}")

    # 2. 读取分数 CSV
    print(f"Reading scores from: {score_csv}")
    rows = []
    with open(score_csv, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            rows.append(row)
    if len(rows) != len(smiles):
        print("Error: SMILES count and score rows mismatch.")
        sys.exit(1)

    # 3. 门限筛选
    passed = []
    for smi, name, row in zip(smiles, names, rows):
        avg = calculate_average_scores(row)
        if avg is not None and avg > threshold:
            passed.append((name, smi))

    # 4. 写入带 name 的 SMILES 文件
    print(f"Writing filtered SMILES to: {output_smi}")
    with open(output_smi, 'w') as f:
        for name, smi in passed:
            f.write(f"{smi} {name}\n")

    print(f"Filtering complete. Kept {len(passed)} of {len(smiles)} molecules.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="mode: 'calc' 计算相似度矩阵；'filter' 按平均相似度筛选"
    )
    subparsers = parser.add_subparsers(dest='mode', required=True)

    p_calc = subparsers.add_parser('calc', help='计算 Tanimoto 相似度矩阵')
    p_calc.add_argument('-i', '--input_smi',   required=True, help='目标 SMILES 文件，格式：SMILES [name]')
    p_calc.add_argument('-q', '--query_smi',   required=True, help='查询 SMILES 列表，每行一个 SMILES')
    p_calc.add_argument('-o', '--output_csv',  required=True, help='输出 CSV（第一列 Name，其后为相似度分数）')
    p_calc.add_argument('-n', '--num_threads', type=int, default=os.cpu_count(), help='线程数')
    p_calc.add_argument('-r', '--radius',      type=int, default=2, help='Morgan 指纹半径')

    p_filt = subparsers.add_parser('filter', help='按平均相似度阈值筛选 SMILES')
    p_filt.add_argument('-s', '--score_csv',  required=True, help='相似度矩阵 CSV 文件')
    p_filt.add_argument('-i', '--input_smi',  required=True, help='原始 SMILES 文件，格式：SMILES [name]')
    p_filt.add_argument('-o', '--output_smi', required=True, help='输出筛选后 SMILES 文件（Name\\tSMILES）')
    p_filt.add_argument('-t', '--threshold',  type=float, required=True, help='平均相似度阈值')

    args = parser.parse_args()
    if args.mode == 'calc':
        calculate_similarities(
            input_smi=args.input_smi,
            query_smi_file=args.query_smi,
            output_csv=args.output_csv,
            num_threads=args.num_threads,
            radius=args.radius
        )
    else:  # filter
        filter_average_similarity(
            score_csv=args.score_csv,
            input_smi=args.input_smi,
            output_smi=args.output_smi,
            threshold=args.threshold
        )
