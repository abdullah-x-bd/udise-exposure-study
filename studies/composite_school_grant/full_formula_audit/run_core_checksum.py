from __future__ import annotations
import csv, os, runpy, tempfile
from pathlib import Path
import duckdb, numpy as np, pandas as pd
from rdrobust import rdrobust

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='formula_checksum_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
BROAD=(1,2,3,6,89,90)
SCHEDULE=[(30,10000,25000,10),(100,25000,50000,20),(250,50000,75000,30),(1000,75000,100000,100)]

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode')
 if not x: raise RuntimeError('id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def pull(r,a):
 x=np.asarray(getattr(r,a),float)
 if a=='ci':return x.reshape(-1,2)[-1]
 return float(x.reshape(-1)[-1])

def fit(y,x,state,c,bw):
 y=np.asarray(y,float);x=np.asarray(x,float);state=pd.Series(state,dtype='object')
 m=np.isfinite(y)&np.isfinite(x)&state.notna().to_numpy()&(np.abs(x-c)<=bw);y=y[m];x=x[m];state=state.to_numpy()[m]
 if len(y)<250 or (x<c).sum()<70 or (x>=c).sum()<70 or pd.Series(state).nunique()<8:return None
 r=rdrobust(y=y,x=x,c=c,p=1,q=2,kernel='tri',h=bw,b=max(bw*1.5,bw+5),cluster=pd.Categorical(state).codes,vce='nn',masspoints='adjust',bwcheck=max(5,min(20,int(round(bw/2)))))
 ci=pull(r,'ci');return dict(tau=pull(r,'coef'),se=pull(r,'se'),p=pull(r,'pv'),ci_low=float(ci[0]),ci_high=float(ci[1]),n=len(y),clusters=pd.Series(state).nunique())

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);report=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/formula_checksum/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');rows=[]
 with tempfile.TemporaryDirectory(prefix='formula_checksum_') as td:
  root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));p2=src(extract(repo,tok,report,'profile_2',root));ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);f=efilt(con,en,ec);es=esum(ec);state=ref(pc,'state','p') or 'NULL';mg=nref(pc,'managment','p')
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  d=con.execute(f"SELECT e.enrol,CAST({state} AS VARCHAR) state,{nref(gc,'grants_receipt','g')} receipt,{nref(gc,'grants_expenditure','g')} expenditure FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {p2} g ON e.pseudocode=CAST(g.{qid(gi)} AS VARCHAR) WHERE {mg} IN ({','.join(map(str,BROAD))})").df()
  x=d.enrol.to_numpy(float);r=d.receipt.to_numpy(float);q=d.expenditure.to_numpy(float);st=d.state
  for end,lower,upper,bw in SCHEDULE:
   vr=np.isfinite(r);vq=np.isfinite(q);outs={'receipt_atleast_upper':np.where(vr,(r>=upper).astype(float),np.nan),'receipt_exact_upper':np.where(vr,np.isclose(r,upper).astype(float),np.nan),'receipt_exact_lower':np.where(vr,np.isclose(r,lower).astype(float),np.nan),'expenditure_atleast_upper':np.where(vq,(q>=upper).astype(float),np.nan)}
   if vr.sum()>100:outs['receipt_w99']=np.where(vr,np.minimum(r,np.nanquantile(r,.99)),np.nan)
   if vq.sum()>100:outs['expenditure_w99']=np.where(vq,np.minimum(q,np.nanquantile(q,.99)),np.nan)
   for name,y in outs.items():
    try:a=fit(y,x,st,end+.5,bw)
    except Exception as e:a={'error':repr(e)}
    if a:rows.append({'assignment_year':ay,'report_year':report,'threshold_end':end,'lower_target':lower,'upper_target':upper,'nominal_jump':upper-lower,'outcome':name,'bw':bw,**a})
 with (out/'checksum.csv').open('w',newline='',encoding='utf-8') as f:
  keys=[]
  for r0 in rows:
   for k in r0:
    if k not in keys:keys.append(k)
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
 print(pd.DataFrame(rows).to_string(index=False),flush=True)
if __name__=='__main__':main()
