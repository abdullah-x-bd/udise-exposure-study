from __future__ import annotations

import gc
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyhdfe

from common import build_panel, write_json, write_rows
from run_need_inspection_memorysafe import _prepare

OUT_ROOT = Path("studies/muslim_government_school_equity/outputs/need_inspection_pyhdfe")
OUTCOMES = [
    "next_log_total_visits",
    "next_log_senior_visits",
    "next_log_academic_inspections",
    "next_log_crc_visits",
    "next_log_block_visits",
    "next_log_district_state_visits",
    "next_any_senior_visits",
    "next_any_academic_inspections",
    "next_any_block_visits",
    "next_any_district_state_visits",
]


def _design(df: pd.DataFrame, current: bool) -> tuple[np.ndarray, list[str]]:
    need = pd.to_numeric(df["need_index"], errors="coerce").to_numpy(np.float32, copy=False)
    if current:
        m = pd.to_numeric(df["muslim_share"], errors="coerce").to_numpy(np.float32, copy=False)
        sc = pd.to_numeric(df["sc_share"], errors="coerce").to_numpy(np.float32, copy=False)
        st = pd.to_numeric(df["st_share"], errors="coerce").to_numpy(np.float32, copy=False)
        obc = pd.to_numeric(df["obc_share"], errors="coerce").to_numpy(np.float32, copy=False)
    else:
        m = pd.to_numeric(df["base_muslim"], errors="coerce").to_numpy(np.float32, copy=False)
        sc = pd.to_numeric(df["base_sc"], errors="coerce").to_numpy(np.float32, copy=False)
        st = pd.to_numeric(df["base_st"], errors="coerce").to_numpy(np.float32, copy=False)
        obc = pd.to_numeric(df["base_obc"], errors="coerce").to_numpy(np.float32, copy=False)

    enrol = np.log1p(pd.to_numeric(df["enrol_c1_12"], errors="coerce").to_numpy(np.float32, copy=False)).astype(np.float32)
    rural = pd.to_numeric(df["base_rural"], errors="coerce").to_numpy(np.float32, copy=False)
    observed = pd.to_numeric(df["need_components_observed"], errors="coerce").to_numpy(np.float32, copy=False)
    mgmt = pd.to_numeric(df["base_management"], errors="coerce").to_numpy(np.float32, copy=False)

    cols = [need, need * m, need * sc, need * st, need * obc, enrol, need * rural, observed]
    names = [
        "need", "need_x_muslim", "need_x_sc", "need_x_st", "need_x_obc",
        "log_enrolment", "need_x_rural", "need_components_observed",
    ]
    finite_codes = np.unique(mgmt[np.isfinite(mgmt)])
    if finite_codes.size:
        base = finite_codes.min()
        for code in finite_codes:
            if code == base:
                continue
            cols.append(need * (mgmt == code).astype(np.float32))
            names.append(f"need_x_management_{int(code)}")
    return np.column_stack(cols).astype(np.float32, copy=False), names


def _cluster_vcov(
    X: np.ndarray,
    resid: np.ndarray,
    cluster: np.ndarray,
    bread_inv: np.ndarray,
) -> tuple[np.ndarray, int]:
    unique, inv = np.unique(cluster, return_inverse=True)
    g = len(unique)
    k = X.shape[1]
    scores = np.zeros((g, k), dtype=np.float64)
    for j in range(k):
        weights = X[:, j].astype(np.float64, copy=False) * resid
        scores[:, j] = np.bincount(inv, weights=weights, minlength=g)
    meat = scores.T @ scores
    vcov = bread_inv @ meat @ bread_inv
    n = len(resid)
    if g > 1 and n > k:
        vcov *= (g / (g - 1)) * ((n - 1) / (n - k))
    return vcov, g


def _fit_once(
    y: np.ndarray,
    X: np.ndarray,
    names: list[str],
    school: np.ndarray,
    district_year: np.ndarray,
    clusters: dict[str, np.ndarray],
    label: str,
) -> dict[str, dict]:
    valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    n = int(valid.sum())
    if n <= X.shape[1] + 20:
        raise RuntimeError(f"insufficient observations for {label}: n={n}")

    yv = y[valid]
    Xv = X[valid]
    school_v = school[valid]
    dy_v = district_year[valid]
    cluster_v = {name: values[valid] for name, values in clusters.items()}

    print(
        f"HDFE START {label}: n={n:,}, k={Xv.shape[1]}, schools={np.unique(school_v).size:,}, "
        f"district_year={np.unique(dy_v).size:,}",
        flush=True,
    )
    started = time.monotonic()

    # PyHDFE's Somaini-Wolak algorithm is non-iterative and is specialized for exactly two FE dimensions.
    # Put the lower-cardinality district-year FE first as recommended by PyHDFE for memory efficiency.
    ids = np.column_stack([dy_v, school_v]).astype(np.int64, copy=False)
    algorithm = pyhdfe.create(
        ids,
        drop_singletons=False,
        compute_degrees=False,
        residualize_method="sw",
    )
    z = np.column_stack([yv, Xv]).astype(np.float64, copy=False)
    zr = algorithm.residualize(z)
    del z, ids, algorithm
    gc.collect()

    ya = zr[:, 0]
    Xa = zr[:, 1:]
    xtx = np.einsum("ni,nj->ij", Xa, Xa, dtype=np.float64, optimize=True)
    xty = np.einsum("ni,n->i", Xa, ya, dtype=np.float64, optimize=True)
    bread_inv = np.linalg.pinv(xtx)
    beta = bread_inv @ xty
    resid = ya - Xa @ beta

    out: dict[str, dict] = {}
    for cname, cvals in cluster_v.items():
        vcov, g = _cluster_vcov(Xa, resid, cvals, bread_inv)
        se = np.sqrt(np.maximum(np.diag(vcov), 0.0))
        zstat = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
        p = np.array([math.erfc(abs(v) / math.sqrt(2)) if np.isfinite(v) else np.nan for v in zstat])
        out[cname] = {
            "n": n,
            "clusters": int(g),
            "coef": dict(zip(names, map(float, beta))),
            "se": dict(zip(names, map(float, se))),
            "p": dict(zip(names, map(float, p))),
            "ci_low": dict(zip(names, map(float, beta - 1.96 * se))),
            "ci_high": dict(zip(names, map(float, beta + 1.96 * se))),
        }

    elapsed = time.monotonic() - started
    print(f"HDFE DONE {label}: {elapsed:.1f}s", flush=True)
    del zr, Xa, ya, resid, bread_inv, Xv, yv, school_v, dy_v, cluster_v
    gc.collect()
    return out


def _model_row(fit: dict, *, outcome: str, spec: str, universe: str, exposure: str, cluster: str) -> dict:
    key = "need_x_muslim"
    return {
        "universe": universe,
        "spec": spec,
        "outcome": outcome,
        "exposure": exposure,
        "cluster": cluster,
        "engine": "pyhdfe_sw",
        "n": fit["n"],
        "clusters": fit["clusters"],
        "need_coef": fit["coef"]["need"],
        "need_p": fit["p"]["need"],
        "need_x_muslim": fit["coef"][key],
        "need_x_muslim_se": fit["se"][key],
        "need_x_muslim_p": fit["p"][key],
        "ci_low": fit["ci_low"][key],
        "ci_high": fit["ci_high"][key],
        "need_x_sc": fit["coef"]["need_x_sc"],
        "need_x_st": fit["coef"]["need_x_st"],
        "need_x_obc": fit["coef"]["need_x_obc"],
    }


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"primary", "current", "core"}:
        raise SystemExit("usage: run_need_inspection_pyhdfe.py {primary|current|core}")
    family = sys.argv[1]
    out = OUT_ROOT / family
    out.mkdir(parents=True, exist_ok=True)

    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='4GB'")

    with tempfile.TemporaryDirectory(prefix=f"muslim_equity_pyhdfe_{family}_") as td:
        root = Path(td)
        panel, reports = build_panel(
            con, repo, token, root / "work", root / "panel",
            teacher=False, facility=True, profile2=True,
        )
        df = _prepare(panel, con)
        base_mask = (
            df["is_state_local_government"].eq(1)
            & df["need_index"].notna()
            & df["base_muslim"].notna()
        )
        if family == "core":
            base_mask &= df["is_core_government"].eq(1)

        required = [
            "academic_year", "year_index", "school_id", "state_cluster", "district_code",
            "is_core_government", "enrol_c1_12", "muslim_share", "sc_share", "st_share", "obc_share",
            "base_muslim", "base_sc", "base_st", "base_obc", "base_rural", "base_management",
            "need_components_observed", "need_index",
        ] + OUTCOMES
        sample = df.loc[base_mask, required].copy()
        del df, base_mask
        gc.collect()

        if family == "primary":
            sample.groupby("academic_year", observed=True).agg(
                rows=("school_id", "size"),
                schools=("school_id", "nunique"),
                mean_need=("need_index", "mean"),
                mean_base_muslim=("base_muslim", "mean"),
                states=("state_cluster", "nunique"),
                districts=("district_code", "nunique"),
            ).reset_index().to_csv(out / "sample_counts.csv", index=False)

            high_need = sample.loc[sample["need_index"] >= 0.5, [
                "school_id", "state_cluster", "need_index", "base_muslim",
                "next_log_total_visits", "next_log_senior_visits", "next_any_senior_visits",
            ]].copy()
            high_need["muslim_bin"] = pd.cut(
                high_need["base_muslim"], bins=np.linspace(0, 1, 21), include_lowest=True,
            )
            bins = high_need.groupby("muslim_bin", observed=True).agg(
                school_years=("school_id", "size"),
                schools=("school_id", "nunique"),
                states=("state_cluster", "nunique"),
                mean_need=("need_index", "mean"),
                mean_next_total_log_visits=("next_log_total_visits", "mean"),
                mean_next_senior_log_visits=("next_log_senior_visits", "mean"),
                next_any_senior_visit_rate=("next_any_senior_visits", "mean"),
            ).reset_index()
            bins["muslim_bin"] = bins["muslim_bin"].astype(str)
            bins.to_csv(out / "five_pp_high_need_response.csv", index=False)
            write_json(out / "source_validation.json", reports)
            del high_need, bins
            gc.collect()

        current = family == "current"
        X, names = _design(sample, current=current)
        school = sample["school_id"].to_numpy(np.int32, copy=True)
        dy = (
            sample["district_code"].to_numpy(np.int64, copy=False) * 16
            + sample["year_index"].to_numpy(np.int64, copy=False)
        )
        state = sample["state_cluster"].to_numpy(np.int16, copy=True)
        district = sample["district_code"].to_numpy(np.int32, copy=True)
        ys = {name: pd.to_numeric(sample[name], errors="coerce").to_numpy(np.float32, copy=True) for name in OUTCOMES}
        sample_rows = len(sample)
        state_count = int(np.unique(state).size)
        district_count = int(np.unique(district).size)
        del sample
        gc.collect()

        print(
            f"FAMILY {family}: rows={sample_rows:,}, states={state_count}, districts={district_count}, "
            f"design_k={X.shape[1]}",
            flush=True,
        )
        if not 33 <= state_count <= 36:
            raise RuntimeError(f"unexpected State-lineage cluster count: {state_count}")

        rows: list[dict] = []
        for outcome in OUTCOMES:
            cluster_map = {"state": state}
            if family == "primary":
                cluster_map["district"] = district
            fits = _fit_once(ys[outcome], X, names, school, dy, cluster_map, f"{family}:{outcome}")

            if family == "primary":
                rows.append(_model_row(
                    fits["state"], outcome=outcome, spec="primary",
                    universe="main_1_2_3_6_89_90", exposure="frozen_baseline_composition", cluster="state",
                ))
                rows.append(_model_row(
                    fits["district"], outcome=outcome, spec="district_cluster",
                    universe="main_1_2_3_6_89_90", exposure="frozen_baseline_composition", cluster="district",
                ))
            elif family == "current":
                rows.append(_model_row(
                    fits["state"], outcome=outcome, spec="contemporaneous_exposure",
                    universe="main_1_2_3_6_89_90", exposure="contemporaneous_composition", cluster="state",
                ))
            else:
                rows.append(_model_row(
                    fits["state"], outcome=outcome, spec="government_universe_robustness",
                    universe="core_1_2_3", exposure="frozen_baseline_composition", cluster="state",
                ))
            del fits
            gc.collect()

        write_rows(out / "models.csv", rows)
        write_json(out / "engine.json", {
            "family": family,
            "engine": "pyhdfe 0.2.0",
            "residualize_method": "sw",
            "drop_singletons": False,
            "compute_degrees": False,
            "sample_rows_before_outcome_complete_case": sample_rows,
            "state_lineage_clusters": state_count,
            "district_clusters": district_count,
            "outcomes": OUTCOMES,
        })
        print(f"FAMILY DONE {family}: wrote {len(rows)} model rows", flush=True)

    con.close()


if __name__ == "__main__":
    main()
