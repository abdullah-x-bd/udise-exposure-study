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
from scipy.stats import t as student_t

import run_statewise_causal_stack as legacy
import run_need_inspection_memorysafe as inspection
import run_need_inspection_pyhdfe as pyins
from common import bh_qvalues
from statewise_panel import build_state_panel

MIN_CLUSTERS = 12
MIN_EXPOSURE_SD = 0.01
legacy.MIN_CLUSTERS = MIN_CLUSTERS
legacy.MIN_EXPOSURE_SD = MIN_EXPOSURE_SD


def _out(root: str, slug: str) -> Path:
    p = Path(root) / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def _status(out: Path, experiment: str, ok: bool, message: str = "") -> None:
    (out / f"{experiment}_status.json").write_text(
        json.dumps({"experiment": experiment, "ok": bool(ok), "message": message}, indent=2),
        encoding="utf-8",
    )


def _cluster_t_p(est: float, se: float, clusters: int) -> float:
    if not (np.isfinite(est) and np.isfinite(se) and se > 0 and clusters >= 2):
        return float("nan")
    return float(2.0 * student_t.sf(abs(est / se), df=clusters - 1))


def _cluster_t_ci(est: float, se: float, clusters: int) -> tuple[float, float]:
    if not (np.isfinite(est) and np.isfinite(se) and se >= 0 and clusters >= 2):
        return float("nan"), float("nan")
    crit = float(student_t.ppf(0.975, df=clusters - 1))
    return float(est - crit * se), float(est + crit * se)


def _retune_primary(out: Path, experiment: str) -> None:
    p = out / f"{experiment}_primary_tests.csv"
    if not p.exists() or p.stat().st_size == 0:
        return
    d = pd.read_csv(p)
    if not len(d):
        return
    d["p_normal_legacy"] = pd.to_numeric(d["p"], errors="coerce")
    est = pd.to_numeric(d["estimate"], errors="coerce")
    se = pd.to_numeric(d["se"], errors="coerce")
    clusters = pd.to_numeric(d["clusters"], errors="coerce")
    d["p"] = [
        _cluster_t_p(float(a), float(b), int(g)) if np.isfinite(g) else np.nan
        for a, b, g in zip(est, se, clusters)
    ]
    d["cluster_t_df"] = clusters - 1
    ci = [
        _cluster_t_ci(float(a), float(b), int(g)) if np.isfinite(g) else (np.nan, np.nan)
        for a, b, g in zip(est, se, clusters)
    ]
    d["cluster_t_ci_low"] = [x[0] for x in ci]
    d["cluster_t_ci_high"] = [x[1] for x in ci]

    # Retune pretrend tests when present.
    if {"pretrend_estimate", "pretrend_p"}.issubset(d.columns):
        d["pretrend_p_normal_legacy"] = pd.to_numeric(d["pretrend_p"], errors="coerce")
        pre_est = pd.to_numeric(d["pretrend_estimate"], errors="coerce")
        # Event-study/first-difference pretrend uses the same fitted covariance and cluster count.
        pre_se = []
        # The compact primary files did not store pretrend SE. Preserve the legacy pretrend p and mark it.
        d["pretrend_inference_note"] = "legacy normal p retained because compact file lacks pretrend SE"

    d["state_family_q"] = np.nan
    support = d["support_ok"].astype(str).str.lower().isin(["true", "1"])
    ids = d.index[support & pd.to_numeric(d["p"], errors="coerce").notna()].tolist()
    if ids:
        d.loc[ids, "state_family_q"] = bh_qvalues(pd.to_numeric(d.loc[ids, "p"], errors="coerce").tolist())
    d.to_csv(p, index=False)


def prepare(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    caps_doc = json.loads(Path(args.caps_json).read_text(encoding="utf-8"))
    caps = caps_doc["caps"] if "caps" in caps_doc else caps_doc
    con = duckdb.connect()
    con.execute("PRAGMA threads=3")
    con.execute("PRAGMA memory_limit='5GB'")
    with tempfile.TemporaryDirectory(prefix=f"statev2_{args.slug}_") as td:
        root = Path(td)
        panel, reports = build_state_panel(
            con, repo, token, root / "work", root / "panel",
            state_lineage=args.state,
            teacher=True, facility=True, profile2=True,
        )
        qin = str(panel).replace("'", "''")
        qout = str(Path(args.panel_out)).replace("'", "''")
        Path(args.panel_out).parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY (SELECT * FROM read_parquet('{qin}')) TO '{qout}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    stats = con.execute(
        f"SELECT COUNT(*) rows, COUNT(DISTINCT pseudocode) schools, COUNT(DISTINCT district) districts, "
        f"COUNT(DISTINCT academic_year) years, COUNT(DISTINCT state) states, "
        f"COUNT(*)-COUNT(DISTINCT pseudocode||'|'||academic_year) duplicate_school_years "
        f"FROM read_parquet('{str(Path(args.panel_out)).replace("'", "''")}')"
    ).fetchone()
    if int(stats[4]) != 1:
        raise RuntimeError(f"State leakage detected: distinct state labels={stats[4]}")
    if int(stats[5]) != 0:
        raise RuntimeError(f"Duplicate school-years detected: {stats[5]}")
    if int(stats[0]) == 0:
        raise RuntimeError(f"No rows found for {args.state}")

    required = {
        "academic_year", "pseudocode", "state", "district", "is_state_local_government",
        "enrol_primary", "muslim_primary", "total_teachers", "enrol_c1_12", "muslim_c1_12",
        "girls_func_toilets", "boys_func_toilets", "water_functional", "electricity_functional",
        "classrooms_major_repair", "academic_inspections", "crc_visits", "block_visits", "district_state_visits",
    }
    cols = {r[0] for r in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{str(Path(args.panel_out)).replace("'", "''")}')"
    ).fetchall()}
    missing = sorted(required - cols)
    if missing:
        raise RuntimeError(f"State panel missing required columns: {missing}")

    meta = {
        "state": args.state,
        "slug": args.slug,
        "panel_rows": int(stats[0]),
        "schools": int(stats[1]),
        "districts": int(stats[2]),
        "years": int(stats[3]),
        "inspection_caps": caps,
        "source_validation": reports,
        "builder": "statewise_panel.build_state_panel",
        "district_labels_normalized": True,
        "join_uniqueness_enforced": True,
    }
    (out / "prep_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(
        f"STATE V2 READY {args.state}: rows={stats[0]:,} schools={stats[1]:,} districts={stats[2]} years={stats[3]}",
        flush=True,
    )
    con.close()


def run_legacy(args: argparse.Namespace, command: str) -> None:
    out = _out(args.out_root, args.slug)
    funcs = {
        "distribution": legacy.distribution,
        "rte": legacy.run_rte,
        "timing": legacy.run_timing,
        "crossing": legacy.run_crossing,
        "repair": legacy.run_repair,
        "onset": legacy.run_onset,
    }
    funcs[command](args)
    exp = {
        "rte": "rte",
        "timing": "rte_timing",
        "crossing": "rte_crossing",
        "repair": "repair",
        "onset": "need_onset",
    }.get(command)
    if exp:
        _retune_primary(out, exp)
        print(f"CLUSTER-T RETUNED {args.state} {exp} df=G-1", flush=True)


def _patched_prepare(panel: Path, con: duckdb.DuckDBPyConnection, meta: dict) -> pd.DataFrame:
    caps = {k: float(v) for k, v in meta["inspection_caps"].items()}
    old = inspection._caps
    inspection._caps = lambda _panel, _con: caps
    try:
        return inspection._prepare(panel, con)
    finally:
        inspection._caps = old


def run_inspection(args: argparse.Namespace) -> None:
    out = _out(args.out_root, args.slug)
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    con = duckdb.connect()
    con.execute("PRAGMA threads=3")
    con.execute("PRAGMA memory_limit='4GB'")
    df = _patched_prepare(Path(args.panel), con, meta)
    base_mask = (
        df["is_state_local_government"].eq(1)
        & df["need_index"].notna()
        & df["base_muslim"].notna()
    )
    sample = df.loc[base_mask].copy()
    del df, base_mask
    gc.collect()

    district_count = int(sample["district_code"].nunique()) if len(sample) else 0
    if district_count < MIN_CLUSTERS:
        _status(out, "need_inspection", True, f"unsupported: district_clusters={district_count}<{MIN_CLUSTERS}")
        pd.DataFrame([{
            "state": args.state, "rows": len(sample), "schools": sample["school_id"].nunique() if len(sample) else 0,
            "districts": district_count, "support_ok": False, "support_reason": f"district_clusters<{MIN_CLUSTERS}"
        }]).to_csv(out / "need_inspection_counts.csv", index=False)
        print(f"INSPECTION SKIP {args.state}: only {district_count} district clusters", flush=True)
        con.close()
        return

    outcomes = legacy.INSPECTION_OUTCOMES
    rows: list[dict] = []
    primary: list[dict] = []

    for family, current, core_only, spec, universe in (
        ("primary", False, False, "primary_frozen", "main_1_2_3_6_89_90"),
        ("current", True, False, "contemporaneous_exposure", "main_1_2_3_6_89_90"),
        ("core", False, True, "core_government", "core_1_2_3"),
    ):
        d = sample.loc[sample["is_core_government"].eq(1)].copy() if core_only else sample
        if len(d) == 0:
            continue
        X, names = pyins._design(d, current=current)
        school = d["school_id"].to_numpy(np.int32, copy=True)
        dy = d["district_code"].to_numpy(np.int64, copy=False) * 16 + d["year_index"].to_numpy(np.int64, copy=False)
        district = d["district_code"].to_numpy(np.int32, copy=True)
        exposure = "muslim_share" if current else "base_muslim"
        exposure_sd = float(pd.to_numeric(d[exposure], errors="coerce").std())

        for outcome in outcomes:
            y = pd.to_numeric(d[outcome], errors="coerce").to_numpy(np.float32, copy=True)
            try:
                fits = pyins._fit_once(
                    y, X, names, school, dy, {"district": district},
                    f"state={args.state}|{family}|{outcome}",
                )
            except RuntimeError as exc:
                print(f"INSPECTION MODEL SKIP {args.state} {family} {outcome}: {exc}", flush=True)
                continue
            fit = fits["district"]
            key = "need_x_muslim"
            est = float(fit["coef"][key])
            se = float(fit["se"][key])
            g = int(fit["clusters"])
            p_t = _cluster_t_p(est, se, g)
            ci_low, ci_high = _cluster_t_ci(est, se, g)
            ok, reason = legacy._support(fit["n"], g, exposure_sd)
            row = {
                "state": args.state, "spec": spec, "universe": universe, "outcome": outcome,
                "exposure": "contemporaneous_composition" if current else "frozen_baseline_composition",
                "cluster": "district", "engine": "pyhdfe_sw_state",
                "n": fit["n"], "clusters": g,
                "need_coef": fit["coef"]["need"],
                "need_x_muslim": est, "need_x_muslim_se": se,
                "need_x_muslim_p_normal_legacy": fit["p"][key],
                "need_x_muslim_p": p_t,
                "ci_low": ci_low, "ci_high": ci_high,
                "need_x_sc": fit["coef"]["need_x_sc"],
                "need_x_st": fit["coef"]["need_x_st"],
                "need_x_obc": fit["coef"]["need_x_obc"],
                "support_ok": ok, "support_reason": reason,
            }
            rows.append(row)
            if family == "primary":
                primary.append({
                    "state": args.state, "experiment": "need_inspection", "test_id": outcome, "outcome": outcome,
                    "estimate": est, "se": se, "p": p_t, "n": fit["n"], "clusters": g,
                    "support_ok": ok, "support_reason": reason,
                    "cluster_t_ci_low": ci_low, "cluster_t_ci_high": ci_high,
                })
            del y, fits
            gc.collect()
        del X, school, dy, district
        if core_only:
            del d
        gc.collect()

    good = [r for r in primary if r["support_ok"] and np.isfinite(r["p"])]
    q = bh_qvalues([r["p"] for r in good]) if good else []
    for r, qq in zip(good, q):
        r["state_family_q"] = qq
    pd.DataFrame(rows).to_csv(out / "need_inspection_models.csv", index=False)
    if primary:
        pd.DataFrame(primary).to_csv(out / "need_inspection_primary_tests.csv", index=False)
    pd.DataFrame([{
        "state": args.state, "rows": len(sample), "schools": sample["school_id"].nunique(),
        "districts": district_count, "mean_need": sample["need_index"].mean(),
        "mean_base_muslim": sample["base_muslim"].mean(),
    }]).to_csv(out / "need_inspection_counts.csv", index=False)
    _status(out, "need_inspection", True, f"models={len(rows)} engine=pyhdfe_sw_state")
    print(f"INSPECTION V2 DONE {args.state}: models={len(rows)}", flush=True)
    con.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "distribution", "rte", "timing", "crossing", "repair", "onset", "inspection"])
    p.add_argument("--state", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--out-root", default="studies/muslim_government_school_equity/outputs/statewise_causal_v2")
    p.add_argument("--panel")
    p.add_argument("--panel-out")
    p.add_argument("--meta")
    p.add_argument("--caps-json")
    args = p.parse_args()
    out = _out(args.out_root, args.slug)
    try:
        if args.command == "prepare":
            if not args.panel_out or not args.caps_json:
                raise RuntimeError("prepare requires --panel-out and --caps-json")
            prepare(args)
        elif args.command == "inspection":
            run_inspection(args)
        else:
            run_legacy(args, args.command)
    except Exception as exc:
        _status(out, args.command, False, f"{type(exc).__name__}: {exc}")
        print(f"STATEWISE V2 FAILURE {args.state} {args.command}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
