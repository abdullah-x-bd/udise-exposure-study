from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_state_maj_int_lib')
YEARS=S['YEARS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
CUT=250.5;BW=30

def write_csv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def fit_state(d,state):
 d=d[np.isfinite(d.receipt)&np.isfinite(d.enrol)&np.isfinite(d.prev_muslim_share)&(d.prev_muslim_share!=.5)&(np.abs(d.enrol-CUT)<=BW)].copy()
 d['M']=(d.prev_muslim_share>.5).astype(int);d['T']=(d.enrol>=CUT).astype(int);d['fe']=d.district.astype(str)
 support=d.groupby(['fe','M','T']).size().unstack(['M','T'],fill_value=0);required=[(0,0),(0,1),(1,0),(1,1)]
 for c in required:
  if c not in support.columns:support[c]=0
 good=support[(support[required]>=3).all(axis=1)].index;d=d[d.fe.isin(good)].copy()
 if len(d)<400 or d.fe.nunique()<8:return None
 d['M']=d['M'].astype(float);d['T']=d['T'].astype(float);d['z']=d.enrol-CUT;d['Tz']=d['T']*d['z'];d['TM']=d['T']*d['M'];d['zM']=d['z']*d['M'];d['TzM']=d['T']*d['z']*d['M'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/BW)
 cols=['y','T','z','Tz','M','TM','zM','TzM']
 for base in ('management','rural_urban','school_category'):
  vals=pd.to_numeric(d[base],errors='coerce').fillna(-999).astype(int);cats=sorted(vals.unique())
  for c in cats[1:]:n=f'cv_{base}_{c}';d[n]=(vals==c).astype(float);cols.append(n)
 d=weighted_demean(d,cols,'fe','w');xcols=['T','z','Tz','M','TM','zM','TzM']+[c for c in cols if c.startswith('cv_')];fit=cluster_fit(d[xcols].to_numpy(float),d.y.to_numpy(float),d.w.to_numpy(float),d.district.astype(str).to_numpy())
 if fit is None:return None
 j=xcols.index('TM');b=float(fit.params[j]);se=float(fit.bse[j]);return {'state':state,'majority_minus_nonmajority_first_stage':b,'se':se,'p':float(fit.pvalues[j]),'ci_low':b-1.96*se,'ci_high':b+1.96*se,'n':int(fit.nobs),'districts':int(d.fe.nunique()),'muslim_majority_n':int((d['M']==1).sum()),'nonmajority_n':int((d['M']==0).sum())}

def main():
 ay=os.environ.get('ASSIGN_YEAR','2022-23');ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/state_majority_interaction/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'stmaj_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,p.muslim_share prev_muslim_share FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 220 AND 281) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d.receipt=pd.to_numeric(d.receipt,errors='coerce');d.prev_muslim_share=pd.to_numeric(d.prev_muslim_share,errors='coerce');rows=[]
 for st,g in d.groupby('state'):
  r=fit_state(g,str(st))
  if r:rows.append({'assignment_year':ay,'report_year':ry,**r})
 write_csv(out/'state_majority_interactions.csv',rows);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'states':rows},indent=2,default=float))
if __name__=='__main__':main()
