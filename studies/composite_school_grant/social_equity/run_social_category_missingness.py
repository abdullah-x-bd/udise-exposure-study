from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_socmiss_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE']
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
def make_cells(d,g):
 x=d[np.isfinite(d[f'prev_{g}_share'])].copy();x=x[x[f'prev_{g}_share']!=.5];x['maj']=(x[f'prev_{g}_share']>.5).astype(int);x['cell']=x.state.astype(str)+'|'+x.district.astype(str)+'|'+x.target.astype(int).astype(str);rows=[]
 for cell,z in x.groupby('cell'):
  a=z[z.maj==1];b=z[z.maj==0]
  if len(a)<5 or len(b)<5:continue
  q=cell.split('|');r={'group':g,'cell':cell,'state':q[0],'district':q[1],'target':int(q[2]),'n_majority':len(a),'n_nonmajority':len(b)}
  for label,zz in [('majority',a),('nonmajority',b)]:
   rec=pd.to_numeric(zz.receipt,errors='coerce');obs=rec.notna();r[label+'_observed_rate']=float(obs.mean());r[label+'_meet_missing0']=float((rec.fillna(0)>=zz.target).mean());r[label+'_positive_missing0']=float((rec.fillna(0)>0).mean())
  rows.append(r)
 return rows
def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_category_missingness/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'socmiss_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d['target']=target(d.enrol);d=d[np.isfinite(d.target)].copy();rows=[]
 for g in SOC:rows+=make_cells(d,g)
 for r in rows:r['assignment_year']=ay;r['report_year']=ry
 write_csv(out/'social_category_missingness_cells.csv',rows);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'cells':len(rows)},indent=2))
if __name__=='__main__':main()
