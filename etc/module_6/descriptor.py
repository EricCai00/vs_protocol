#!/usr/bin/env python3
import os
import sys
import csv
import argparse
from rdkit import Chem
from rdkit.Chem import Lipinski
from tqdm import tqdm

# -----------------------------------------------------------------------------
# Functions for HBA calculation and filtering
# -----------------------------------------------------------------------------

def calculate_hba_counts(input_smi, output_csv):
    """
    读取 SMILES 文件，计算每条分子的 HBA 数量，并保存到 CSV。
    :param input_smi: 输入 SMILES 文件路径，每行一个 SMILES
    :param output_csv: 输出 CSV 文件路径，包含两列：SMILES, HBA
    """
    smiles_list = []
    name_list = []
    try:
        with open(input_smi, 'r') as f:
            for line in f:
                smi, name = line.strip().split()
                if smi:
                    name_list.append(name)
                    smiles_list.append(smi)
    except Exception as e:
        print(f"Error reading SMILES file: {e}")
        sys.exit(1)

    # 计算 HBA 并写入 CSV
    try:
        with open(output_csv, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["name", "HBA"])
            for i, name in tqdm(enumerate(name_list)):
                smi = smiles_list[i]
                mol = Chem.MolFromSmiles(smi)
                hba = Lipinski.NumHAcceptors(mol) if mol else None
                writer.writerow([name, hba if hba is not None else "N/A"])
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        sys.exit(1)

    print(f"HBA counts saved to {output_csv}")


def filter_by_hba_threshold(counts_csv, output_smi, threshold):
    """
    根据 HBA 阈值过滤分子，保留 HBA <= threshold 的 SMILES。
    :param counts_csv: 包含 SMILES 和 HBA 列的 CSV 文件
    :param output_smi: 输出 SMILES 文件路径，满足条件的 SMILES 每行一个
    :param threshold: 最大 HBA 值阈值
    """
    passed = []
    try:
        with open(counts_csv, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    hba = int(row['HBA'])
                except ValueError:
                    continue
                if hba <= threshold:
                    passed.append(row['SMILES'])
    except Exception as e:
        print(f"Error reading counts CSV: {e}")
        sys.exit(1)

    try:
        with open(output_smi, 'w') as f:
            for smi in passed:
                f.write(smi + "\n")
    except Exception as e:
        print(f"Error writing output SMILES: {e}")
        sys.exit(1)

    print(f"Filtering complete. Kept {len(passed)} molecules with HBA <= {threshold}.")


# -----------------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Mode: 'calc' to compute HBA counts, 'filter' to select by HBA threshold"
    )
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # 计算模式
    p_calc = subparsers.add_parser('calc', help='Compute HBA counts for SMILES file')
    p_calc.add_argument('-i', '--input_smi', required=True, help='输入 SMILES 文件路径')
    p_calc.add_argument('-o', '--output_csv', required=True, help='输出 HBA counts CSV 文件路径')

    # 过滤模式
    p_filter = subparsers.add_parser('filter', help='Filter SMILES by HBA threshold')
    p_filter.add_argument('-c', '--counts_csv', required=True, help='输入 HBA counts CSV 文件路径')
    p_filter.add_argument('-o', '--output_smi', required=True, help='输出过滤后的 SMILES 文件路径')
    p_filter.add_argument('-t', '--threshold', type=int, required=True, help='HBA 最大阈值')

    args = parser.parse_args()

    if args.mode == 'calc':
        calculate_hba_counts(
            input_smi=args.input_smi,
            output_csv=args.output_csv
        )
    elif args.mode == 'filter':
        filter_by_hba_threshold(
            counts_csv=args.counts_csv,
            output_smi=args.output_smi,
            threshold=args.threshold
        )
    else:
        parser.print_help()
        sys.exit(1)
