from __future__ import annotations

import csv, json, math, os, runpy, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from rdrobust import rdrobust

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='timing_matrix_lib')
YEARS=P['YEARS']; extract=P['extract_archive']; src=P['csv_source']; cols=P['source_columns']; labels=P['identify_early_social_labels']; qid=P['qid']; lit=P['lit']; ref=P['ref']; nref=P['nref']
C=250.5; GOV='(1,2,3)'; BW=30


def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x: raise RuntimeError('missing school identifier')
    return x


def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:
        return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c)
    if not ls: raise RuntimeError('could not identify social category rows')
    return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"


def esum(c,maxclass):
    q=[f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,maxclass+1) for s in ('b','g') if f'c{k}_{s}' in c]
    if not q: raise RuntimeError('no class enrolment columns')
    return ' + '.join(q)


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)


def fast(y,x,bw=30):
    m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-C)<=bw);y=y[m];x=x[m]
    if len(y)<300 or (x<C).sum()<80 or (x>=C).sum()<80:return None
    z=x-C;t=(x>=C).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z]
    A=X.T@(w[:,None]*X)
    try:B=np.linalg.inv(A)
    except np.linalg.LinAlgError:B=np.linalg.pinv(A)
    b=B@(X.T@(w*y));e=y-X@b;M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4);se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se>0 else None
    return {'tau':tau,'se':se,'p':p,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'n':len(y),'n_left':int((x<C).sum()),'n_right':int((x>=C).sum())}


def robust(y,x,state,bw=30):
    m=np.isfinite(y)&np.isfinite(x)&np.isfinite(state)&(np.abs(x-C)<=bw);y=y[m];x=x[m];state=state[m]
    if len(y)<500:return None
    try:
        r=rdrobust(y=y,x=x,c=C,p=1,q=2,kernel='tri',h=bw,b=45,cluster=pd.Categorical(state).codes,vce='cr3',masspoints='adjust',bwcheck=15)
        co=float(np.asarray(r.coef,dtype=float).reshape(-1)[-1]);se=float(np.asarray(r.se,dtype=float).reshape(-1)[-1]);pv=float(np.asarray(r.pv,dtype=float).reshape(-1)[-1]);ci=np.asarray(r.ci,dtype=float).reshape(-1,2)[-1]
        return {'tau':co,'se':se,'p':pv,'ci_low':float(ci[0]),'ci_high':float(ci[1]),'n':len(y)}
    except Exception as e:return {'error':repr(e),'n':len(y)}


def main():
    ay=os.environ['ASSIGN_YEAR']; ai=YEARS.index(ay);repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/timing_matrix/{ay}');out.mkdir(parents=True,exist_ok=True);rows=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'timing_{ay}_') as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));ec,pc=cols(con,en),cols(con,p1);ei,pi=ident(ec),ident(pc);f=efilt(con,en,ec);e12=esum(ec,12);e8=esum(ec,8)
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({e12}) enrol,SUM({e8}) enrol18 FROM {en} WHERE {f} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT e.pseudocode,e.enrol,e.enrol18,{nref(pc,'state','p')} state FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 180 AND 321")
        for oy in YEARS:
            lag=YEARS.index(oy)-ai
            if lag < -3 or lag > 4:continue
            p2=src(extract(repo,tok,oy,'profile_2',root));gc=cols(con,p2);gi=ident(gc)
            con.execute(f"CREATE OR REPLACE TEMP TABLE fin AS SELECT CAST({qid(gi)} AS VARCHAR) pseudocode,{nref(gc,'grants_receipt')} receipt,{nref(gc,'grants_expenditure')} expenditure FROM {p2}")
            d=con.execute('SELECT b.*,f.receipt,f.expenditure FROM base b LEFT JOIN fin f USING(pseudocode)').df()
            for sample,mask in [('all',np.ones(len(d),bool)),('pm220',d.enrol18.fillna(99999).to_numpy(float)<=220),('pm200',d.enrol18.fillna(99999).to_numpy(float)<=200)]:
                z=d.loc[mask];x=z.enrol.to_numpy(float);st=z.state.to_numpy(float);r=z.receipt.to_numpy(float);q=z.expenditure.to_numpy(float)
                vr=np.isfinite(r);vq=np.isfinite(q)
                outcomes={
                  'receipt_ge75000':np.where(vr,(r>=75000).astype(float),np.nan),
                  'receipt_gt50000':np.where(vr,(r>50000).astype(float),np.nan),
                  'receipt_positive':np.where(vr,(r>0).astype(float),np.nan),
                  'expenditure_ge75000':np.where(vq,(q>=75000).astype(float),np.nan),
                  'expenditure_gt50000':np.where(vq,(q>50000).astype(float),np.nan),
                  'expenditure_positive':np.where(vq,(q>0).astype(float),np.nan),
                }
                if vr.sum()>100:outcomes['receipt_winsor99']=np.where(vr,np.minimum(r,np.nanquantile(r,.99)),np.nan)
                if vq.sum()>100:outcomes['expenditure_winsor99']=np.where(vq,np.minimum(q,np.nanquantile(q,.99)),np.nan)
                for name,y in outcomes.items():
                    for bw in (20,30,40):
                        res=fast(y,x,bw)
                        if res:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'sample':sample,'outcome':name,'estimator':'local_linear_hc','bw':bw,**res})
                # expensive publication estimator only for primary categorical first stage, all sample
                if sample=='all':
                    res=robust(outcomes['receipt_ge75000'],x,st,30)
                    if res:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'sample':sample,'outcome':'receipt_ge75000','estimator':'rdrobust_cr3','bw':30,**res})
            print(json.dumps({'assignment':ay,'outcome':oy,'lag':lag,'n':len(d)}),flush=True)
    write_csv(out/'timing.csv',rows)
    rr=[r for r in rows if r['estimator']=='rdrobust_cr3' and 'tau' in r]
    md=['# Timing results for '+ay,'','Threshold coordinate 250.5. Primary outcome is P(reported CSG receipt >= Rs 75,000).','']
    for r in sorted(rr,key=lambda x:x['lag']):md.append(f"- {r['outcome_year']} lag {r['lag']:+d}: {100*r['tau']:.2f} pp (95% CI {100*r['ci_low']:.2f} to {100*r['ci_high']:.2f}), p={r['p']:.4g}")
    (out/'RESULTS.md').write_text('\n'.join(md),encoding='utf-8');print('\n'.join(md),flush=True);con.close()

if __name__=='__main__':main()
