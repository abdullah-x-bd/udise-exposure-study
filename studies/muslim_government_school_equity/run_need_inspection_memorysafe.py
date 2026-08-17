from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import add_shares, bh_qvalues, build_panel, fit_wls_clustered, muslim_bin, write_json, write_rows
from cluster_harmonization import canonicalize_state_series

OUT = Path("studies/muslim_government_school_equity/outputs/need_inspection_corrected")


def _valid_expr(col: str) -> str:
    return f"CASE WHEN TRY_CAST({col} AS DOUBLE)>=0 THEN TRY_CAST({col} AS DOUBLE) END"


def _caps(panel: Path, con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    q = str(panel).replace("'", "''")
    raw = ["academic_inspections", "crc_visits", "block_visits", "district_state_visits"]
    out: dict[str, float] = {}
    for col in raw:
        val = con.execute(
            f"SELECT quantile_cont(v,0.995) FROM (SELECT {_valid_expr(col)} v FROM read_parquet('{q}')) WHERE v IS NOT NULL"
        ).fetchone()[0]
        out[col] = float(val) if val is not None else np.nan
    vals = {c: _valid_expr(c) for c in raw}
    total = (
        "CASE WHEN " + " AND ".join(f"({vals[c]}) IS NULL" for c in raw) + " THEN NULL ELSE "
        + "+".join(f"COALESCE(({vals[c]}),0)" for c in raw) + " END"
    )
    senior_raw = ["block_visits", "district_state_visits"]
    senior = (
        "CASE WHEN " + " AND ".join(f"({vals[c]}) IS NULL" for c in senior_raw) + " THEN NULL ELSE "
        + "+".join(f"COALESCE(({vals[c]}),0)" for c in senior_raw) + " END"
    )
    for name, expr in (("total_visits", total), ("senior_visits", senior)):
        val = con.execute(
            f"SELECT quantile_cont(v,0.995) FROM (SELECT {expr} v FROM read_parquet('{q}')) WHERE v IS NOT NULL"
        ).fetchone()[0]
        out[name] = float(val) if val is not None else np.nan
    return out


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    caps = _caps(panel, con)
    df = con.execute(f"""
        WITH p AS (
          SELECT academic_year,pseudocode,state,district,rural_urban,management,school_category,lowclass,highclass,
                 is_state_local_government,is_core_government,enrol_c1_12,boys_c1_12,girls_c1_12,
                 general_c1_12,sc_c1_12,st_c1_12,obc_c1_12,muslim_c1_12,christian_c1_12,sikh_c1_12,buddhist_c1_12,parsi_c1_12,jain_c1_12,
                 total_classrooms,classrooms_major_repair,boys_func_toilets,girls_func_toilets,water_functional,electricity_functional,
                 academic_inspections,crc_visits,block_visits,district_state_visits,
                 MAX(is_state_local_government) OVER (PARTITION BY pseudocode) AS ever_government
          FROM read_parquet('{q}')
          WHERE enrol_c1_12 IS NOT NULL
        )
        SELECT * EXCLUDE(ever_government) FROM p WHERE ever_government=1
    """).df()

    df = add_shares(df, primary=False)
    years = {y: i for i, y in enumerate(sorted(df.academic_year.unique()))}
    df["year_index"] = df.academic_year.map(years).astype("int8")

    df["state_lineage_name"] = canonicalize_state_series(df["state"])
    district_norm = df["district"].astype("string").str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
    district_key = df["state_lineage_name"].astype("string") + "|" + district_norm
    df["state_cluster"], _ = pd.factorize(df["state_lineage_name"], sort=True)
    df["district_code"], _ = pd.factorize(district_key, sort=True)
    df["school_id"], _ = pd.factorize(df["pseudocode"].astype("string"), sort=False)
    df["state_cluster"] = df["state_cluster"].astype("int16")
    df["district_code"] = df["district_code"].astype("int32")
    df["school_id"] = df["school_id"].astype("int32")
    df["academic_year"] = df["academic_year"].astype("category")
    df.drop(columns=["pseudocode", "state", "district"], inplace=True)

    df.sort_values(["school_id", "year_index"], inplace=True, kind="mergesort")
    df.reset_index(drop=True, inplace=True)

    girls = pd.to_numeric(df["girls_c1_12"], errors="coerce")
    boys = pd.to_numeric(df["boys_c1_12"], errors="coerce")
    gf = pd.to_numeric(df["girls_func_toilets"], errors="coerce")
    bf = pd.to_numeric(df["boys_func_toilets"], errors="coerce")
    major = pd.to_numeric(df["classrooms_major_repair"], errors="coerce")
    rooms = pd.to_numeric(df["total_classrooms"], errors="coerce")
    water = pd.to_numeric(df["water_functional"], errors="coerce")
    elec = pd.to_numeric(df["electricity_functional"], errors="coerce")

    components = np.column_stack([
        np.where((girls > 0) & gf.notna(), (gf <= 0).astype(float), np.nan),
        np.where((boys > 0) & bf.notna(), (bf <= 0).astype(float), np.nan),
        np.where(water.notna(), (water <= 0).astype(float), np.nan),
        np.where(elec.notna(), (elec <= 0).astype(float), np.nan),
        np.where((rooms > 0) & major.notna(), (major > 0).astype(float), np.nan),
    ]).astype("float32")
    observed = np.sum(np.isfinite(components), axis=1).astype("int8")
    need = np.nanmean(components, axis=1)
    need[observed < 3] = np.nan
    df["need_components_observed"] = observed
    df["need_index"] = need.astype("float32")
    del components, girls, boys, gf, bf, major, rooms, water, elec, need, observed

    raw_cols = ["academic_inspections", "crc_visits", "block_visits", "district_state_visits"]
    raw_arrays: dict[str, pd.Series] = {}
    for col in raw_cols:
        x = pd.to_numeric(df[col], errors="coerce").where(lambda z: z >= 0)
        raw_arrays[col] = x
        cap = caps[col]
        if np.isfinite(cap):
            x = x.clip(upper=cap)
        df[f"log_{col}"] = np.log1p(x).astype("float32")
        df[f"any_{col}"] = np.where(x.notna(), (x > 0).astype("float32"), np.nan).astype("float32")

    raw_counts = pd.DataFrame(raw_arrays)
    total = raw_counts.sum(axis=1, min_count=1)
    senior = raw_counts[["block_visits", "district_state_visits"]].sum(axis=1, min_count=1)
    for name, x in (("total_visits", total), ("senior_visits", senior)):
        cap = caps[name]
        if np.isfinite(cap):
            x = x.clip(upper=cap)
        df[f"log_{name}"] = np.log1p(x).astype("float32")
        df[f"any_{name}"] = np.where(x.notna(), (x > 0).astype("float32"), np.nan).astype("float32")
    del raw_counts, raw_arrays, total, senior

    earliest_cols = ["school_id", "year_index", "muslim_share", "sc_share", "st_share", "obc_share", "rural_urban", "management"]
    earliest = (
        df.loc[df["muslim_share"].notna(), earliest_cols]
        .sort_values(["school_id", "year_index"], kind="mergesort")
        .drop_duplicates("school_id")
        .rename(columns={
            "muslim_share":"base_muslim", "sc_share":"base_sc", "st_share":"base_st", "obc_share":"base_obc",
            "rural_urban":"base_rural", "management":"base_management",
        })
        .drop(columns="year_index")
    )
    df = df.merge(earliest, on="school_id", how="left", sort=False, copy=False)
    del earliest

    outcome_cols = [
        "log_academic_inspections", "log_crc_visits", "log_block_visits", "log_district_state_visits",
        "log_total_visits", "log_senior_visits", "any_academic_inspections", "any_block_visits",
        "any_district_state_visits", "any_senior_visits",
    ]
    g = df.groupby("school_id", sort=False, observed=True)
    next_year = g["year_index"].shift(-1)
    next_gov = g["is_state_local_government"].shift(-1)
    valid = next_year.eq(df["year_index"] + 1) & next_gov.eq(1)
    for col in outcome_cols:
        nxt = g[col].shift(-1)
        df[f"next_{col}"] = nxt.where(valid).astype("float32")
    del g, next_year, next_gov, valid

    keep = [
        "academic_year", "year_index", "school_id", "state_cluster", "district_code",
        "is_state_local_government", "is_core_government", "enrol_c1_12", "management", "rural_urban",
        "muslim_share", "sc_share", "st_share", "obc_share", "base_muslim", "base_sc", "base_st", "base_obc",
        "base_rural", "base_management", "need_components_observed", "need_index",
    ] + [f"next_{c}" for c in outcome_cols]
    df = df[keep]
    gc.collect()
    return df


def _fit(d: pd.DataFrame, outcome: str, cluster: str = "state", current_exposure: bool = False) -> dict | None:
    need = pd.to_numeric(d["need_index"], errors="coerce").to_numpy(float)
    if current_exposure:
        m = pd.to_numeric(d["muslim_share"], errors="coerce").to_numpy(float)
        sc = pd.to_numeric(d["sc_share"], errors="coerce").to_numpy(float)
        st = pd.to_numeric(d["st_share"], errors="coerce").to_numpy(float)
        obc = pd.to_numeric(d["obc_share"], errors="coerce").to_numpy(float)
        exposure_name = "contemporaneous_composition"
    else:
        m = pd.to_numeric(d["base_muslim"], errors="coerce").to_numpy(float)
        sc = pd.to_numeric(d["base_sc"], errors="coerce").to_numpy(float)
        st = pd.to_numeric(d["base_st"], errors="coerce").to_numpy(float)
        obc = pd.to_numeric(d["base_obc"], errors="coerce").to_numpy(float)
        exposure_name = "frozen_baseline_composition"
    enrol = np.log1p(pd.to_numeric(d["enrol_c1_12"], errors="coerce").to_numpy(float))
    rural = pd.to_numeric(d["base_rural"], errors="coerce").to_numpy(float)
    observed = pd.to_numeric(d["need_components_observed"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(d["base_management"], errors="coerce")

    cols = [need, need*m, need*sc, need*st, need*obc, enrol, need*rural, observed]
    names = ["need", "need_x_muslim", "need_x_sc", "need_x_st", "need_x_obc", "log_enrolment", "need_x_rural", "need_components_observed"]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            dum = (mgmt.to_numpy(float) == code).astype(float)
            cols.append(need*dum)
            names.append(f"need_x_management_{int(code)}")
    X = np.column_stack(cols)
    school = d["school_id"].to_numpy(np.int32, copy=False)
    dy = d["district_code"].to_numpy(np.int64, copy=False) * 16 + d["year_index"].to_numpy(np.int64, copy=False)
    if cluster == "state":
        clusters = d["state_cluster"].to_numpy(np.int16, copy=False)
    else:
        clusters = d["district_code"].to_numpy(np.int32, copy=False)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, np.ones(len(d)),
            clusters, absorb_groups=[school, dy], names=names,
        )
    except RuntimeError:
        return None
    key = "need_x_muslim"
    ans = {
        "outcome": outcome, "exposure": exposure_name, "cluster": cluster,
        "n": fit["n"], "clusters": fit["clusters"],
        "need_coef": fit["coef"]["need"], "need_p": fit["p"]["need"],
        "need_x_muslim": fit["coef"][key], "need_x_muslim_se": fit["se"][key],
        "need_x_muslim_p": fit["p"][key], "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
        "need_x_sc": fit["coef"]["need_x_sc"], "need_x_st": fit["coef"]["need_x_st"], "need_x_obc": fit["coef"]["need_x_obc"],
    }
    del X
    gc.collect()
    return ans


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='5GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_inspection_safe_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=False, facility=True, profile2=True)
        df = _prepare(panel, con)
        mask = (df["is_state_local_government"] == 1) & df["need_index"].notna() & df["base_muslim"].notna()
        sample = df.loc[mask]
        del mask, df
        gc.collect()

        sample.groupby("academic_year", observed=True).agg(
            rows=("school_id","size"), schools=("school_id","nunique"), mean_need=("need_index","mean"),
            mean_base_muslim=("base_muslim","mean"), states=("state_cluster","nunique"), districts=("district_code","nunique")
        ).reset_index().to_csv(OUT/"sample_counts.csv", index=False)

        outcomes = [
            "next_log_total_visits", "next_log_senior_visits", "next_log_academic_inspections", "next_log_crc_visits",
            "next_log_block_visits", "next_log_district_state_visits", "next_any_senior_visits",
            "next_any_academic_inspections", "next_any_block_visits", "next_any_district_state_visits",
        ]
        rows: list[dict] = []
        core_mask = sample["is_core_government"].eq(1)
        for outcome in outcomes:
            for cluster, current, spec, universe, subset in [
                ("state", False, "primary", "main_1_2_3_6_89_90", sample),
                ("district", False, "district_cluster", "main_1_2_3_6_89_90", sample),
                ("state", True, "contemporaneous_exposure", "main_1_2_3_6_89_90", sample),
                ("state", False, "government_universe_robustness", "core_1_2_3", sample.loc[core_mask]),
            ]:
                ans = _fit(subset, outcome, cluster, current)
                if ans:
                    rows.append({"universe": universe, "spec": spec, **ans})
        primary_ix = [i for i, r in enumerate(rows) if r["spec"] == "primary"]
        qs = bh_qvalues([rows[i]["need_x_muslim_p"] for i in primary_ix])
        for i, qv in zip(primary_ix, qs):
            rows[i]["need_x_muslim_q"] = qv
        write_rows(OUT/"need_inspection_models.csv", rows)

        bin_frame = sample.loc[sample["need_index"] >= 0.5, ["school_id","state_cluster","need_index","base_muslim","next_log_total_visits","next_log_senior_visits","next_any_senior_visits"]].copy()
        bin_frame["muslim_bin"] = muslim_bin(bin_frame["base_muslim"])
        bin_rows = []
        for label, d in bin_frame.groupby("muslim_bin", observed=True):
            bin_rows.append({
                "muslim_bin": str(label), "school_years": len(d), "schools": d.school_id.nunique(), "states": d.state_cluster.nunique(),
                "mean_need": float(d.need_index.mean()),
                "mean_next_total_log_visits": float(pd.to_numeric(d.next_log_total_visits, errors="coerce").mean()),
                "mean_next_senior_log_visits": float(pd.to_numeric(d.next_log_senior_visits, errors="coerce").mean()),
                "next_any_senior_visit_rate": float(pd.to_numeric(d.next_any_senior_visits, errors="coerce").mean()),
            })
        write_rows(OUT/"five_pp_high_need_response.csv", bin_rows)
        write_json(OUT/"source_validation.json", reports)

        primary = [r for r in rows if r["spec"] == "primary" and r["universe"] == "main_1_2_3_6_89_90"]
        lines = [
            "# Need-to-inspection national experiment, corrected inference",
            "",
            f"Eligible government school-years with a valid need index: {len(sample):,}.",
            "",
            "Primary inference uses stable State-lineage clusters and memory-safe numeric fixed-effect identifiers. Following-year outcomes remain censored after exit from the State/local-government universe.",
        ]
        for r in primary:
            qv = r.get("need_x_muslim_q", float("nan"))
            lines.append(
                f"- {r['outcome']}: need x Muslim = {r['need_x_muslim']:+.4f} "
                f"(95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), "
                f"p={r['need_x_muslim_p']:.4g}, q={qv:.4g}, n={r['n']:,}, clusters={r['clusters']}"
            )
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
