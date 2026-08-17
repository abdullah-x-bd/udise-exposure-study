from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import RTE_CUTOFFS, bh_qvalues, build_panel, fit_wls_clustered, write_json, write_rows
from cluster_harmonization import state_sql

OUT = Path("studies/muslim_government_school_equity/outputs/rte_crossing_eventstudy")
YEARS = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]


def _harmonize(panel: Path, con: duckdb.DuckDBPyConnection) -> Path:
    out = panel.with_name(panel.stem + "_state_lineage.parquet")
    qin = str(panel).replace("'", "''"); qout = str(out).replace("'", "''")
    con.execute(f"COPY (SELECT * REPLACE ({state_sql('state')} AS state) FROM read_parquet('{qin}')) TO '{qout}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return out


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    year_case = "CASE academic_year " + " ".join(f"WHEN '{y}' THEN {i}" for i, y in enumerate(YEARS)) + " END"
    cut_values = ",".join(f"({float(c)})" for c in RTE_CUTOFFS)
    return con.execute(f"""
        WITH base0 AS (
          SELECT academic_year,pseudocode,state,district,rural_urban,management,lowclass,highclass,
                 is_state_local_government,is_core_government,enrol_primary,total_teachers,
                 muslim_primary/NULLIF(enrol_primary,0) AS muslim_share,
                 sc_primary/NULLIF(enrol_primary,0) AS sc_share,
                 st_primary/NULLIF(enrol_primary,0) AS st_share,
                 obc_primary/NULLIF(enrol_primary,0) AS obc_share,
                 {year_case} AS year_index
          FROM read_parquet('{q}')
          WHERE enrol_primary IS NOT NULL AND lowclass=1 AND highclass=5
        ), base AS (
          SELECT *,
                 LAG(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_year_index,
                 LAG(enrol_primary) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_enrol,
                 LAG(is_state_local_government) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_gov,
                 ARG_MIN(muslim_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_muslim,
                 ARG_MIN(sc_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_sc,
                 ARG_MIN(st_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_st,
                 ARG_MIN(obc_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_obc
          FROM base0
        ), candidates AS (
          SELECT b.*, c.column0 AS cutoff,
                 ROW_NUMBER() OVER (PARTITION BY pseudocode,c.column0 ORDER BY year_index) AS rn
          FROM base b CROSS JOIN (VALUES {cut_values}) c
          WHERE b.is_state_local_government=1 AND b.lag_gov=1
            AND b.lag_year_index=b.year_index-1
            AND b.lag_enrol <= FLOOR(c.column0) AND b.enrol_primary >= CEIL(c.column0)
            AND ABS(b.lag_enrol-c.column0)<=20 AND ABS(b.enrol_primary-c.column0)<=20
            AND b.frozen_muslim IS NOT NULL
        ), events AS (
          SELECT pseudocode,cutoff,year_index AS event_year,frozen_muslim,frozen_sc,frozen_st,frozen_obc
          FROM candidates WHERE rn=1
        ), panel AS (
          SELECT b.*, e.cutoff,e.event_year,(b.year_index-e.event_year) AS event_time,
                 e.frozen_muslim,e.frozen_sc,e.frozen_st,e.frozen_obc,
                 CASE
                   WHEN b.enrol_primary BETWEEN 1 AND 60 THEN 2
                   WHEN b.enrol_primary BETWEEN 61 AND 90 THEN 3
                   WHEN b.enrol_primary BETWEEN 91 AND 120 THEN 4
                   WHEN b.enrol_primary BETWEEN 121 AND 150 THEN 5
                 END AS required_teachers
          FROM base0 b JOIN events e USING(pseudocode)
          WHERE b.is_state_local_government=1
            AND b.year_index BETWEEN e.event_year-2 AND e.event_year+2
            AND b.state IS NOT NULL AND b.district IS NOT NULL
        )
        SELECT *,
               CASE WHEN required_teachers IS NOT NULL AND total_teachers IS NOT NULL THEN GREATEST(required_teachers-total_teachers,0) END AS teacher_deficit,
               CASE WHEN required_teachers IS NOT NULL AND total_teachers IS NOT NULL THEN CAST(total_teachers>=required_teachers AS DOUBLE) END AS meets_norm
        FROM panel
        ORDER BY cutoff,pseudocode,year_index
    """).df()


def _fit(d: pd.DataFrame, outcome: str, cutoff: float) -> dict | None:
    x = d.loc[d["cutoff"].eq(cutoff) & d["event_time"].between(-2,2)].copy()
    if len(x) < 1000:
        return None
    et = pd.to_numeric(x["event_time"], errors="coerce").to_numpy(float)
    m = pd.to_numeric(x["frozen_muslim"], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(x["frozen_sc"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(x["frozen_st"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(x["frozen_obc"], errors="coerce").to_numpy(float)
    logn = np.log1p(pd.to_numeric(x["enrol_primary"], errors="coerce").to_numpy(float))

    cols = [logn]; names = ["log_enrolment"]
    for k in (-2, 0, 1, 2):
        e = (et == k).astype(float)
        cols.extend([e, e*m, e*sc, e*st, e*obc])
        names.extend([f"event_{k}", f"event_{k}_x_muslim", f"event_{k}_x_sc", f"event_{k}_x_st", f"event_{k}_x_obc"])
    X = np.column_stack(cols)
    event_unit = (x["pseudocode"].astype(str) + "|" + x["cutoff"].astype(str)).to_numpy(object)
    district_year = (x["district"].astype(str) + "|" + x["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(x[outcome], errors="coerce").to_numpy(float), X, np.ones(len(x)),
            x["state"].to_numpy(object), absorb_groups=[event_unit, district_year], names=names,
        )
    except RuntimeError:
        return None

    row = {"cutoff": cutoff, "outcome": outcome, "n": fit["n"], "clusters": fit["clusters"]}
    for k in (-2, 0, 1, 2):
        key = f"event_{k}_x_muslim"
        row[f"muslim_event_{k}"] = fit["coef"][key]
        row[f"muslim_event_{k}_se"] = fit["se"][key]
        row[f"muslim_event_{k}_p"] = fit["p"][key]
        row[f"muslim_event_{k}_ci_low"] = fit["ci_low"][key]
        row[f"muslim_event_{k}_ci_high"] = fit["ci_high"][key]
    return row


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='6GB'")
    with tempfile.TemporaryDirectory(prefix="rte_crossing_eventstudy_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=True, facility=False, profile2=False)
        panel = _harmonize(panel, con)
        ev = _prepare(panel, con)
        ev.groupby(["cutoff","event_time"]).agg(rows=("pseudocode","size"), schools=("pseudocode","nunique"), states=("state","nunique"), districts=("district","nunique")).reset_index().to_csv(OUT/"event_counts.csv", index=False)

        rows = []
        for cutoff in RTE_CUTOFFS:
            for outcome in ("total_teachers", "teacher_deficit", "meets_norm"):
                ans = _fit(ev, outcome, float(cutoff))
                if ans: rows.append(ans)

        # Confirmatory family: Muslim interaction at event 0 and +1 for total teachers across three cutoffs.
        pvals = []; locs = []
        for i, r in enumerate(rows):
            if r["outcome"] == "total_teachers":
                for k in (0, 1):
                    pvals.append(r[f"muslim_event_{k}_p"]); locs.append((i,k))
        for (i,k), q in zip(locs, bh_qvalues(pvals)):
            rows[i][f"muslim_event_{k}_q"] = q
        write_rows(OUT/"eventstudy_models.csv", rows)
        write_json(OUT/"source_validation.json", reports)

        lines = ["# RTE threshold-crossing event study", "", "Event -1 is the omitted reference period. Event -2 is the pre-trend diagnostic. Event 0 is the first upward crossing of a statutory staffing threshold.", ""]
        for r in rows:
            if r["outcome"] != "total_teachers": continue
            lines.append(f"- cutoff {r['cutoff']}: pretrend(-2)={r['muslim_event_-2']:+.4f} p={r['muslim_event_-2_p']:.4g}; event0={r['muslim_event_0']:+.4f} p={r['muslim_event_0_p']:.4g} q={r.get('muslim_event_0_q', float('nan')):.4g}; event+1={r['muslim_event_1']:+.4f} p={r['muslim_event_1_p']:.4g} q={r.get('muslim_event_1_q', float('nan')):.4g}; n={r['n']:,}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
