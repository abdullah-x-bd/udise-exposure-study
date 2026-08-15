from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb, numpy as np, pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_majority_fs_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];cluster_fit=S['cluster_fit'];weighted_demean=S['weighted_demean']
CUT=250.5;BW=30

def write_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows:path.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def rd(d,fe_col):
 d=d[np.isfinite(d.receipt)&np.isfinite(d.enrol)&(np.abs(d.enrol-CUT)<=BW)].copy()
 if len(d)<500 or d[fe_col].astype(str).nunique()<8:return None
 d['T']=(d.enrol>=CUT).astype(float);d['z']=d.enrol-CUT;d['Tz']=d['T']*d['z'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/BW);d['fe']=d[fe_col].astype(str)
 d=weighted_demean(d,['y','T','z','Tz'],'fe','w')
 X=d[['T','z','Tz']].to_numpy(float);fit=cluster_fit(X,d.y.to_numpy(float),d.w.to_numpy(float),d[fe_col].astype(str).to_numpy())
 if fit is None:return None
 return {'tau':float(fit.params[0]),'se':float(fit.bse[0]),'p':float(fit.pvalues[0]),'ci_low':float(fit.params[0]-1.96*fit.bse[0]),'ci_high':float(fit.params[0]+1.96*fit.bse[0]),'n':int(fit.nobs),'clusters':int(d[fe_col].astype(str).nunique())}

def majority_interaction(d):
 d=d[np.isfinite(d.receipt)&np.isfinite(d.enrol)&np.isfinite(d.prev_muslim_share)&(d.prev_muslim_share!=.5)&(np.abs(d.enrol-CUT)<=BW)].copy()
 if len(d)<2000:return None
 d['M']=(d.prev_muslim_share>.5).astype(int);d['T']=(d.enrol>=CUT).astype(int);d['fe']=d.state.astype(str)+'|'+d.district.astype(str)
 # Identification is restricted to districts with both composition groups on both sides of the cutoff.
 support=d.groupby(['fe','M','T']).size().unstack(['M','T'],fill_value=0)
 required=[(0,0),(0,1),(1,0),(1,1)]
 for c in required:
  if c not in support.columns:support[c]=0
 good=support[(support[required]>=5).all(axis=1)].index
 d=d[d.fe.isin(good)].copy()
 if len(d)<1000 or d.fe.nunique()<20:return None
 d['M']=d['M'].astype(float);d['T']=d['T'].astype(float);d['z']=d.enrol-CUT;d['Tz']=d['T']*d['z'];d['TM']=d['T']*d['M'];d['zM']=d['z']*d['M'];d['TzM']=d['T']*d['z']*d['M'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/BW)
 cols=['y','T','z','Tz','M','TM','zM','TzM']
 for base in ('management','rural_urban','school_category'):
  vals=pd.to_numeric(d[base],errors='coerce').fillna(-999).astype(int);cats=sorted(vals.unique())
  for c in cats[1:]:name=f'cv_{base}_{c}';d[name]=(vals==c).astype(float);cols.append(name)
 d=weighted_demean(d,cols,'fe','w');xcols=['T','z','Tz','M','TM','zM','TzM']+[c for c in cols if c.startswith('cv_')];fit=cluster_fit(d[xcols].to_numpy(float),d.y.to_numpy(float),d.w.to_numpy(float),d.state.astype(str).to_numpy())
 if fit is None:return None
 j=xcols.index('TM');b=float(fit.params[j]);se=float(fit.bse[j]);p=float(fit.pvalues[j]);return {'majority_minus_nonmajority_first_stage':b,'se':se,'p':p,'ci_low':b-1.96*se,'ci_high':b+1.96*se,'n':int(fit.nobs),'states':int(d.state.nunique()),'districts':int(d.district.nunique()),'overlap_rule':'at least 5 observations in each of M0/T0, M0/T1, M1/T0, M1/T1 within district'}

def raw_levels(d):
 out={}
 for label,lo,hi in [('below_241_250',241,250),('above_251_260',251,260),('below_221_250',221,250),('above_251_280',251,280)]:
  x=d[(d.enrol>=lo)&(d.enrol<=hi)&np.isfinite(d.receipt)]
  out[label+'_n']=len(x);out[label+'_ge75']=float((x.receipt>=75000).mean()) if len(x) else np.nan;out[label+'_positive']=float((x.receipt>0).mean()) if len(x) else np.nan
 return out

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_majority_fs/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'majfs_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,p.muslim_share prev_muslim_share FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 220 AND 281) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d.receipt=pd.to_numeric(d.receipt,errors='coerce');d.prev_muslim_share=pd.to_numeric(d.prev_muslim_share,errors='coerce');d=d[np.isfinite(d.enrol)&np.isfinite(d.prev_muslim_share)].copy()
 rows=[]
 groups=[('muslim_majority',d.prev_muslim_share>.5),('non_muslim_majority',d.prev_muslim_share<.5),('muslim_75plus',d.prev_muslim_share>=.75),('muslim_90plus',d.prev_muslim_share>=.9)]
 for label,mask in groups:
  x=d[mask];r=rd(x,'state')
  if r:rows.append({'assignment_year':ay,'report_year':ry,'scope':'national','category':label,**raw_levels(x),**r})
 inter=majority_interaction(d)
 if inter:inter={'assignment_year':ay,'report_year':ry,**inter}
 state_rows=[]
 for st,g in d.groupby('state'):
  for label,mask in [('muslim_majority',g.prev_muslim_share>.5),('non_muslim_majority',g.prev_muslim_share<.5)]:
   x=g[mask]
   if len(x)<500 or x.district.astype(str).nunique()<8:continue
   r=rd(x,'district')
   if r:state_rows.append({'assignment_year':ay,'report_year':ry,'state':str(st),'category':label,**raw_levels(x),**r})
 write_csv(out/'majority_first_stage.csv',rows);write_csv(out/'majority_interaction.csv',[inter] if inter else []);write_csv(out/'state_majority_first_stage.csv',state_rows);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'national_rows':len(rows),'interaction':inter,'state_rows':len(state_rows)},indent=2,default=float))
if __name__=='__main__':main()
