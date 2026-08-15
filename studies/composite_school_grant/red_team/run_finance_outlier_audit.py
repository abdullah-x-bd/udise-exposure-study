from __future__ import annotations

import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb
import numpy as np

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
F=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='f')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];rd=F['rd']

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def est(y,e,s):
    return rd(np.asarray(y,float),np.asarray(e,float),np.asarray(s,float),250,30,1)

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=[x for x in os.environ['FUTURE_YEARS'].split(',') if x];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True);rows=[];dist=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));pr=src(extract(repo,tok,ay,'profile_1',root));ec,pc=cols(con,en),cols(con,pr);ei,pi=ident(ec),ident(pc)
        terms=[f"COALESCE({nref(ec,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in ec]
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({' + '.join(terms)}) enrol FROM {en} WHERE {efilt(con,en,ec)} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT ee.pseudocode,ee.enrol,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state FROM ee JOIN {pr} p ON ee.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND ee.enrol BETWEEN 175 AND 325")
        joins=[];rec=[];exps=[]
        for j,fy in enumerate(fys):
            p2=src(extract(repo,tok,fy,'profile_2',root));c=cols(con,p2);i=ident(c)
            con.execute(f"CREATE TEMP TABLE g{j} AS SELECT CAST({qid(i)} AS VARCHAR) pseudocode,{nref(c,'grants_receipt')} r{j},{nref(c,'grants_expenditure')} x{j} FROM {p2}")
            joins.append(f'LEFT JOIN g{j} USING(pseudocode)');rec.append(f'r{j}');exps.append(f'x{j}')
        con.execute(f"CREATE TEMP TABLE s AS SELECT base.*, {','.join(rec+exps)} FROM base {' '.join(joins)}")
        # First observable year first stage under robust transformations.
        for v,label in [('r0','receipt_first'),('x0','expenditure_first')]:
            a=con.execute(f'SELECT {v} y,enrol,state FROM s WHERE {v} IS NOT NULL AND enrol BETWEEN 175 AND 325').fetchnumpy();y=np.asarray(a['y'],float);e=np.asarray(a['enrol'],float);st=np.asarray(a['state'],float);finite=np.isfinite(y);y,e,st=y[finite],e[finite],st[finite]
            qs=np.quantile(y,[.5,.9,.95,.99,.995,.999,1]);dist.append({'outcome':label,**{f'q{q:g}':float(vv) for q,vv in zip([50,90,95,99,99.5,99.9,100],qs)}})
            transforms=[('raw',y),('asinh_per_1000',np.arcsinh(y/1000.0)),('indicator_positive',(y>0).astype(float)),('indicator_ge_75000',(y>=75000).astype(float)),('indicator_ge_50000',(y>=50000).astype(float))]
            for q in (.99,.995,.999):
                cap=float(np.quantile(y,q));transforms.append((f'winsor_{q}',np.minimum(y,cap)))
                m=y<=cap;rr=est(y[m],e[m],st[m]);
                if rr:rows.append({'period':'first','outcome':label,'transform':f'trim_{q}','cap':cap,**rr})
            for nm,yy in transforms:
                rr=est(yy,e,st)
                if rr:rows.append({'period':'first','outcome':label,'transform':nm,**rr})
        # Complete-case cumulative expenditure and receipt, plus robust transforms.
        for vars_,label in [(exps,'cumulative_expenditure'),(rec,'cumulative_receipt')]:
            condition=' AND '.join(f'{v} IS NOT NULL' for v in vars_);sumx=' + '.join(vars_);a=con.execute(f'SELECT ({sumx}) y,enrol,state FROM s WHERE {condition}').fetchnumpy();y=np.asarray(a['y'],float);e=np.asarray(a['enrol'],float);st=np.asarray(a['state'],float);finite=np.isfinite(y);y,e,st=y[finite],e[finite],st[finite]
            qs=np.quantile(y,[.5,.9,.95,.99,.995,.999,1]);dist.append({'outcome':label,**{f'q{q:g}':float(vv) for q,vv in zip([50,90,95,99,99.5,99.9,100],qs)}})
            trans=[('raw',y),('asinh_per_1000',np.arcsinh(y/1000.0))]
            for q in (.99,.995,.999):
                cap=float(np.quantile(y,q));trans.append((f'winsor_{q}',np.minimum(y,cap)));m=y<=cap;rr=est(y[m],e[m],st[m]);
                if rr:rows.append({'period':'cumulative','outcome':label,'transform':f'trim_{q}','cap':cap,**rr})
            for nm,yy in trans:
                rr=est(yy,e,st)
                if rr:rows.append({'period':'cumulative','outcome':label,'transform':nm,**rr})
    if rows:
        with (out/'finance_outlier_audit.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if dist:
        keys=[]
        for r in dist:
            for k in r:
                if k not in keys:keys.append(k)
        with (out/'finance_distribution.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(dist)
    summary={'assignment_year':ay,'future_years':fys,'distributions':dist,'estimates':rows};(out/'finance_outlier_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));con.close()
if __name__=='__main__':main()
