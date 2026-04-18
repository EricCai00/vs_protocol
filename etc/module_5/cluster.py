#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import sys
import argparse
import chemfp
from chemfp import search

def taylor_butina_cluster(similarity_table):
    """
    Perform Taylor-Butina clustering on a symmetric Tanimoto similarity table.
    Returns a list of (centroid_index, member_indices_set).
    This function remains unchanged as its logic is correct and efficient.
    """
    # Build a list of (cluster_size, index, neighbor_indices) sorted descending by cluster_size
    centroid_table = sorted(
        ((len(indices), i, indices)
         for (i, indices) in enumerate(similarity_table.iter_indices())),
        reverse=True
    )

    clusters = []
    seen = set()
    for _, fp_idx, members in centroid_table:
        if fp_idx in seen:
            continue
        # This fingerprint is a new centroid. Mark it as seen.
        seen.add(fp_idx)
        # Find members of its cluster which have not yet been assigned to any other cluster.
        # The centroid's own index is in 'members', but it is removed here because it's already in 'seen'.
        unassigned = set(members) - seen
        
        # The centroid and the unassigned neighbors form the new cluster.
        clusters.append((fp_idx, unassigned))
        
        # Mark the newly assigned members as seen.
        seen.update(unassigned)

    return clusters


def run_clustering(fingerprint_file, threshold, output_dir):
    """
    1) Load a fingerprint arena from `fingerprint_file`.
    2) Build an all-vs-all symmetric thresholded Tanimoto search table.
    3) Run Taylor-Butina clustering.
    4) Write cluster representatives to 'cluster_representatives.txt'.
    5) Write detailed cluster information (members and similarities) to 'clusters_detailed.txt'.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print("Loading fingerprints from: {0}".format(fingerprint_file))
    try:
        arena = chemfp.load_fingerprints(fingerprint_file)
    except Exception as e:
        sys.stderr.write("ERROR: Failed to load fingerprints '{0}': {1}\n".format(fingerprint_file, e))
        sys.exit(1)

    print("Building symmetric Tanimoto search table (threshold = {0}) ...".format(threshold))
    # This table contains all pairs of fingerprints with similarity >= threshold
    sim_table = search.threshold_tanimoto_search_symmetric(arena, threshold=float(threshold))

    print("Performing Taylor–Butina clustering ...")
    clusters = taylor_butina_cluster(sim_table)

    # --- BLOCK 1: Write original simple output (UNCHANGED) ---
    reps_out = os.path.join(output_dir, 'cluster_representatives.txt')
    try:
        with open(reps_out, 'w') as f_out:
            for centroid_idx, member_indices in clusters:
                f_out.write(arena.ids[centroid_idx] + "\n")
        print("Saved {0} representatives to: {1}".format(len(clusters), reps_out))
    except Exception as e:
        sys.stderr.write("ERROR: Could not write representatives file: {0}\n".format(e))
        sys.exit(1)

    # --- BLOCK 2: Write new detailed output (NEWLY ADDED) ---
    detailed_out = os.path.join(output_dir, 'clusters_detailed.txt')
    try:
        with open(detailed_out, 'w') as f_out:
            f_out.write("# Detailed cluster information from Taylor-Butina clustering\n")
            f_out.write("# Tanimoto threshold = {0}\n".format(threshold))
            f_out.write("# Format: Member_ID   Similarity_to_Centroid\n\n")

            total_clustered_fps = 0
            # Sort clusters by size (largest first) for more readable output
            sorted_clusters = sorted(clusters, key=lambda x: len(x[1]), reverse=True)

            for i, (centroid_idx, member_indices) in enumerate(sorted_clusters):
                cluster_size = len(member_indices) + 1 # +1 for the centroid itself
                total_clustered_fps += cluster_size
                centroid_id = arena.ids[centroid_idx]

                f_out.write("--- Cluster {0} (size: {1}, centroid: {2}) ---\n".format(i + 1, cluster_size, centroid_id))

                # To get similarity scores, we query the sim_table.
                # sim_table[centroid_idx] efficiently returns all neighbors and their scores.
                # We convert it to a dictionary for fast lookups.
                neighbor_scores = dict(sim_table[centroid_idx])

                # Write the centroid itself (similarity to itself is 1.0)
                f_out.write("{0}\t1.0000\t(centroid)\n".format(centroid_id))

                # Sort members by similarity to the centroid (highest first)
                sorted_members = sorted(
                    list(member_indices),
                    key=lambda m_idx: neighbor_scores.get(m_idx, 0.0),
                    reverse=True
                )

                for member_idx in sorted_members:
                    member_id = arena.ids[member_idx]
                    # The score should always be found, but .get() is safer
                    score = neighbor_scores.get(member_idx, 0.0)
                    f_out.write("{0}\t{1:.4f}\n".format(member_id, score))
                
                f_out.write("\n") # Add a blank line for readability

        # --- BLOCK 3: Print summary statistics (NEWLY ADDED) ---
        print("Saved {0} clusters to: {1}".format(len(clusters), detailed_out))

    except Exception as e:
        sys.stderr.write("ERROR: Could not write detailed clusters file: {0}\n".format(e))
        sys.exit(1)

    print("\nClustering complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Cluster a fingerprint file using Taylor–Butina (thresholded Tanimoto)."
    )
    parser.add_argument(
        '-f', '--fingerprints',
        required=True,
        help="Path to a ChemFP fingerprint file (.fps or .txt)"
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
        fingerprint_file=args.fingerprints,
        threshold=args.threshold,
        output_dir=args.output_dir
    )