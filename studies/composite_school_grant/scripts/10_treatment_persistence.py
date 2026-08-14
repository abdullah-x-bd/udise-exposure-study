from __future__ import annotations

import csv, json, os, runpy, tempfile
from pathlib import Path
import duckdb
import numpy as np

PANEL=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='panel_lib')
FOCUS=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='focus_lib')
extract_archive=PANEL['extract_archive'];csv_source=PANEL['csv_source'];source_columns=PANEL['source_columns'];identify_early_social_labels=PANEL['identify_early_social_labels'];qid=PANEL['qid'];lit=PANEL['lit'];ref=PANEL['ref'];nref=PANEL['nref'];rd=FOCUS['rd']
CUTOFF=250;BW=30;DONUT=1

def total_enrol(con,src,c):
    terms=[f"COALESCE({nref(c,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in c]
    if 'item_group' in c and 'item_id' in c:f=f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN (1,2,3,4)"
    else:
        labs=identify_early_social_labels(con,src,c);d=ref(c,'item_desc');f=f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})"
    return ' + '.join(terms),f

def write_csv(path:Path,rows:list[dict]):
    if not rows:path.write_text('',encoding='utf-8');return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys:keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main():
    ay=os.environ['ASSIGN_YEAR'];future=os.environ['FUTURE_YEARS'].split(',');repo=os.environ['HF_DATASET_REPO'];token=os.environ['HF_TOKEN']
    out=Path(f"studies/composite_school_grant/outputs/treatment_persistence/{ay}");out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix='csg_persist_') as td:
        root=Path(td)
        ae=csv_source(extract_archive(repo,token,ay,'enrolment_1',root));ap1=csv_source(extract_archive(repo,token,ay,'profile_1',root));ec=source_columns(con,ae);ac=source_columns(con,ap1);eid=ec.get('pseudocode') or ec.get('psuedocode');aid=ac.get('pseudocode') or ac.get('psuedocode');total,filt=total_enrol(con,ae,ec)
        con.execute(f"CREATE TEMP TABLE assign AS SELECT CAST({qid(eid)} AS VARCHAR) pseudocode,SUM({total}) enrol0 FROM {ae} WHERE {filt} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE aprof AS SELECT CAST({qid(aid)} AS VARCHAR) pseudocode,CAST({ref(ac,'state')} AS VARCHAR) state_key,{nref(ac,'managment')} mgmt FROM {ap1}")
        con.execute(f"CREATE TEMP TABLE base AS SELECT a.pseudocode,a.enrol0,DENSE_RANK() OVER(ORDER BY p.state_key) state FROM assign a JOIN aprof p USING(pseudocode) WHERE p.mgmt IN(1,2,3) AND a.enrol0 BETWEEN {CUTOFF-BW} AND {CUTOFF+BW}")
        selects=['b.pseudocode','b.enrol0','b.state'];joins=[]
        for i,y in enumerate(future):
            e=csv_source(extract_archive(repo,token,y,'enrolment_1',root));p1=csv_source(extract_archive(repo,token,y,'profile_1',root));p2=csv_source(extract_archive(repo,token,y,'profile_2',root));ecy=source_columns(con,e);p1c=source_columns(con,p1);p2c=source_columns(con,p2);ei=ecy.get('pseudocode') or ecy.get('psuedocode');p1i=p1c.get('pseudocode') or p1c.get('psuedocode');p2i=p2c.get('pseudocode') or p2c.get('psuedocode');ts,ff=total_enrol(con,e,ecy)
            con.execute(f"CREATE TEMP TABLE e{i} AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({ts}) enrol_{i} FROM {e} WHERE {ff} GROUP BY 1")
            con.execute(f"CREATE TEMP TABLE g{i} AS SELECT CAST(p.{qid(p1i)} AS VARCHAR) pseudocode,{nref(p1c,'managment','p')} mgmt_{i},{nref(p2c,'grants_receipt','g')} receipt_{i},{nref(p2c,'grants_expenditure','g')} expend_{i} FROM {p1} p JOIN {p2} g ON CAST(p.{qid(p1i)} AS VARCHAR)=CAST(g.{qid(p2i)} AS VARCHAR)")
            joins += [f'LEFT JOIN e{i} USING(pseudocode)',f'LEFT JOIN g{i} USING(pseudocode)']
            selects += [f'e{i}.enrol_{i}',f'g{i}.receipt_{i}',f'g{i}.expend_{i}',f'g{i}.mgmt_{i}']
        con.execute(f"CREATE TEMP TABLE panel AS SELECT {','.join(selects)} FROM base b {' '.join(joins)}")
        # require government status in all observed future rounds for a stable institutional sample
        cond=' AND '.join(f'(mgmt_{i} IN (1,2,3) OR mgmt_{i} IS NULL)' for i in range(len(future)))
        con.execute(f"CREATE TEMP TABLE s AS SELECT * FROM panel WHERE {cond}")
        results=[]
        for i,y in enumerate(future):
            for var,label in [(f'enrol_{i}',f'enrolment_{y}'),(f'receipt_{i}',f'receipt_{y}'),(f'expend_{i}',f'expenditure_{y}')]:
                arr=con.execute(f'SELECT {var} y,enrol0 enrol,state FROM s WHERE {var} IS NOT NULL').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                if est:results.append({'outcome':label,'round':y,**est})
            arr=con.execute(f'SELECT CASE WHEN enrol_{i}>250 THEN 1.0 ELSE 0.0 END y,enrol0 enrol,state FROM s WHERE enrol_{i} IS NOT NULL').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
            if est:results.append({'outcome':f'above250_{y}','round':y,**est})
        # cumulative financial reporting across all available rounds, complete cases and zero-safe positive/zero values
        for typ in ('receipt','expend'):
            vars=[f'{typ}_{i}' for i in range(len(future))]
            sumexpr=' + '.join(f'COALESCE({v},0)' for v in vars)
            complete=' AND '.join(f'{v} IS NOT NULL' for v in vars)
            arr=con.execute(f'SELECT ({sumexpr}) y,enrol0 enrol,state FROM s WHERE {complete}').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
            if est:results.append({'outcome':f'cumulative_{typ}_{future[0]}_to_{future[-1]}','round':f'{future[0]}..{future[-1]}',**est})
        write_csv(out/'persistence_rd.csv',results);(out/'summary.json').write_text(json.dumps({'assignment_year':ay,'future_years':future,'results':results},indent=2),encoding='utf-8')
        print('PERSISTENCE RESULTS')
        for r in results:print(json.dumps(r),flush=True)
    con.close()
if __name__=='__main__':main()
