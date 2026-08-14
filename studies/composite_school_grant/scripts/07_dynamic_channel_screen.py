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
rd = FOCUS["rd"]

CUTOFF = 250
BANDWIDTH = 30
DONUT = 1

# These are identifiers, geography, source metadata, or treatment-definition fields rather than outcomes.
EXCLUDE_PATTERNS = (
    "pseudocode", "psuedocode", "udise", "school_code", "state", "district", "block", "cluster",
    "village", "panchayat", "ward", "pin", "latitude", "longitude", "management", "managment",
    "school_category", "school_type", "rural_urban", "lowclass", "highclass", "year_estb", "school_name",
    "respondent", "mobile", "email", "loc_desc", "location", "item_group", "item_id", "item_desc",
)

# Treatment/accounting variables are handled separately and are not part of the outcome fishing screen.
TREATMENT_PATTERNS = ("grant", "receipt", "expenditure", "fund", "amount_sanction", "amount_received")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower().replace("\ufeff", "")).strip("_")


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
        w.writeheader(); w.writerows(rows)


def bh_qvalues(rows: list[dict], pkey: str = "p") -> None:
    valid = [(i, float(r[pkey])) for i, r in enumerate(rows) if r.get(pkey) is not None and math.isfinite(float(r[pkey]))]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    running = 1.0
    for rank in range(m, 0, -1):
        idx, p = valid[rank - 1]
        q = min(running, p * m / rank)
        running = q
        rows[idx]["q_bh"] = q


def is_candidate(name: str) -> bool:
    n = norm(name)
    if any(p in n for p in EXCLUDE_PATTERNS):
        return False
    if any(p in n for p in TREATMENT_PATTERNS):
        return False
    return True


def total_enrolment_sql(con: duckdb.DuckDBPyConnection, source: str, cols: dict[str, str]) -> tuple[str, str]:
    terms = [
        f"COALESCE({nref(cols, f'c{c}_{s}')},0)"
        for c in range(1, 13)
        for s in ("b", "g")
        if f"c{c}_{s}" in cols
    ]
    if not terms:
        raise RuntimeError("No class enrolment columns")
    if "item_group" in cols and "item_id" in cols:
        filt = f"{nref(cols,'item_group')}=1 AND {nref(cols,'item_id')} IN (1,2,3,4)"
    else:
        labels = identify_early_social_labels(con, source, cols)
        if not labels:
            raise RuntimeError("Cannot identify social-category rows")
        d = ref(cols, "item_desc")
        filt = f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labels)})"
    return " + ".join(terms), filt


def numeric_aliases(cols: dict[str, str], prefix: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for n, actual in cols.items():
        if not is_candidate(n):
            continue
        alias = f"{prefix}__{n}"
        out.append((n, f"{num(qid(actual))} AS {qid(alias)}"))
    return out


def build_small_table(
    con: duckdb.DuckDBPyConnection,
    source: str,
    cols: dict[str, str],
    id_name: str,
    sample_table: str,
    out_name: str,
    prefix: str,
) -> list[str]:
    pairs = numeric_aliases(cols, prefix)
    select = ",".join(expr for _, expr in pairs)
    sid = qid(id_name)
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE {out_name} AS
      SELECT CAST(r.{sid} AS VARCHAR) pseudocode{',' if select else ''}{select}
      FROM {source} r JOIN {sample_table} s ON CAST(r.{sid} AS VARCHAR)=s.pseudocode
    """)
    return [n for n, _ in pairs]


def main() -> None:
    assign_year = os.environ["ASSIGN_YEAR"]
    grant_year = os.environ["GRANT_YEAR"]
    outcome_year = os.environ["OUTCOME_YEAR"]
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path(f"studies/composite_school_grant/outputs/dynamic_channels/{assign_year}_grant_{grant_year}_outcome_{outcome_year}")
    out.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")

    with tempfile.TemporaryDirectory(prefix="csg_dynamic_") as td:
        work = Path(td)
        # Assignment-year sources.
        a_enr = csv_source(extract_archive(repo, token, assign_year, "enrolment_1", work))
        a_p1 = csv_source(extract_archive(repo, token, assign_year, "profile_1", work))
        a_fac = csv_source(extract_archive(repo, token, assign_year, "facility", work))
        a_p2 = csv_source(extract_archive(repo, token, assign_year, "profile_2", work))
        # Grant-year sources.
        g_p1 = csv_source(extract_archive(repo, token, grant_year, "profile_1", work))
        g_p2 = csv_source(extract_archive(repo, token, grant_year, "profile_2", work))
        # Outcome-year sources.
        o_p1 = csv_source(extract_archive(repo, token, outcome_year, "profile_1", work))
        o_fac = csv_source(extract_archive(repo, token, outcome_year, "facility", work))
        o_p2 = csv_source(extract_archive(repo, token, outcome_year, "profile_2", work))

        ec = source_columns(con, a_enr); apc = source_columns(con, a_p1)
        gpc = source_columns(con, g_p1); gp2c = source_columns(con, g_p2)
        opc = source_columns(con, o_p1); ofc = source_columns(con, o_fac); op2c = source_columns(con, o_p2)
        afc = source_columns(con, a_fac); ap2c = source_columns(con, a_p2)

        ids = {}
        for key, c in (("e",ec),("ap1",apc),("af",afc),("ap2",ap2c),("gp1",gpc),("gp2",gp2c),("op1",opc),("of",ofc),("op2",op2c)):
            ids[key] = c.get("pseudocode") or c.get("psuedocode")
            if not ids[key]: raise RuntimeError(f"Missing school id in {key}")

        class_sum, social_filter = total_enrolment_sql(con, a_enr, ec)
        con.execute(f"""
          CREATE TEMP TABLE assign_enrol AS
          SELECT CAST({qid(ids['e'])} AS VARCHAR) pseudocode, SUM({class_sum}) enrol
          FROM {a_enr} WHERE {social_filter} GROUP BY 1
        """)

        # State is retained as text and encoded categorically. Management must remain government in assignment, grant and outcome years.
        con.execute(f"""
          CREATE TEMP TABLE assignment_profile AS
          SELECT CAST({qid(ids['ap1'])} AS VARCHAR) pseudocode,
                 CAST({ref(apc,'state')} AS VARCHAR) state_key,
                 {nref(apc,'managment')} management
          FROM {a_p1}
        """)
        con.execute(f"""
          CREATE TEMP TABLE grant_profile AS
          SELECT CAST(p.{qid(ids['gp1'])} AS VARCHAR) pseudocode,
                 {nref(gpc,'managment','p')} management_grant,
                 {nref(gp2c,'grants_receipt','g')} csg_receipt_grantyear,
                 {nref(gp2c,'grants_expenditure','g')} csg_expenditure_grantyear
          FROM {g_p1} p JOIN {g_p2} g ON CAST(p.{qid(ids['gp1'])} AS VARCHAR)=CAST(g.{qid(ids['gp2'])} AS VARCHAR)
        """)
        con.execute(f"""
          CREATE TEMP TABLE outcome_profile AS
          SELECT CAST(p.{qid(ids['op1'])} AS VARCHAR) pseudocode,
                 {nref(opc,'managment','p')} management_outcome,
                 {nref(op2c,'grants_receipt','g')} csg_receipt_outcomeyear,
                 {nref(op2c,'grants_expenditure','g')} csg_expenditure_outcomeyear
          FROM {o_p1} p JOIN {o_p2} g ON CAST(p.{qid(ids['op1'])} AS VARCHAR)=CAST(g.{qid(ids['op2'])} AS VARCHAR)
        """)
        con.execute(f"""
          CREATE TEMP TABLE sample_ids AS
          SELECT e.pseudocode,e.enrol,
                 DENSE_RANK() OVER (ORDER BY a.state_key) state,
                 g.csg_receipt_grantyear,g.csg_expenditure_grantyear,
                 o.csg_receipt_outcomeyear,o.csg_expenditure_outcomeyear
          FROM assign_enrol e
          JOIN assignment_profile a USING(pseudocode)
          JOIN grant_profile g USING(pseudocode)
          JOIN outcome_profile o USING(pseudocode)
          WHERE a.management IN (1,2,3) AND g.management_grant IN (1,2,3) AND o.management_outcome IN (1,2,3)
            AND e.enrol BETWEEN {CUTOFF-BANDWIDTH} AND {CUTOFF+BANDWIDTH}
            AND g.csg_receipt_grantyear IS NOT NULL
        """)
        n = con.execute("SELECT COUNT(*) FROM sample_ids").fetchone()[0]
        states = con.execute("SELECT COUNT(DISTINCT state) FROM sample_ids").fetchone()[0]
        print(f"DYNAMIC SAMPLE {assign_year}->{grant_year}->{outcome_year}: n={n:,}, states={states}", flush=True)

        # Treatment persistence: grant year and later outcome-year CSG accounting.
        grant_results=[]
        for var in ("csg_receipt_grantyear","csg_expenditure_grantyear","csg_receipt_outcomeyear","csg_expenditure_outcomeyear"):
            arr=con.execute(f"SELECT {var} y,enrol,state FROM sample_ids WHERE {var} IS NOT NULL").fetchnumpy()
            est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BANDWIDTH,DONUT)
            if est: grant_results.append({"variable":var,**est})

        # Broad facility screen across every numeric field common to assignment and outcome files.
        af_names = build_small_table(con, a_fac, afc, ids['af'], "sample_ids", "base_fac", "b")
        of_names = build_small_table(con, o_fac, ofc, ids['of'], "sample_ids", "out_fac", "o")
        common_fac = sorted(set(af_names) & set(of_names))

        # Broad profile_2 screen, excluding grant/funding variables by name.
        ap2_names = build_small_table(con, a_p2, ap2c, ids['ap2'], "sample_ids", "base_p2", "b")
        op2_names = build_small_table(con, o_p2, op2c, ids['op2'], "sample_ids", "out_p2", "o")
        common_p2 = sorted(set(ap2_names) & set(op2_names))

        screens: list[dict] = []
        for family, base_table, out_table, names in (
            ("facility","base_fac","out_fac",common_fac),
            ("profile_2","base_p2","out_p2",common_p2),
        ):
            for name in names:
                bcol=qid(f"b__{name}"); ocol=qid(f"o__{name}")
                # Require sufficient numeric support and actual variation.
                stats=con.execute(f"""
                  SELECT COUNT(*) FILTER (WHERE b.{bcol} IS NOT NULL AND o.{ocol} IS NOT NULL) n_pair,
                         COUNT(DISTINCT b.{bcol}) FILTER (WHERE b.{bcol} IS NOT NULL) b_dist,
                         COUNT(DISTINCT o.{ocol}) FILTER (WHERE o.{ocol} IS NOT NULL) o_dist,
                         STDDEV_POP(b.{bcol}) FILTER (WHERE b.{bcol} IS NOT NULL) b_sd,
                         MIN(b.{bcol}),MAX(b.{bcol}),MIN(o.{ocol}),MAX(o.{ocol})
                  FROM sample_ids s LEFT JOIN {base_table} b USING(pseudocode) LEFT JOIN {out_table} o USING(pseudocode)
                """).fetchone()
                n_pair,b_dist,o_dist,b_sd,bmin,bmax,omin,omax=stats
                if n_pair is None or n_pair<2000 or (b_dist or 0)<2 or (o_dist or 0)<2:
                    continue
                arr=con.execute(f"""
                  SELECT (o.{ocol}-b.{bcol}) y,s.enrol,s.state
                  FROM sample_ids s JOIN {base_table} b USING(pseudocode) JOIN {out_table} o USING(pseudocode)
                  WHERE b.{bcol} IS NOT NULL AND o.{ocol} IS NOT NULL
                """).fetchnumpy()
                est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BANDWIDTH,DONUT)
                if not est: continue
                barr=con.execute(f"""
                  SELECT b.{bcol} y,s.enrol,s.state
                  FROM sample_ids s JOIN {base_table} b USING(pseudocode)
                  WHERE b.{bcol} IS NOT NULL
                """).fetchnumpy()
                pre=rd(barr['y'],barr['enrol'],barr['state'],CUTOFF,BANDWIDTH,DONUT)
                screens.append({
                    "family":family,"field":name,"n_pair":int(n_pair),"base_distinct":int(b_dist or 0),"outcome_distinct":int(o_dist or 0),
                    "base_sd":b_sd,"base_min":bmin,"base_max":bmax,"outcome_min":omin,"outcome_max":omax,
                    **est,
                    "std_effect": (est['tau']/b_sd if b_sd not in (None,0) and math.isfinite(float(b_sd)) else None),
                    "baseline_tau":None if not pre else pre['tau'],"baseline_p":None if not pre else pre['p'],
                })

        bh_qvalues(screens)
        for r in screens:
            r["clean_baseline"] = r.get("baseline_p") is None or r["baseline_p"]>0.10
            r["candidate_after_fdr"] = bool(r.get("q_bh") is not None and r["q_bh"]<0.10 and r["clean_baseline"])

        # Separate the strongest exploratory candidates from the complete screen.
        ranked=sorted(screens,key=lambda r:(0 if r['candidate_after_fdr'] else 1, r.get('q_bh',1.0), -abs(r.get('std_effect') or 0)))
        candidates=[r for r in ranked if r['candidate_after_fdr']][:30]

        write_csv(out/"all_numeric_channel_screen.csv",screens)
        write_csv(out/"fdr_candidates.csv",candidates)
        write_csv(out/"grant_persistence.csv",grant_results)
        summary={
            "assignment_year":assign_year,"grant_year":grant_year,"outcome_year":outcome_year,"n":int(n),"states":int(states),
            "common_facility_fields_screened":len([r for r in screens if r['family']=='facility']),
            "common_profile2_fields_screened":len([r for r in screens if r['family']=='profile_2']),
            "grant_persistence":grant_results,
            "fdr_candidates":candidates,
            "top_20_by_raw_p":sorted(screens,key=lambda r:r.get('p',1.0))[:20],
        }
        (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
        print("GRANT PERSISTENCE",flush=True)
        for r in grant_results: print(json.dumps(r),flush=True)
        print("FDR CANDIDATES",flush=True)
        for r in candidates: print(json.dumps(r),flush=True)
        print("TOP RAW-P SCREEN",flush=True)
        for r in summary['top_20_by_raw_p']: print(json.dumps(r),flush=True)

    con.close()

if __name__=="__main__":
    main()
