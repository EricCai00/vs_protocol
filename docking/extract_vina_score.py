#!/public/home/caiyi/software/miniconda3/bin/python
"""
extract_vina_score.py

Extract Vina docking scores from PDBQT files.

Can be used as a script or imported as a module.
"""
import math
from glob import glob
from multiprocessing import Pool
from pathlib import Path
from tqdm import tqdm

def _extract_score(file_list):
    out = []
    for file in tqdm(file_list):
        with open(file) as f:
            # skip header
            f.readline()
            # parse score line
            parts = f.readline().split()
            # if len(parts) < 4:
            #     raise ValueError(f"Unexpected format in file {file}")
            try:
                score = float(parts[3])
            except:
                print('Error on', file, parts)
                continue
        mol_name = file.split('/')[-1][:-10]
        out.append(f"{score},{mol_name}\n")
    return out

def extract_scores(
    name: str,
    docked_dir: str,
    output_dir: str,
    threads: int,
    suffix: str = '_out.pdbqt'
) -> Path:
    """
    Core function to extract docking scores and ZINC IDs from PDBQT files.

    Args:
        name:      dataset name (e.g., 'train', 'valid', 'test')
        docked_dir: path to directory containing PDBQT files
        output_dir: path to directory where output will be saved
        threads:   number of parallel worker processes
        suffix:    file suffix for PDBQT files (default '_out.pdbqt')

    Returns:
        Path to the output labels file
    """

    # Collect files
    files = glob(f"{docked_dir}/*{suffix}")
    if not files:
        raise FileNotFoundError(f"No files found in {docked_dir} with suffix {suffix}")

    # Split for multiprocessing
    split_len = math.ceil(len(files) / threads)
    file_splits = [files[i * split_len:(i + 1) * split_len] for i in range(threads)]


    # Run multiprocessing
    with Pool(threads) as pool:
        out_splits = pool.map(_extract_score, file_splits)

    # Write output
    output_path = Path(output_dir) / f"{name}_dock_scores.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as out_file:
        out_file.write('score,name\n')
        for split in out_splits:
            out_file.writelines(split)

    return output_path


# CLI entrypoint
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Extract Vina scores and ZINC IDs from docked PDBQT files',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-n', '--name', required=True,
                        help="dataset name: 'train','valid','test' or custom")
    parser.add_argument('-d', '--docked_dir', required=True,
                        help='directory containing docked PDBQT files')
    parser.add_argument('-o', '--output_dir', required=True,
                        help='directory to save output labels file')
    parser.add_argument('-t', '--threads', type=int, required=True,
                        help='number of parallel threads')
    parser.add_argument('-sf', '--suffix', default='_out.pdbqt',
                        help="suffix of PDBQT files (default '_out.pdbqt')")
    args = parser.parse_args()

    output = extract_scores(
        name=args.name,
        docked_dir=args.docked_dir,
        output_dir=args.output_dir,
        threads=args.threads,
        suffix=args.suffix
    )
    print(f"Labels file written to: {output}")
