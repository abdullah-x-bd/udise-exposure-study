from __future__ import annotations

import json, os, runpy, tempfile
from pathlib import Path
import duckdb

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
F=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='f')
C=runpy.run_path('studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py',run_name='c')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];rd=F['rd'];component_exprs=C['component_exprs'];ASSETS=C['ASSET_COMPONENTS']

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def rr(con,table,y,where='TRUE'):
    a=con.execute(f'SELECT {y} y,enrol,state FROM {table} WHERE ({where}) AND ({y}) IS NOT NULL').fetchnumpy();return rd(a['y'],a['enrol'],a['state'],250,30,1)

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=[x for x in os.environ['FUTURE_YEARS'].split(',') if x];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True);res=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4')
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));pr=src(extract(repo,tok,ay,'profile_1',root));fac=src(extract(repo,tok,ay,'facility',root));ec,pc,fc=cols(con,en),cols(con,pr),cols(con,fac);ei,pi,fi=ident(ec),ident(pc),ident(fc)
        terms=[f"COALESCE({nref(ec,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in ec]
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({' + '.join(terms)}) enrol FROM {en} WHERE {efilt(con,en,ec)} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT ee.pseudocode,ee.enrol,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state FROM ee JOIN {pr} p ON ee.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND ee.enrol BETWEEN 220 AND 280")
        bc=component_exprs(fc,'f');con.execute(f"CREATE TEMP TABLE bf AS SELECT CAST({qid(fi)} AS VARCHAR) pseudocode,{','.join(x+' b_'+n for n,x in bc.items())} FROM {fac} f")
        for j,fy in enumerate(fys):
            p=src(extract(repo,tok,fy,'profile_1',root));fa=src(extract(repo,tok,fy,'facility',root));pc2,fc2=cols(con,p),cols(con,fa);pi2,fi2=ident(pc2),ident(fc2)
            con.execute(f"CREATE TEMP TABLE pm{j} AS SELECT CAST({qid(pi2)} AS VARCHAR) pseudocode,{nref(pc2,'managment')} mgmt FROM {p}")
            oc=component_exprs(fc2,'f');con.execute(f"CREATE TEMP TABLE of{j} AS SELECT CAST({qid(fi2)} AS VARCHAR) pseudocode,{','.join(x+' c_'+n for n,x in oc.items())} FROM {fa} f")
            con.execute(f"CREATE TEMP TABLE s{j} AS SELECT b.*,m.mgmt,{','.join('x.b_'+a for a in ASSETS)},{','.join('o.c_'+a for a in ASSETS)} FROM base b LEFT JOIN pm{j} m USING(pseudocode) LEFT JOIN bf x USING(pseudocode) LEFT JOIN of{j} o USING(pseudocode)")
            res.append({'year':fy,'outcome':'remains_government','sample':'assignment_gov',**(rr(con,f's{j}',"CASE WHEN mgmt IN(1,2,3) THEN 1.0 WHEN mgmt IS NOT NULL THEN 0.0 END") or {})})
            res.append({'year':fy,'outcome':'management_observed','sample':'assignment_gov',**(rr(con,f's{j}',"CASE WHEN mgmt IS NOT NULL THEN 1.0 ELSE 0.0 END") or {})})
            den=[f"CASE WHEN b_{a}=1 AND c_{a} IS NOT NULL THEN 1 ELSE 0 END" for a in ASSETS];num=[f"CASE WHEN b_{a}=1 AND c_{a} IS NOT NULL THEN 1.0-c_{a} ELSE 0.0 END" for a in ASSETS];det=f"CASE WHEN ({' + '.join(den)})>=3 THEN ({' + '.join(num)})/NULLIF(({' + '.join(den)}),0) END"
            for sample,w in [('assignment_gov_only','TRUE'),('still_gov','mgmt IN(1,2,3)')]:
                e=rr(con,f's{j}',det,w);res.append({'year':fy,'outcome':'deterioration_composite','sample':sample,**(e or {})})
    (out/'management_selection.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(res,indent=2));con.close()
if __name__=='__main__':main()
