from __future__ import annotations
import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='multi_thr_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];GOV='(1,2,3)'
SCHEDULE=[(30,25000,10),(100,50000,20),(250,75000,30),(1000,100000,100)]

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode');
 if not x:raise RuntimeError('id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def rd(y,x,c,bw):
 m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-c)<=bw);y=y[m];x=x[m]
 if len(y)<200 or (x<c).sum()<50 or (x>=c).sum()<50:return None
 z=x-c;t=(x>=c).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z];A=X.T@(w[:,None]*X)
 try:B=np.linalg.inv(A)
 except np.linalg.LinAlgError:B=np.linalg.pinv(A)
 b=B@(X.T@(w*y));e=y-X@b;M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4);se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se else None;return {'tau':tau,'se':se,'p':p,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'n':len(y)}

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);report=YEARS[ai+3];grant=YEARS[ai+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/multi_threshold/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();rows=[]
 with tempfile.TemporaryDirectory(prefix='multithr_') as td:
  root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));p2=src(extract(repo,tok,report,'profile_2',root));ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);f=efilt(con,en,ec);es=esum(ec)
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  d=con.execute(f"SELECT e.enrol,{nref(gc,'grants_receipt','g')} receipt,{nref(gc,'grants_expenditure','g')} expenditure FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {p2} g ON e.pseudocode=CAST(g.{qid(gi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV}").df();xall=d.enrol.to_numpy(float);rall=d.receipt.to_numpy(float);eall=d.expenditure.to_numpy(float)
  for end,target,bw in SCHEDULE:
   c=end+.5;vr=np.isfinite(rall);ve=np.isfinite(eall);outs={'receipt_atleast_target':np.where(vr,(rall>=target).astype(float),np.nan),'receipt_exact_target':np.where(vr,np.isclose(rall,target).astype(float),np.nan),'expenditure_atleast_target':np.where(ve,(eall>=target).astype(float),np.nan),'expenditure_exact_target':np.where(ve,np.isclose(eall,target).astype(float),np.nan)}
   for name,y in outs.items():
    a=rd(y,xall,c,bw)
    if a:rows.append({'assignment_year':ay,'grant_financial_year':grant,'udise_report_year':report,'threshold_end':end,'threshold_start':end+1,'target_grant':target,'outcome':name,'bw':bw,**a})
 write(out/'multi_threshold.csv',rows);(out/'RESULTS.md').write_text('# Multi-threshold formula test '+ay+'\n\n'+json.dumps(rows,indent=2),encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True);con.close()
if __name__=='__main__':main()
