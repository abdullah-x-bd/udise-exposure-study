from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_joint_level_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
VARS=['sc','st','obc','muslim','christian','sikh','buddhist','parsi','jain']

def write_csv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def target(e):
 e=np.asarray(e,float);return np.select([(e>=31)&(e<=100),(e>=101)&(e<=250),(e>=251)&(e<=1000),e>1000],[25000.,50000.,75000.,100000.],default=np.nan)

def fit(d):
 cols=[f'prev_{g}_share' for g in VARS];keep=np.isfinite(d.meet_target)&np.isfinite(d.enrol)&(d.enrol>0)
 for c in cols:keep &= np.isfinite(d[c])
 x=d[keep].copy()
 if len(x)<5000:return []
 x['y']=x.meet_target.astype(float);x['w']=1.;x['log_enrol']=np.log(x.enrol.astype(float));base=['y','log_enrol'];xcols=['log_enrol']
 for g,c in zip(VARS,cols):x[g]=x[c].astype(float);base.append(g);xcols.append(g)
 for b in ('management','rural_urban','school_category'):
  v=pd.to_numeric(x[b],errors='coerce').fillna(-999).astype(int);cats=sorted(v.unique())
  for c in cats[1:]:n=f'cv_{b}_{c}';x[n]=(v==c).astype(float);base.append(n);xcols.append(n)
 x['fe']=x.state.astype(str)+'|'+x.district.astype(str)+'|'+x.target.astype(int).astype(str);x=weighted_demean(x,base,'fe','w');fit=cluster_fit(x[xcols].to_numpy(float),x.y.to_numpy(float),x.w.to_numpy(float),x.state.astype(str).to_numpy())
 if fit is None:return []
 out=[]
 for g in VARS:
  j=xcols.index(g);b=float(fit.params[j]);se=float(fit.bse[j]);p=float(fit.pvalues[j]);out.append({'group':g,'coef_per_10pp':b*.1,'se_per_10pp':se*.1,'p':p,'ci_low_per_10pp':(b-1.96*se)*.1,'ci_high_per_10pp':(b+1.96*se)*.1,'n':int(fit.nobs),'states':int(x.state.nunique()),'district_band_fe':int(x.fe.nunique()),'controls':'log enrolment + management + rural/urban + school category; district x nominal-band FE'})
 return out

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/joint_level_controls/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'jointlevel_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d['target']=target(d.enrol);d=d[np.isfinite(d.target)].copy();rec=pd.to_numeric(d.receipt,errors='coerce');d['meet_target']=np.where(rec.notna(),(rec>=d.target).astype(float),np.nan)
 for g in VARS:d[f'prev_{g}_share']=pd.to_numeric(d[f'prev_{g}_share'],errors='coerce')
 rows=fit(d)
 for r in rows:r['assignment_year']=ay;r['report_year']=ry
 write_csv(out/'joint_level_coefficients.csv',rows);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry,'n':len(d)},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'coefficients':rows},indent=2,default=float))
if __name__=='__main__':main()
