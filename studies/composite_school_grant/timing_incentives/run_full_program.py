from __future__ import annotations

import csv
import json
import math
import os
import runpy
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from rdrobust import rdrobust

PANEL = runpy.run_path(
    "studies/composite_school_grant/scripts/03_build_panel.py",
    run_name="csg_panel_lib_timing",
)

YEARS = PANEL["YEARS"]
build_year = PANEL["build_year"]
csv_source = PANEL["csv_source"]
source_columns = PANEL["source_columns"]
identify_early_social_labels = PANEL["identify_early_social_labels"]
qid = PANEL["qid"]
lit = PANEL["lit"]
ref = PANEL["ref"]
nref = PANEL["nref"]
num = PANEL["num"]
sql_list = PANEL["sql_list"]

CUTOFF_END = 250
CUTOFF = 250.5
GOV = (1, 2, 3)
PRIMARY_BW = 30
MIN_RD_N = 500
STATE_MIN_SIDE = 25
RNG = np.random.default_rng(20260815)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=float), encoding="utf-8")


def ident(cols: dict[str, str]) -> str:
    x = cols.get("pseudocode") or cols.get("psuedocode")
    if not x:
        raise RuntimeError("school identifier missing")
    return x


def enrol_filter(con: duckdb.DuckDBPyConnection, src: str, cols: dict[str, str]) -> tuple[str, list[str]]:
    if "item_group" in cols and "item_id" in cols:
        return f"{nref(cols,'item_group')}=1 AND {nref(cols,'item_id')} IN (1,2,3,4)", []
    labs = identify_early_social_labels(con, src, cols)
    if not labs:
        raise RuntimeError("could not identify social-category rows")
    d = ref(cols, "item_desc")
    return f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})", labs


def class_expr(cols: dict[str, str], max_class: int) -> str:
    terms = [
        f"COALESCE({nref(cols, f'c{c}_{s}')},0)"
        for c in range(1, max_class + 1)
        for s in ("b", "g")
        if f"c{c}_{s}" in cols
    ]
    if not terms:
        raise RuntimeError(f"no class 1-{max_class} enrolment columns")
    return " + ".join(terms)


def robust_scalar(x) -> float | None:
    try:
        a = np.asarray(x, dtype=float)
        if a.size == 0:
            return None
        v = float(a.reshape(-1)[-1])
        return v if math.isfinite(v) else None
    except Exception:
        return None


def rd_fit(y: np.ndarray, x: np.ndarray, state: np.ndarray, bw: float = PRIMARY_BW, c: float = CUTOFF) -> dict | None:
    m = np.isfinite(y) & np.isfinite(x) & np.isfinite(state)
    m &= np.abs(x - c) <= bw
    y, x, state = y[m], x[m], state[m]
    left = int(np.sum(x < c)); right = int(np.sum(x >= c))
    if len(y) < MIN_RD_N or left < 100 or right < 100:
        return None
    state_codes = pd.Categorical(state).codes.astype(int)
    try:
        r = rdrobust(
            y=y,
            x=x,
            c=c,
            p=1,
            q=2,
            kernel="tri",
            h=bw,
            b=max(45, bw * 1.5),
            cluster=state_codes,
            vce="cr3",
            masspoints="adjust",
            bwcheck=15,
        )
        coef = robust_scalar(r.coef)
        se = robust_scalar(r.se)
        pv = robust_scalar(r.pv)
        ci = np.asarray(r.ci, dtype=float)
        lo = float(ci.reshape(-1, 2)[-1, 0]) if ci.size >= 2 else None
        hi = float(ci.reshape(-1, 2)[-1, 1]) if ci.size >= 2 else None
        return {
            "tau": coef, "se": se, "p": pv, "ci_low": lo, "ci_high": hi,
            "n": int(len(y)), "n_left": left, "n_right": right,
            "bw": bw, "cutoff_coordinate": c,
        }
    except Exception as e:
        return {"error": repr(e), "n": int(len(y)), "n_left": left, "n_right": right, "bw": bw}


def local_wls_hc(y: np.ndarray, x: np.ndarray, bw: float = PRIMARY_BW, c: float = CUTOFF) -> dict | None:
    m = np.isfinite(y) & np.isfinite(x) & (np.abs(x - c) <= bw)
    y, x = y[m], x[m]
    left = int(np.sum(x < c)); right = int(np.sum(x >= c))
    if len(y) < 80 or left < STATE_MIN_SIDE or right < STATE_MIN_SIDE:
        return None
    z = x - c
    t = (x >= c).astype(float)
    w = np.maximum(0.0, 1.0 - np.abs(z) / bw)
    X = np.column_stack([np.ones(len(x)), t, z, t * z])
    keep = w > 0
    X, y, w = X[keep], y[keep], w[keep]
    if len(y) <= X.shape[1] + 4:
        return None
    xtwx = X.T @ (w[:, None] * X)
    try:
        bread = np.linalg.inv(xtwx)
    except np.linalg.LinAlgError:
        bread = np.linalg.pinv(xtwx)
    beta = bread @ (X.T @ (w * y))
    resid = y - X @ beta
    meat = X.T @ ((w * resid)[:, None] ** 2 * X)
    cov = bread @ meat @ bread
    cov *= len(y) / max(1, len(y) - X.shape[1])
    se = float(np.sqrt(max(0.0, cov[1, 1])))
    tau = float(beta[1])
    zstat = tau / se if se > 0 else np.nan
    p = math.erfc(abs(zstat) / math.sqrt(2.0)) if math.isfinite(zstat) else None
    return {
        "tau": tau, "se": se, "p": p,
        "ci_low": tau - 1.96 * se, "ci_high": tau + 1.96 * se,
        "n": int(len(y)), "n_left": left, "n_right": right,
    }


def poisson_counterfactual(count_map: dict[int, int], cutoff_end: int, window: int, zone: int = 5) -> dict | None:
    xs = np.arange(max(1, cutoff_end - window), cutoff_end + window + 2)
    ys = np.array([count_map.get(int(v), 0) for v in xs], dtype=float)
    if ys.sum() < 300:
        return None
    sens = (xs >= cutoff_end - zone) & (xs <= cutoff_end + zone)
    fit = ~sens
    z = (xs - (cutoff_end + 0.5)) / max(1.0, float(window))

    def heap_class(v: int) -> int:
        if v % 100 == 0: return 5
        if v % 50 == 0: return 4
        if v % 25 == 0: return 3
        if v % 10 == 0: return 2
        if v % 5 == 0: return 1
        return 0

    hc = np.array([heap_class(int(v)) for v in xs])
    X = [np.ones(len(xs)), z, z**2, z**3]
    for k in range(1, 6):
        X.append((hc == k).astype(float))
    X = np.column_stack(X)
    try:
        import statsmodels.api as sm
        model = sm.GLM(ys[fit], X[fit], family=sm.families.Poisson()).fit(maxiter=200, disp=0)
        pred = np.asarray(model.predict(X), dtype=float)
    except Exception:
        coef, *_ = np.linalg.lstsq(X[fit], np.log1p(ys[fit]), rcond=None)
        pred = np.maximum(0.0, np.expm1(X @ coef))

    above = (xs >= cutoff_end + 1) & (xs <= cutoff_end + zone)
    below = (xs >= cutoff_end - zone) & (xs <= cutoff_end - 1)
    oa, ea = float(ys[above].sum()), float(pred[above].sum())
    ob, eb = float(ys[below].sum()), float(pred[below].sum())
    if ea <= 0 or eb <= 0:
        return None
    return {
        "obs_above": oa, "exp_above": ea, "excess_above": oa - ea,
        "excess_ratio_above": oa / ea - 1.0,
        "obs_below": ob, "exp_below": eb, "excess_below": ob - eb,
        "excess_ratio_below": ob / eb - 1.0,
        "net_shift": (oa - ea) - (ob - eb),
        "heaping_adjusted_asymmetry": (oa / ea - 1.0) - (ob / eb - 1.0),
        "count_cutoff": int(count_map.get(cutoff_end, 0)),
        "count_first_above": int(count_map.get(cutoff_end + 1, 0)),
        "window": window, "zone": zone,
    }


def meta_by_lag(rows: list[dict]) -> list[dict]:
    out = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("tau") is None or r.get("se") in (None, 0) or not math.isfinite(float(r.get("se", np.nan))):
            continue
        groups[(r["sample"], r["outcome"], r["lag"], r["bw"])].append(r)
    for key, rr in sorted(groups.items(), key=lambda kv: str(kv[0])):
        vals = np.array([float(x["tau"]) for x in rr])
        ses = np.array([float(x["se"]) for x in rr])
        w = 1.0 / np.maximum(ses**2, 1e-12)
        tau = float(np.sum(w * vals) / np.sum(w))
        se = float(np.sqrt(1.0 / np.sum(w)))
        out.append({
            "sample": key[0], "outcome": key[1], "lag": key[2], "bw": key[3],
            "cohorts": len(rr), "tau_ivw": tau, "se_ivw": se,
            "ci_low": tau - 1.96 * se, "ci_high": tau + 1.96 * se,
            "tau_median": float(np.median(vals)), "tau_min": float(np.min(vals)), "tau_max": float(np.max(vals)),
        })
    return out


def within_year_permutation_corr(df: pd.DataFrame, xcol: str, ycol: str, wcol: str, reps: int = 2000) -> dict | None:
    d = df[["assignment_year", xcol, ycol, wcol]].dropna().copy()
    if len(d) < 20:
        return None
    for c in [xcol, ycol]:
        d[c + "_dm"] = d[c] - d.groupby("assignment_year")[c].transform("mean")
    x = d[xcol + "_dm"].to_numpy(float); y = d[ycol + "_dm"].to_numpy(float)
    w = np.maximum(1.0, d[wcol].to_numpy(float))
    def wcorr(a, b):
        ma = np.average(a, weights=w); mb = np.average(b, weights=w)
        ca = a - ma; cb = b - mb
        den = math.sqrt(np.average(ca*ca, weights=w) * np.average(cb*cb, weights=w))
        return float(np.average(ca*cb, weights=w) / den) if den > 0 else np.nan
    obs = wcorr(x, y)
    if not math.isfinite(obs):
        return None
    ge = 0
    years = d["assignment_year"].to_numpy()
    for _ in range(reps):
        yp = y.copy()
        for yr in np.unique(years):
            idx = np.where(years == yr)[0]
            yp[idx] = RNG.permutation(yp[idx])
        r = wcorr(x, yp)
        if math.isfinite(r) and abs(r) >= abs(obs):
            ge += 1
    return {"n": len(d), "weighted_within_year_corr": obs, "permutation_p": (ge + 1) / (reps + 1), "reps": reps}


def make_aux_enrol(con: duckdb.DuckDBPyConnection, work: Path, year: str, out: Path) -> dict:
    paths = sorted((work / year / "enrolment_1").glob("*.csv"))
    if not paths:
        raise RuntimeError(f"missing extracted enrolment paths for {year}")
    s = csv_source(paths); c = source_columns(con, s); sid = ident(c)
    filt, labs = enrol_filter(con, s, c)
    e12 = class_expr(c, 12); e8 = class_expr(c, 8)
    aux = out / "aux" / f"{year}_enrol_aux.parquet"
    aux.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY (SELECT CAST({qid(sid)} AS VARCHAR) pseudocode, SUM({e12}) enrol_c1_12_check, "
        f"SUM({e8}) enrol_c1_8 FROM {s} WHERE {filt} GROUP BY 1) TO {lit(str(aux))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    rec = {"year": year, "early_social_labels": labs, "has_item_group": "item_group" in c}
    if "item_group" in c:
        group = out / "aux" / f"{year}_group_totals.parquet"
        con.execute(
            f"COPY (SELECT CAST({qid(sid)} AS VARCHAR) pseudocode, CAST({nref(c,'item_group')} AS INTEGER) item_group, "
            f"SUM({e12}) enrol_total FROM {s} WHERE {nref(c,'item_group')} IS NOT NULL GROUP BY 1,2) "
            f"TO {lit(str(group))} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        q = con.execute(
            f"""
            WITH g AS (SELECT * FROM read_parquet({lit(str(group))})),
            p AS (SELECT pseudocode,
                         MAX(enrol_total) FILTER(WHERE item_group=1) g1,
                         MAX(enrol_total) FILTER(WHERE item_group=2) g2
                  FROM g GROUP BY 1)
            SELECT COUNT(*) FILTER(WHERE g1 IS NOT NULL AND g2 IS NOT NULL) n,
                   median(g2/NULLIF(g1,0)) FILTER(WHERE g1>0 AND g2 IS NOT NULL) med_ratio,
                   AVG(ABS(g2-g1)) FILTER(WHERE g1 IS NOT NULL AND g2 IS NOT NULL) mean_abs_diff,
                   AVG(CASE WHEN g1=g2 THEN 1.0 ELSE 0.0 END) FILTER(WHERE g1 IS NOT NULL AND g2 IS NOT NULL) exact_share
            FROM p
            """
        ).fetchone()
        rec.update({"group12_matched": int(q[0] or 0), "group2_to_group1_median_ratio": q[1], "group12_mean_abs_diff": q[2], "group12_exact_share": q[3]})
    return rec


def build_enriched_panel(con: duckdb.DuckDBPyConnection, repo: str, token: str, out: Path) -> tuple[Path, list[dict], list[dict]]:
    reports = []
    recon = []
    year_paths = []
    with tempfile.TemporaryDirectory(prefix="csg_timing_full_") as td:
        work = Path(td)
        for year in YEARS:
            print("BUILD", year, flush=True)
            rep = build_year(con, repo, token, year, work, out / "base_panel")
            reports.append(rep)
            recon.append(make_aux_enrol(con, work, year, out))
            basep = out / "base_panel" / "year_parquet" / f"{year}.parquet"
            auxp = out / "aux" / f"{year}_enrol_aux.parquet"
            ep = out / "enriched_year" / f"{year}.parquet"
            ep.parent.mkdir(parents=True, exist_ok=True)
            con.execute(
                f"COPY (SELECT b.*, a.enrol_c1_8 FROM read_parquet({lit(str(basep))}) b "
                f"LEFT JOIN read_parquet({lit(str(auxp))}) a USING(pseudocode)) "
                f"TO {lit(str(ep))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
            )
            year_paths.append(ep)
            shutil.rmtree(work / year, ignore_errors=True)
    panel = out / "enriched_school_year_panel.parquet"
    con.execute(
        f"COPY (SELECT * FROM read_parquet({sql_list(year_paths)}, union_by_name=true)) "
        f"TO {lit(str(panel))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    return panel, reports, recon


def timing_experiments(con: duckdb.DuckDBPyConnection, panel: Path, out: Path) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    state_rows: list[dict] = []
    yindex = {y: i for i, y in enumerate(YEARS)}
    for ay in YEARS:
        for oy in YEARS:
            lag = yindex[oy] - yindex[ay]
            if lag < -3 or lag > 4:
                continue
            print("TIMING", ay, oy, "lag", lag, flush=True)
            df = con.execute(
                f"""
                SELECT a.enrol_c1_12 x, a.enrol_c1_8 x18, a.state state,
                       f.csg_receipt receipt, f.csg_expenditure expenditure
                FROM read_parquet({lit(str(panel))}) a
                LEFT JOIN read_parquet({lit(str(panel))}) f
                  ON a.pseudocode=f.pseudocode AND f.academic_year={lit(oy)}
                WHERE a.academic_year={lit(ay)} AND a.management IN {GOV}
                  AND a.enrol_c1_12 BETWEEN 180 AND 321
                """
            ).df()
            if df.empty:
                continue
            samples = {
                "all": np.ones(len(df), dtype=bool),
                "pmposhan_safe220": (df["x18"].fillna(99999).to_numpy(float) <= 220),
                "pmposhan_safe200": (df["x18"].fillna(99999).to_numpy(float) <= 200),
            }
            for sname, sm in samples.items():
                d = df.loc[sm].copy()
                if len(d) < MIN_RD_N:
                    continue
                rec = d["receipt"].to_numpy(float)
                exp = d["expenditure"].to_numpy(float)
                valid_r = np.isfinite(rec); valid_e = np.isfinite(exp)
                outcomes: dict[str, np.ndarray] = {
                    "receipt_ge75000": np.where(valid_r, (rec >= 75000).astype(float), np.nan),
                    "receipt_gt50000": np.where(valid_r, (rec > 50000).astype(float), np.nan),
                    "receipt_positive": np.where(valid_r, (rec > 0).astype(float), np.nan),
                    "expenditure_ge75000": np.where(valid_e, (exp >= 75000).astype(float), np.nan),
                    "expenditure_gt50000": np.where(valid_e, (exp > 50000).astype(float), np.nan),
                    "expenditure_positive": np.where(valid_e, (exp > 0).astype(float), np.nan),
                }
                if valid_r.sum() > 100:
                    cap = float(np.nanquantile(rec[valid_r], .99)); outcomes["receipt_winsor99"] = np.where(valid_r, np.minimum(rec, cap), np.nan)
                if valid_e.sum() > 100:
                    cap = float(np.nanquantile(exp[valid_e], .99)); outcomes["expenditure_winsor99"] = np.where(valid_e, np.minimum(exp, cap), np.nan)
                x = d["x"].to_numpy(float); st = d["state"].to_numpy(float)
                for oname, yy in outcomes.items():
                    for bw in (20, 30, 40):
                        fit = rd_fit(yy, x, st, bw=bw)
                        if fit:
                            rows.append({"assignment_year": ay, "outcome_year": oy, "lag": lag, "sample": sname, "outcome": oname, **fit})

            rec = df["receipt"].to_numpy(float)
            yy = np.where(np.isfinite(rec), (rec >= 75000).astype(float), np.nan)
            for state, g in df.assign(_y=yy).groupby("state"):
                if pd.isna(state):
                    continue
                fit = local_wls_hc(g["_y"].to_numpy(float), g["x"].to_numpy(float), bw=30)
                if fit:
                    state_rows.append({"assignment_year": ay, "outcome_year": oy, "lag": lag, "state": state, "outcome": "receipt_ge75000", **fit})
    write_csv(out / "timing_matrix.csv", rows)
    meta = meta_by_lag(rows)
    write_csv(out / "timing_meta_by_lag.csv", meta)
    write_csv(out / "state_timing.csv", state_rows)
    return rows, state_rows


def bunching_experiments(con: duckdb.DuckDBPyConnection, panel: Path, out: Path) -> tuple[list[dict], list[dict]]:
    national: list[dict] = []
    state_rows: list[dict] = []
    true_cutoffs = {30: "CSG", 100: "CSG", 250: "CSG", 1000: "CSG"}
    pseudo = [50, 150, 200, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900]
    for year in YEARS:
        counts = con.execute(
            f"SELECT CAST(enrol_c1_12 AS INTEGER) x, COUNT(*) n FROM read_parquet({lit(str(panel))}) "
            f"WHERE academic_year={lit(year)} AND management IN {GOV} AND enrol_c1_12 BETWEEN 1 AND 1150 GROUP BY 1"
        ).fetchall()
        cmap = {int(x): int(n) for x, n in counts if x is not None}
        for c, kind in [(x, "true") for x in true_cutoffs] + [(x, "pseudo") for x in pseudo]:
            win = 40 if c < 500 else 120
            m = poisson_counterfactual(cmap, c, win)
            if m:
                national.append({"academic_year": year, "threshold_end": c, "threshold_start": c+1, "kind": kind, "known_program": true_cutoffs.get(c, ""), **m})

        sdf = con.execute(
            f"SELECT state, CAST(enrol_c1_12 AS INTEGER) x, COUNT(*) n FROM read_parquet({lit(str(panel))}) "
            f"WHERE academic_year={lit(year)} AND management IN {GOV} AND enrol_c1_12 BETWEEN 215 AND 286 GROUP BY 1,2"
        ).df()
        for st, g in sdf.groupby("state"):
            cmap_s = {int(r.x): int(r.n) for r in g.itertuples()}
            m = poisson_counterfactual(cmap_s, 250, 30)
            if m:
                local_n = int(g["n"].sum())
                if local_n >= 150:
                    state_rows.append({"assignment_year": year, "state": st, "local_n": local_n, **m})
    write_csv(out / "bunching_national.csv", national)
    write_csv(out / "state_year_bunching.csv", state_rows)

    ranks = []
    ndf = pd.DataFrame(national)
    if not ndf.empty:
        for year, g in ndf.groupby("academic_year"):
            p = g[g.kind == "pseudo"]["heaping_adjusted_asymmetry"].dropna().to_numpy(float)
            t = g[(g.kind == "true") & (g.threshold_end == 250)]
            if len(t) and len(p):
                v = float(t.iloc[0].heaping_adjusted_asymmetry)
                ranks.append({"academic_year": year, "threshold_end": 250, "metric": v, "pseudo_count": len(p), "percentile_among_pseudo": float(np.mean(p <= v))})
    write_csv(out / "bunching_placebo_rank.csv", ranks)
    return national, state_rows


def crossing_experiments(con: duckdb.DuckDBPyConnection, panel: Path, out: Path) -> list[dict]:
    rows = []
    yi = {y: i for i, y in enumerate(YEARS)}
    thresholds = [(250, "true"), (200, "pseudo"), (300, "pseudo")]
    for prev, curr in zip(YEARS[:-1], YEARS[1:]):
        nxt = YEARS[yi[curr] + 1] if yi[curr] + 1 < len(YEARS) else None
        nxt_join = (
            f"LEFT JOIN read_parquet({lit(str(panel))}) n ON p.pseudocode=n.pseudocode AND n.academic_year={lit(nxt)}"
            if nxt else ""
        )
        nxt_sel = "n.enrol_c1_12 next_x" if nxt else "NULL::DOUBLE next_x"
        df = con.execute(
            f"""
            SELECT p.pseudocode, p.enrol_c1_12 prev_x, c.enrol_c1_12 curr_x, {nxt_sel}
            FROM read_parquet({lit(str(panel))}) p
            JOIN read_parquet({lit(str(panel))}) c ON p.pseudocode=c.pseudocode AND c.academic_year={lit(curr)}
            {nxt_join}
            WHERE p.academic_year={lit(prev)} AND p.management IN {GOV}
              AND p.enrol_c1_12 BETWEEN 150 AND 350
            """
        ).df()
        for c, kind in thresholds:
            d = df[(df.prev_x >= c-20) & (df.prev_x <= c)].copy()
            if len(d) < 100:
                continue
            landing = ((d.curr_x >= c+1) & (d.curr_x <= c+5)).mean()
            landing_below = ((d.curr_x >= c-5) & (d.curr_x <= c-1)).mean()
            crossed = (d.curr_x >= c+1).mean()
            rec = {"from_year": prev, "to_year": curr, "threshold_end": c, "kind": kind, "n_prev_below20": len(d), "p_land_first5_above": landing, "p_land_last5_below": landing_below, "p_cross": crossed}
            if nxt:
                a = df[(df.curr_x >= c+1) & (df.curr_x <= c+5) & df.next_x.notna()]
                b = df[(df.curr_x >= c+6) & (df.curr_x <= c+10) & df.next_x.notna()]
                rec.update({
                    "next_year": nxt,
                    "n_first5_above": len(a),
                    "reversion_first5_to_below": float((a.next_x <= c).mean()) if len(a) else None,
                    "n_second5_above": len(b),
                    "reversion_second5_to_below": float((b.next_x <= c).mean()) if len(b) else None,
                })
            rows.append(rec)

    for i in range(2, len(YEARS)):
        y0, y1, y2 = YEARS[i-2], YEARS[i-1], YEARS[i]
        df = con.execute(
            f"""
            SELECT a.enrol_c1_12 x0,b.enrol_c1_12 x1,c.enrol_c1_12 x2
            FROM read_parquet({lit(str(panel))}) a
            JOIN read_parquet({lit(str(panel))}) b ON a.pseudocode=b.pseudocode AND b.academic_year={lit(y1)}
            JOIN read_parquet({lit(str(panel))}) c ON a.pseudocode=c.pseudocode AND c.academic_year={lit(y2)}
            WHERE a.academic_year={lit(y0)} AND a.management IN {GOV}
              AND a.enrol_c1_12 BETWEEN 150 AND 350
            """
        ).df()
        pred = df.x1 + (df.x1 - df.x0)
        df = df.assign(pred=pred)
        for c, kind in thresholds:
            near = df[(df.pred >= c-4) & (df.pred <= c)].copy()
            left_placebo = df[(df.pred >= c-9) & (df.pred <= c-5)].copy()
            right_placebo = df[(df.pred >= c+1) & (df.pred <= c+5)].copy()
            if len(near) < 100:
                continue
            rows.append({
                "from_year": y1, "to_year": y2, "threshold_end": c, "kind": kind,
                "analysis": "two_year_linear_prediction",
                "n_pred_last5_below": len(near),
                "p_actual_first5_above_given_pred_last5_below": float(((near.x2 >= c+1) & (near.x2 <= c+5)).mean()),
                "n_pred_5_9_below": len(left_placebo),
                "p_shift_to_analogous_plus5_left": float(((left_placebo.x2 >= c-4) & (left_placebo.x2 <= c)).mean()) if len(left_placebo) else None,
                "n_pred_first5_above": len(right_placebo),
                "p_shift_to_second5_above_right": float(((right_placebo.x2 >= c+6) & (right_placebo.x2 <= c+10)).mean()) if len(right_placebo) else None,
            })
    write_csv(out / "targeted_crossing_dynamics.csv", rows)
    return rows


def reconciliation_experiments(con: duckdb.DuckDBPyConnection, out: Path, recon_build: list[dict]) -> list[dict]:
    rows = []
    for rec in recon_build:
        year = rec["year"]
        group = out / "aux" / f"{year}_group_totals.parquet"
        if not group.exists() or not rec.get("group12_matched"):
            continue
        med = rec.get("group2_to_group1_median_ratio")
        usable = med is not None and 0.9 <= float(med) <= 1.1
        q = con.execute(
            f"""
            WITH g AS (SELECT * FROM read_parquet({lit(str(group))})),
            p AS (SELECT pseudocode,
                         MAX(enrol_total) FILTER(WHERE item_group=1) g1,
                         MAX(enrol_total) FILTER(WHERE item_group=2) g2
                  FROM g GROUP BY 1),
            z AS (SELECT *, g2-g1 diff, ABS(g2-g1) adiff FROM p WHERE g1 BETWEEN 220 AND 280 AND g2 IS NOT NULL)
            SELECT COUNT(*) n,
                   AVG(adiff) mean_abs_diff,
                   AVG(CASE WHEN diff=0 THEN 1.0 ELSE 0.0 END) exact_share,
                   AVG(adiff) FILTER(WHERE g1 BETWEEN 245 AND 250) below_abs_diff,
                   AVG(adiff) FILTER(WHERE g1 BETWEEN 251 AND 256) above_abs_diff,
                   AVG(CASE WHEN g2 BETWEEN 251 AND 255 THEN 1.0 ELSE 0.0 END) FILTER(WHERE g1 BETWEEN 251 AND 255) group2_confirms_first5
            FROM z
            """
        ).fetchone()
        rows.append({"academic_year": year, "group2_usable_as_independent_total": usable, "median_ratio_g2_g1": med,
                     "n_near250": int(q[0] or 0), "mean_abs_diff": q[1], "exact_share": q[2], "below_abs_diff": q[3], "above_abs_diff": q[4], "group2_confirms_first5_share": q[5]})
    write_csv(out / "enrolment_reconciliation.csv", rows)
    return rows


def implementation_bunching_link(state_timing: list[dict], state_bunching: list[dict], out: Path) -> list[dict]:
    t = pd.DataFrame(state_timing); b = pd.DataFrame(state_bunching)
    results = []
    if t.empty or b.empty:
        write_csv(out / "implementation_bunching_link.csv", results); return results
    for lag in [-1, 0, 1, 2, 3]:
        tt = t[t.lag == lag].copy()
        m = b.merge(tt[["assignment_year", "state", "tau", "n"]], on=["assignment_year", "state"], how="inner")
        m = m.rename(columns={"tau": "first_stage_tau", "n": "first_stage_n"})
        if len(m) < 20:
            continue
        r = within_year_permutation_corr(m, "first_stage_tau", "heaping_adjusted_asymmetry", "local_n")
        if r:
            results.append({"lag": lag, **r})
        m.to_csv(out / f"implementation_bunching_stateyear_lag{lag:+d}.csv", index=False)
    write_csv(out / "implementation_bunching_link.csv", results)
    return results


def positive_control_experiments(con: duckdb.DuckDBPyConnection, panel: Path, out: Path) -> list[dict]:
    rows = []
    for year in YEARS:
        df = con.execute(
            f"""
            SELECT enrol_c1_12 x,state,
                   COALESCE(laptops,0)+COALESCE(tablets,0)+COALESCE(desktops,0) device_count,
                   CASE WHEN COALESCE(laptops,0)+COALESCE(tablets,0)+COALESCE(desktops,0)>0 THEN 1.0 ELSE 0.0 END device_any,
                   CASE WHEN internet_raw=1 THEN 1.0 WHEN internet_raw=2 THEN 0.0 ELSE NULL END internet
            FROM read_parquet({lit(str(panel))})
            WHERE academic_year={lit(year)} AND management IN {GOV}
              AND highclass>=9 AND enrol_c1_12 BETWEEN 600 AND 801
            """
        ).df()
        if df.empty: continue
        x=df.x.to_numpy(float); st=df.state.to_numpy(float)
        for name in ["device_count","device_any","internet"]:
            y=df[name].to_numpy(float)
            fit=rd_fit(y,x,st,bw=60,c=700.5)
            if fit: rows.append({"academic_year":year,"threshold_end":700,"outcome":name,"interpretation":"imperfect_positive_control_additional_ICT_support",**fit})
    write_csv(out / "positive_control_ict700.csv", rows)
    return rows


def detectability_audit(out: Path) -> None:
    rows = [
        {"spending_channel":"minor repairs and maintenance","typical_UDISE_measure":"asset existence/functionality; room condition counts","measurement_type":"binary/count/ordinal","small_spend_detectability":"low to medium","reason":"repair can preserve the same category without crossing a recorded state"},
        {"spending_channel":"furniture replacement/additions","typical_UDISE_measure":"furniture availability category","measurement_type":"coarse ordinal","small_spend_detectability":"low","reason":"a few desks rarely move a whole-school category"},
        {"spending_channel":"cleaning and sanitation consumables","typical_UDISE_measure":"toilet/handwash availability and functionality","measurement_type":"binary/count","small_spend_detectability":"very low","reason":"consumables improve service quality without changing asset stock"},
        {"spending_channel":"teaching-learning materials and stationery","typical_UDISE_measure":"no transaction-level quantity/quality measure","measurement_type":"mostly unobserved","small_spend_detectability":"very low","reason":"flow input is not represented by a persistent stock variable"},
        {"spending_channel":"electricity/water/internet bills","typical_UDISE_measure":"service/asset availability","measurement_type":"mostly binary","small_spend_detectability":"low","reason":"paying a bill changes continuity/intensity, not whether infrastructure exists"},
        {"spending_channel":"small ICT replacement","typical_UDISE_measure":"device counts and internet yes/no","measurement_type":"count/binary","small_spend_detectability":"medium for devices; low for service","reason":"counts can move, but replacement can leave counts unchanged"},
        {"spending_channel":"accessibility repairs","typical_UDISE_measure":"ramp/handrail availability","measurement_type":"binary","small_spend_detectability":"low","reason":"quality repair is invisible if presence remains yes"},
        {"spending_channel":"large new visible asset","typical_UDISE_measure":"rooms/toilets/devices/labs where counted","measurement_type":"count/binary","small_spend_detectability":"medium to high","reason":"new stock should move a count if the expenditure is large enough"},
    ]
    write_csv(out / "outcome_detectability_audit.csv", rows)


def headline_summary(timing_rows, meta_rows, bunching_rows, link_rows, crossing_rows, recon_rows, pc_rows) -> str:
    lines = ["# CSG timing and incentives full-program results", "", "This file is generated by the analysis workflow. It intentionally separates empirical facts from interpretation.", ""]
    mm = [r for r in meta_rows if r["sample"]=="all" and r["outcome"]=="receipt_ge75000" and r["bw"]==30]
    lines += ["## Timing first stage", "", "Inverse-variance pooled RD estimates for the probability of reporting CSG receipt >= Rs 75,000, by lag between enrolment year and financial-reporting year:", ""]
    for r in sorted(mm, key=lambda z:z["lag"]):
        lines.append(f"- lag {r['lag']:+d}: {100*r['tau_ivw']:.2f} pp (95% CI {100*r['ci_low']:.2f} to {100*r['ci_high']:.2f}), {r['cohorts']} cohorts")
    if mm:
        pos=[r for r in mm if 0<=r['lag']<=3]
        if pos:
            best=max(pos,key=lambda z:z['tau_ivw'])
            lines += ["", f"Largest pooled positive-lag first stage in the pre-specified 0..3 window occurs at lag {best['lag']:+d}: {100*best['tau_ivw']:.2f} pp."]
    lines += ["", "## Bunching around 250", ""]
    bb=[r for r in bunching_rows if r["kind"]=="true" and r["threshold_end"]==250]
    for r in bb:
        lines.append(f"- {r['academic_year']}: heaping-adjusted asymmetry {r['heaping_adjusted_asymmetry']:.3f}; count at 251 = {r['count_first_above']:,}")
    lines += ["", "## Implementation intensity versus bunching", ""]
    for r in link_rows:
        lines.append(f"- lag {r['lag']:+d}: weighted within-year correlation {r['weighted_within_year_corr']:.3f}, permutation p={r['permutation_p']:.4f}, n={r['n']} state-years")
    lines += ["", "## Interpretation guardrails", "", "- A same-labelled-year first stage must not be interpreted as implementation strength until the lag structure is established.", "- The 250/251 boundary is represented at 250.5 in the new analysis because the entitlement changes between integer enrolments 250 and 251.", "- Bunching is evidence of non-smooth administrative enrolment, not by itself proof of intentional manipulation.", "- UDISE stock variables are often too coarse to detect small recurring CSG purchases. See outcome_detectability_audit.csv.", ""]
    return "\n".join(lines)


def main() -> None:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path("studies/composite_school_grant/outputs/timing_incentives")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    con.execute("PRAGMA temp_directory='/tmp/duckdb_csg_timing'")

    panel, build_reports, recon_build = build_enriched_panel(con, repo, token, out)
    jdump(out / "build_manifest.json", {"years": YEARS, "build_reports": build_reports, "reconciliation_build": recon_build})

    timing_rows, state_timing = timing_experiments(con, panel, out)
    meta = meta_by_lag(timing_rows)
    bunching_rows, state_bunching = bunching_experiments(con, panel, out)
    crossing_rows = crossing_experiments(con, panel, out)
    recon_rows = reconciliation_experiments(con, out, recon_build)
    link_rows = implementation_bunching_link(state_timing, state_bunching, out)
    pc_rows = positive_control_experiments(con, panel, out)
    detectability_audit(out)

    (out / "RESULTS.md").write_text(
        headline_summary(timing_rows, meta, bunching_rows, link_rows, crossing_rows, recon_rows, pc_rows),
        encoding="utf-8",
    )
    jdump(out / "run_manifest.json", {
        "cutoff_end": CUTOFF_END,
        "cutoff_coordinate": CUTOFF,
        "years": YEARS,
        "timing_rows": len(timing_rows),
        "state_timing_rows": len(state_timing),
        "bunching_rows": len(bunching_rows),
        "state_bunching_rows": len(state_bunching),
        "crossing_rows": len(crossing_rows),
        "reconciliation_rows": len(recon_rows),
        "implementation_bunching_rows": len(link_rows),
        "positive_control_rows": len(pc_rows),
    })
    print((out / "RESULTS.md").read_text(encoding="utf-8"), flush=True)
    con.close()


if __name__ == "__main__":
    main()
