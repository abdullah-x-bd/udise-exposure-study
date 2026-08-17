from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import RTE_CUTOFFS, bh_qvalues, build_panel, fit_wls_clustered, write_json, write_rows
from cluster_harmonization import state_sql

OUT = Path("studies/muslim_government_school_equity/outputs/rte_timing_hardened")
YEARS = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]


def _harmonize(panel: Path, con: duckdb.DuckDBPyConnection) -> Path:
    out = panel.with_name(panel.stem + "_state_lineage.parquet")
    qin = str(panel).replace("'", "''")
    qout = str(out).replace("'", "''")
    con.execute(
        f"COPY (SELECT * REPLACE ({state_sql('state')} AS state) FROM read_parquet('{qin}')) "
        f"TO '{qout}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    return out


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    year_case = "CASE academic_year " + " ".join(f"WHEN '{y}' THEN {i}" for i, y in enumerate(YEARS)) + " END"
    return con.execute(f"""
        WITH base AS (
          SELECT *, {year_case} AS year_index,
                 muslim_primary/NULLIF(enrol_primary,0) AS muslim_share,
                 sc_primary/NULLIF(enrol_primary,0) AS sc_share,
                 st_primary/NULLIF(enrol_primary,0) AS st_share,
                 obc_primary/NULLIF(enrol_primary,0) AS obc_share
          FROM read_parquet('{q}')
          WHERE enrol_primary IS NOT NULL
        ), w AS (
          SELECT *,
                 LAG(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_year_index,
                 LAG(muslim_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_muslim_share,
                 LAG(sc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_sc_share,
                 LAG(st_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_st_share,
                 LAG(obc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_obc_share,
                 LEAD(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS next_year_index,
                 LEAD(is_state_local_government) OVER (PARTITION BY pseudocode ORDER BY year_index) AS next_is_gov,
                 LEAD(enrol_primary) OVER (PARTITION BY pseudocode ORDER BY year_index) AS next_enrol_primary,
                 LEAD(total_teachers) OVER (PARTITION BY pseudocode ORDER BY year_index) AS next_total_teachers_raw,
                 LEAD(muslim_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead_muslim_share,
                 ARG_MIN(muslim_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_muslim_share
          FROM base
        )
        SELECT academic_year,year_index,pseudocode,state,district,rural_urban,management,
               is_state_local_government,is_core_government,enrol_primary,total_teachers,
               lag_muslim_share,lag_sc_share,lag_st_share,lag_obc_share,frozen_muslim_share,
               CASE WHEN next_year_index=year_index+1 THEN next_is_gov END AS next_is_gov,
               CASE WHEN next_year_index=year_index+1 THEN next_enrol_primary END AS next_enrol_primary,
               CASE WHEN next_year_index=year_index+1 AND next_is_gov=1 THEN next_total_teachers_raw END AS next_total_teachers,
               CASE WHEN next_year_index=year_index+1 THEN lead_muslim_share END AS lead_muslim_share
        FROM w
        WHERE is_state_local_government=1
          AND lowclass=1 AND highclass=5
          AND enrol_primary BETWEEN 30 AND 151
          AND state IS NOT NULL AND district IS NOT NULL
          AND lag_year_index=year_index-1
          AND lag_muslim_share IS NOT NULL
    """).df()


def _fit(d: pd.DataFrame, cutoff: float, *, exposure: str, cluster: str = "state",
         donut: bool = False, persistent: bool = True, bw: float = 20.0) -> dict | None:
    x = d.copy()
    r0 = pd.to_numeric(x["enrol_primary"], errors="coerce") - cutoff
    x = x.loc[r0.abs() <= bw].copy()
    if donut:
        x = x.loc[~pd.to_numeric(x["enrol_primary"], errors="coerce").isin([math.floor(cutoff), math.ceil(cutoff)])].copy()
    if persistent:
        next_e = pd.to_numeric(x["next_enrol_primary"], errors="coerce")
        now_above = pd.to_numeric(x["enrol_primary"], errors="coerce") >= math.ceil(cutoff)
        next_above = next_e >= math.ceil(cutoff)
        x = x.loc[next_e.notna() & (now_above == next_above)].copy()
    if len(x) < 500:
        return None

    r = pd.to_numeric(x["enrol_primary"], errors="coerce").to_numpy(float) - cutoff
    t = (r >= 0).astype(float)
    m = pd.to_numeric(x[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(x["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(x["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(x["lag_obc_share"], errors="coerce").to_numpy(float)
    rural = pd.to_numeric(x["rural_urban"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(x["management"], errors="coerce")

    cols = [t, r, t*r, m, t*m, r*m, t*r*m, sc, st, obc, rural]
    names = ["above", "running", "above_running", "muslim_share", "above_muslim_share",
             "running_muslim_share", "above_running_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban"]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            cols.append((mgmt.to_numpy(float) == code).astype(float))
            names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    w = np.maximum(0.0, 1.0 - np.abs(r) / bw)
    dy = (x["district"].astype(str) + "|" + x["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(x["next_total_teachers"], errors="coerce").to_numpy(float), X, w,
            x[cluster].to_numpy(object), absorb_groups=[dy], names=names,
        )
    except RuntimeError:
        return None
    key = "above_muslim_share"
    return {
        "cutoff": cutoff, "bandwidth": bw, "exposure": exposure, "cluster": cluster,
        "donut": int(donut), "persistent_side": int(persistent), "n": fit["n"], "clusters": fit["clusters"],
        "base_jump": fit["coef"]["above"], "base_jump_p": fit["p"]["above"],
        "muslim_interaction": fit["coef"][key], "muslim_interaction_se": fit["se"][key],
        "muslim_interaction_p": fit["p"][key], "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
    }


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='6GB'")
    with tempfile.TemporaryDirectory(prefix="rte_timing_hardened_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=True, facility=False, profile2=False)
        panel = _harmonize(panel, con)
        df = _prepare(panel, con)
        df.groupby("academic_year").agg(rows=("pseudocode","size"), schools=("pseudocode","nunique"), states=("state","nunique"), districts=("district","nunique")).reset_index().to_csv(OUT/"sample_counts.csv", index=False)

        rows: list[dict] = []
        core = df.loc[df["is_core_government"].eq(1)].copy()
        for cutoff in RTE_CUTOFFS:
            specs = [
                (df, "lag_muslim_share", "state", False, True, "primary_persistent"),
                (df, "lag_muslim_share", "district", False, True, "district_cluster"),
                (df, "frozen_muslim_share", "state", False, True, "frozen_exposure"),
                (df, "lag_muslim_share", "state", True, True, "donut"),
                (df, "lag_muslim_share", "state", False, False, "continuity_only"),
                (df, "lead_muslim_share", "state", False, True, "future_share_placebo"),
                (core, "lag_muslim_share", "state", False, True, "core_government"),
            ]
            for sample, exposure, cluster, donut, persistent, spec in specs:
                ans = _fit(sample, cutoff, exposure=exposure, cluster=cluster, donut=donut, persistent=persistent)
                if ans:
                    ans["spec"] = spec
                    ans["universe"] = "core_1_2_3" if spec == "core_government" else "main_1_2_3_6_89_90"
                    rows.append(ans)

        primary_ix = [i for i, r in enumerate(rows) if r["spec"] == "primary_persistent"]
        qvals = bh_qvalues([rows[i]["muslim_interaction_p"] for i in primary_ix])
        for i, q in zip(primary_ix, qvals):
            rows[i]["timing_family_q"] = q
        write_rows(OUT/"timing_models.csv", rows)
        write_json(OUT/"source_validation.json", reports)

        lines = ["# Hardened delayed RTE staffing RD", "", "Primary timing inference requires consecutive t+1 observation, continued State/local-government status, and persistence on the same side of the statutory cutoff.", ""]
        for r in (rows[i] for i in primary_ix):
            lines.append(f"- cutoff {r['cutoff']}: interaction {r['muslim_interaction']:+.4f} (95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), p={r['muslim_interaction_p']:.4g}, q={r.get('timing_family_q', float('nan')):.4g}, n={r['n']:,}, clusters={r['clusters']}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
