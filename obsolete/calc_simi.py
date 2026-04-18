import argparse
import os
import csv
import math
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import DataStructs
from multiprocessing import Pool
import tqdm

# Global variables (populated in main)
ARGS_CONFIG = None
QUERY_FINGERPRINTS_DATA = None  # Stores {"original_index": idx, "smi": q_smi, "fingerprint": q_fp}

def calculate_fingerprint_c(mol_smi_tuple):
    """Helper function to calculate Morgan fingerprint.
       Accepts (smiles, radius).
    """
    smi, radius = mol_smi_tuple
    mol = Chem.MolFromSmiles(smi)
    if mol:
        try:
            return AllChem.GetMorganFingerprint(mol, radius=radius)
        except Exception:
            return None
    return None

def calculate_similarity_chunk_c(target_smi_chunk_with_indices):
    """
    Calculates similarities for a chunk of target SMILES against global query fingerprints.
    Returns:
        list: A list of tuples: [(original_target_index, [score_q1, score_q2, ...]), ...]
              Score list might be [None, None, ...] if target processing failed.
    """
    chunk_results_with_indices = []
    if not target_smi_chunk_with_indices or not QUERY_FINGERPRINTS_DATA:
        return chunk_results_with_indices

    num_queries = len(QUERY_FINGERPRINTS_DATA)
    query_fps = [item["fingerprint"] for item in QUERY_FINGERPRINTS_DATA]

    for original_idx, target_smi in target_smi_chunk_with_indices:
        target_mol = None
        target_fp = None
        try:
            target_mol = Chem.MolFromSmiles(target_smi)
            if target_mol:
                target_fp = AllChem.GetMorganFingerprint(target_mol, radius=ARGS_CONFIG['radius'])
        except Exception:
            pass  # Error parsing target SMILES or generating fingerprint

        if not target_fp:
            # Append None list to maintain row correspondence if target fails
            scores = [None] * num_queries
        else:
            scores = [0.0] * num_queries  # Initialize scores for this target
            for i, query_fp in enumerate(query_fps):
                scores[i] = DataStructs.TanimotoSimilarity(target_fp, query_fp)

        chunk_results_with_indices.append((original_idx, scores))

    return chunk_results_with_indices


def process_queries_and_targets(input_smi, query_smi_file, output_csv, num_threads=os.cpu_count(), radius=2):
    global ARGS_CONFIG, QUERY_FINGERPRINTS_DATA
    ARGS_CONFIG = {'num_threads': num_threads, 'radius': radius}

    # 1. Read Query SMILES and generate fingerprints
    print(f"Reading query SMILES from: {query_smi_file}")
    query_smi_list_from_file = []
    try:
        with open(query_smi_file, 'r') as f_query:
            for line in f_query:
                smi = line.strip().split(None, 1)[0]  # Take first part
                if smi:
                    query_smi_list_from_file.append(smi)
    except FileNotFoundError:
        print(f"Error: Query SMILES file not found: {query_smi_file}")
        return
    except Exception as e:
        print(f"Error reading query file: {e}")
        return

    if not query_smi_list_from_file:
        print("No SMILES found in query file.")
        return
    print(f"Processing {len(query_smi_list_from_file)} query SMILES...")

    valid_queries_data_list = []
    for idx, q_smi in enumerate(query_smi_list_from_file):
        q_mol = Chem.MolFromSmiles(q_smi)
        if q_mol:
            q_fp = AllChem.GetMorganFingerprint(q_mol, radius=radius)
            if q_fp:
                valid_queries_data_list.append({"original_index": idx, "smi": q_smi, "fingerprint": q_fp})
            else:
                print(f"Warning: Could not generate fingerprint for query: '{q_smi}' (line {idx+1}). Skipping.")
        else:
            print(f"Warning: Could not parse query SMILES: '{q_smi}' (line {idx+1}). Skipping.")

    if not valid_queries_data_list:
        print("No valid query fingerprints generated.")
        return
    QUERY_FINGERPRINTS_DATA = valid_queries_data_list
    print(f"Generated fingerprints for {len(QUERY_FINGERPRINTS_DATA)} valid queries.")

    # 2. Read Target SMILES
    print(f"Reading target SMILES from: {input_smi}")
    target_smi_lines_with_original_indices = []  # Stores (original_index, smi)
    try:
        with open(input_smi, 'r') as f_target:
            raw_lines = f_target.read().splitlines()
            for idx, line in enumerate(raw_lines):
                smi = line.strip().split(None, 1)[0]  # Extract SMILES
                if smi:
                    target_smi_lines_with_original_indices.append((idx, smi))
    except FileNotFoundError:
        print(f"Error: Target file not found: {input_smi}")
        return
    except Exception as e:
        print(f"Error reading target file: {e}")
        return

    if not target_smi_lines_with_original_indices:
        print("No target SMILES found in input file.")
        return
    num_targets = len(target_smi_lines_with_original_indices)

    # 3. Parallel Processing
    actual_num_threads = min(num_threads, num_targets) if num_targets > 0 else 1
    split_len = math.ceil(num_targets / actual_num_threads) if actual_num_threads > 0 and num_targets > 0 else 0

    line_splits = []  # Each element is a list of (original_target_idx, target_smi)
    if split_len > 0:
        for i in range(actual_num_threads):
            start = i * split_len
            end = (i + 1) * split_len
            if start < num_targets:
                line_splits.append(target_smi_lines_with_original_indices[start:end])
    else:
        print("No target data to process or invalid threading configuration.")
        return

    # This list will store all results in the original order of target SMILES
    # Each element will be a list of scores for the corresponding target SMILES
    all_target_scores_ordered = [[None] * len(QUERY_FINGERPRINTS_DATA) for _ in range(num_targets)]

    if line_splits:
        print(f"Starting similarity calculation with {actual_num_threads} threads for {len(QUERY_FINGERPRINTS_DATA)} queries and {num_targets} targets.")
        with Pool(actual_num_threads) as pool:
            # imap_unordered returns an iterator of results as they complete
            # calculate_similarity_chunk_c now processes chunks with original indices
            pool_results = list(tqdm.tqdm(pool.imap_unordered(calculate_similarity_chunk_c, line_splits), total=len(line_splits), desc="Calculating Similarities"))

        print("Aggregating results in order...")
        # Aggregate from list of lists of tuples
        for chunk_result_list_with_indices in pool_results:
            for original_idx, scores in chunk_result_list_with_indices:
                all_target_scores_ordered[original_idx] = scores
    else:
        print("No target data to process.")

    # 4. Write Output CSV Matrix (scores only)
    print(f"Writing similarity scores to '{output_csv}'...")
    try:
        with open(output_csv, 'w', newline='') as f_csv:
            writer = csv.writer(f_csv)
            # Write header: Query_OrigLine_1, Query_OrigLine_X, ...
            header = [f"Query_OrigLine_{item['original_index']+1}" for item in QUERY_FINGERPRINTS_DATA]
            writer.writerow(header)

            written_count = 0
            for scores_list in all_target_scores_ordered:
                # Format scores to 3 decimal places, treat None as "N/A"
                formatted_scores = [f"{score:.3f}" if score is not None else "N/A" for score in scores_list]
                writer.writerow(formatted_scores)
                written_count += 1

            print(f"Score matrix saved successfully. Wrote {written_count} rows (corresponding to targets).")
            if written_count != num_targets:
                print(f"Warning: Number of rows written ({written_count}) does not match number of input targets ({num_targets}). This might indicate issues.")

    except Exception as e:
        print(f"Error writing CSV output file '{output_csv}': {e}")

    print("\nProcessing complete.")


# Main entry point for the command line
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Calculate Tanimoto similarity matrix (CSV output, scores only) using Morgan fingerprints.")
    parser.add_argument("-i", "--input_smi", required=True, help="Path to the input SMILES file containing target molecules.")
    parser.add_argument("-q", "--query_smi_file", required=True, help="Path to the SMILES file containing query molecules.")
    parser.add_argument("-o", "--output_csv", required=True, help="Path to the output CSV file for the similarity scores matrix (no target SMILES column).")
    parser.add_argument("-n", "--num_threads", type=int, default=os.cpu_count(), help=f"Number of threads to use. (Default: {os.cpu_count()})")
    parser.add_argument("-r", "--radius", type=int, default=2, help="Radius for Morgan fingerprint. (Default: 2)")

    parsed_args = parser.parse_args()

    # Call the function with parsed arguments
    process_queries_and_targets(
        input_smi=parsed_args.input_smi,
        query_smi_file=parsed_args.query_smi_file,
        output_csv=parsed_args.output_csv,
        num_threads=parsed_args.num_threads,
        radius=parsed_args.radius
    )
