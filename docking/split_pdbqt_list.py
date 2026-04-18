#!/public/home/caiyi/software/miniconda3/bin/python
"""
split_pdbqt_list.py

Python replacement for split_pdbqt_list.sh:
- Splits a list of PDBQT ligand files into multiple chunk files for parallel processing.
- Can be used as an importable function or as a standalone CLI script.
"""
import argparse
import math
import shutil
from pathlib import Path

def split_pdbqt_list(
    working_dir: Path,
    prefix: str,
    num_splits: int,
    list_path: Path = None
) -> None:
    """
    Split a ligand list into num_splits chunks under working_dir/prefix_list_split,
    writing only basenames in each chunk file.

    Args:
        working_dir: Path to working directory
        prefix: name prefix for files
        num_splits: desired number of split files
        list_path: optional existing list file; if None, uses working_dir/prefix_list.txt
    """
    wd = working_dir.resolve()
    pdbqt_dir = wd / f"{prefix}_pdbqt"

    # Determine list file and generate if needed
    if list_path:
        list_file = list_path.resolve()
    else:
        list_file = wd / f"{prefix}_list.txt"
        if not pdbqt_dir.is_dir():
            raise FileNotFoundError(f"Directory not found: {pdbqt_dir}")
        with list_file.open('w') as f:
            for item in sorted(pdbqt_dir.iterdir()):
                if item.suffix == '.pdbqt':
                    f.write(item.name + '\n')

    # Read all lines
    lines = list_file.read_text().splitlines()
    total = len(lines)
    if total == 0:
        raise ValueError(f"No entries found in list: {list_file}")

    # Compute split size, rounding up
    chunk_size = math.ceil(total / num_splits)

    # Prepare output directory
    split_dir = wd / f"{prefix}_list_split"
    if split_dir.exists():
        # rotate old splits
        i = 1
        while (wd / f"{prefix}_list_split_{i}").exists():
            i += 1
        shutil.move(str(split_dir), str(wd / f"{prefix}_list_split_{i}"))
    split_dir.mkdir(parents=True, exist_ok=True)

    # Write chunk files with only basenames
    for idx in range(num_splits):
        start = idx * chunk_size
        end = min(start + chunk_size, total)
        chunk = lines[start:end]
        if not chunk:
            break
        out_file = split_dir / f"{prefix}_list_split_{idx:02d}.txt"
        with out_file.open('w') as f:
            for entry in chunk:
                f.write(Path(entry).name + "\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Split PDBQT ligand list into multiple chunk files',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-d', '--working-dir', required=True,
                        type=Path, help='Working directory')
    parser.add_argument('-n', '--name', required=True,
                        help='File name prefix')
    parser.add_argument('-s', '--splits', required=True, type=int,
                        help='Number of split files to create')
    parser.add_argument('-l', '--list', type=Path,
                        help='Optional existing list file (one entry per line)')
    args = parser.parse_args()
    split_pdbqt_list(
        working_dir=args.working_dir,
        prefix=args.name,
        num_splits=args.splits,
        list_path=args.list
    )
