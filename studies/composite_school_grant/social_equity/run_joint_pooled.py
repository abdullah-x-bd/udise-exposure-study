from __future__ import annotations

import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,pandas as pd

S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_joint_pooled_social')
J=runpy.run_path('studies/composite_school_grant/social_equity/run_joint_composition.py',run_name='csg_joint_pooled_fit')
YEARS=S['YEARS'];PRIMARY=S['PRIMARY_ASSIGNMENT_YEARS'];GROUPS=S['GROUPS'];BROAD_STATE=S['BROAD_STATE']
build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];government_universe=S['government_universe'];lit=S['lit']
fit_joint=J['fit_joint'];SOCIAL=J['SOCIAL'];RELIG=J['RELIG']

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
 repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path('studies/composite_school_grant/outputs/social_equity_joint_pooled');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'");cps={};fps={};valid=[]
 needed_comp=['2018-19','2019-20','2020-21','2021-22','2022-23'];needed_fin=[YEARS[YEARS.index(y)+3] for y in PRIMARY]
 with tempfile.TemporaryDirectory(prefix='jointpooled_') as td:
  root=Path(td)
  for y in needed_comp:
   p,d=build_composition_year(con,repo,tok,y,root,out);cps[y]=p;valid.append(d);shutil.rmtree(root/y,ignore_errors=True)
  for y in needed_fin:
   fps[y]=load_financial_year(con,repo,tok,y,root,out);shutil.rmtree(root/y,ignore_errors=True)
 cohorts=[]
 for ay in PRIMARY:
  ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);co=out/f'local_{ay}.parquet'
  con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,f.expenditure,{prevcols} FROM read_parquet({lit(str(cps[ay]))}) a LEFT JOIN read_parquet({lit(str(fps[ry]))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(cps[prev]))}) p USING(pseudocode) WHERE a.enrol BETWEEN 150 AND 351) TO {lit(str(co))} (FORMAT PARQUET,COMPRESSION ZSTD)");cohorts.append(co)
 pooled=out/'pooled.parquet';con.execute(f"COPY (SELECT * FROM read_parquet([{','.join(lit(str(x)) for x in cohorts)}],union_by_name=true)) TO {lit(str(pooled))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(pooled))})').df();d=d[government_universe(d.management,BROAD_STATE)].copy();rows=[];tests=[]
 for family,groups in [('social_category',SOCIAL),('religion',RELIG)]:
  for source in ('previous','assignment'):
   for cutoff,label in [(250.5,'true_250'),(200.5,'placebo_200'),(300.5,'placebo_300')]:
    bw=30 if cutoff==250.5 else 20
    for fe in ('state_year','district_year'):
     rr,j=fit_joint(d,groups,cutoff,bw,fe,source)
     for r in rr:rows.append({'family':family,'source':source,'cutoff':cutoff,'cutoff_label':label,'fe':fe,**r})
     if j:tests.append({'family':family,'source':source,'cutoff':cutoff,'cutoff_label':label,'fe':fe,**j})
 write(out/'joint_pooled_coefficients.csv',rows);write(out/'joint_pooled_tests.csv',tests);(out/'validation.json').write_text(json.dumps(valid,indent=2,default=float),encoding='utf-8')
 pref=[r for r in rows if r['source']=='previous' and r['cutoff_label']=='true_250' and r['fe']=='district_year'];lines=['# Pooled joint compositional CSG heterogeneity','','Four correctly aligned cohorts pooled. Broad State/UT-government sample. Previous-year composition, district-by-year fixed effects, state-clustered inference.','']
 for r in pref:lines.append(f"- {r['family']} {r['group']}: {100*r['coef_per_10pp']:+.3f} pp per +10pp relative share (95% CI {100*r['ci_low_per_10pp']:+.3f} to {100*r['ci_high_per_10pp']:+.3f}), p={r['p']:.4g}")
 for t in tests:
  if t['source']=='previous' and t['cutoff_label']=='true_250' and t['fe']=='district_year':lines.append(f"- Joint {t['family']} Wald: chi2({t['joint_df']})={t['joint_wald_chi2']:.3f}, p={t['joint_p']:.4g}")
 (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8');print('\n'.join(lines),flush=True);con.close()
if __name__=='__main__':main()
