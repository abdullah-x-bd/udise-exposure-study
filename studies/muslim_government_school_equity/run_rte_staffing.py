from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import (
    RTE_CUTOFFS,
    add_shares,
    bh_qvalues,
    build_panel,
    fit_wls_clustered,
    muslim_bin,
    required_primary_teachers,
    write_json,
    write_rows,
)

OUT = Path("studies/muslim_government_school_equity/outputs/rte_staffing")
BANDWIDTHS = (15.0, 20.0, 30.0)
FAKE_CUTOFFS = (75.5, 105.5, 135.5)


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(
        f"""
        SELECT academic_year,pseudocode,state,district,rural_urban,management,school_category,
               lowclass,highclass,is_state_local_government,is_core_government,
               enrol_primary,general_primary,sc_primary,st_primary,obc_primary,
               muslim_primary,christian_primary,sikh_primary,buddhist_primary,parsi_primary,jain_primary,
               total_teachers,primary_serving_teachers,regular_teachers,contract_teachers,female_teachers
        FROM read_parquet('{str(panel).replace("'","''")}')
        WHERE enrol_primary IS NOT NULL
        """
    ).df()
    df = add_shares(df, primary=True)
    year_index = {y: i for i, y in enumerate(sorted(df.academic_year.unique()))}
    df["year_index"] = df.academic_year.map(year_index)
    df = df.sort_values(["pseudocode", "year_index"]).reset_index(drop=True)
    for col in ("muslim_share", "sc_share", "st_share", "obc_share", "general_share"):
        df[f"lag_{col}"] = df.groupby("pseudocode")[col].shift(1)
    df["lag_year_index"] = df.groupby("pseudocode")["year_index"].shift(1)
    good_lag = df["lag_year_index"].eq(df["year_index"] - 1)
    for col in ("muslim_share", "sc_share", "st_share", "obc_share", "general_share"):
        df.loc[~good_lag, f"lag_{col}"] = np.nan

    df["next_total_teachers"] = df.groupby("pseudocode")["total_teachers"].shift(-1)
    df["next_primary_serving_teachers"] = df.groupby("pseudocode")["primary_serving_teachers"].shift(-1)
    df["next_year_index"] = df.groupby("pseudocode")["year_index"].shift(-1)
    good_next = df["next_year_index"].eq(df["year_index"] + 1)
    df.loc[~good_next, ["next_total_teachers", "next_primary_serving_teachers"]] = np.nan

    earliest = (
        df.loc[df["muslim_share"].notna(), ["pseudocode", "year_index", "muslim_share", "sc_share", "st_share", "obc_share"]]
        .sort_values(["pseudocode", "year_index"])
        .drop_duplicates("pseudocode")
        .rename(columns={
            "muslim_share": "frozen_muslim_share",
            "sc_share": "frozen_sc_share",
            "st_share": "frozen_st_share",
            "obc_share": "frozen_obc_share",
        })
    )
    df = df.merge(earliest.drop(columns="year_index"), on="pseudocode", how="left")
    df["required_teachers"] = required_primary_teachers(df["enrol_primary"])
    df["meets_norm"] = np.where(
        df["required_teachers"].notna() & pd.to_numeric(df["total_teachers"], errors="coerce").notna(),
        (pd.to_numeric(df["total_teachers"], errors="coerce") >= df["required_teachers"]).astype(float),
        np.nan,
    )
    return df


def _design(d: pd.DataFrame, cutoff: float, exposure: str, bw: float) -> tuple[np.ndarray, list[str], np.ndarray]:
    r = pd.to_numeric(d["enrol_primary"], errors="coerce").to_numpy(float) - cutoff
    t = (r >= 0).astype(float)
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    rural = pd.to_numeric(d["rural_urban"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(d["management"], errors="coerce")
    cols = [t, r, t*r, m, t*m, r*m, t*r*m, sc, st, obc, rural]
    names = ["above", "running", "above_running", "muslim_share", "above_muslim_share", "running_muslim_share", "above_running_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban"]
    for code in sorted(x for x in mgmt.dropna().unique() if x != mgmt.dropna().min()):
        cols.append((mgmt.to_numpy(float) == code).astype(float))
        names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    weights = np.maximum(0.0, 1.0 - np.abs(r) / bw)
    return X, names, weights


def _fit_one(
    sample: pd.DataFrame,
    *,
    cutoff: float,
    bw: float,
    outcome: str,
    exposure: str,
    cluster_col: str = "state",
    donut: bool = False,
) -> dict | None:
    d = sample.copy()
    r = pd.to_numeric(d["enrol_primary"], errors="coerce") - cutoff
    d = d.loc[r.abs() <= bw].copy()
    if donut:
        left, right = math.floor(cutoff), math.ceil(cutoff)
        d = d.loc[~pd.to_numeric(d["enrol_primary"], errors="coerce").isin([left, right])].copy()
    if len(d) < 500:
        return None
    X, names, weights = _design(d, cutoff, exposure, bw)
    district_year = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    year = d["academic_year"].astype(str).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, weights,
            d[cluster_col].to_numpy(object), absorb_groups=[district_year, year], names=names,
        )
    except RuntimeError:
        return None
    key = "above_muslim_share"
    return {
        "cutoff": cutoff, "bandwidth": bw, "outcome": outcome, "exposure": exposure,
        "cluster": cluster_col, "donut": int(donut),
        "n": fit["n"], "clusters": fit["clusters"],
        "base_jump": fit["coef"]["above"], "base_jump_se": fit["se"]["above"], "base_jump_p": fit["p"]["above"],
        "muslim_interaction": fit["coef"][key], "muslim_interaction_se": fit["se"][key],
        "muslim_interaction_p": fit["p"][key], "muslim_interaction_ci_low": fit["ci_low"][key],
        "muslim_interaction_ci_high": fit["ci_high"][key],
    }


def _stacked_fit(sample: pd.DataFrame, outcome: str, exposure: str, bw: float, cluster_col: str = "state") -> dict | None:
    frames = []
    for cutoff in RTE_CUTOFFS:
        x = sample.copy()
        x["cutoff"] = cutoff
        x["running_stack"] = pd.to_numeric(x["enrol_primary"], errors="coerce") - cutoff
        x = x.loc[x["running_stack"].abs() <= bw].copy()
        frames.append(x)
    d = pd.concat(frames, ignore_index=True)
    if len(d) < 1000:
        return None
    r = d["running_stack"].to_numpy(float)
    t = (r >= 0).astype(float)
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    rural = pd.to_numeric(d["rural_urban"], errors="coerce").to_numpy(float)
    X = np.column_stack([t, r, t*r, m, t*m, r*m, t*r*m, sc, st, obc, rural])
    names = ["above", "running", "above_running", "muslim_share", "above_muslim_share", "running_muslim_share", "above_running_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban"]
    weights = np.maximum(0.0, 1.0 - np.abs(r) / bw)
    district_year = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    cutoff_year = (d["cutoff"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, weights,
            d[cluster_col].to_numpy(object), absorb_groups=[district_year, cutoff_year], names=names,
        )
    except RuntimeError:
        return None
    key = "above_muslim_share"
    return {
        "cutoff": "stacked", "bandwidth": bw, "outcome": outcome, "exposure": exposure,
        "cluster": cluster_col, "donut": 0, "n": fit["n"], "clusters": fit["clusters"],
        "base_jump": fit["coef"]["above"], "base_jump_se": fit["se"]["above"], "base_jump_p": fit["p"]["above"],
        "muslim_interaction": fit["coef"][key], "muslim_interaction_se": fit["se"][key],
        "muslim_interaction_p": fit["p"][key], "muslim_interaction_ci_low": fit["ci_low"][key],
        "muslim_interaction_ci_high": fit["ci_high"][key],
    }


def _simple_rd(d: pd.DataFrame, cutoff: float, bw: float, outcome: str) -> dict | None:
    x = d.copy()
    r = pd.to_numeric(x["enrol_primary"], errors="coerce") - cutoff
    x = x.loc[r.abs() <= bw].copy()
    r = pd.to_numeric(x["enrol_primary"], errors="coerce").to_numpy(float) - cutoff
    t = (r >= 0).astype(float)
    X = np.column_stack([t, r, t*r])
    names = ["above", "running", "above_running"]
    w = np.maximum(0.0, 1.0 - np.abs(r)/bw)
    dy = (x["district"].astype(str) + "|" + x["academic_year"].astype(str)).to_numpy(object)
    year = x["academic_year"].astype(str).to_numpy(object)
    try:
        fit = fit_wls_clustered(pd.to_numeric(x[outcome], errors="coerce").to_numpy(float), X, w, x["state"].to_numpy(object), absorb_groups=[dy, year], names=names)
    except RuntimeError:
        return None
    return {"cutoff": cutoff, "outcome": outcome, "n": fit["n"], "jump": fit["coef"]["above"], "se": fit["se"]["above"], "p": fit["p"]["above"]}


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_rte_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=True, facility=False, profile2=False)
        df = _prepare(panel, con)

        sample = df.loc[
            (df["is_state_local_government"] == 1)
            & (pd.to_numeric(df["lowclass"], errors="coerce") == 1)
            & (pd.to_numeric(df["highclass"], errors="coerce") == 5)
            & df["lag_muslim_share"].notna()
        ].copy()
        core_sample = sample.loc[sample["is_core_government"] == 1].copy()

        counts = sample.groupby("academic_year", dropna=False).agg(
            schools=("pseudocode", "nunique"), rows=("pseudocode", "size"),
            mean_muslim_share=("lag_muslim_share", "mean"),
        ).reset_index()
        counts.to_csv(OUT/"sample_counts.csv", index=False)

        rows: list[dict] = []
        outcomes = ("total_teachers", "primary_serving_teachers", "meets_norm", "regular_teachers", "contract_teachers", "female_teachers", "next_total_teachers")
        for outcome in outcomes:
            for cutoff in RTE_CUTOFFS:
                for bw in BANDWIDTHS:
                    ans = _fit_one(sample, cutoff=cutoff, bw=bw, outcome=outcome, exposure="lag_muslim_share")
                    if ans:
                        ans["universe"] = "main_1_2_3_6_89_90"
                        rows.append(ans)
                ans = _fit_one(sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="lag_muslim_share", donut=True)
                if ans:
                    ans["universe"] = "main_1_2_3_6_89_90"; rows.append(ans)
                ans = _fit_one(sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="lag_muslim_share", cluster_col="district")
                if ans:
                    ans["universe"] = "main_1_2_3_6_89_90"; rows.append(ans)
                ans = _fit_one(core_sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="lag_muslim_share")
                if ans:
                    ans["universe"] = "core_1_2_3"; rows.append(ans)
                ans = _fit_one(sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="frozen_muslim_share")
                if ans:
                    ans["universe"] = "main_1_2_3_6_89_90"; rows.append(ans)
            pooled = _stacked_fit(sample, outcome, "lag_muslim_share", 20)
            if pooled:
                pooled["universe"] = "main_1_2_3_6_89_90"; rows.append(pooled)

        q = bh_qvalues([r["muslim_interaction_p"] for r in rows])
        for row, qv in zip(rows, q):
            row["muslim_interaction_q"] = qv
        write_rows(OUT/"rte_staffing_models.csv", rows)

        placebo_rows = []
        for cutoff in FAKE_CUTOFFS:
            ans = _fit_one(sample, cutoff=cutoff, bw=15, outcome="total_teachers", exposure="lag_muslim_share")
            if ans:
                placebo_rows.append(ans)
        write_rows(OUT/"fake_cutoffs.csv", placebo_rows)

        balance_rows = []
        for cutoff in RTE_CUTOFFS:
            for outcome in ("lag_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban"):
                ans = _simple_rd(sample, cutoff, 20, outcome)
                if ans:
                    balance_rows.append(ans)
        qbal = bh_qvalues([r["p"] for r in balance_rows])
        for row, qv in zip(balance_rows, qbal):
            row["q"] = qv
        write_rows(OUT/"predetermined_balance.csv", balance_rows)

        density_rows = []
        for year, yy in sample.groupby("academic_year"):
            counts_exact = pd.to_numeric(yy["enrol_primary"], errors="coerce").value_counts()
            for cutoff in RTE_CUTOFFS:
                left, right = math.floor(cutoff), math.ceil(cutoff)
                density_rows.append({
                    "academic_year": year, "cutoff": cutoff,
                    "n_exact_left": int(counts_exact.get(left, 0)), "n_exact_right": int(counts_exact.get(right, 0)),
                    "right_left_ratio": (float(counts_exact.get(right, 0))/float(counts_exact.get(left, 0))) if counts_exact.get(left, 0) else None,
                    "n_window_left": int(((pd.to_numeric(yy.enrol_primary, errors='coerce') >= left-10) & (pd.to_numeric(yy.enrol_primary, errors='coerce') <= left)).sum()),
                    "n_window_right": int(((pd.to_numeric(yy.enrol_primary, errors='coerce') >= right) & (pd.to_numeric(yy.enrol_primary, errors='coerce') <= right+10)).sum()),
                })
        write_rows(OUT/"density_masspoint_diagnostics.csv", density_rows)

        binned_rows = []
        sample["muslim_bin"] = muslim_bin(sample["lag_muslim_share"])
        for label, dd in sample.groupby("muslim_bin", observed=True):
            if len(dd) < 800 or dd["state"].nunique() < 5:
                continue
            for cutoff in RTE_CUTOFFS:
                ans = _simple_rd(dd, cutoff, 20, "total_teachers")
                if ans:
                    ans["muslim_bin"] = str(label)
                    ans["states"] = int(dd["state"].nunique())
                    binned_rows.append(ans)
        write_rows(OUT/"five_pp_bin_staffing_jumps.csv", binned_rows)
        write_json(OUT/"source_validation.json", reports)

        headline = [r for r in rows if r["cutoff"] == "stacked" and r["outcome"] == "total_teachers" and r["exposure"] == "lag_muslim_share" and r["cluster"] == "state" and r["bandwidth"] == 20 and r["universe"] == "main_1_2_3_6_89_90"]
        lines = ["# RTE staffing national experiment", "", f"Eligible main-sample school-years: {len(sample):,}."]
        for r in headline:
            lines += ["", f"Stacked cutoff Muslim interaction: {r['muslim_interaction']:+.4f} teachers per 100 percentage-point increase in predetermined Muslim share", f"95% CI {r['muslim_interaction_ci_low']:+.4f} to {r['muslim_interaction_ci_high']:+.4f}; p={r['muslim_interaction_p']:.4g}; q={r['muslim_interaction_q']:.4g}; n={r['n']:,}."]
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
