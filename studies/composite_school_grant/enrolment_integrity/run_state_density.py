from __future__ import annotations

import csv
import math
import os
import re
import runpy
import tempfile
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

P = runpy.run_path(
    "studies/composite_school_grant/scripts/03_build_panel.py",
    run_name="state_density_lib",
)
extract = P["extract_archive"]
csv_source = P["csv_source"]
source_columns = P["source_columns"]
identify_early_social_labels = P["identify_early_social_labels"]
qid = P["qid"]
lit = P["lit"]
ref = P["ref"]
nref = P["nref"]

BROAD_STATE = {1, 2, 3, 6, 89, 90}
POLICY_LINES = (30.5, 100.5, 250.5)


def ident(cols: dict[str, str]) -> str:
    x = cols.get("pseudocode") or cols.get("psuedocode")
    if not x:
        raise RuntimeError("School identifier missing")
    return x


def enrol_filter(con, src: str, cols: dict[str, str]) -> str:
    if "item_group" in cols and "item_id" in cols:
        return f"{nref(cols, 'item_group')}=1 AND {nref(cols, 'item_id')} IN (1,2,3,4)"
    labels = identify_early_social_labels(con, src, cols)
    if not labels:
        raise RuntimeError("Could not identify social-category rows")
    d = ref(cols, "item_desc")
    return f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labels)})"


def enrol_sum(cols: dict[str, str]) -> str:
    terms = [
        f"COALESCE({nref(cols, f'c{k}_{sex}')},0)"
        for k in range(1, 13)
        for sex in ("b", "g")
        if f"c{k}_{sex}" in cols
    ]
    if not terms:
        raise RuntimeError("No Class I-XII enrolment columns found")
    return " + ".join(terms)


def pick_state_expr(cols: dict[str, str]) -> str:
    # Prefer an explicit name field when available. UDISE extracts often expose `state`
    # itself as the state-name field, so retain it before falling back to code-like fields.
    for name in ("state_name", "statename", "state", "state_id", "state_code", "state_cd"):
        r = ref(cols, name)
        if r:
            return f"CAST({r} AS VARCHAR)"
    raise RuntimeError("No state field found")


def safe_slug(value: str) -> str:
    x = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip()).strip("_")
    return x[:100] or "unknown_state"


def density_counts(z: pd.DataFrame) -> pd.Series:
    return z.groupby("enrol").size().reindex(range(0, 401), fill_value=0)


def draw_individual(z: pd.DataFrame, state: str, year: str, path: Path) -> None:
    g = density_counts(z)
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(g.index, g.values, linewidth=1)
    for x in POLICY_LINES:
        ax.axvline(x, linestyle="--", linewidth=1)
    ax.set_xlim(0, 400)
    ax.set_xlabel("Reported total enrolment, Classes I-XII")
    ax.set_ylabel("Number of schools")
    ax.set_title(f"{state} — {year}: school count by reported enrolment (broad State-government sample)")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_contact_sheet(df: pd.DataFrame, states: list[str], year: str, path: Path) -> None:
    # Normalize by each State/UT's own 0-400 school count so small jurisdictions remain visible.
    ncols = 4
    nrows = math.ceil(len(states) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(18, max(4, 2.8 * nrows)), squeeze=False)
    for ax, state in zip(axes.ravel(), states):
        z = df[df.state == state]
        g = density_counts(z)
        denom = max(float(g.sum()), 1.0)
        ax.plot(g.index, 100.0 * g.values / denom, linewidth=0.8)
        for x in POLICY_LINES:
            ax.axvline(x, linestyle="--", linewidth=0.6)
        ax.set_xlim(0, 400)
        ax.set_title(str(state), fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes.ravel()[len(states):]:
        ax.axis("off")
    fig.suptitle(
        f"{year}: State/UT enrolment densities, broad State-government sample\n"
        "Each panel uses percentage of that State/UT's schools with enrolment 0–400; dashed lines at 30/31, 100/101 and 250/251",
        fontsize=13,
    )
    fig.supxlabel("Reported total enrolment, Classes I-XII")
    fig.supylabel("Percent of State/UT schools in 0–400 range")
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.965))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    year = os.environ["YEAR"]
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path(f"studies/composite_school_grant/outputs/state_density/{year}")
    graph_dir = out / "individual_states"
    graph_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    with tempfile.TemporaryDirectory(prefix=f"state_density_{year}_") as td:
        root = Path(td)
        en_src = csv_source(extract(repo, token, year, "enrolment_1", root))
        p1_src = csv_source(extract(repo, token, year, "profile_1", root))
        ec = source_columns(con, en_src)
        pc = source_columns(con, p1_src)
        ei = ident(ec)
        pi = ident(pc)
        ef = enrol_filter(con, en_src, ec)
        es = enrol_sum(ec)
        state_expr = pick_state_expr(pc)
        management_expr = nref(pc, "managment")

        con.execute(
            f"""
            CREATE TEMP TABLE ee AS
            SELECT CAST({qid(ei)} AS VARCHAR) AS pseudocode,
                   CAST(SUM({es}) AS INTEGER) AS enrol
            FROM {en_src}
            WHERE {ef}
            GROUP BY 1
            """
        )
        d = con.execute(
            f"""
            SELECT e.pseudocode,
                   e.enrol,
                   {state_expr} AS state,
                   CAST({management_expr} AS INTEGER) AS management
            FROM ee e
            JOIN {p1_src} p
              ON e.pseudocode = CAST(p.{qid(pi)} AS VARCHAR)
            WHERE e.enrol BETWEEN 0 AND 400
            """
        ).df()
        con.close()

    d = d[d.management.isin(BROAD_STATE)].copy()
    d = d[d.state.notna()].copy()
    d["state"] = d["state"].astype(str).str.strip()
    states = sorted([s for s in d.state.unique().tolist() if s and s.lower() not in {"nan", "none"}])

    index_rows: list[dict] = []
    count_rows: list[dict] = []
    for state in states:
        z = d[d.state == state].copy()
        slug = safe_slug(state)
        filename = f"density_0_400_{slug}.png"
        draw_individual(z, state, year, graph_dir / filename)
        g = density_counts(z)
        index_rows.append(
            {
                "academic_year": year,
                "state": state,
                "n_schools_0_400": int(len(z)),
                "graph_file": f"individual_states/{filename}",
                "count_at_50": int(g.loc[50]),
                "count_at_100": int(g.loc[100]),
                "count_at_250": int(g.loc[250]),
                "count_at_251": int(g.loc[251]),
            }
        )
        for enrol, n in g.items():
            count_rows.append(
                {
                    "academic_year": year,
                    "state": state,
                    "enrolment": int(enrol),
                    "school_count": int(n),
                }
            )

    draw_contact_sheet(d, states, year, out / f"ALL_STATES_contact_sheet_{year}.png")
    write_csv(out / "STATE_GRAPH_INDEX.csv", index_rows)
    write_csv(out / "state_density_counts_0_400.csv", count_rows)

    lines = [
        f"# State-wise 0–400 enrolment density graphs — {year}",
        "",
        f"Generated {len(states)} State/UT-specific graphs using the broad State-government management universe: codes 1, 2, 3, 6, 89 and 90.",
        "",
        "Each individual graph is the same descriptive density design as the national 0–400 plot and marks the CSG boundaries at 30/31, 100/101 and 250/251.",
        "",
        "The contact sheet normalizes each panel to percentages only so that small State/UT distributions remain visually legible. Individual PNGs retain raw school counts on the y-axis.",
        "",
        "These graphs are descriptive. A spike at a round number is not by itself evidence of manipulation.",
        "",
        "## Files",
        "",
        f"- `ALL_STATES_contact_sheet_{year}.png`",
        "- `individual_states/*.png`",
        "- `STATE_GRAPH_INDEX.csv`",
        "- `state_density_counts_0_400.csv`",
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {len(states)} state/UT graphs for {year}", flush=True)
    print("States:", states, flush=True)


if __name__ == "__main__":
    main()
