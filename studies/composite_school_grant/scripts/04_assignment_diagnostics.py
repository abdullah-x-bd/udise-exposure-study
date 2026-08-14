from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import duckdb

YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]
YEAR_INDEX = {y:i for i,y in enumerate(YEARS)}


def expected_amount(enrol: float | None, schedule: str) -> float | None:
    if enrol is None or not math.isfinite(enrol) or enrol <= 0:
        return None
    if schedule == "current":
        if enrol <= 30: return 10000.0
        if enrol <= 100: return 25000.0
        if enrol <= 250: return 50000.0
        if enrol <= 1000: return 75000.0
        return 100000.0
    if schedule == "legacy":
        if enrol <= 100: return 25000.0
        if enrol <= 250: return 50000.0
        if enrol <= 1000: return 75000.0
        return 100000.0
    raise ValueError(schedule)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main() -> None:
    panel = Path("studies/composite_school_grant/outputs/panel/school_year_panel.parquet")
    out = Path("studies/composite_school_grant/outputs/assignment_diagnostics")
    out.mkdir(parents=True, exist_ok=True)
    con=duckdb.connect()
    con.execute("PRAGMA threads=4")

    # Grant distributions by year.
    distributions=[]
    management=[]
    for y in YEARS:
        rows=con.execute(f"""
          SELECT csg_receipt, COUNT(*) n
          FROM read_parquet('{panel.as_posix()}')
          WHERE academic_year='{y}'
          GROUP BY csg_receipt ORDER BY n DESC LIMIT 30
        """).fetchall()
        for val,n in rows:
            distributions.append({"year":y,"csg_receipt":val,"n":int(n)})
        mrows=con.execute(f"""
          SELECT management, COUNT(*) n,
                 COUNT(csg_receipt) n_nonnull,
                 SUM(CASE WHEN csg_receipt>0 THEN 1 ELSE 0 END) n_positive,
                 AVG(csg_receipt) FILTER (WHERE csg_receipt IS NOT NULL) mean_receipt
          FROM read_parquet('{panel.as_posix()}')
          WHERE academic_year='{y}'
          GROUP BY management ORDER BY n DESC
        """).fetchall()
        for m,n,nn,np,avg in mrows:
            management.append({"year":y,"management":m,"n":int(n),"n_nonnull":int(nn),"n_positive":int(np or 0),"nonnull_rate":float(nn/n) if n else None,"positive_rate":float((np or 0)/n) if n else None,"mean_receipt":avg})

    # Build same-school current/lag pairs for lags 0-3.
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE p AS
      SELECT *, CASE academic_year
        {' '.join(f"WHEN '{y}' THEN {i}" for i,y in enumerate(YEARS))}
      END AS yi
      FROM read_parquet('{panel.as_posix()}')
    """)

    match_rows=[]
    cell_rows=[]
    for lag in range(0,4):
        if lag==0:
            join="c.pseudocode=l.pseudocode AND c.yi=l.yi"
        else:
            join=f"c.pseudocode=l.pseudocode AND c.yi=l.yi+{lag}"
        pairs=con.execute(f"""
          SELECT c.academic_year current_year, l.academic_year enrolment_year,
                 c.pseudocode, c.state, c.management,
                 c.csg_receipt, c.csg_expenditure,
                 l.enrol_c1_12, l.enrol_incl_preprimary
          FROM p c JOIN p l ON {join}
          WHERE c.csg_receipt IS NOT NULL
        """).fetchall()
        cols=[d[0] for d in con.description]
        records=[dict(zip(cols,r)) for r in pairs]
        for measure in ("enrol_c1_12","enrol_incl_preprimary"):
            for schedule in ("current","legacy"):
                by_year={}
                for r in records:
                    val=r[measure]
                    exp=expected_amount(val,schedule)
                    if exp is None or r["csg_receipt"] is None:
                        continue
                    d=by_year.setdefault(r["current_year"], {"n":0,"match":0,"abs_err":0.0,"positive_n":0,"positive_match":0})
                    d["n"]+=1; d["abs_err"]+=abs(float(r["csg_receipt"])-exp)
                    if abs(float(r["csg_receipt"])-exp)<0.5: d["match"]+=1
                    if float(r["csg_receipt"])>0:
                        d["positive_n"]+=1
                        if abs(float(r["csg_receipt"])-exp)<0.5: d["positive_match"]+=1
                for cy,d in by_year.items():
                    match_rows.append({
                        "lag":lag,"current_year":cy,"enrolment_measure":measure,"schedule":schedule,
                        "n":d["n"],"exact_match_rate":d["match"]/d["n"] if d["n"] else None,
                        "mean_absolute_error":d["abs_err"]/d["n"] if d["n"] else None,
                        "positive_n":d["positive_n"],"positive_exact_match_rate":d["positive_match"]/d["positive_n"] if d["positive_n"] else None,
                    })

        # Enrollment-cell grant means around candidate cutoffs, useful without imposing linearity.
        if lag>0:
            for measure in ("enrol_c1_12","enrol_incl_preprimary"):
                for cutoff in (30,100,250,1000):
                    for r in records:
                        e=r[measure]
                        if e is None or abs(float(e)-cutoff)>20:
                            continue
                        if r["csg_receipt"] is None:
                            continue
                        cell_rows.append({"lag":lag,"current_year":r["current_year"],"enrolment_year":r["enrolment_year"],"measure":measure,"cutoff":cutoff,"enrolment":int(round(float(e))),"receipt":float(r["csg_receipt"]),"expenditure":None if r["csg_expenditure"] is None else float(r["csg_expenditure"])})

    # Collapse cells before writing.
    collapsed={}
    for r in cell_rows:
        k=(r['lag'],r['current_year'],r['enrolment_year'],r['measure'],r['cutoff'],r['enrolment'])
        d=collapsed.setdefault(k,{"n":0,"sum_r":0.0,"n_e":0,"sum_e":0.0})
        d['n']+=1; d['sum_r']+=r['receipt']
        if r['expenditure'] is not None:
            d['n_e']+=1; d['sum_e']+=r['expenditure']
    collapsed_rows=[]
    for k,d in collapsed.items():
        collapsed_rows.append({"lag":k[0],"current_year":k[1],"enrolment_year":k[2],"measure":k[3],"cutoff":k[4],"enrolment":k[5],"n":d['n'],"mean_receipt":d['sum_r']/d['n'],"mean_expenditure":d['sum_e']/d['n_e'] if d['n_e'] else None})

    write_csv(out/'grant_distributions.csv', distributions)
    write_csv(out/'management_grant_reporting.csv', management)
    write_csv(out/'schedule_lag_match.csv', match_rows)
    write_csv(out/'local_enrolment_cells.csv', collapsed_rows)

    # Human-readable ranking of lag/measure/schedule by positive exact match.
    ranked=sorted([r for r in match_rows if r['positive_exact_match_rate'] is not None], key=lambda r:r['positive_exact_match_rate'], reverse=True)
    report={"top_schedule_lag_matches":ranked[:40]}
    (out/'assignment_diagnostics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print("TOP SCHEDULE/LAG MATCHES")
    for r in ranked[:40]: print(json.dumps(r), flush=True)
    print("\nTOP GRANT VALUES BY YEAR")
    for y in YEARS:
        print(y, [(r['csg_receipt'],r['n']) for r in distributions if r['year']==y][:12], flush=True)
    print("\nMANAGEMENT REPORTING")
    for y in YEARS:
        print(y, [r for r in management if r['year']==y][:15], flush=True)
    con.close()

if __name__=='__main__':
    main()
