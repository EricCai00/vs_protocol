#!/usr/bin/env python3
"""
result_analysis.py

Module 6: Result Analysis

Consolidates docking scores with upstream module outputs (H-bond analysis,
physicochemical properties, ADMET scores, drug-likeness predictions) into a
ranked hit list, summary statistics, and export-ready CSV/HTML reports.

Ranking logic:
  Each available metric is min-max normalised to [0, 1] and multiplied by its
  configurable weight.  A higher composite score → better candidate.

  - Docking score   (lower raw value = better binding → sign is flipped)
  - Key-residue H-bonds (higher = better)
  - ADMET score        (higher = better)
  - Drug-likeness count (higher = better; number of models that predict > 0.5)
"""

import os
import textwrap
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_asc(series: pd.Series) -> pd.Series:
    """Normalise so that LOWER raw values map to HIGHER normalised values (0-1)."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(np.ones(len(series)), index=series.index)
    return (hi - series) / (hi - lo)


def _norm_desc(series: pd.Series) -> pd.Series:
    """Normalise so that HIGHER raw values map to HIGHER normalised values (0-1)."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(np.ones(len(series)), index=series.index)
    return (series - lo) / (hi - lo)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_result_analysis(
    project_name: str,
    project_dir: str,
    dock_dir: str,
    pc_dir: Optional[str] = None,
    admet_dir: Optional[str] = None,
    dln_dir: Optional[str] = None,
    output_suffix: str = "",
    top_n: int = 500,
    weight_docking: float = 1.0,
    weight_hbond: float = 0.5,
    weight_admet: float = 0.5,
    weight_druglikeness: float = 0.3,
    export_html: bool = False,
) -> str:
    """
    Build a ranked hit-list from all upstream module outputs.

    Parameters
    ----------
    project_name    : project identifier (used for file path inference)
    project_dir     : root project directory
    dock_dir        : directory produced by the docking module
    pc_dir          : physicochemical directory (Module 3a), or None to skip
    admet_dir       : ADMET directory (Module 3b), or None to skip
    dln_dir         : drug-likeness directory (Module 3c), or None to skip
    output_suffix   : optional suffix appended to docked-output directory name
    top_n           : number of top-ranked compounds to include in the report
    weight_docking  : composite-score weight for normalised docking score
    weight_hbond    : composite-score weight for key-residue H-bond count
    weight_admet    : composite-score weight for ADMET score
    weight_druglikeness : composite-score weight for drug-likeness count
    export_html     : whether to also write an HTML report

    Returns
    -------
    Path to the ranked hit-list CSV.
    """

    result_dir = os.path.join(project_dir, "result_analysis")
    os.makedirs(result_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Docking scores (required)
    # ------------------------------------------------------------------
    score_path = os.path.join(dock_dir, f"{project_name}_dock_scores.txt")
    if not os.path.isfile(score_path):
        raise FileNotFoundError(
            f"Docking score file not found: {score_path}\n"
            "Please run the docking module (Module 5) before result analysis."
        )
    df = pd.read_csv(score_path)           # columns: score, name
    df = df.rename(columns={"name": "compound_id", "score": "dock_score"})
    df["dock_score"] = pd.to_numeric(df["dock_score"], errors="coerce")
    df = df.dropna(subset=["dock_score"])
    print(f"  Loaded {len(df):,} docking scores from {score_path}")

    # ------------------------------------------------------------------
    # 2. H-bond analysis (optional)
    # ------------------------------------------------------------------
    hbond_path = os.path.join(dock_dir, "hbond_counts.csv")
    if os.path.isfile(hbond_path):
        hb = pd.read_csv(hbond_path)       # columns: ligand_name, total_hbonds, key_residue_hbonds
        hb = hb.rename(columns={"ligand_name": "compound_id"})
        df = df.merge(hb[["compound_id", "total_hbonds", "key_residue_hbonds"]],
                      on="compound_id", how="left")
        print(f"  Merged H-bond data ({len(hb):,} entries) from {hbond_path}")
    else:
        warnings.warn(f"H-bond file not found ({hbond_path}); skipping.")
        df["total_hbonds"] = np.nan
        df["key_residue_hbonds"] = np.nan

    # ------------------------------------------------------------------
    # 3. Physicochemical properties (optional)
    # ------------------------------------------------------------------
    pc_cols_keep = ["MW", "LogP", "QED", "SAscore", "TPSA", "nHD", "nHA", "nRot"]
    if pc_dir and os.path.isdir(pc_dir):
        pc_file = os.path.join(pc_dir, "physchem.csv")
        if os.path.isfile(pc_file):
            pc = pd.read_csv(pc_file)
            if "name" in pc.columns:
                pc = pc.rename(columns={"name": "compound_id"})
            avail = [c for c in pc_cols_keep if c in pc.columns]
            df = df.merge(pc[["compound_id"] + avail], on="compound_id", how="left")
            print(f"  Merged physicochemical properties ({len(pc):,} entries, "
                  f"cols: {avail}) from {pc_file}")
        else:
            warnings.warn(f"Physicochemical file not found ({pc_file}); skipping.")
    else:
        warnings.warn("pc_dir not set or not found; skipping physicochemical merge.")

    # ------------------------------------------------------------------
    # 4. ADMET scores (optional)
    # ------------------------------------------------------------------
    if admet_dir and os.path.isdir(admet_dir):
        admet_score_file = os.path.join(admet_dir, f"admetlab_score_{project_name}.csv")
        if os.path.isfile(admet_score_file):
            admet = pd.read_csv(admet_score_file)   # columns: name, score
            admet = admet.rename(columns={"name": "compound_id", "score": "admet_score"})
            df = df.merge(admet[["compound_id", "admet_score"]], on="compound_id", how="left")
            print(f"  Merged ADMET scores ({len(admet):,} entries) from {admet_score_file}")
        else:
            warnings.warn(f"ADMET score file not found ({admet_score_file}); skipping.")
    else:
        warnings.warn("admet_dir not set or not found; skipping ADMET merge.")

    # ------------------------------------------------------------------
    # 5. Drug-likeness predictions (optional)
    # ------------------------------------------------------------------
    dln_model_names = ["generaldl", "specdl-ftt", "specdl-zinc", "specdl-cm", "specdl-cp"]
    if dln_dir and os.path.isdir(dln_dir):
        dln_files_found = []
        for model in dln_model_names:
            fp = os.path.join(dln_dir, f"druglikeness_{model}.csv")
            if os.path.isfile(fp):
                dln_files_found.append((model, fp))

        if dln_files_found:
            # Reconstruct name list from the first available file length
            # The dln CSVs have predictions in row order matching the input library;
            # we cannot join them directly unless a name column exists.
            # Use the first file to check for a name column, else fall back to index join.
            first_model, first_fp = dln_files_found[0]
            first_df = pd.read_csv(first_fp)
            has_name_col = "name" in first_df.columns or "compound_id" in first_df.columns

            if has_name_col:
                name_col = "name" if "name" in first_df.columns else "compound_id"
                dln_merge = first_df[[name_col, "prediction"]].rename(
                    columns={name_col: "compound_id", "prediction": f"dln_{first_model}"}
                )
                for model, fp in dln_files_found[1:]:
                    tmp = pd.read_csv(fp)[[name_col, "prediction"]].rename(
                        columns={name_col: "compound_id", "prediction": f"dln_{model}"}
                    )
                    dln_merge = dln_merge.merge(tmp, on="compound_id", how="outer")
                df = df.merge(dln_merge, on="compound_id", how="left")
            else:
                # Row-order join: assumes dln CSVs are in the same order as docking results
                warnings.warn(
                    "Drug-likeness CSV files have no 'name' column; "
                    "skipping drug-likeness merge to avoid row-order mismatches."
                )
                dln_files_found = []

            if dln_files_found:
                dln_cols = [f"dln_{m}" for m, _ in dln_files_found]
                present = [c for c in dln_cols if c in df.columns]
                df["dln_count"] = (df[present] > 0.5).sum(axis=1)
                print(f"  Merged drug-likeness predictions "
                      f"({len(dln_files_found)} models: {[m for m,_ in dln_files_found]}) "
                      f"from {dln_dir}")
        else:
            warnings.warn(f"No drug-likeness CSV files found in {dln_dir}; skipping.")
    else:
        warnings.warn("dln_dir not set or not found; skipping drug-likeness merge.")

    # ------------------------------------------------------------------
    # 6. Composite scoring
    # ------------------------------------------------------------------
    composite = pd.Series(np.zeros(len(df)), index=df.index)
    weight_total = 0.0

    # Docking score (lower = better → ascending normalisation)
    norm_dock = _norm_asc(df["dock_score"])
    composite += weight_docking * norm_dock
    weight_total += weight_docking

    # Key-residue H-bonds (higher = better)
    if "key_residue_hbonds" in df.columns and df["key_residue_hbonds"].notna().any():
        filled = df["key_residue_hbonds"].fillna(0.0)
        composite += weight_hbond * _norm_desc(filled)
        weight_total += weight_hbond

    # ADMET score (higher = better)
    if "admet_score" in df.columns and df["admet_score"].notna().any():
        filled = df["admet_score"].fillna(df["admet_score"].median())
        composite += weight_admet * _norm_desc(filled)
        weight_total += weight_admet

    # Drug-likeness count (higher = better)
    if "dln_count" in df.columns and df["dln_count"].notna().any():
        filled = df["dln_count"].fillna(0.0)
        composite += weight_druglikeness * _norm_desc(filled)
        weight_total += weight_druglikeness

    df["composite_score"] = composite / weight_total
    df["rank"] = df["composite_score"].rank(ascending=False, method="min").astype(int)
    df = df.sort_values("rank")

    # ------------------------------------------------------------------
    # 7. Export ranked CSV
    # ------------------------------------------------------------------
    # Reorder columns: identifiers first, then scores, then molecular props
    front_cols = ["rank", "compound_id", "dock_score", "composite_score"]
    score_cols = [c for c in ["key_residue_hbonds", "total_hbonds",
                               "admet_score", "dln_count"] if c in df.columns]
    pc_present = [c for c in pc_cols_keep if c in df.columns]
    dln_model_cols = [c for c in df.columns if c.startswith("dln_") and c != "dln_count"]
    ordered = front_cols + score_cols + pc_present + dln_model_cols
    remaining = [c for c in df.columns if c not in ordered]
    df = df[ordered + remaining]

    ranked_csv = os.path.join(result_dir, f"{project_name}_ranked_hits.csv")
    df.to_csv(ranked_csv, index=False, float_format="%.4f")
    print(f"  Ranked hit-list ({len(df):,} compounds) → {ranked_csv}")

    # ------------------------------------------------------------------
    # 8. Top-N hit-list
    # ------------------------------------------------------------------
    top_df = df.head(top_n)
    top_csv = os.path.join(result_dir, f"{project_name}_top{top_n}_hits.csv")
    top_df.to_csv(top_csv, index=False, float_format="%.4f")
    print(f"  Top-{top_n} hits → {top_csv}")

    # ------------------------------------------------------------------
    # 9. Summary report (plain text)
    # ------------------------------------------------------------------
    summary_path = os.path.join(result_dir, f"{project_name}_summary.txt")
    _write_summary(df, top_df, project_name, summary_path,
                   weights=dict(docking=weight_docking, hbond=weight_hbond,
                                admet=weight_admet, druglikeness=weight_druglikeness))
    print(f"  Summary report → {summary_path}")

    # ------------------------------------------------------------------
    # 10. Optional HTML report
    # ------------------------------------------------------------------
    if export_html:
        html_path = os.path.join(result_dir, f"{project_name}_top{top_n}_report.html")
        _write_html(top_df, project_name, html_path, top_n)
        print(f"  HTML report → {html_path}")

    return ranked_csv


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _write_summary(df: pd.DataFrame, top_df: pd.DataFrame,
                   project_name: str, path: str, weights: dict) -> None:
    total = len(df)
    top_n = len(top_df)

    lines = [
        "=" * 70,
        f"  Virtual Screening Result Analysis — {project_name}",
        "=" * 70,
        "",
        f"  Total compounds ranked : {total:,}",
        f"  Top-N report size      : {top_n:,}",
        "",
        "  Composite score weights used:",
        f"    Docking score      : {weights['docking']:.2f}",
        f"    Key-residue H-bonds: {weights['hbond']:.2f}",
        f"    ADMET score        : {weights['admet']:.2f}",
        f"    Drug-likeness count: {weights['druglikeness']:.2f}",
        "",
        "  --- Docking score statistics (kcal/mol) ---",
        f"    Min   : {df['dock_score'].min():.3f}",
        f"    Mean  : {df['dock_score'].mean():.3f}",
        f"    Median: {df['dock_score'].median():.3f}",
        f"    Max   : {df['dock_score'].max():.3f}",
        "",
    ]

    if "key_residue_hbonds" in df.columns:
        has_hb = df["key_residue_hbonds"].notna()
        n_with_hb = int((df.loc[has_hb, "key_residue_hbonds"] > 0).sum())
        pct = 100 * n_with_hb / total if total else 0
        lines += [
            "  --- H-bond statistics ---",
            f"    Compounds with ≥1 key-residue H-bond : {n_with_hb:,} ({pct:.1f}%)",
            f"    Mean key-residue H-bonds (top {top_n})  : "
            f"{top_df['key_residue_hbonds'].mean():.2f}",
            "",
        ]

    if "admet_score" in df.columns:
        lines += [
            "  --- ADMET score statistics ---",
            f"    Mean (all) : {df['admet_score'].mean():.4f}",
            f"    Mean (top {top_n}): {top_df['admet_score'].mean():.4f}",
            "",
        ]

    if "dln_count" in df.columns:
        lines += [
            "  --- Drug-likeness statistics ---",
            f"    Mean model-consensus count (all)   : {df['dln_count'].mean():.2f}",
            f"    Mean model-consensus count (top {top_n}): {top_df['dln_count'].mean():.2f}",
            "",
        ]

    lines += [
        "  --- Top-10 compounds by composite score ---",
        "",
    ]
    display_cols = ["rank", "compound_id", "dock_score", "composite_score"]
    display_cols += [c for c in ["key_residue_hbonds", "admet_score", "dln_count"]
                     if c in df.columns]
    header = "  " + "  ".join(f"{c:<22}" for c in display_cols)
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for _, row in df.head(10).iterrows():
        vals = []
        for c in display_cols:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:<22.4f}")
            else:
                vals.append(f"{str(v):<22}")
        lines.append("  " + "  ".join(vals))

    lines += ["", "=" * 70]

    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _write_html(top_df: pd.DataFrame, project_name: str, path: str, top_n: int) -> None:
    """Write a self-contained HTML table report."""
    display_cols = ["rank", "compound_id", "dock_score", "composite_score"]
    display_cols += [c for c in ["key_residue_hbonds", "total_hbonds",
                                  "admet_score", "dln_count",
                                  "MW", "LogP", "QED", "SAscore", "TPSA"]
                     if c in top_df.columns]
    sub = top_df[display_cols].copy()

    def _colour_row(row):
        rank = row.get("rank", None)
        if rank is None:
            return [""] * len(row)
        if rank <= 10:
            bg = "#d4edda"
        elif rank <= 50:
            bg = "#fff3cd"
        else:
            bg = ""
        return [f"background-color: {bg}" if bg else "" for _ in row]

    styled = (
        sub.style
        .apply(_colour_row, axis=1)
        .format({c: "{:.4f}" for c in sub.select_dtypes("float").columns})
        .set_caption(f"Top-{top_n} Virtual Screening Hits — {project_name}")
        .set_table_styles([
            {"selector": "caption",
             "props": [("font-size", "1.3em"), ("font-weight", "bold"),
                       ("text-align", "left"), ("margin-bottom", "8px")]},
            {"selector": "th",
             "props": [("background-color", "#343a40"), ("color", "white"),
                       ("padding", "6px 10px"), ("text-align", "center")]},
            {"selector": "td",
             "props": [("padding", "4px 10px"), ("text-align", "center"),
                       ("font-family", "monospace")]},
            {"selector": "table",
             "props": [("border-collapse", "collapse"), ("width", "100%")]},
            {"selector": "tr:nth-child(even)",
             "props": [("background-color", "#f8f9fa")]},
        ])
    )

    html_body = styled.to_html()
    html = textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8"/>
          <title>VS Results — {project_name}</title>
        </head>
        <body style="font-family:sans-serif; margin:24px;">
        {html_body}
        </body>
        </html>
    """)
    with open(path, "w") as fh:
        fh.write(html)
