from __future__ import annotations
import csv,json,math,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_social_balance_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE']
CUT=250.5;BW=30

def write(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows:path.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def fit(y,x,cl):
 m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-CUT)<=BW)&pd.Series(cl,dtype='object').notna().to_numpy();y=y[m];x=x[m];cl=np.asarray(cl,dtype=object)[m]
 z=x-CUT;t=(x>=CUT).astype(float);w=np.maximum(0,1-np.abs(z)/BW);X=np.c_[np.ones(len(x)),t,z,t*z];A=X.T@(w[:,None]*X)
 try:B=np.linalg.inv(A)
 except np.linalg.LinAlgError:B=np.linalg.pinv(A)
 b=B@(X.T@(w*y));e=y-X@b;meat=np.zeros((4,4));
 for g in pd.unique(cl):
  ix=np.where(cl==g)[0];s=X[ix].T@(w[ix]*e[ix]);meat+=np.outer(s,s)
 G=len(pd.unique(cl));N=len(y);K=4;V=B@meat@B
 if G>1:V*=G/(G-1)*(N-1)/(N-K)
 se=float(np.sqrt(max(V[1,1],0)));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se>0 else None
 return {'tau':tau,'se':se,'p':p,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'n':N,'states':G}

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_balance/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'balance_{ay}_') as td:
  root=Path(td);cp,dc=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,dp=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True)
  prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'local.parquet';con.execute(f"COPY (SELECT a.pseudocode,a.state,a.district,a.management,a.enrol,{prevcols} FROM read_parquet({lit(str(cp))}) a LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 220 AND 281) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();d=d[government_universe(d.management,BROAD_STATE)].copy();rows=[]
 for g in GROUPS:
  r=fit(pd.to_numeric(d[f'prev_{g}_share'],errors='coerce').to_numpy(float),pd.to_numeric(d.enrol,errors='coerce').to_numpy(float),d.state.to_numpy(object));rows.append({'assignment_year':ay,'previous_year':prev,'group':g,**r})
 write(out/'predetermined_composition_continuity.csv',rows);(out/'validation.json').write_text(json.dumps({'assignment':dc,'previous':dp},indent=2,default=float),encoding='utf-8');print(pd.DataFrame(rows).to_string(index=False),flush=True);con.close()
if __name__=='__main__':main()
