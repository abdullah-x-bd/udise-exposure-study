from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import add_shares, bh_qvalues, build_panel, fit_wls_clustered, muslim_bin, write_json, write_rows

OUT = Path("studies/muslim_government_school_equity/outputs/failure_to_repair")
FAILURES = ("girls_toilet", "boys_toilet", "water", "electricity", "major_repair")


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    df = con.execute(f"""
        SELECT academic_year,pseudocode,state,district,rural_urban,management,school_category,lowclass,highclass,
               is_state_local_government,is_core_government,enrol_c1_12,boys_c1_12,girls_c1_12,
               general_c1_12,sc_c1_12,st_c1_12,obc_c1_12,muslim_c1_12,christian_c1_12,sikh_c1_12,buddhist_c1_12,parsi_c1_12,jain_c1_12,
               total_classrooms,classrooms_major_repair,boys_toilets,boys_func_toilets,girls_toilets,girls_func_toilets,
               water_functional,electricity_functional
        FROM read_parquet('{q}') WHERE enrol_c1_12 IS NOT NULL
    """).df()
    df = add_shares(df, primary=False)
    years = {y: i for i, y in enumerate(sorted(df.academic_year.unique()))}
    df["year_index"] = df.academic_year.map(years)
    df = df.sort_values(["pseudocode", "year_index"]).reset_index(drop=True)

    girls = pd.to_numeric(df["girls_c1_12"], errors="coerce")
    boys = pd.to_numeric(df["boys_c1_12"], errors="coerce")
    gfunc = pd.to_numeric(df["girls_func_toilets"], errors="coerce")
    bfunc = pd.to_numeric(df["boys_func_toilets"], errors="coerce")
    major = pd.to_numeric(df["classrooms_major_repair"], errors="coerce")
    rooms = pd.to_numeric(df["total_classrooms"], errors="coerce")
    df["girls_toilet_ok"] = np.where((girls > 0) & gfunc.notna(), (gfunc > 0).astype(float), np.nan)
    df["boys_toilet_ok"] = np.where((boys > 0) & bfunc.notna(), (bfunc > 0).astype(float), np.nan)
    df["water_ok"] = pd.to_numeric(df["water_functional"], errors="coerce")
    df["electricity_ok"] = pd.to_numeric(df["electricity_functional"], errors="coerce")
    df["major_repair_ok"] = np.where((rooms > 0) & major.notna(), (major <= 0).astype(float), np.nan)

    for col in ("muslim_share", "sc_share", "st_share", "obc_share", "general_share", "enrol_c1_12", "management", "rural_urban", "girls_toilets", "boys_toilets", "total_classrooms"):
        df[f"lag_{col}"] = df.groupby("pseudocode")[col].shift(1)
    df["lag_year_index"] = df.groupby("pseudocode")["year_index"].shift(1)
    consecutive = df["lag_year_index"].eq(df["year_index"] - 1)
    for col in ("muslim_share", "sc_share", "st_share", "obc_share", "general_share", "enrol_c1_12", "management", "rural_urban", "girls_toilets", "boys_toilets", "total_classrooms"):
        df.loc[~consecutive, f"lag_{col}"] = np.nan

    earliest = (
        df.loc[df["muslim_share"].notna(), ["pseudocode", "year_index", "muslim_share"]]
        .sort_values(["pseudocode", "year_index"]).drop_duplicates("pseudocode")
        .rename(columns={"muslim_share": "frozen_muslim_share"})
    )
    df = df.merge(earliest[["pseudocode", "frozen_muslim_share"]], on="pseudocode", how="left")

    for failure in FAILURES:
        ok = f"{failure}_ok"
        df[f"lag_{ok}"] = df.groupby("pseudocode")[ok].shift(1)
        df.loc[~consecutive, f"lag_{ok}"] = np.nan
        for h in (1, 2, 3):
            df[f"{ok}_lead{h}"] = df.groupby("pseudocode")[ok].shift(-h)
            lead_year = df.groupby("pseudocode")["year_index"].shift(-h)
            df.loc[~lead_year.eq(df["year_index"] + h), f"{ok}_lead{h}"] = np.nan
    return df


def _events(df: pd.DataFrame, failure: str) -> pd.DataFrame:
    ok = f"{failure}_ok"
    ev = df.loc[
        (df["is_state_local_government"] == 1)
        & (df[f"lag_{ok}"] == 1)
        & (df[ok] == 0)
        & df["lag_muslim_share"].notna()
    ].copy()
    ev["failure_type"] = failure
    ev["exposure"] = ev["lag_muslim_share"]
    if failure == "girls_toilet":
        ev["baseline_stock"] = pd.to_numeric(ev["lag_girls_toilets"], errors="coerce")
    elif failure == "boys_toilet":
        ev["baseline_stock"] = pd.to_numeric(ev["lag_boys_toilets"], errors="coerce")
    elif failure == "major_repair":
        ev["baseline_stock"] = pd.to_numeric(ev["lag_total_classrooms"], errors="coerce")
    else:
        ev["baseline_stock"] = 0.0

    for h in (1, 2, 3):
        leads = [pd.to_numeric(ev[f"{ok}_lead{j}"], errors="coerce") for j in range(1, h + 1)]
        lead_frame = pd.concat(leads, axis=1)
        any_repair = (lead_frame == 1).any(axis=1)
        complete = lead_frame.notna().all(axis=1)
        ev[f"repair_by_{h}"] = np.where(any_repair, 1.0, np.where(complete, 0.0, np.nan))
    return ev


def _fit(ev: pd.DataFrame, outcome: str, exposure: str, cluster: str = "state") -> dict | None:
    d = ev.copy()
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    logn = np.log1p(pd.to_numeric(d["lag_enrol_c1_12"], errors="coerce").to_numpy(float))
    rural = pd.to_numeric(d["lag_rural_urban"], errors="coerce").to_numpy(float)
    stock = np.log1p(pd.to_numeric(d["baseline_stock"], errors="coerce").fillna(0).to_numpy(float))
    mgmt = pd.to_numeric(d["management"], errors="coerce")
    cols = [m, sc, st, obc, logn, rural, stock]
    names = ["muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "log_enrolment", "rural_urban", "log_baseline_stock"]
    finite_mgmt = mgmt.dropna()
    if len(finite_mgmt):
        base = finite_mgmt.min()
        for code in sorted(x for x in finite_mgmt.unique() if x != base):
            cols.append((mgmt.to_numpy(float) == code).astype(float)); names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    dy = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, np.ones(len(d)),
            d[cluster].to_numpy(object), absorb_groups=[dy], names=names,
        )
    except RuntimeError:
        return None
    key = "muslim_share"
    return {
        "n": fit["n"], "clusters": fit["clusters"], "cluster": cluster,
        "coef_muslim_share": fit["coef"][key], "se_muslim_share": fit["se"][key],
        "p_muslim_share": fit["p"][key], "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
    }


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_repair_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=False, facility=True, profile2=False)
        df = _prepare(panel, con)
        event_frames = [_events(df, f) for f in FAILURES]
        all_events = pd.concat(event_frames, ignore_index=True)

        event_counts = all_events.groupby(["academic_year", "failure_type"]).agg(events=("pseudocode","size"), schools=("pseudocode","nunique"), states=("state","nunique"), districts=("district","nunique"), mean_pre_failure_muslim_share=("exposure","mean")).reset_index()
        event_counts.to_csv(OUT/"event_counts.csv", index=False)

        rows = []
        for failure, ev in all_events.groupby("failure_type"):
            for h in (1, 2, 3):
                outcome = f"repair_by_{h}"
                ans = _fit(ev, outcome, "exposure", "state")
                if ans:
                    rows.append({"failure_type": failure, "horizon_years": h, "exposure": "lag_muslim_share", "universe": "main_1_2_3_6_89_90", **ans})
                ans = _fit(ev, outcome, "exposure", "district")
                if ans:
                    rows.append({"failure_type": failure, "horizon_years": h, "exposure": "lag_muslim_share", "universe": "main_1_2_3_6_89_90", **ans})
                frozen = ev.copy(); frozen["frozen_exposure"] = frozen["frozen_muslim_share"]
                ans = _fit(frozen, outcome, "frozen_exposure", "state")
                if ans:
                    rows.append({"failure_type": failure, "horizon_years": h, "exposure": "frozen_muslim_share", "universe": "main_1_2_3_6_89_90", **ans})
                core = ev.loc[ev["is_core_government"] == 1].copy()
                ans = _fit(core, outcome, "exposure", "state") if len(core) else None
                if ans:
                    rows.append({"failure_type": failure, "horizon_years": h, "exposure": "lag_muslim_share", "universe": "core_1_2_3", **ans})
        qs = bh_qvalues([r["p_muslim_share"] for r in rows])
        for r, q in zip(rows, qs): r["q_muslim_share"] = q
        write_rows(OUT/"repair_models.csv", rows)

        all_events["muslim_bin"] = muslim_bin(all_events["exposure"])
        bin_rows = []
        for (failure, label), d in all_events.groupby(["failure_type", "muslim_bin"], observed=True):
            row = {"failure_type": failure, "muslim_bin": str(label), "events": len(d), "states": d.state.nunique(), "districts": d.district.nunique()}
            for h in (1, 2, 3):
                y = pd.to_numeric(d[f"repair_by_{h}"], errors="coerce")
                row[f"repair_rate_{h}y"] = float(y.mean()) if y.notna().any() else None
                row[f"observed_{h}y"] = int(y.notna().sum())
            bin_rows.append(row)
        write_rows(OUT/"five_pp_repair_rates.csv", bin_rows)
        write_json(OUT/"source_validation.json", reports)

        primary = [r for r in rows if r["cluster"] == "state" and r["exposure"] == "lag_muslim_share" and r["universe"] == "main_1_2_3_6_89_90"]
        lines = ["# Failure-to-repair national experiment", "", f"Incident documented failures: {len(all_events):,}.", "", "Coefficient is the change in repair probability associated with moving Muslim share from 0 to 100%, conditional on district-by-onset-year and prespecified covariates."]
        for r in primary:
            lines.append(f"- {r['failure_type']} within {r['horizon_years']}y: {r['coef_muslim_share']:+.4f} (95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), p={r['p_muslim_share']:.4g}, q={r['q_muslim_share']:.4g}, n={r['n']:,}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
