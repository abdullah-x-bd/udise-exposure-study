from __future__ import annotations

import json, os, runpy, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from rdrobust import rdrobust

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def arr(x):
    try:return np.asarray(x,dtype=float).tolist()
    except Exception:return str(x)

def result_dict(r):
    return {'coef':arr(r.coef),'se':arr(r.se),'pv':arr(r.pv),'ci':arr(r.ci),'bws':arr(r.bws),'N_h':arr(r.N_h),'N':arr(r.N),'masspoints':str(getattr(r,'masspoints',None)),'vce':str(getattr(r,'vce',None))}

def fit(y,x,state,covs,h=None):
    kw=dict(y=y,x=x,c=250,p=1,q=2,kernel='tri',covs=covs,cluster=state,vce='cr3',masspoints='adjust',bwcheck=15)
    if h is not None:kw.update(h=h,b=max(45,h*1.5))
    return result_dict(rdrobust(**kw))

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=[z for z in os.environ['FUTURE_YEARS'].split(',') if z];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True);res=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));pr=src(extract(repo,tok,ay,'profile_1',root));ec,pc=cols(con,en),cols(con,pr);ei,pi=ident(ec),ident(pc)
        terms=[f"COALESCE({nref(ec,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in ec]
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({' + '.join(terms)}) enrol FROM {en} WHERE {efilt(con,en,ec)} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT ee.pseudocode,ee.enrol,CAST({ref(pc,'state','p')} AS VARCHAR) state_key FROM ee JOIN {pr} p ON ee.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND ee.enrol BETWEEN 100 AND 400")
        joins=[];rs=[];xs=[]
        for j,fy in enumerate(fys):
            p2=src(extract(repo,tok,fy,'profile_2',root));c=cols(con,p2);i=ident(c);con.execute(f"CREATE TEMP TABLE g{j} AS SELECT CAST({qid(i)} AS VARCHAR) pseudocode,{nref(c,'grants_receipt')} r{j},{nref(c,'grants_expenditure')} x{j} FROM {p2}");joins.append(f'LEFT JOIN g{j} USING(pseudocode)');rs.append(f'r{j}');xs.append(f'x{j}')
        con.execute(f"CREATE TEMP TABLE s AS SELECT base.*, {','.join(rs+xs)} FROM base {' '.join(joins)}")
        df=con.execute('SELECT * FROM s').df()
        state_codes=pd.Categorical(df.state_key).codes.astype(int);covs=pd.get_dummies(df.state_key,drop_first=True,dtype=float).to_numpy()
        x=df.enrol.to_numpy(float)
        outcomes={}
        y=df.r0.to_numpy(float); cap=np.nanquantile(y,.99);outcomes['receipt_winsor99']=np.minimum(y,cap);outcomes['receipt_ge75000']=(y>=75000).astype(float)
        y=df.x0.to_numpy(float); cap=np.nanquantile(y,.99);outcomes['expenditure_winsor99']=np.minimum(y,cap);outcomes['expenditure_ge75000']=(y>=75000).astype(float)
        complete=np.ones(len(df),dtype=bool)
        for v in xs:complete &= df[v].notna().to_numpy()
        cy=np.zeros(len(df),float)
        for v in xs:cy += df[v].fillna(0).to_numpy(float)
        cap=np.quantile(cy[complete],.99);outcomes['cumulative_expenditure_winsor99']=np.minimum(cy,cap)
        for name,y in outcomes.items():
            m=np.isfinite(y)&np.isfinite(x)
            if name.startswith('cumulative_'):m &= complete
            # donut out exact 250 and 251 to mirror primary analysis conservatively
            m &= ~np.isin(x,[250,251])
            xx=x[m];yy=y[m];ss=state_codes[m];zz=covs[m,:]
            for spec,h in [('mse',None),('fixed30',30),('fixed20',20),('fixed40',40)]:
                try:r=fit(yy,xx,ss,zz,h);res.append({'assignment_year':ay,'outcome':name,'spec':spec,**r});print(name,spec,json.dumps(r),flush=True)
                except Exception as e:res.append({'assignment_year':ay,'outcome':name,'spec':spec,'error':repr(e)});print('ERROR',name,spec,repr(e),flush=True)
    (out/'rdrobust_audit.json').write_text(json.dumps(res,indent=2),encoding='utf-8');con.close()
if __name__=='__main__':main()
