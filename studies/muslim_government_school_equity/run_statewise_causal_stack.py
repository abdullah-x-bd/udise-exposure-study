from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import RTE_CUTOFFS, bh_qvalues, build_panel, write_json, write_rows
from cluster_harmonization import state_sql
import run_rte_staffing as rte
import run_rte_timing_hardened as timing
import run_rte_crossing_eventstudy as crossing
import run_failure_to_repair as repair
import run_need_inspection_memorysafe as inspection
import run_need_onset_firstdiff as onset

MIN_CLUSTERS = 8
MIN_EXPOSURE_SD = 0.01
RTE_OUTCOMES = (
    "total_teachers", "meets_norm", "primary_serving_teachers", "regular_teachers",
    "contract_teachers", "female_teachers", "next_total_teachers",
)
INSPECTION_OUTCOMES = [
    "next_log_total_visits", "next_log_senior_visits", "next_log_academic_inspections",
    "next_log_crc_visits", "next_log_block_visits", "next_log_district_state_visits",
    "next_any_senior_visits", "next_any_academic_inspections", "next_any_block_visits",
    "next_any_district_state_visits",
]


def _out(root: str, slug: str) -> Path:
    p = Path(root) / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def _status(out: Path, experiment: str, ok: bool, message: str = "") -> None:
    (out / f"{experiment}_status.json").write_text(
        json.dumps({"experiment": experiment, "ok": bool(ok), "message": message}, indent=2),
        encoding="utf-8",
    )


def _read_meta(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _support(n: int | float | None, clusters: int | float | None, exposure_sd: float | None = None) -> tuple[bool, str]:
    n0 = int(n or 0)
    c0 = int(clusters or 0)
    reasons = []
    if n0 < 500:
        reasons.append("n<500")
    if c0 < MIN_CLUSTERS:
        reasons.append(f"district_clusters<{MIN_CLUSTERS}")
    if exposure_sd is not None and (not np.isfinite(exposure_sd) or exposure_sd < MIN_EXPOSURE_SD):
        reasons.append(f"muslim_share_sd<{MIN_EXPOSURE_SD}")
    return (not reasons), ";".join(reasons)


def _append_primary(out: Path, experiment: str, rows: list[dict]) -> None:
    if not rows:
        return
    for r in rows:
        r["experiment"] = experiment
    pd.DataFrame(rows).to_csv(out / f"{experiment}_primary_tests.csv", index=False)


def prepare(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    con = duckdb.connect()
    con.execute("PRAGMA threads=3")
    con.execute("PRAGMA memory_limit='5GB'")
    work_root = Path(args.work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    full_dir = work_root / "full_panel"
    extract_dir = work_root / "extract"
    panel, reports = build_panel(
        con, repo, token, extract_dir, full_dir,
        teacher=True, facility=True, profile2=True,
    )
    # Preserve national winsorization scale for all state inspection/onset runs.
    caps = inspection._caps(panel, con)

    target = args.state.replace("'", "''")
    qin = str(panel).replace("'", "''")
    qout = str(Path(args.panel_out)).replace("'", "''")
    canon = state_sql("state")
    con.execute(
        f"COPY (SELECT * REPLACE ({canon} AS state) FROM read_parquet('{qin}') "
        f"WHERE {canon}='{target}') TO '{qout}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    stats = con.execute(
        f"SELECT COUNT(*) rows, COUNT(DISTINCT pseudocode) schools, COUNT(DISTINCT district) districts, "
        f"COUNT(DISTINCT academic_year) years FROM read_parquet('{qout}')"
    ).fetchone()
    meta = {
        "state": args.state,
        "slug": args.slug,
        "panel_rows": int(stats[0]),
        "schools": int(stats[1]),
        "districts": int(stats[2]),
        "years": int(stats[3]),
        "inspection_caps": caps,
        "source_validation": reports,
    }
    (out / "prep_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"STATE READY {args.state}: rows={stats[0]:,} schools={stats[1]:,} districts={stats[2]} years={stats[3]}", flush=True)
    if stats[0] == 0:
        raise RuntimeError(f"No rows found for canonical state {args.state}")
    con.close()


def distribution(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    con = duckdb.connect()
    q = str(Path(args.panel)).replace("'", "''")
    base = f"""
      WITH s AS (
        SELECT academic_year,pseudocode,enrol_c1_12,muslim_c1_12,
               muslim_c1_12/NULLIF(enrol_c1_12,0) AS muslim_share
        FROM read_parquet('{q}')
        WHERE academic_year='2025-26' AND is_state_local_government=1
          AND enrol_c1_12>0 AND muslim_c1_12 IS NOT NULL
      ), b AS (
        SELECT *, CASE
          WHEN muslim_share=0 THEN '0%'
          WHEN muslim_share<=0.05 THEN '>0-5%'
          WHEN muslim_share<=0.10 THEN '>5-10%'
          WHEN muslim_share<=0.20 THEN '>10-20%'
          WHEN muslim_share<=0.30 THEN '>20-30%'
          WHEN muslim_share<=0.40 THEN '>30-40%'
          WHEN muslim_share<=0.50 THEN '>40-50%'
          WHEN muslim_share<=0.75 THEN '>50-75%'
          ELSE '>75-100%' END AS band
        FROM s
      )
    """
    dist = con.execute(base + """
      SELECT band, COUNT(*) schools, SUM(enrol_c1_12) students, SUM(muslim_c1_12) muslim_students,
             AVG(muslim_share) mean_school_muslim_share
      FROM b GROUP BY band
    """).df()
    total_muslim = float(dist["muslim_students"].sum()) if len(dist) else 0.0
    dist["share_state_muslim_students"] = dist["muslim_students"] / total_muslim if total_muslim else np.nan
    dist.insert(0, "state", args.state)
    dist.to_csv(out / "distribution_bands.csv", index=False)

    summary = con.execute(base + """
      SELECT COUNT(*) schools, SUM(enrol_c1_12) students, SUM(muslim_c1_12) muslim_students,
             AVG(muslim_share) mean_school_muslim_share,
             SUM(CASE WHEN muslim_share>0.5 THEN 1 ELSE 0 END) muslim_majority_schools,
             SUM(CASE WHEN muslim_share>0.5 THEN muslim_c1_12 ELSE 0 END) muslim_students_in_majority_schools,
             SUM(CASE WHEN muslim_share>=0.75 THEN muslim_c1_12 ELSE 0 END) muslim_students_in_75plus_schools
      FROM b
    """).df()
    if len(summary):
        summary.insert(0, "state", args.state)
        ms = float(summary.loc[0, "muslim_students"] or 0)
        summary["share_muslim_students_in_majority_schools"] = (
            float(summary.loc[0, "muslim_students_in_majority_schools"] or 0) / ms if ms else np.nan
        )
        summary["share_muslim_students_in_75plus_schools"] = (
            float(summary.loc[0, "muslim_students_in_75plus_schools"] or 0) / ms if ms else np.nan
        )
    summary.to_csv(out / "distribution_summary.csv", index=False)
    _status(out, "distribution", True)
    print(summary.to_string(index=False), flush=True)
    con.close()


def run_rte(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    df = rte._prepare(Path(args.panel), con)
    sample = df.loc[df["lag_muslim_share"].notna()].copy()
    core = sample.loc[sample["is_core_government"].eq(1)].copy()
    rows: list[dict] = []
    primary: list[dict] = []

    for outcome in RTE_OUTCOMES:
        for cutoff in RTE_CUTOFFS:
            specs = [
                (sample, 20.0, "lag_muslim_share", False, "primary_bw20", "main_1_2_3_6_89_90"),
                (sample, 15.0, "lag_muslim_share", False, "bandwidth_15", "main_1_2_3_6_89_90"),
                (sample, 30.0, "lag_muslim_share", False, "bandwidth_30", "main_1_2_3_6_89_90"),
                (sample, 20.0, "lag_muslim_share", True, "donut", "main_1_2_3_6_89_90"),
                (sample, 20.0, "frozen_muslim_share", False, "frozen_exposure", "main_1_2_3_6_89_90"),
                (core, 20.0, "lag_muslim_share", False, "core_government", "core_1_2_3"),
            ]
            for d, bw, exposure, donut, spec, universe in specs:
                if len(d) == 0:
                    continue
                ans = rte._fit_one(d, cutoff=float(cutoff), bw=bw, outcome=outcome, exposure=exposure,
                                   cluster_col="district", donut=donut)
                if not ans:
                    continue
                # Exposure variation in the actual local window.
                rr = (pd.to_numeric(d["enrol_primary"], errors="coerce") - float(cutoff)).abs() <= bw
                sd = float(pd.to_numeric(d.loc[rr, exposure], errors="coerce").std())
                ok, reason = _support(ans["n"], ans["clusters"], sd)
                row = {"state": args.state, "spec": spec, "universe": universe,
                       "support_ok": ok, "support_reason": reason, **ans}
                rows.append(row)
                if spec == "primary_bw20" and outcome in ("total_teachers", "meets_norm"):
                    primary.append({
                        "state": args.state, "test_id": f"{outcome}|cutoff={cutoff}", "outcome": outcome,
                        "cutoff": cutoff, "estimate": ans["muslim_interaction"],
                        "se": ans["muslim_interaction_se"], "p": ans["muslim_interaction_p"],
                        "n": ans["n"], "clusters": ans["clusters"], "support_ok": ok,
                        "support_reason": reason,
                    })
    # State-specific placebo cutoffs for total teachers.
    for cutoff in rte.FAKE_CUTOFFS:
        ans = rte._fit_one(sample, cutoff=float(cutoff), bw=20.0, outcome="total_teachers",
                           exposure="lag_muslim_share", cluster_col="district")
        if ans:
            ok, reason = _support(ans["n"], ans["clusters"])
            rows.append({"state": args.state, "spec": "fake_cutoff", "universe": "main_1_2_3_6_89_90",
                         "support_ok": ok, "support_reason": reason, **ans})
    # Stacked narrow-window result, with district names substituted solely as the clustering vector.
    tmp = sample.copy(); tmp["state"] = tmp["district"].astype(str)
    stacked = rte._stacked_fit(tmp, "total_teachers", "lag_muslim_share", bw=10.0)
    if stacked:
        ok, reason = _support(stacked["n"], stacked["clusters"])
        stacked.update(state=args.state, spec="stacked_bw10", universe="main_1_2_3_6_89_90",
                       support_ok=ok, support_reason=reason, cluster="district")
        rows.append(stacked)

    if primary:
        q = bh_qvalues([r["p"] for r in primary if r["support_ok"]])
        j = 0
        for r in primary:
            if r["support_ok"]:
                r["state_family_q"] = q[j]; j += 1
    pd.DataFrame(rows).to_csv(out / "rte_models.csv", index=False)
    _append_primary(out, "rte", primary)
    _status(out, "rte", True, f"models={len(rows)}")
    print(f"RTE DONE {args.state}: models={len(rows)} headline_tests={len(primary)}", flush=True)
    con.close(); del df, sample, core; gc.collect()


def run_timing(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    df = timing._prepare(Path(args.panel), con)
    core = df.loc[df["is_core_government"].eq(1)].copy()
    rows: list[dict] = []
    primary: list[dict] = []
    for cutoff in RTE_CUTOFFS:
        specs = [
            (df, "lag_muslim_share", False, True, "primary_persistent", "main_1_2_3_6_89_90"),
            (df, "frozen_muslim_share", False, True, "frozen_exposure", "main_1_2_3_6_89_90"),
            (df, "lag_muslim_share", True, True, "donut", "main_1_2_3_6_89_90"),
            (df, "lag_muslim_share", False, False, "continuity_only", "main_1_2_3_6_89_90"),
            (df, "lead_muslim_share", False, True, "future_share_placebo", "main_1_2_3_6_89_90"),
            (core, "lag_muslim_share", False, True, "core_government", "core_1_2_3"),
        ]
        for d, exposure, donut, persistent, spec, universe in specs:
            if len(d) == 0:
                continue
            ans = timing._fit(d, float(cutoff), exposure=exposure, cluster="district",
                              donut=donut, persistent=persistent, bw=20.0)
            if not ans:
                continue
            sd = float(pd.to_numeric(d[exposure], errors="coerce").std())
            ok, reason = _support(ans["n"], ans["clusters"], sd)
            row = {"state": args.state, "spec": spec, "universe": universe,
                   "support_ok": ok, "support_reason": reason, **ans}
            rows.append(row)
            if spec == "primary_persistent":
                primary.append({
                    "state": args.state, "test_id": f"next_total_teachers|cutoff={cutoff}",
                    "outcome": "next_total_teachers", "cutoff": cutoff,
                    "estimate": ans["muslim_interaction"], "se": ans["muslim_interaction_se"],
                    "p": ans["muslim_interaction_p"], "n": ans["n"], "clusters": ans["clusters"],
                    "support_ok": ok, "support_reason": reason,
                })
    if primary:
        good = [r for r in primary if r["support_ok"]]
        q = bh_qvalues([r["p"] for r in good]) if good else []
        for r, qq in zip(good, q): r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "rte_timing_models.csv", index=False)
    _append_primary(out, "rte_timing", primary)
    _status(out, "rte_timing", True, f"models={len(rows)}")
    print(f"TIMING DONE {args.state}: models={len(rows)}", flush=True)
    con.close(); del df, core; gc.collect()


def run_crossing(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    ev = crossing._prepare(Path(args.panel), con)
    # crossing._fit uses `state` only as its cluster vector. Within-state inference must cluster by district.
    fit_ev = ev.copy()
    fit_ev["state"] = fit_ev["district"].astype(str)
    rows: list[dict] = []
    primary: list[dict] = []
    for cutoff in RTE_CUTOFFS:
        for outcome in ("total_teachers", "teacher_deficit", "meets_norm"):
            ans = crossing._fit(fit_ev, outcome, float(cutoff))
            if not ans:
                continue
            sub = ev.loc[ev["cutoff"].eq(float(cutoff)) & ev["event_time"].between(-2, 2)]
            sd = float(pd.to_numeric(sub["frozen_muslim"], errors="coerce").std())
            ok, reason = _support(ans["n"], ans["clusters"], sd)
            row = {"state": args.state, "cluster": "district", "support_ok": ok,
                   "support_reason": reason, **ans}
            rows.append(row)
            if outcome == "total_teachers":
                for k in (0, 1):
                    primary.append({
                        "state": args.state, "test_id": f"total_teachers|cutoff={cutoff}|event={k}",
                        "outcome": "total_teachers", "cutoff": cutoff, "event_time": k,
                        "estimate": ans[f"muslim_event_{k}"], "se": ans[f"muslim_event_{k}_se"],
                        "p": ans[f"muslim_event_{k}_p"], "pretrend_estimate": ans["muslim_event_-2"],
                        "pretrend_p": ans["muslim_event_-2_p"], "n": ans["n"],
                        "clusters": ans["clusters"], "support_ok": ok, "support_reason": reason,
                    })
    good = [r for r in primary if r["support_ok"]]
    q = bh_qvalues([r["p"] for r in good]) if good else []
    for r, qq in zip(good, q): r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "rte_crossing_models.csv", index=False)
    _append_primary(out, "rte_crossing", primary)
    _status(out, "rte_crossing", True, f"models={len(rows)}")
    print(f"CROSSING DONE {args.state}: models={len(rows)}", flush=True)
    con.close(); del ev, fit_ev; gc.collect()


def run_repair(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    evall = repair._prepare_events(Path(args.panel), con)
    rows: list[dict] = []
    primary: list[dict] = []
    for failure, ev in evall.groupby("failure_type"):
        core = ev.loc[ev["is_core_government"].eq(1)].copy()
        for h in (1, 2, 3):
            outcome = f"repair_by_{h}"
            specs = [
                (ev, "lag_muslim_share", "primary", "main_1_2_3_6_89_90"),
                (ev, "frozen_muslim_share", "frozen_exposure", "main_1_2_3_6_89_90"),
                (core, "lag_muslim_share", "core_government", "core_1_2_3"),
            ]
            for d, exposure, spec, universe in specs:
                if len(d) == 0:
                    continue
                ans = repair._fit(d, outcome, exposure, "district")
                if not ans:
                    continue
                sd = float(pd.to_numeric(d[exposure], errors="coerce").std())
                ok, reason = _support(ans["n"], ans["clusters"], sd)
                row = {"state": args.state, "failure_type": failure, "horizon_years": h,
                       "outcome": outcome, "exposure": exposure, "spec": spec, "universe": universe,
                       "support_ok": ok, "support_reason": reason, **ans}
                rows.append(row)
                if spec == "primary":
                    primary.append({
                        "state": args.state, "test_id": f"{failure}|{h}y", "outcome": outcome,
                        "domain": failure, "horizon_years": h, "estimate": ans["coef_muslim_share"],
                        "se": ans["se_muslim_share"], "p": ans["p_muslim_share"],
                        "n": ans["n"], "clusters": ans["clusters"], "support_ok": ok,
                        "support_reason": reason,
                    })
    good = [r for r in primary if r["support_ok"]]
    q = bh_qvalues([r["p"] for r in good]) if good else []
    for r, qq in zip(good, q): r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "repair_models.csv", index=False)
    _append_primary(out, "repair", primary)
    # aggregate event counts only
    if len(evall):
        evall.groupby(["academic_year", "failure_type"]).agg(
            events=("pseudocode", "size"), schools=("pseudocode", "nunique"), districts=("district", "nunique")
        ).reset_index().assign(state=args.state).to_csv(out / "repair_event_counts.csv", index=False)
    _status(out, "repair", True, f"models={len(rows)} events={len(evall)}")
    print(f"REPAIR DONE {args.state}: events={len(evall):,} models={len(rows)}", flush=True)
    con.close(); del evall; gc.collect()


def _patched_prepare(panel: Path, con: duckdb.DuckDBPyConnection, meta: dict) -> pd.DataFrame:
    caps = {k: float(v) for k, v in meta["inspection_caps"].items()}
    old = inspection._caps
    inspection._caps = lambda _panel, _con: caps
    try:
        return inspection._prepare(panel, con)
    finally:
        inspection._caps = old


def run_onset(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug); meta = _read_meta(args.meta)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    df = _patched_prepare(Path(args.panel), con, meta)
    ev = onset._events(df)
    del df; gc.collect()
    rows: list[dict] = []
    primary: list[dict] = []
    for outcome in onset.OUTCOMES:
        for phase, spec in (("post", "primary"), ("pre", "pretrend_placebo")):
            ans = onset._fit(ev, outcome, phase=phase, cluster="district", core=False)
            if not ans:
                continue
            sd = float(pd.to_numeric(ev["base_muslim"], errors="coerce").std())
            ok, reason = _support(ans["n"], ans["clusters"], sd)
            row = {"state": args.state, "spec": spec, "support_ok": ok, "support_reason": reason, **ans}
            rows.append(row)
            if spec == "primary":
                primary.append({
                    "state": args.state, "test_id": outcome, "outcome": outcome,
                    "estimate": ans["muslim_coef"], "se": ans["muslim_se"], "p": ans["muslim_p"],
                    "n": ans["n"], "clusters": ans["clusters"], "support_ok": ok,
                    "support_reason": reason,
                })
        ans = onset._fit(ev, outcome, phase="post", cluster="district", core=True)
        if ans:
            ok, reason = _support(ans["n"], ans["clusters"])
            rows.append({"state": args.state, "spec": "core_government", "support_ok": ok,
                         "support_reason": reason, **ans})
    # attach corresponding pretrend to headline tests
    for p in primary:
        pre = next((r for r in rows if r.get("spec") == "pretrend_placebo" and r.get("outcome") == p["outcome"]), None)
        if pre:
            p["pretrend_estimate"] = pre["muslim_coef"]; p["pretrend_p"] = pre["muslim_p"]
    good = [r for r in primary if r["support_ok"]]
    q = bh_qvalues([r["p"] for r in good]) if good else []
    for r, qq in zip(good, q): r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "need_onset_models.csv", index=False)
    _append_primary(out, "need_onset", primary)
    if len(ev):
        pd.DataFrame([{"state": args.state, "events": len(ev), "schools": ev["school_id"].nunique(),
                       "districts": ev["district_code"].nunique()}]).to_csv(out / "need_onset_counts.csv", index=False)
    _status(out, "need_onset", True, f"events={len(ev)} models={len(rows)}")
    print(f"ONSET DONE {args.state}: events={len(ev):,} models={len(rows)}", flush=True)
    con.close(); del ev; gc.collect()


def run_inspection(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug); meta = _read_meta(args.meta)
    con = duckdb.connect(); con.execute("PRAGMA threads=3"); con.execute("PRAGMA memory_limit='5GB'")
    df = _patched_prepare(Path(args.panel), con, meta)
    mask = df["is_state_local_government"].eq(1) & df["need_index"].notna() & df["base_muslim"].notna()
    sample = df.loc[mask].copy(); del df, mask; gc.collect()
    core = sample.loc[sample["is_core_government"].eq(1)].copy()
    rows: list[dict] = []
    primary: list[dict] = []
    for outcome in INSPECTION_OUTCOMES:
        specs = [
            (sample, False, "primary_frozen", "main_1_2_3_6_89_90"),
            (sample, True, "contemporaneous_exposure", "main_1_2_3_6_89_90"),
            (core, False, "core_government", "core_1_2_3"),
        ]
        for d, current, spec, universe in specs:
            if len(d) == 0:
                continue
            print(f"INSPECTION FIT {args.state} {outcome} {spec} rows={len(d):,}", flush=True)
            ans = inspection._fit(d, outcome, cluster="district", current_exposure=current)
            if not ans:
                continue
            exposure = "muslim_share" if current else "base_muslim"
            sd = float(pd.to_numeric(d[exposure], errors="coerce").std())
            ok, reason = _support(ans["n"], ans["clusters"], sd)
            row = {"state": args.state, "spec": spec, "universe": universe,
                   "support_ok": ok, "support_reason": reason, **ans}
            rows.append(row)
            if spec == "primary_frozen":
                primary.append({
                    "state": args.state, "test_id": outcome, "outcome": outcome,
                    "estimate": ans["need_x_muslim"], "se": ans["need_x_muslim_se"],
                    "p": ans["need_x_muslim_p"], "n": ans["n"], "clusters": ans["clusters"],
                    "support_ok": ok, "support_reason": reason,
                })
            gc.collect()
    good = [r for r in primary if r["support_ok"]]
    q = bh_qvalues([r["p"] for r in good]) if good else []
    for r, qq in zip(good, q): r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "need_inspection_models.csv", index=False)
    _append_primary(out, "need_inspection", primary)
    if len(sample):
        pd.DataFrame([{"state": args.state, "rows": len(sample), "schools": sample["school_id"].nunique(),
                       "districts": sample["district_code"].nunique(), "mean_need": sample["need_index"].mean(),
                       "mean_base_muslim": sample["base_muslim"].mean()}]).to_csv(out / "need_inspection_counts.csv", index=False)
    _status(out, "need_inspection", True, f"models={len(rows)}")
    print(f"INSPECTION DONE {args.state}: models={len(rows)}", flush=True)
    con.close(); del sample, core; gc.collect()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "distribution", "rte", "timing", "crossing", "repair", "onset", "inspection"])
    p.add_argument("--state", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--out-root", default="studies/muslim_government_school_equity/outputs/statewise_causal")
    p.add_argument("--panel")
    p.add_argument("--panel-out")
    p.add_argument("--meta")
    p.add_argument("--work-root", default="/tmp/statewise_udise_work")
    args = p.parse_args()
    out = _out(args.out_root, args.slug)
    funcs = {
        "prepare": prepare, "distribution": distribution, "rte": run_rte, "timing": run_timing,
        "crossing": run_crossing, "repair": run_repair, "onset": run_onset, "inspection": run_inspection,
    }
    try:
        funcs[args.command](args)
    except Exception as e:
        _status(out, args.command, False, f"{type(e).__name__}: {e}")
        print(f"STATEWISE FAILURE {args.state} {args.command}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
