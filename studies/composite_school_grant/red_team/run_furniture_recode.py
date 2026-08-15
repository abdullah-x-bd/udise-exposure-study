from __future__ import annotations

import csv,json,os,runpy,tempfile
from pathlib import Path
import duckdb

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
F=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='f')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];rd=F['rd']

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def filt(con,s,c):
    if 'item_group' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=os.environ['FUTURE_YEARS'].split(',');repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True);rows=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4')
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);e=src(extract(repo,tok,ay,'enrolment_1',root));p=src(extract(repo,tok,ay,'profile_1',root));fa=src(extract(repo,tok,ay,'facility',root));ec,pc,fc=cols(con,e),cols(con,p),cols(con,fa);ei,pi,fi=ident(ec),ident(pc),ident(fc)
        terms=[f"COALESCE({nref(ec,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in ec]
        con.execute(f"CREATE TEMP TABLE en AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({' + '.join(terms)}) enrol FROM {e} WHERE {filt(con,e,ec)} GROUP BY 1")
        if 'furniture_availability' not in fc:raise RuntimeError('baseline furniture missing')
        bfur=f"CASE WHEN {nref(fc,'furniture_availability','f')}=1 THEN 1.0 WHEN {nref(fc,'furniture_availability','f')} IN(2,3) THEN 0.0 END"
        con.execute(f"CREATE TEMP TABLE base AS SELECT en.pseudocode,en.enrol,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state,{bfur} bfull FROM en JOIN {p} p ON en.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {fa} f ON en.pseudocode=CAST(f.{qid(fi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND en.enrol BETWEEN 220 AND 280")
        for j,fy in enumerate(fys):
            ff=src(extract(repo,tok,fy,'facility',root));cc=cols(con,ff);ii=ident(cc)
            if 'furniture_availability' not in cc:continue
            cfur=f"CASE WHEN {nref(cc,'furniture_availability')}=1 THEN 1.0 WHEN {nref(cc,'furniture_availability')} IN(2,3) THEN 0.0 END"
            con.execute(f"CREATE TEMP TABLE o{j} AS SELECT CAST({qid(ii)} AS VARCHAR) pseudocode,{cfur} cfull FROM {ff}")
            specs=[('full_coverage_change','cfull-bfull','bfull IS NOT NULL AND cfull IS NOT NULL'),('deterioration','1.0-cfull','bfull=1 AND cfull IS NOT NULL'),('upgrade','cfull','bfull=0 AND cfull IS NOT NULL')]
            for name,y,w in specs:
                arr=con.execute(f"SELECT {y} y,enrol,state FROM base JOIN o{j} USING(pseudocode) WHERE {w}").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],250,30,1)
                if est:rows.append({'assignment_year':ay,'outcome_year':fy,'outcome':name,**est})
    with (out/'furniture_recode.csv').open('w',newline='') as f:
        if rows:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'furniture_recode.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows,indent=2));con.close()
if __name__=='__main__':main()
