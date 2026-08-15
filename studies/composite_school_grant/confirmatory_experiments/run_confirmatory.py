from __future__ import annotations

import csv
import json
import math
import os
import runpy
import shutil
import tempfile
from pathlib import Path

import duckdb
import numpy as np

# Reuse audited I/O and RD routines from the discovery study.
PANEL = runpy.run_path("studies/composite_school_grant/scripts/03_build_panel.py", run_name="csg_panel_lib")
FOCUS = runpy.run_path("tools/csg_focused_2022_2024.py", run_name="csg_focus_lib")

extract_archive = PANEL["extract_archive"]
csv_source = PANEL["csv_source"]
source_columns = PANEL["source_columns"]
identify_early_social_labels = PANEL["identify_early_social_labels"]
qid = PANEL["qid"]
lit = PANEL["lit"]
ref = PANEL["ref"]
nref = PANEL["nref"]
num = PANEL["num"]
water_raw = PANEL["water_expr"]
rd = FOCUS["rd"]

CUTOFF = 250
BW = 30
DONUT = 1
LOCAL_STATS_BW = 75
GOV_MGMT = "(1,2,3)"

ASSET_COMPONENTS = [
    "water_functional",
    "handwash_meal",
    "electricity",
    "internet",
    "library",
    "ramps",
    "handrails",
    "girls_toilet_full",
    "boys_toilet_full",
]

INDEX_FAMILIES = {
    "core_functionality": [
        "water_functional", "handwash_meal", "electricity", "library",
        "girls_toilet_full", "boys_toilet_full", "classroom_good_share",
    ],
    "wash": ["water_functional", "handwash_meal", "girls_toilet_full", "boys_toilet_full"],
    "digital": ["internet", "device_presence", "ict_lab"],
    "accessibility": ["ramps", "handrails", "cwsn_boys_full", "cwsn_girls_full"],
}
INDEX_FAMILIES["overall"] = sorted(set(sum(INDEX_FAMILIES.values(), [])))


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


def bh_adjust(rows: list[dict], pkey: str = "p") -> None:
    eligible = [(i, float(r[pkey])) for i, r in enumerate(rows) if r.get(pkey) is not None and math.isfinite(float(r[pkey]))]
    eligible.sort(key=lambda x: x[1])
    m = len(eligible)
    prev = 1.0
    for rank_rev, (idx, p) in enumerate(reversed(eligible), start=1):
        rank = m - rank_rev + 1
        q = min(prev, p * m / rank)
        rows[idx]["q_bh"] = q
        prev = q


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def attach_power_equivalence(rec: dict, margins: list[float]) -> None:
    se = rec.get("se")
    tau = rec.get("tau")
    if se is None or tau is None or not math.isfinite(float(se)) or float(se) <= 0:
        return
    se = float(se); tau = float(tau)
    rec["mde80"] = 2.80 * se
    rec["smallest_95ci_equivalence_margin"] = max(abs(float(rec["ci_low"])), abs(float(rec["ci_high"])))
    for delta in margins:
        # TOST: reject theta <= -delta and theta >= +delta.
        p_lower = 1.0 - normal_cdf((tau + delta) / se)
        p_upper = normal_cdf((tau - delta) / se)
        p_equiv = max(p_lower, p_upper)
        tag = str(delta).replace(".", "p")
        rec[f"tost_margin_{tag}_p"] = p_equiv
        rec[f"equivalent_within_{tag}"] = p_equiv < 0.05


def bool01(cols: dict[str, str], name: str, alias: str) -> str:
    r = ref(cols, name, alias)
    if not r:
        return "NULL"
    v = num(r)
    return f"CASE WHEN {v}=1 THEN 1.0 WHEN {v}=2 THEN 0.0 ELSE NULL END"


def water01(cols: dict[str, str], alias: str) -> str:
    raw = water_raw(cols, alias, True)
    return f"CASE WHEN ({raw})=1 THEN 1.0 WHEN ({raw})=2 THEN 0.0 ELSE NULL END"


def ratio01(numer: str, denom: str, empty_zero: bool = False) -> str:
    if empty_zero:
        return (
            f"CASE WHEN {denom} IS NULL OR {numer} IS NULL THEN NULL "
            f"WHEN {denom}<=0 THEN 0.0 ELSE LEAST(1.0,GREATEST(0.0,{numer}/{denom})) END"
        )
    return f"CASE WHEN {denom}>0 THEN LEAST(1.0,GREATEST(0.0,{numer}/{denom})) ELSE NULL END"


def full_functional(cols: dict[str, str], total_name: str, func_name: str, alias: str) -> str:
    t = nref(cols, total_name, alias); f = nref(cols, func_name, alias)
    if t == "NULL" or f == "NULL":
        return "NULL"
    return f"CASE WHEN {t} IS NULL OR {f} IS NULL THEN NULL WHEN {t}<=0 THEN 0.0 WHEN {f}>={t} THEN 1.0 ELSE 0.0 END"


def device_presence(cols: dict[str, str], alias: str) -> str:
    vals = [nref(cols, k, alias) for k in ("laptop", "tablet", "desktop") if ref(cols, k, alias)]
    if not vals:
        return "NULL"
    return "CASE WHEN " + " OR ".join(f"COALESCE({v},0)>0" for v in vals) + " THEN 1.0 ELSE 0.0 END"


def ict_lab(cols: dict[str, str], alias: str) -> str:
    for k in ("comp_ict_lab_yn", "ict_lab_yn"):
        if ref(cols, k, alias):
            return bool01(cols, k, alias)
    return "NULL"


def component_exprs(cols: dict[str, str], alias: str) -> dict[str, str]:
    rooms = nref(cols, "total_class_rooms", alias)
    good = nref(cols, "classrooms_in_good_condition", alias)
    return {
        "water_functional": water01(cols, alias),
        "handwash_meal": bool01(cols, "handwash_facility_for_meal", alias),
        "electricity": bool01(cols, "electricity_availability", alias),
        "internet": bool01(cols, "internet", alias),
        "library": bool01(cols, "library_availability", alias),
        "ramps": bool01(cols, "availability_ramps", alias),
        "handrails": bool01(cols, "availability_of_handrails", alias),
        "girls_toilet_full": full_functional(cols, "total_girls_toilet", "total_girls_func_toilet", alias),
        "boys_toilet_full": full_functional(cols, "total_boys_toilet", "total_boys_func_toilet", alias),
        "cwsn_boys_full": full_functional(cols, "total_boys_cwsn_toilet", "func_boys_cwsn_friendly", alias),
        "cwsn_girls_full": full_functional(cols, "total_girls_cwsn_toilet", "func_girls_cwsn_friendly", alias),
        "classroom_good_share": ratio01(good, rooms),
        "device_presence": device_presence(cols, alias),
        "ict_lab": ict_lab(cols, alias),
    }


def total_enrolment_setup(con: duckdb.DuckDBPyConnection, source: str, cols: dict[str, str]) -> tuple[str, str, list[str]]:
    terms = [
        f"COALESCE({nref(cols, f'c{c}_{s}')},0)"
        for c in range(1, 13) for s in ("b", "g") if f"c{c}_{s}" in cols
    ]
    if not terms:
        raise RuntimeError("No class enrolment columns found")
    if "item_group" in cols and "item_id" in cols:
        filt = f"{nref(cols,'item_group')}=1 AND {nref(cols,'item_id')} IN (1,2,3,4)"
        labels: list[str] = []
    else:
        labels = identify_early_social_labels(con, source, cols)
        if not labels:
            raise RuntimeError("Could not identify mutually exclusive social-category rows")
        d = ref(cols, "item_desc")
        filt = f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labels)})"
    return " + ".join(terms), filt, labels


def sql_mean_expr(names: list[str], prefix: str, min_obs: int) -> str:
    obs = " + ".join(f"CASE WHEN {prefix}{n} IS NOT NULL THEN 1 ELSE 0 END" for n in names)
    sm = " + ".join(f"COALESCE({prefix}{n},0.0)" for n in names)
    return f"CASE WHEN ({obs})>={min_obs} THEN ({sm})/NULLIF(({obs}),0) ELSE NULL END"


def zmean_expr(names: list[str], prefix: str, stats: dict[str, tuple[float, float]], min_obs: int) -> str:
    valid = [n for n in names if n in stats and stats[n][1] is not None and stats[n][1] > 1e-9]
    if not valid:
        return "NULL"
    min_obs = min(min_obs, len(valid))
    zs = {n: f"(({prefix}{n})-({stats[n][0]}))/({stats[n][1]})" for n in valid}
    obs = " + ".join(f"CASE WHEN {prefix}{n} IS NOT NULL THEN 1 ELSE 0 END" for n in valid)
    sm = " + ".join(f"CASE WHEN {prefix}{n} IS NULL THEN 0.0 ELSE {zs[n]} END" for n in valid)
    return f"CASE WHEN ({obs})>={min_obs} THEN ({sm})/NULLIF(({obs}),0) ELSE NULL END"


def estimate_from_sql(con: duckdb.DuckDBPyConnection, table: str, yexpr: str, extra_where: str = "TRUE") -> dict | None:
    arr = con.execute(
        f"SELECT {yexpr} y,enrol,state FROM {table} "
        f"WHERE enrol BETWEEN {CUTOFF-BW} AND {CUTOFF+BW} AND ({extra_where}) AND ({yexpr}) IS NOT NULL"
    ).fetchnumpy()
    if len(arr.get("y", [])) < 500:
        return None
    return rd(arr["y"], arr["enrol"], arr["state"], CUTOFF, BW, DONUT)


def main() -> None:
    assign_year = os.environ["ASSIGN_YEAR"]
    future_years = [y.strip() for y in os.environ["FUTURE_YEARS"].split(",") if y.strip()]
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path(f"studies/composite_school_grant/outputs/confirmatory/{assign_year}")
    out.mkdir(parents=True, exist_ok=True)

    transition_rows: list[dict] = []
    heterogeneity_rows: list[dict] = []
    index_rows: list[dict] = []
    equivalence_rows: list[dict] = []
    finance_rows: list[dict] = []
    diagnostics: dict = {"assignment_year": assign_year, "future_years": future_years}

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")

    with tempfile.TemporaryDirectory(prefix=f"csg_confirm_{assign_year}_") as td:
        work = Path(td)
        a_enr = csv_source(extract_archive(repo, token, assign_year, "enrolment_1", work))
        a_p1 = csv_source(extract_archive(repo, token, assign_year, "profile_1", work))
        a_fac = csv_source(extract_archive(repo, token, assign_year, "facility", work))
        ec, pc, fc = source_columns(con, a_enr), source_columns(con, a_p1), source_columns(con, a_fac)
        eid = ec.get("pseudocode") or ec.get("psuedocode")
        pid = pc.get("pseudocode") or pc.get("psuedocode")
        fid = fc.get("pseudocode") or fc.get("psuedocode")
        if not all([eid, pid, fid]):
            raise RuntimeError("Missing baseline school identifier")

        class_sum, social_filter, early_labels = total_enrolment_setup(con, a_enr, ec)
        con.execute(
            f"CREATE TEMP TABLE base_enrol AS SELECT CAST({qid(eid)} AS VARCHAR) pseudocode, "
            f"SUM({class_sum}) enrol FROM {a_enr} WHERE {social_filter} GROUP BY 1"
        )
        bcomp = component_exprs(fc, "f")
        baseline_select = ",".join(f"{expr} AS b_{name}" for name, expr in bcomp.items())
        con.execute(
            f"""
            CREATE TEMP TABLE base0 AS
            SELECT e.pseudocode,e.enrol,
                   CAST({ref(pc,'state','p')} AS VARCHAR) state_key,
                   {nref(pc,'managment','p')} management,
                   {baseline_select}
            FROM base_enrol e
            JOIN {a_p1} p ON e.pseudocode=CAST(p.{qid(pid)} AS VARCHAR)
            LEFT JOIN {a_fac} f ON e.pseudocode=CAST(f.{qid(fid)} AS VARCHAR)
            WHERE {nref(pc,'managment','p')} IN {GOV_MGMT}
            """
        )
        # State encoding is categorical, never a numeric coercion of UDISE state labels.
        con.execute(
            "CREATE TEMP TABLE base AS SELECT *, DENSE_RANK() OVER (ORDER BY state_key) state FROM base0"
        )

        # Pre-treatment deficit score used only for heterogeneity.
        deficit_obs = " + ".join(f"CASE WHEN b_{n} IS NOT NULL THEN 1 ELSE 0 END" for n in ASSET_COMPONENTS)
        deficit_sum = " + ".join(f"CASE WHEN b_{n} IS NULL THEN 0.0 ELSE 1.0-b_{n} END" for n in ASSET_COMPONENTS)
        con.execute(
            f"ALTER TABLE base ADD COLUMN deficit_score DOUBLE; "
            f"UPDATE base SET deficit_score=CASE WHEN ({deficit_obs})>=5 THEN ({deficit_sum})/NULLIF(({deficit_obs}),0) ELSE NULL END"
        )
        q33, q67 = con.execute(
            f"SELECT quantile_cont(deficit_score,0.333333),quantile_cont(deficit_score,0.666667) "
            f"FROM base WHERE enrol BETWEEN {CUTOFF-LOCAL_STATS_BW} AND {CUTOFF+LOCAL_STATS_BW} AND deficit_score IS NOT NULL"
        ).fetchone()
        if q33 is None or q67 is None:
            raise RuntimeError("Could not calculate baseline-need quantiles")
        con.execute(
            f"ALTER TABLE base ADD COLUMN need_stratum VARCHAR; "
            f"UPDATE base SET need_stratum=CASE WHEN deficit_score IS NULL THEN NULL "
            f"WHEN deficit_score<={float(q33)} THEN 'low' WHEN deficit_score>={float(q67)} THEN 'high' ELSE 'middle' END"
        )
        diagnostics["early_social_labels"] = early_labels
        diagnostics["deficit_q33"] = q33
        diagnostics["deficit_q67"] = q67
        diagnostics["base_local_counts_by_need"] = [
            {"stratum": r[0], "n": int(r[1])} for r in con.execute(
                f"SELECT need_stratum,COUNT(*) FROM base WHERE enrol BETWEEN {CUTOFF-LOCAL_STATS_BW} AND {CUTOFF+LOCAL_STATS_BW} GROUP BY 1 ORDER BY 1"
            ).fetchall()
        ]

        # Baseline component moments for fixed standardisation.
        component_stats: dict[str, tuple[float, float]] = {}
        for name in bcomp:
            mu, sd, n = con.execute(
                f"SELECT AVG(b_{name}),STDDEV_SAMP(b_{name}),COUNT(b_{name}) FROM base "
                f"WHERE enrol BETWEEN {CUTOFF-LOCAL_STATS_BW} AND {CUTOFF+LOCAL_STATS_BW}"
            ).fetchone()
            if mu is not None and sd is not None and n >= 1000 and float(sd) > 1e-9:
                component_stats[name] = (float(mu), float(sd))
        diagnostics["component_stats"] = {k: {"mean": v[0], "sd": v[1]} for k, v in component_stats.items()}

        # Baseline raw index expressions and baseline-index moments.
        index_raw_b: dict[str, str] = {}
        index_baseline_stats: dict[str, tuple[float, float]] = {}
        for idx, names in INDEX_FAMILIES.items():
            valid = [n for n in names if n in component_stats]
            min_obs = max(2, math.ceil(len(valid) / 2)) if valid else 99
            expr = zmean_expr(valid, "b_", component_stats, min_obs)
            index_raw_b[idx] = expr
            mu, sd, n = con.execute(
                f"SELECT AVG({expr}),STDDEV_SAMP({expr}),COUNT({expr}) FROM base "
                f"WHERE enrol BETWEEN {CUTOFF-LOCAL_STATS_BW} AND {CUTOFF+LOCAL_STATS_BW}"
            ).fetchone()
            if mu is not None and sd is not None and n >= 1000 and float(sd) > 1e-9:
                index_baseline_stats[idx] = (float(mu), float(sd))
        diagnostics["index_baseline_stats"] = {k: {"mean": v[0], "sd": v[1]} for k, v in index_baseline_stats.items()}

        future_tables: list[str] = []
        for fy in future_years:
            p1s = csv_source(extract_archive(repo, token, fy, "profile_1", work))
            p2s = csv_source(extract_archive(repo, token, fy, "profile_2", work))
            facs = csv_source(extract_archive(repo, token, fy, "facility", work))
            p1c, p2c, fcc = source_columns(con, p1s), source_columns(con, p2s), source_columns(con, facs)
            p1id = p1c.get("pseudocode") or p1c.get("psuedocode")
            p2id = p2c.get("pseudocode") or p2c.get("psuedocode")
            fcid = fcc.get("pseudocode") or fcc.get("psuedocode")
            if not all([p1id, p2id, fcid]):
                raise RuntimeError(f"Missing future identifiers in {fy}")
            ccomp = component_exprs(fcc, "f")
            current_select = ",".join(f"{expr} AS c_{name}" for name, expr in ccomp.items())
            safe = fy.replace("-", "_")
            table = f"pair_{safe}"
            future_tables.append(table)
            con.execute(
                f"""
                CREATE TEMP TABLE {table} AS
                SELECT b.*,
                       {nref(p2c,'grants_receipt','g')} receipt,
                       {nref(p2c,'grants_expenditure','g')} expenditure,
                       {current_select}
                FROM base b
                JOIN {p1s} p ON b.pseudocode=CAST(p.{qid(p1id)} AS VARCHAR)
                LEFT JOIN {p2s} g ON b.pseudocode=CAST(g.{qid(p2id)} AS VARCHAR)
                LEFT JOIN {facs} f ON b.pseudocode=CAST(f.{qid(fcid)} AS VARCHAR)
                WHERE {nref(p1c,'managment','p')} IN {GOV_MGMT}
                """
            )
            diagnostics[f"n_{fy}"] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

            # EXPERIMENT 1: maintenance versus upgrade, asset by asset.
            asset_future_rows: dict[str, list[dict]] = {"deterioration": [], "upgrade": []}
            for asset in ASSET_COMPONENTS:
                observed = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE b_{asset} IS NOT NULL AND c_{asset} IS NOT NULL"
                ).fetchone()[0]
                if observed < 1000:
                    continue
                det = estimate_from_sql(con, table, f"CASE WHEN b_{asset}=1 THEN 1.0-c_{asset} END")
                if det:
                    rec = {"experiment": 1, "assignment_year": assign_year, "outcome_year": fy,
                           "family": "deterioration", "asset": asset, **det}
                    attach_power_equivalence(rec, [0.02, 0.05])
                    transition_rows.append(rec); asset_future_rows["deterioration"].append(rec)
                up = estimate_from_sql(con, table, f"CASE WHEN b_{asset}=0 THEN c_{asset} END")
                if up:
                    rec = {"experiment": 1, "assignment_year": assign_year, "outcome_year": fy,
                           "family": "upgrade", "asset": asset, **up}
                    attach_power_equivalence(rec, [0.02, 0.05])
                    transition_rows.append(rec); asset_future_rows["upgrade"].append(rec)
            for fam in asset_future_rows:
                bh_adjust(asset_future_rows[fam])

            # Composite transition rates across baseline-eligible assets.
            det_terms = [f"CASE WHEN b_{a}=1 AND c_{a} IS NOT NULL THEN 1.0-c_{a} ELSE 0.0 END" for a in ASSET_COMPONENTS]
            det_den = [f"CASE WHEN b_{a}=1 AND c_{a} IS NOT NULL THEN 1 ELSE 0 END" for a in ASSET_COMPONENTS]
            up_terms = [f"CASE WHEN b_{a}=0 AND c_{a} IS NOT NULL THEN c_{a} ELSE 0.0 END" for a in ASSET_COMPONENTS]
            up_den = [f"CASE WHEN b_{a}=0 AND c_{a} IS NOT NULL THEN 1 ELSE 0 END" for a in ASSET_COMPONENTS]
            det_expr = f"CASE WHEN ({' + '.join(det_den)})>=3 THEN ({' + '.join(det_terms)})/NULLIF(({' + '.join(det_den)}),0) END"
            up_expr = f"CASE WHEN ({' + '.join(up_den)})>=2 THEN ({' + '.join(up_terms)})/NULLIF(({' + '.join(up_den)}),0) END"
            for fam, expr in (("deterioration_composite", det_expr), ("upgrade_composite", up_expr)):
                est = estimate_from_sql(con, table, expr)
                if est:
                    rec = {"experiment": 1, "assignment_year": assign_year, "outcome_year": fy,
                           "family": fam, "asset": "composite", **est}
                    attach_power_equivalence(rec, [0.02, 0.05])
                    transition_rows.append(rec)
                    equivalence_rows.append({**rec, "scale": "proportion"})

            # EXPERIMENT 4: fixed-baseline dynamic indices.
            for idx, names in INDEX_FAMILIES.items():
                if idx not in index_baseline_stats:
                    continue
                valid = [n for n in names if n in component_stats]
                if not valid:
                    continue
                min_obs = max(2, math.ceil(len(valid) / 2))
                braw = zmean_expr(valid, "b_", component_stats, min_obs)
                craw = zmean_expr(valid, "c_", component_stats, min_obs)
                imu, isd = index_baseline_stats[idx]
                bz = f"(({braw})-({imu}))/({isd})"
                cz = f"(({craw})-({imu}))/({isd})"
                delta = f"({cz})-({bz})"
                est = estimate_from_sql(con, table, delta)
                if est:
                    rec = {"experiment": 4, "assignment_year": assign_year, "outcome_year": fy,
                           "index": idx, "family": "dynamic_index_change", **est}
                    attach_power_equivalence(rec, [0.05, 0.10])
                    index_rows.append(rec)
                    equivalence_rows.append({**rec, "scale": "baseline_index_sd"})

            # EXPERIMENT 2: heterogeneity by pre-treatment need.
            for stratum in ("low", "middle", "high"):
                where = f"need_stratum='{stratum}'"
                for var in ("receipt", "expenditure"):
                    est = estimate_from_sql(con, table, var, where)
                    if est:
                        finance_rows.append({"experiment": 2, "assignment_year": assign_year, "outcome_year": fy,
                                             "need_stratum": stratum, "outcome": var, **est})
                for fam, expr in (("deterioration_composite", det_expr), ("upgrade_composite", up_expr)):
                    est = estimate_from_sql(con, table, expr, where)
                    if est:
                        heterogeneity_rows.append({"experiment": 2, "assignment_year": assign_year, "outcome_year": fy,
                                                   "need_stratum": stratum, "outcome": fam, **est})
                for idx, names in INDEX_FAMILIES.items():
                    if idx not in index_baseline_stats:
                        continue
                    valid = [n for n in names if n in component_stats]
                    min_obs = max(2, math.ceil(len(valid) / 2))
                    braw = zmean_expr(valid, "b_", component_stats, min_obs)
                    craw = zmean_expr(valid, "c_", component_stats, min_obs)
                    imu, isd = index_baseline_stats[idx]
                    delta = f"((({craw})-({imu}))/({isd}))-((({braw})-({imu}))/({isd}))"
                    est = estimate_from_sql(con, table, delta, where)
                    if est:
                        heterogeneity_rows.append({"experiment": 2, "assignment_year": assign_year, "outcome_year": fy,
                                                   "need_stratum": stratum, "outcome": f"index_{idx}", **est})

        # Cumulative expenditure through all available future rounds, overall and by baseline need.
        if future_tables:
            joins = []
            select_exp = []
            select_rec = []
            for i, table in enumerate(future_tables):
                alias = f"f{i}"
                joins.append(f"LEFT JOIN {table} {alias} ON b.pseudocode={alias}.pseudocode")
                select_exp.append(f"{alias}.expenditure")
                select_rec.append(f"{alias}.receipt")
            exp_obs = " + ".join(f"CASE WHEN {x} IS NOT NULL THEN 1 ELSE 0 END" for x in select_exp)
            rec_obs = " + ".join(f"CASE WHEN {x} IS NOT NULL THEN 1 ELSE 0 END" for x in select_rec)
            exp_sum = " + ".join(f"COALESCE({x},0.0)" for x in select_exp)
            rec_sum = " + ".join(f"COALESCE({x},0.0)" for x in select_rec)
            con.execute(
                f"CREATE TEMP TABLE cumulative AS SELECT b.*, "
                f"CASE WHEN ({exp_obs})={len(future_tables)} THEN ({exp_sum}) END cumulative_expenditure, "
                f"CASE WHEN ({rec_obs})={len(future_tables)} THEN ({rec_sum}) END cumulative_receipt "
                f"FROM base b {' '.join(joins)}"
            )
            for stratum in ("all", "low", "middle", "high"):
                where = "TRUE" if stratum == "all" else f"need_stratum='{stratum}'"
                for var in ("cumulative_expenditure", "cumulative_receipt"):
                    est = estimate_from_sql(con, "cumulative", var, where)
                    if est:
                        finance_rows.append({"experiment": 2, "assignment_year": assign_year,
                                             "outcome_year": "..".join(future_years), "need_stratum": stratum,
                                             "outcome": var, **est})

    # Final FDR across individual asset transition tests within cohort × year × family.
    for fy in future_years:
        for fam in ("deterioration", "upgrade"):
            subset = [r for r in transition_rows if r["outcome_year"] == fy and r["family"] == fam]
            bh_adjust(subset)

    write_csv(out / "experiment1_maintenance_upgrade.csv", transition_rows)
    write_csv(out / "experiment2_need_heterogeneity.csv", heterogeneity_rows)
    write_csv(out / "experiment2_finance_by_need.csv", finance_rows)
    write_csv(out / "experiment3_power_equivalence.csv", equivalence_rows)
    write_csv(out / "experiment4_dynamic_indices.csv", index_rows)

    summary = {
        "assignment_year": assign_year,
        "future_years": future_years,
        "diagnostics": diagnostics,
        "transition_composites": [r for r in transition_rows if r["family"].endswith("_composite")],
        "individual_transition_fdr_hits_q10": [r for r in transition_rows if r.get("q_bh", 1.0) < 0.10 and r["family"] in {"deterioration", "upgrade"}],
        "dynamic_indices": index_rows,
        "finance_by_need": finance_rows,
        "heterogeneity": heterogeneity_rows,
        "equivalence": equivalence_rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("CONFIRMATORY SUMMARY", flush=True)
    print("ASSIGNMENT", assign_year, "FUTURE", future_years, flush=True)
    print("NEED CUTS", q33, q67, flush=True)
    print("\nEXPERIMENT 1 COMPOSITES", flush=True)
    for r in summary["transition_composites"]:
        print(json.dumps(r), flush=True)
    print("\nEXPERIMENT 1 FDR HITS", len(summary["individual_transition_fdr_hits_q10"]), flush=True)
    for r in summary["individual_transition_fdr_hits_q10"]:
        print(json.dumps(r), flush=True)
    print("\nEXPERIMENT 4 DYNAMIC INDICES", flush=True)
    for r in index_rows:
        print(json.dumps(r), flush=True)
    print("\nEXPERIMENT 2 CUMULATIVE FINANCE / NEED", flush=True)
    for r in finance_rows:
        if r["outcome"].startswith("cumulative"):
            print(json.dumps(r), flush=True)
    print("\nEXPERIMENT 2 HETEROGENEITY", flush=True)
    for r in heterogeneity_rows:
        print(json.dumps(r), flush=True)
    con.close()


if __name__ == "__main__":
    main()
