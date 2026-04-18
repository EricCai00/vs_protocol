import csv
from rdkit import Chem
import argparse

def filter_substructure(input_smi_filepath, substructure_smiles_list, output_csv_filepath, output_filtered_smi_filepath):
    # 1. Load substructures
    patterns = []
    valid_pattern_indices = []
    print("Loading substructures...")
    for idx, smiles_str in enumerate(substructure_smiles_list):
        pattern = Chem.MolFromSmiles(smiles_str)
        patterns.append(pattern) # Store pattern or None
        if pattern is None:
            print(f"  WARNING: Substructure {idx+1} ('{smiles_str}') failed to load.")
        else:
            valid_pattern_indices.append(idx) # Keep track of valid ones

    if not valid_pattern_indices:
        print("ERROR: No valid substructures could be created. Exiting.")
        return

    match_matrix_rows = []
    molecules_with_at_least_one_match_lines = []
    header = ["Input_SMILES", "ID"] + [f"Substruct_{i+1}" for i in range(len(patterns))]
    match_matrix_rows.append(header)

    # 2. Process input SMILES file
    print(f"Processing molecules from '{input_smi_filepath}'...")
    try:
        with open(input_smi_filepath, 'r') as f_in:
            for i, line in enumerate(f_in):
                line = line.strip()
                if not line: continue

                parts = line.split(None, 1)
                smiles_mol_str = parts[0]
                mol_id = parts[1] if len(parts) > 1 else f"Mol_{i+1}"
                row_data = [smiles_mol_str, mol_id]
                mol = Chem.MolFromSmiles(smiles_mol_str)

                if mol is None:
                    print(f"  WARNING: Could not parse SMILES: '{smiles_mol_str}'. Marking as errors.")
                    row_data.extend(["ERROR"] * len(patterns)) # Mark parse error in CSV
                    match_matrix_rows.append(row_data)
                    continue

                current_mol_match_statuses = [0] * len(patterns)
                has_at_least_one_match = False
                for pattern_idx in valid_pattern_indices: # Only check valid patterns
                     pattern = patterns[pattern_idx]
                     if mol.HasSubstructMatch(pattern):
                         current_mol_match_statuses[pattern_idx] = 1
                         has_at_least_one_match = True
                
                row_data.extend(current_mol_match_statuses)
                match_matrix_rows.append(row_data)

                if has_at_least_one_match:
                    molecules_with_at_least_one_match_lines.append(line)

    except FileNotFoundError:
        print(f"ERROR: Input file not found: '{input_smi_filepath}'")
        return
    except Exception as e:
        print(f"ERROR processing file '{input_smi_filepath}': {e}")
        return

    # 3. Write the matching matrix to CSV
    print(f"Writing matching matrix to '{output_csv_filepath}'...")
    try:
        with open(output_csv_filepath, 'w', newline='') as f_csv:
            writer = csv.writer(f_csv)
            writer.writerows(match_matrix_rows)
        print(f"Matrix saved successfully. Rows: {len(match_matrix_rows)-1}")
    except Exception as e:
        print(f"ERROR writing CSV file '{output_csv_filepath}': {e}")

    # 4. Write the filtered SMILES file
    print(f"Writing filtered SMILES to '{output_filtered_smi_filepath}'...")
    if molecules_with_at_least_one_match_lines:
        try:
            with open(output_filtered_smi_filepath, 'w') as f_filtered_smi:
                for line_content in molecules_with_at_least_one_match_lines:
                    f_filtered_smi.write(line_content + "\n")
            print(f"{len(molecules_with_at_least_one_match_lines)} molecules saved.")
        except Exception as e:
            print(f"ERROR writing filtered SMILES file '{output_filtered_smi_filepath}': {e}")
    else:
        print("No molecules matched any substructures. Filtered SMILES file is empty.")
        open(output_filtered_smi_filepath, 'w').close() # Create empty file

    print("\nProcessing complete.")

if __name__ == '__main__':
    usage = 'substructure.py -i <input_smi> -o <output_dir> -l <substructure_list>'

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-i', '--input_smi')
    parser.add_argument('-o', '--output_dir')
    parser.add_argument('-l', '--substructure_list')
    args = parser.parse_args()
    with open(args.substructure_list) as f:
        substructure_smiles_input = f.read().splitlines()

    input_smi_file = args.input_smi
    output_csv_file = f'{args.output_dir}/matching_pattern_matrix.csv'
    output_filtered_smi_file = f'{args.output_dir}/matched_at_least_one.smi'
    filter_substructure(
        input_smi_filepath=input_smi_file,
        substructure_smiles_list=substructure_smiles_input,
        output_csv_filepath=output_csv_file,
        output_filtered_smi_filepath=output_filtered_smi_file
    )