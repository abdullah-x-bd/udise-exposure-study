from __future__ import annotations
import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='state_lag_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];C=250.5;GOV='(1,2,3)'

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode');
 if not x:raise RuntimeError('id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def statex(c,a):
 for k in ('state','state_id','state_code','state_cd'):
  r=ref(c,k,a)
  if r:return f"CAST({r} AS VARCHAR)"
 raise RuntimeError('state missing')

def fit(y,x,bw=30):
 m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-C)<=bw);y=y[m];x=x[m]
 if len(y)<80 or (x<C).sum()<25 or (x>=C).sum()<25:return None
 z=x-C;t=(x>=C).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z];A=X.T@(w[:,None]*X)
 try:B=np.linalg.inv(A)
 except np.linalg.LinAlgError:B=np.linalg.pinv(A)
 b=B@(X.T@(w*y));e=y-X@b;M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4);se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se else None;return {'tau':tau,'se':se,'p':p,'n':len(y),'n_left':int((x<C).sum()),'n_right':int((x>=C).sum())}

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/state_lag/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();rows=[]
 with tempfile.TemporaryDirectory(prefix='statelag_') as td:
  root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));ec,pc=cols(con,en),cols(con,p1);ei,pi=ident(ec),ident(pc);f=efilt(con,en,ec);es=esum(ec);st=statex(pc,'p')
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  con.execute(f"CREATE TEMP TABLE base AS SELECT e.pseudocode,e.enrol,{st} state FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 180 AND 321")
  for oi in range(max(0,ai-2),min(len(YEARS),ai+5)):
   oy=YEARS[oi];lag=oi-ai;p2=src(extract(repo,tok,oy,'profile_2',root));gc=cols(con,p2);gi=ident(gc);con.execute(f"CREATE OR REPLACE TEMP TABLE fin AS SELECT CAST({qid(gi)} AS VARCHAR) pseudocode,{nref(gc,'grants_receipt')} receipt FROM {p2}")
   d=con.execute('SELECT b.state,b.enrol,f.receipt FROM base b LEFT JOIN fin f USING(pseudocode)').df()
   for state,z in d.groupby('state'):
    r=z.receipt.to_numpy(float);y=np.where(np.isfinite(r),(r>=75000).astype(float),np.nan);a=fit(y,z.enrol.to_numpy(float));
    if a:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'state':state,**a})
 write(out/'state_lag.csv',rows);df=pd.DataFrame(rows);summ=[]
 if len(df):
  for state,g in df.groupby('state'):
   gp=g[g.lag>=0]
   if len(gp):
    best=gp.loc[gp.tau.idxmax()];summ.append({'assignment_year':ay,'state':state,'best_positive_lag':int(best.lag),'best_tau':float(best.tau),'best_p':float(best.p),'lags_available':','.join(map(str,sorted(gp.lag.unique())))})
 write(out/'best_lag_by_state.csv',summ);counts=pd.DataFrame(summ).best_positive_lag.value_counts().sort_index().to_dict() if summ else {}; (out/'RESULTS.md').write_text('# State lag '+ay+'\n\nBest-lag counts: '+json.dumps(counts,indent=2),encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True);con.close()
if __name__=='__main__':main()
