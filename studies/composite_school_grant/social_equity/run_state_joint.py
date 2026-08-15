from __future__ import annotations

import csv, json, os, runpy, shutil, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_state_joint_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
SOCIAL=['sc','st','obc']
RELIG=['muslim','christian','sikh','buddhist','parsi','jain']
CUT=250.5;BW=30

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def fit_state(df,groups,state):
    cols=[f'prev_{g}_share' for g in groups]
    d=df.copy();keep=np.isfinite(d.receipt)&np.isfinite(d.enrol)
    for c in cols:keep &= np.isfinite(d[c])
    d=d[keep & (np.abs(d.enrol-CUT)<=BW)].copy()
    if len(d)<500 or d.district.astype(str).nunique()<8 or (d.enrol<CUT).sum()<150 or (d.enrol>=CUT).sum()<150:return [],None
    d['T']=(d.enrol>=CUT).astype(float);d['z']=d.enrol-CUT;d['Tz']=d['T']*d['z'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/BW)
    base=['y','T','z','Tz'];xcols=['T','z','Tz'];inter=[]
    for g,c in zip(groups,cols):
        s='S_'+g;ts='TS_'+g;zs='zS_'+g;tzs='TzS_'+g
        d[s]=d[c].astype(float);d[ts]=d['T']*d[s];d[zs]=d['z']*d[s];d[tzs]=d['T']*d['z']*d[s]
        base += [s,ts,zs,tzs];xcols += [s,ts,zs,tzs];inter.append(ts)
    for b in ('management','rural_urban','school_category'):
        v=pd.to_numeric(d[b],errors='coerce').fillna(-999).astype(int);cats=sorted(v.unique())
        for c in cats[1:]:
            n=f'cv_{b}_{c}';d[n]=(v==c).astype(float);base.append(n);xcols.append(n)
    d['fe']=d.district.astype(str)
    d=weighted_demean(d,base,'fe','w')
    fit=cluster_fit(d[xcols].to_numpy(float),d.y.to_numpy(float),d.w.to_numpy(float),d.district.astype(str).to_numpy())
    if fit is None:return [],None
    out=[]
    for g,ts in zip(groups,inter):
        j=xcols.index(ts);b=float(fit.params[j]);se=float(fit.bse[j]);p=float(fit.pvalues[j])
        out.append({'state':state,'group':g,'coef_per_10pp':b*.1,'se_per_10pp':se*.1,'p':p,'ci_low_per_10pp':(b-1.96*se)*.1,'ci_high_per_10pp':(b+1.96*se)*.1,'n':int(fit.nobs),'districts':int(d.district.astype(str).nunique())})
    return out,{'state':state,'n':int(fit.nobs),'districts':int(d.district.astype(str).nunique())}

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_state_joint/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'statejoint_{ay}_') as td:
        root=Path(td);cp,dc=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,dp=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True)
        prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'local.parquet'
        con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,f.expenditure,{prevcols} FROM read_parquet({lit(str(cp))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 220 AND 281) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();d=d[government_universe(d.management,BROAD_STATE)].copy();rows=[];support=[]
    for state,sd in d.groupby('state'):
        for family,groups in [('social_category',SOCIAL),('religion',RELIG)]:
            rr,s=fit_state(sd,groups,str(state))
            for r in rr:rows.append({'assignment_year':ay,'report_year':ry,'family':family,**r})
            if s:support.append({'assignment_year':ay,'report_year':ry,'family':family,**s})
    write_csv(out/'state_joint_coefficients.csv',rows);write_csv(out/'state_joint_support.csv',support);(out/'validation.json').write_text(json.dumps({'assignment':dc,'previous':dp},indent=2,default=float),encoding='utf-8')
    print(json.dumps({'assignment_year':ay,'report_year':ry,'coefficient_rows':len(rows),'states':len(set(r['state'] for r in rows))},indent=2),flush=True);con.close()
if __name__=='__main__':main()
