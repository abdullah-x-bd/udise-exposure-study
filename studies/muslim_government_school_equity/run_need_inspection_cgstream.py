from __future__ import annotations

import gc
import json
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pyhdfe

import run_need_inspection_fastcodes as base

CG_TOL = 1e-8
CG_ITERATION_LIMIT = 10000
BLOCK_COLS = 4


def _cluster_vcov_streamed(
    X: np.memmap,
    resid: np.ndarray,
    cluster_codes: np.ndarray,
    bread_inv: np.ndarray,
) -> tuple[np.ndarray, int]:
    c = np.asarray(cluster_codes, dtype=np.int32)
    counts = np.bincount(c)
    active = counts > 0
    g = int(active.sum())
    scores = np.zeros((counts.size, X.shape[1]), dtype=np.float64)
    for j in range(X.shape[1]):
        xj = np.asarray(X[:, j])
        weights = xj * resid
        scores[:, j] = np.bincount(c, weights=weights, minlength=counts.size)
        del weights
    meat = scores[active].T @ scores[active]
    vcov = bread_inv @ meat @ bread_inv
    n, k = len(resid), X.shape[1]
    if g > 1 and n > k:
        vcov *= (g / (g - 1)) * ((n - 1) / (n - k))
    return vcov, g


def _fit_once_cgstream(
    y: np.ndarray,
    X: np.ndarray,
    names: list[str],
    school: np.ndarray,
    district_year: np.ndarray,
    clusters: dict[str, np.ndarray],
    label: str,
) -> dict[str, dict]:
    design_valid = np.all(np.isfinite(X), axis=1)
    valid = np.isfinite(y) & design_valid
    idx = np.flatnonzero(valid).astype(np.int32, copy=False)
    n = int(idx.size)
    k = int(X.shape[1])
    if n <= k + 20:
        raise RuntimeError(f"insufficient observations for {label}: n={n}")

    print(
        f"CGSTREAM HDFE START {label}: n={n:,}, k={k}, "
        f"schools={np.unique(school[idx]).size:,}, district_year={np.unique(district_year[idx]).size:,}",
        flush=True,
    )
    started = time.monotonic()

    ids = np.empty((n, 2), dtype=np.int32)
    ids[:, 0] = district_year[idx]
    ids[:, 1] = school[idx]
    algorithm = pyhdfe.create(
        ids,
        drop_singletons=False,
        compute_degrees=False,
        residualize_method="map",
        options={
            "transform": "symmetric",
            "acceleration": "cg",
            "tol": CG_TOL,
            "iteration_limit": CG_ITERATION_LIMIT,
        },
    )

    with tempfile.TemporaryDirectory(prefix="cgstream_fit_") as td:
        td_path = Path(td)
        y_path = td_path / "y_resid.dat"
        x_path = td_path / "x_resid.dat"

        y_in = np.empty((n, 1), dtype=np.float64)
        y_in[:, 0] = y[idx]
        t0 = time.monotonic()
        y_out = algorithm.residualize(y_in)
        ya = np.memmap(y_path, dtype=np.float64, mode="w+", shape=(n,))
        ya[:] = y_out[:, 0]
        ya.flush()
        del y_in, y_out
        gc.collect()
        print(f"CGSTREAM {label}: y residualized in {time.monotonic() - t0:.1f}s", flush=True)

        Xa = np.memmap(x_path, dtype=np.float64, mode="w+", shape=(n, k))
        for start in range(0, k, BLOCK_COLS):
            stop = min(k, start + BLOCK_COLS)
            block = np.empty((n, stop - start), dtype=np.float64)
            for j in range(start, stop):
                block[:, j - start] = X[idx, j]
            bt = time.monotonic()
            block_r = algorithm.residualize(block)
            Xa[:, start:stop] = block_r
            Xa.flush()
            print(
                f"CGSTREAM {label}: X cols {start + 1}-{stop}/{k} residualized in {time.monotonic() - bt:.1f}s",
                flush=True,
            )
            del block, block_r
            gc.collect()

        del algorithm, ids
        gc.collect()

        xtx = np.asarray(Xa.T @ Xa)
        xty = np.asarray(Xa.T @ ya)
        bread_inv = np.linalg.pinv(xtx)
        beta = bread_inv @ xty
        resid = np.asarray(ya) - Xa @ beta

        out: dict[str, dict] = {}
        for cname, all_codes in clusters.items():
            cvals = all_codes[idx].astype(np.int32, copy=False)
            vcov, g = _cluster_vcov_streamed(Xa, resid, cvals, bread_inv)
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
                "iterations": -1,
                "convergence": float(CG_TOL),
            }

        elapsed = time.monotonic() - started
        print(f"CGSTREAM HDFE DONE {label}: {elapsed:.1f}s", flush=True)
        del Xa, ya, resid, bread_inv, beta, xtx, xty
        gc.collect()

    del idx
    gc.collect()
    return out


def _model_row_cg(fit: dict, **kwargs) -> dict:
    row = base._model_row_original(fit, **kwargs)
    row["engine"] = "pyhdfe_map_symmetric_cg_streamed"
    return row


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"primary", "current", "core"}:
        raise SystemExit("usage: run_need_inspection_cgstream.py {primary|current|core}")
    family = sys.argv[1]

    base._fit_once = _fit_once_cgstream
    base._model_row_original = base._model_row
    base._model_row = _model_row_cg
    base.main()

    engine_path = base.OUT_ROOT / family / "engine.json"
    if engine_path.exists():
        payload = json.loads(engine_path.read_text(encoding="utf-8"))
        payload.update({
            "engine": "pyhdfe 0.2.0 map symmetric CG streamed",
            "residualize_method": "map",
            "transform": "symmetric",
            "acceleration": "cg",
            "tol": CG_TOL,
            "iteration_limit": CG_ITERATION_LIMIT,
            "block_cols": BLOCK_COLS,
        })
        engine_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
