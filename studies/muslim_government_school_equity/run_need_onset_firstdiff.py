from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import bh_qvalues, build_panel, fit_wls_clustered, write_json, write_rows
from run_need_inspection_memorysafe import _prepare

OUT = Path("studies/muslim_government_school_equity/outputs/need_onset_firstdiff")
OUTCOMES = [
    "next_log_total_visits",
    "next_log_senior_visits",
    "next_log_academic_inspections",
    "next_log_crc_visits",
    "next_log_block_visits",
    "next_log_district_state_visits",
]


def _events(df: pd.DataFrame) -> pd.DataFrame:
    x = df.sort_values(["school_id", "year_index"], kind="mergesort").copy()
    g = x.groupby("school_id", sort=False, observed=True)
    lag_year = g["year_index"].shift(1)
    lag2_year = g["year_index"].shift(2)
    lag_need = g["need_index"].shift(1)
    lag_gov = g["is_state_local_government"].shift(1)
    lag2_gov = g["is_state_local_government"].shift(2)

    consecutive = lag_year.eq(x["year_index"] - 1) & lag2_year.eq(x["year_index"] - 2)
    onset = (
        consecutive
        & x["is_state_local_government"].eq(1)
        & lag_gov.eq(1)
        & lag2_gov.eq(1)
        & pd.to_numeric(lag_need, errors="coerce").eq(0)
        & pd.to_numeric(x["need_index"], errors="coerce").gt(0)
        & x["base_muslim"].notna()
    )

    for col in OUTCOMES:
        # next_* at t is response in t+1; lag(next_*) is response in t; lag2(next_*) is response in t-1.
        x[f"post_{col}"] = pd.to_numeric(x[col], errors="coerce")
        x[f"base_{col}"] = pd.to_numeric(g[col].shift(1), errors="coerce")
        x[f"pre_{col}"] = pd.to_numeric(g[col].shift(2), errors="coerce")
        x[f"delta_post_{col}"] = x[f"post_{col}"] - x[f"base_{col}"]
        x[f"delta_pre_{col}"] = x[f"base_{col}"] - x[f"pre_{col}"]

    keep = [
        "academic_year", "year_index", "school_id", "state_cluster", "district_code",
        "is_core_government", "enrol_c1_12", "need_index", "need_components_observed",
        "base_muslim", "base_sc", "base_st", "base_obc", "base_rural", "base_management",
    ] + [f"delta_post_{c}" for c in OUTCOMES] + [f"delta_pre_{c}" for c in OUTCOMES]
    ev = x.loc[onset, keep].copy()
    del x, g, onset, consecutive
    gc.collect()
    return ev


def _fit(ev: pd.DataFrame, outcome: str, *, phase: str, cluster: str = "state", core: bool = False) -> dict | None:
    d = ev.loc[ev["is_core_government"].eq(1)].copy() if core else ev.copy()
    ycol = f"delta_{phase}_{outcome}"
    m = pd.to_numeric(d["base_muslim"], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["base_sc"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["base_st"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["base_obc"], errors="coerce").to_numpy(float)
    need = pd.to_numeric(d["need_index"], errors="coerce").to_numpy(float)
    logn = np.log1p(pd.to_numeric(d["enrol_c1_12"], errors="coerce").to_numpy(float))
    rural = pd.to_numeric(d["base_rural"], errors="coerce").to_numpy(float)
    observed = pd.to_numeric(d["need_components_observed"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(d["base_management"], errors="coerce")

    cols = [m, sc, st, obc, need, logn, rural, observed]
    names = ["muslim_share", "sc_share", "st_share", "obc_share", "onset_need", "log_enrolment", "rural", "need_components_observed"]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            cols.append((mgmt.to_numpy(float) == code).astype(float))
            names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    dy = (d["district_code"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    clusters = d["state_cluster"].to_numpy(object) if cluster == "state" else d["district_code"].to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[ycol], errors="coerce").to_numpy(float), X, np.ones(len(d)),
            clusters, absorb_groups=[dy], names=names,
        )
    except RuntimeError:
        return None
    key = "muslim_share"
    return {
        "outcome": outcome, "phase": phase, "cluster": cluster,
        "universe": "core_1_2_3" if core else "main_1_2_3_6_89_90",
        "n": fit["n"], "clusters": fit["clusters"],
        "muslim_coef": fit["coef"][key], "muslim_se": fit["se"][key], "muslim_p": fit["p"][key],
        "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
        "sc_coef": fit["coef"]["sc_share"], "st_coef": fit["coef"]["st_share"], "obc_coef": fit["coef"]["obc_share"],
    }


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='5GB'")
    with tempfile.TemporaryDirectory(prefix="need_onset_fd_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=False, facility=True, profile2=True)
        df = _prepare(panel, con)
        ev = _events(df)
        del df
        gc.collect()

        ev.groupby("academic_year", observed=True).agg(
            events=("school_id","size"), schools=("school_id","nunique"), states=("state_cluster","nunique"),
            districts=("district_code","nunique"), mean_onset_need=("need_index","mean"), mean_base_muslim=("base_muslim","mean")
        ).reset_index().to_csv(OUT/"event_counts.csv", index=False)

        rows: list[dict] = []
        for outcome in OUTCOMES:
            for phase in ("post", "pre"):
                ans = _fit(ev, outcome, phase=phase, cluster="state", core=False)
                if ans: rows.append({"spec":"primary" if phase == "post" else "pretrend_placebo", **ans})
            ans = _fit(ev, outcome, phase="post", cluster="district", core=False)
            if ans: rows.append({"spec":"district_cluster", **ans})
            ans = _fit(ev, outcome, phase="post", cluster="state", core=True)
            if ans: rows.append({"spec":"core_government", **ans})

        primary_ix = [i for i,r in enumerate(rows) if r["spec"] == "primary"]
        qvals = bh_qvalues([rows[i]["muslim_p"] for i in primary_ix])
        for i,q in zip(primary_ix,qvals): rows[i]["primary_family_q"] = q
        write_rows(OUT/"models.csv", rows)
        write_json(OUT/"source_validation.json", reports)

        lines = [
            "# Need-onset first-difference administrative-response experiment", "",
            "Events are consecutive State/local-government school-years that move from need_index=0 to need_index>0. The post outcome is the within-school change in inspection response from t to t+1; the pretrend placebo is the analogous change before onset.", ""
        ]
        for i in primary_ix:
            r = rows[i]
            pre = next((z for z in rows if z["outcome"]==r["outcome"] and z["spec"]=="pretrend_placebo"), None)
            pretxt = f"; pretrend={pre['muslim_coef']:+.4f}, p={pre['muslim_p']:.4g}" if pre else ""
            lines.append(f"- {r['outcome']}: post={r['muslim_coef']:+.4f} (95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), p={r['muslim_p']:.4g}, q={r.get('primary_family_q', float('nan')):.4g}, n={r['n']:,}{pretxt}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
