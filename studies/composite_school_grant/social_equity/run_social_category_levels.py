from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_soclevel_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
SOC=['general','sc','st','obc']

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
def overlap(d,g):
 x=d[np.isfinite(d[f'prev_{g}_share'])].copy();x=x[x[f'prev_{g}_share']!=.5];x['maj']=(x[f'prev_{g}_share']>.5).astype(int);x['cell']=x.state.astype(str)+'|'+x.district.astype(str)+'|'+x.target.astype(int).astype(str);rows=[]
 for cell,z in x.groupby('cell'):
  a=z[z.maj==1].meet_target.dropna();b=z[z.maj==0].meet_target.dropna()
  if len(a)<5 or len(b)<5:continue
  q=cell.split('|');rows.append({'group':g,'cell':cell,'state':q[0],'district':q[1],'target':int(q[2]),'n_majority':len(a),'n_nonmajority':len(b),'majority_rate':float(a.mean()),'nonmajority_rate':float(b.mean())})
 return rows
def standardize(rows):
 out=[]
 for g,z0 in pd.DataFrame(rows).groupby('group') if rows else []:
  z=z0.copy();w=(2*z.n_majority*z.n_nonmajority/(z.n_majority+z.n_nonmajority)).to_numpy(float);w=w/w.sum();pm=float(np.sum(w*z.majority_rate));pn=float(np.sum(w*z.nonmajority_rate));out.append({'group':g,'cells':len(z),'states':z.state.nunique(),'districts':z.district.nunique(),'majority_rate':pm,'nonmajority_rate':pn,'difference':pm-pn})
 return out
def joint(d):
 x=d.copy();cols=[f'prev_{g}_share' for g in ['sc','st','obc']];keep=np.isfinite(x.meet_target)
 for c in cols:keep&=np.isfinite(x[c])
 x=x[keep].copy();x['y']=x.meet_target.astype(float);x['w']=1.;base=['y'];xcols=[]
 for g,c in zip(['sc','st','obc'],cols):x[g]=x[c].astype(float);base.append(g);xcols.append(g)
 for b in ('management','rural_urban','school_category'):
  v=pd.to_numeric(x[b],errors='coerce').fillna(-999).astype(int);cats=sorted(v.unique())
  for c in cats[1:]:n=f'cv_{b}_{c}';x[n]=(v==c).astype(float);base.append(n);xcols.append(n)
 x['fe']=x.district.astype(str)+'|'+x.target.astype(int).astype(str);x=weighted_demean(x,base,'fe','w');fit=cluster_fit(x[xcols].to_numpy(float),x.y.to_numpy(float),x.w.to_numpy(float),x.state.astype(str).to_numpy())
 if fit is None:return []
 out=[]
 for j,g in enumerate(['sc','st','obc']):b=float(fit.params[j]);se=float(fit.bse[j]);out.append({'group':g,'reference':'general','coef_per_10pp':b*.1,'se_per_10pp':se*.1,'p':float(fit.pvalues[j]),'ci_low_per_10pp':(b-1.96*se)*.1,'ci_high_per_10pp':(b+1.96*se)*.1,'n':int(fit.nobs),'states':x.state.astype(str).nunique(),'district_band_fe':x.fe.nunique()})
 return out
def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_category_levels/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'soclev_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d['target']=target(d.enrol);rec=pd.to_numeric(d.receipt,errors='coerce');d=d[np.isfinite(d.target)].copy();rec=pd.to_numeric(d.receipt,errors='coerce');d['meet_target']=np.where(rec.notna(),(rec>=d.target).astype(float),np.nan)
 cells=[]
 for g in SOC:cells+=overlap(d,g)
 std=standardize(cells);jj=joint(d)
 for coll in (cells,std,jj):
  for r in coll:r['assignment_year']=ay;r['report_year']=ry
 write_csv(out/'social_category_overlap_cells.csv',cells);write_csv(out/'social_category_standardized.csv',std);write_csv(out/'social_category_joint_levels.csv',jj);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'cells':len(cells),'joint':jj},indent=2,default=float))
if __name__=='__main__':main()
