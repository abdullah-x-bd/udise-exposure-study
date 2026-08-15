from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_state_support_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build=S['build_composition_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD=S['BROAD_STATE']

def write(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows:path.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_state_support/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'support_{ay}_') as td:
  root=Path(td);cp,dc=build(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,dp=build(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'local.parquet';con.execute(f"COPY (SELECT a.state,a.district,a.management,a.enrol,{prevcols} FROM read_parquet({lit(str(cp))}) a LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 220 AND 281) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();d=d[government_universe(d.management,BROAD)].copy();rows=[]
 for state,z in d.groupby('state'):
  for g in GROUPS:
   x=pd.to_numeric(z[f'prev_{g}_share'],errors='coerce').dropna()
   if len(x)==0:continue
   rows.append({'assignment_year':ay,'previous_year':prev,'state':state,'group':g,'n':len(x),'mean':float(x.mean()),'sd':float(x.std()),'p10':float(x.quantile(.1)),'p90':float(x.quantile(.9)),'min':float(x.min()),'max':float(x.max()),'positive_share':float((x>0).mean()),'above_10pct_share':float((x>=.1).mean())})
 write(out/'state_group_support.csv',rows);(out/'validation.json').write_text(json.dumps({'assignment':dc,'previous':dp},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'rows':len(rows)},indent=2),flush=True);con.close()
if __name__=='__main__':main()
