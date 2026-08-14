from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

YEARS=[f"{y}-{str(y+1)[-2:]}" for y in range(2018,2026)]


def write_csv(path:Path,rows:list[dict])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: path.write_text('',encoding='utf-8'); return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def expected_sql(measure:str,schedule:str)->str:
    if schedule=='current':
        return f"CASE WHEN {measure} BETWEEN 1 AND 30 THEN 10000 WHEN {measure}<=100 THEN 25000 WHEN {measure}<=250 THEN 50000 WHEN {measure}<=1000 THEN 75000 WHEN {measure}>1000 THEN 100000 END"
    if schedule=='legacy':
        return f"CASE WHEN {measure} BETWEEN 1 AND 100 THEN 25000 WHEN {measure}<=250 THEN 50000 WHEN {measure}<=1000 THEN 75000 WHEN {measure}>1000 THEN 100000 END"
    raise ValueError(schedule)


def main()->None:
    panel=Path('studies/composite_school_grant/outputs/panel/school_year_panel.parquet')
    out=Path('studies/composite_school_grant/outputs/assignment_diagnostics');out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4')
    case=' '.join(f"WHEN '{y}' THEN {i}" for i,y in enumerate(YEARS))
    con.execute(f"""
      CREATE OR REPLACE TEMP VIEW p AS
      SELECT *,CASE academic_year {case} END yi
      FROM read_parquet('{panel.as_posix()}')
    """)

    distributions=[];management=[]
    for y in YEARS:
        for val,n in con.execute(f"SELECT csg_receipt,COUNT(*) FROM p WHERE academic_year='{y}' AND management IN (1,2,3) GROUP BY 1 ORDER BY 2 DESC LIMIT 30").fetchall():
            distributions.append({'year':y,'csg_receipt':val,'n':int(n)})
        for m,n,nn,np,avg in con.execute(f"""
          SELECT management,COUNT(*),COUNT(csg_receipt),SUM(CASE WHEN csg_receipt>0 THEN 1 ELSE 0 END),AVG(csg_receipt) FILTER(WHERE csg_receipt IS NOT NULL)
          FROM p WHERE academic_year='{y}' GROUP BY 1 ORDER BY 2 DESC
        """).fetchall():
            management.append({'year':y,'management':m,'n':int(n),'n_nonnull':int(nn),'n_positive':int(np or 0),'nonnull_rate':float(nn/n) if n else None,'positive_rate':float((np or 0)/n) if n else None,'mean_receipt':avg})

    match_rows=[];cells=[]
    for lag in range(4):
        con.execute(f"""
          CREATE OR REPLACE TEMP VIEW pair AS
          SELECT c.academic_year current_year,l.academic_year enrolment_year,c.pseudocode,c.state,c.management,
                 c.csg_receipt,c.csg_expenditure,l.enrol_c1_12,l.enrol_incl_preprimary
          FROM p c JOIN p l ON c.pseudocode=l.pseudocode AND c.yi=l.yi+{lag}
          WHERE c.management IN (1,2,3) AND c.csg_receipt IS NOT NULL
        """)
        for measure in ('enrol_c1_12','enrol_incl_preprimary'):
            for schedule in ('current','legacy'):
                exp=expected_sql(measure,schedule)
                rows=con.execute(f"""
                  SELECT current_year,COUNT(*) n,
                         AVG(CASE WHEN ABS(csg_receipt-({exp}))<0.5 THEN 1.0 ELSE 0.0 END) exact_match_rate,
                         AVG(ABS(csg_receipt-({exp}))) mae,
                         COUNT(*) FILTER(WHERE csg_receipt>0) positive_n,
                         AVG(CASE WHEN csg_receipt>0 THEN CASE WHEN ABS(csg_receipt-({exp}))<0.5 THEN 1.0 ELSE 0.0 END END) positive_exact
                  FROM pair WHERE {measure}>0 GROUP BY 1 ORDER BY 1
                """).fetchall()
                for cy,n,em,mae,pn,pe in rows:
                    match_rows.append({'lag':lag,'current_year':cy,'enrolment_measure':measure,'schedule':schedule,'n':int(n),'exact_match_rate':em,'mean_absolute_error':mae,'positive_n':int(pn),'positive_exact_match_rate':pe})
        if lag>0:
            for measure in ('enrol_c1_12','enrol_incl_preprimary'):
                for cutoff,bw in ((30,20),(100,40),(250,75),(1000,150)):
                    rows=con.execute(f"""
                      SELECT current_year,enrolment_year,CAST(ROUND({measure}) AS INTEGER) enrolment,COUNT(*) n,AVG(csg_receipt),AVG(csg_expenditure)
                      FROM pair WHERE {measure} BETWEEN {cutoff-bw} AND {cutoff+bw}
                      GROUP BY 1,2,3 ORDER BY 1,3
                    """).fetchall()
                    for cy,ey,e,n,mr,me in rows:
                        cells.append({'lag':lag,'current_year':cy,'enrolment_year':ey,'measure':measure,'cutoff':cutoff,'enrolment':e,'n':int(n),'mean_receipt':mr,'mean_expenditure':me})

    write_csv(out/'grant_distributions.csv',distributions);write_csv(out/'management_grant_reporting.csv',management);write_csv(out/'schedule_lag_match.csv',match_rows);write_csv(out/'local_enrolment_cells.csv',cells)
    ranked=sorted([r for r in match_rows if r['positive_exact_match_rate'] is not None],key=lambda r:r['positive_exact_match_rate'],reverse=True)
    (out/'assignment_diagnostics.json').write_text(json.dumps({'top_schedule_lag_matches':ranked[:60]},indent=2),encoding='utf-8')
    print('TOP SCHEDULE/LAG MATCHES')
    for r in ranked[:60]: print(json.dumps(r),flush=True)
    print('\nTOP GOVERNMENT-SCHOOL GRANT VALUES')
    for y in YEARS: print(y,[(r['csg_receipt'],r['n']) for r in distributions if r['year']==y][:15],flush=True)
    print('\nMANAGEMENT REPORTING')
    for y in YEARS: print(y,[r for r in management if r['year']==y][:15],flush=True)
    con.close()

if __name__=='__main__': main()
