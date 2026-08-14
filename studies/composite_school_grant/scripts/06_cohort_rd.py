from __future__ import annotations

import csv
import json
import math
import os
import re
import runpy
import shutil
import tempfile
from pathlib import Path

import duckdb
import numpy as np

# Reuse the already-audited cross-vintage I/O and RD routines without executing their mains.
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


def bool01(cols: dict[str, str], name: str, alias: str) -> str:
    r = ref(cols, name, alias)
    if not r:
        return "NULL"
    v = num(r)
    return f"CASE WHEN {v}=1 THEN 1.0 WHEN {v}=2 THEN 0.0 ELSE NULL END"


def water01(cols: dict[str, str], alias: str) -> str:
    raw = water_raw(cols, alias, True)
    return f"CASE WHEN ({raw})=1 THEN 1.0 WHEN ({raw})=2 THEN 0.0 ELSE NULL END"


def share_expr(n: str, d: str) -> str:
    return f"CASE WHEN {d}>0 THEN LEAST(1.0,GREATEST(0.0,{n}/{d})) ELSE NULL END"


def outcomes(cols: dict[str, str], alias: str) -> dict[str, str]:
    rooms = nref(cols, "total_class_rooms", alias)
    minor = nref(cols, "classrooms_needs_minor_repair", alias)
    major = nref(cols, "classrooms_needs_major_repair", alias)
    good = nref(cols, "classrooms_in_good_condition", alias)
    gt = nref(cols, "total_girls_toilet", alias)
    gf = nref(cols, "total_girls_func_toilet", alias)
    bt = nref(cols, "total_boys_toilet", alias)
    bf = nref(cols, "total_boys_func_toilet", alias)
    return {
        "minor_repair_share": share_expr(minor, rooms),
        "major_repair_share": share_expr(major, rooms),
        "good_classroom_share": share_expr(good, rooms),
        "girls_toilet_functional_share": share_expr(gf, gt),
        "boys_toilet_functional_share": share_expr(bf, bt),
        "water_functional": water01(cols, alias),
        "handwash_meal": bool01(cols, "handwash_facility_for_meal", alias),
        "electricity": bool01(cols, "electricity_availability", alias),
        "internet": bool01(cols, "internet", alias),
        "library": bool01(cols, "library_availability", alias),
    }


def total_enrolment_sql(con: duckdb.DuckDBPyConnection, src: str, cols: dict[str, str]) -> tuple[str, list[str]]:
    class_terms = [
        f"COALESCE({nref(cols, f'c{c}_{s}')},0)"
        for c in range(1, 13)
        for s in ("b", "g")
        if f"c{c}_{s}" in cols
    ]
    if not class_terms:
        raise RuntimeError("No class enrolment columns")
    class_sum = " + ".join(class_terms)
    if "item_group" in cols and "item_id" in cols:
        filt = f"{nref(cols,'item_group')}=1 AND {nref(cols,'item_id')} IN (1,2,3,4)"
        labels: list[str] = []
    else:
        labels = identify_early_social_labels(con, src, cols)
        if not labels:
            raise RuntimeError("Could not identify social-category rows")
        d = ref(cols, "item_desc")
        filt = f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labels)})"
    return f"SUM({class_sum})", [filt, *labels]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ay = os.environ["ASSIGN_YEAR"]
    oy = os.environ["OUTCOME_YEAR"]
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path(f"studies/composite_school_grant/outputs/cohorts/{ay}_to_{oy}")
    out.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")

    with tempfile.TemporaryDirectory(prefix=f"csg_{ay}_{oy}_") as td:
        work = Path(td)
        a_enr = csv_source(extract_archive(repo, token, ay, "enrolment_1", work))
        a_p1 = csv_source(extract_archive(repo, token, ay, "profile_1", work))
        a_fac = csv_source(extract_archive(repo, token, ay, "facility", work))
        o_p1 = csv_source(extract_archive(repo, token, oy, "profile_1", work))
        o_p2 = csv_source(extract_archive(repo, token, oy, "profile_2", work))
        o_fac = csv_source(extract_archive(repo, token, oy, "facility", work))

        ec, apc, afc = source_columns(con, a_enr), source_columns(con, a_p1), source_columns(con, a_fac)
        opc, op2c, ofc = source_columns(con, o_p1), source_columns(con, o_p2), source_columns(con, o_fac)
        ids = {}
        for name, c in (("enr", ec), ("ap1", apc), ("af", afc), ("op1", opc), ("op2", op2c), ("of", ofc)):
            ids[name] = c.get("pseudocode") or c.get("psuedocode")
            if not ids[name]:
                raise RuntimeError(f"Missing school id in {name}")

        total_sql, filter_and_labels = total_enrolment_sql(con, a_enr, ec)
        social_filter = filter_and_labels[0]
        labels = filter_and_labels[1:]
        con.execute(f"""
          CREATE TEMP TABLE enr AS
          SELECT CAST({qid(ids['enr'])} AS VARCHAR) pseudocode, {total_sql} enrol
          FROM {a_enr}
          WHERE {social_filter}
          GROUP BY 1
        """)

        aout = outcomes(afc, "f")
        oout = outcomes(ofc, "f")
        apid, afid = qid(ids["ap1"]), qid(ids["af"])
        opid, op2id, ofid = qid(ids["op1"]), qid(ids["op2"]), qid(ids["of"])
        con.execute(f"""
          CREATE TEMP TABLE abase AS
          SELECT CAST(p.{apid} AS VARCHAR) pseudocode,
                 {nref(apc,'state','p')} state,
                 {nref(apc,'district','p')} district,
                 {nref(apc,'managment','p')} management,
                 {','.join(expr + ' b_' + name for name,expr in aout.items())}
          FROM {a_p1} p LEFT JOIN {a_fac} f
            ON CAST(p.{apid} AS VARCHAR)=CAST(f.{afid} AS VARCHAR)
        """)

        derived = []
        for name, expr in oout.items():
            derived += [f"{expr} c_{name}", f"b.b_{name}", f"({expr})-b.b_{name} d_{name}"]
        con.execute(f"""
          CREATE TEMP TABLE sample AS
          SELECT e.pseudocode,e.enrol,b.state,b.district,b.management management_base,
                 {nref(opc,'managment','p')} management_current,
                 {nref(op2c,'grants_receipt','g')} receipt,
                 {nref(op2c,'grants_expenditure','g')} expenditure,
                 {','.join(derived)}
          FROM enr e
          JOIN abase b USING(pseudocode)
          JOIN {o_p1} p ON e.pseudocode=CAST(p.{opid} AS VARCHAR)
          JOIN {o_p2} g ON e.pseudocode=CAST(g.{op2id} AS VARCHAR)
          LEFT JOIN {o_fac} f ON e.pseudocode=CAST(f.{ofid} AS VARCHAR)
          WHERE b.management IN (1,2,3)
            AND {nref(opc,'managment','p')} IN (1,2,3)
            AND e.enrol>0
            AND {nref(op2c,'grants_receipt','g')} IS NOT NULL
        """)
        n = con.execute("SELECT COUNT(*) FROM sample").fetchone()[0]
        states = con.execute("SELECT COUNT(DISTINCT state) FROM sample WHERE state IS NOT NULL").fetchone()[0]
        print(f"COHORT {ay}->{oy}: n={n:,}, states={states}, early_labels={labels}", flush=True)

        results: list[dict] = []
        pretests: list[dict] = []
        cells: list[dict] = []
        specs = {100: [20,30,40], 250: [20,30,40,50,75]}
        outcome_names = list(aout)
        for cutoff, bws in specs.items():
            for bw in bws:
                for donut in (0,1,2):
                    for var, fam in (("receipt","first_stage_receipt"),("expenditure","first_stage_expenditure")):
                        arr = con.execute(f"SELECT {var} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND {var} IS NOT NULL").fetchnumpy()
                        est = rd(arr["y"],arr["enrol"],arr["state"],cutoff,bw,donut)
                        if est:
                            results.append({"assignment_year":ay,"outcome_year":oy,"family":fam,"outcome":var,"cutoff":cutoff,"bandwidth":bw,"donut":donut,**est})
                    for name in outcome_names:
                        arr = con.execute(f"SELECT d_{name} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND d_{name} IS NOT NULL").fetchnumpy()
                        est = rd(arr["y"],arr["enrol"],arr["state"],cutoff,bw,donut)
                        if est:
                            results.append({"assignment_year":ay,"outcome_year":oy,"family":"outcome_change","outcome":name,"cutoff":cutoff,"bandwidth":bw,"donut":donut,**est})
                        arr = con.execute(f"SELECT b_{name} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND b_{name} IS NOT NULL").fetchnumpy()
                        est = rd(arr["y"],arr["enrol"],arr["state"],cutoff,bw,donut)
                        if est:
                            pretests.append({"assignment_year":ay,"outcome_year":oy,"outcome":name,"cutoff":cutoff,"bandwidth":bw,"donut":donut,**est})
            maxbw=max(bws)
            for e, nn, mr, me in con.execute(f"""
              SELECT CAST(enrol AS INTEGER),COUNT(*),AVG(receipt),AVG(expenditure)
              FROM sample WHERE enrol BETWEEN {cutoff-maxbw} AND {cutoff+maxbw}
              GROUP BY 1 ORDER BY 1
            """).fetchall():
                cells.append({"assignment_year":ay,"outcome_year":oy,"cutoff":cutoff,"enrol":e,"n":int(nn),"mean_receipt":mr,"mean_expenditure":me})

        density=[]
        for cutoff,bws in specs.items():
            for bw in bws:
                s=[r for r in cells if r["cutoff"]==cutoff and abs(r["enrol"]-cutoff)<=bw]
                e=np.array([r["enrol"] for r in s],float); cnt=np.array([r["n"] for r in s],float)
                x=e-(cutoff+.5); d=(e>cutoff).astype(float); X=np.column_stack([np.ones(len(e)),d,x,d*x])
                beta=np.linalg.lstsq(X,np.log(cnt+.5),rcond=None)[0]
                left=sum(r["n"] for r in s if cutoff-5<=r["enrol"]<=cutoff-1); right=sum(r["n"] for r in s if cutoff+1<=r["enrol"]<=cutoff+5)
                density.append({"assignment_year":ay,"outcome_year":oy,"cutoff":cutoff,"bandwidth":bw,"log_density_jump":float(beta[1]),"implied_pct":float((math.exp(beta[1])-1)*100),"right_left_5_ratio":right/left if left else None})

        write_csv(out/"estimates.csv",results); write_csv(out/"pretreatment.csv",pretests); write_csv(out/"cells.csv",cells); write_csv(out/"density.csv",density)
        central=[r for r in results if r["cutoff"]==250 and r["bandwidth"]==30 and r["donut"]==1]
        summary={"assignment_year":ay,"outcome_year":oy,"n":int(n),"states":int(states),"early_social_labels":labels,"central_250_bw30_donut1":central,"density":density}
        (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("CENTRAL 250 SPEC", flush=True)
        for r in central: print(json.dumps(r), flush=True)
        print("DENSITY", json.dumps(density), flush=True)
    con.close()

if __name__ == "__main__":
    main()
