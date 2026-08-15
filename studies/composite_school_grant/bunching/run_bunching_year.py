from __future__ import annotations
import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
import statsmodels.api as sm

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='bunch_lib')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
TRUE=[30,100,250,1000]; PLACEBO=[50,75,125,150,175,200,225,275,300,325,350,375,400,450,500,550,600,650,700,750,800,850,900]
GOV='(1,2,3)'

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode');
 if not x:raise RuntimeError('id missing')
 return x

def filt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def heap(v):
 if v%100==0:return 5
 if v%50==0:return 4
 if v%25==0:return 3
 if v%10==0:return 2
 if v%5==0:return 1
 return 0

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def one(cmap,c,window,zone=5):
 xs=np.arange(max(1,c-window),c+window+2);y=np.array([cmap.get(int(x),0) for x in xs],float);z=(xs-(c+.5))/window;h=np.array([heap(int(x)) for x in xs]);sens=(xs>=c-zone)&(xs<=c+zone)
 X=np.column_stack([np.ones(len(xs)),z,z*z,z*z*z]+[(h==k).astype(float) for k in range(1,6)])
 fit=~sens
 try:
  model=sm.GLM(y[fit],X[fit],family=sm.families.Poisson()).fit(maxiter=200,disp=0);pred=model.predict(X)
 except Exception:
  b=np.linalg.lstsq(X[fit],np.log1p(y[fit]),rcond=None)[0];pred=np.maximum(0,np.expm1(X@b))
 a=(xs>=c+1)&(xs<=c+zone);b=(xs>=c-zone)&(xs<=c-1);oa=float(y[a].sum());ea=float(pred[a].sum());ob=float(y[b].sum());eb=float(pred[b].sum())
 if ea<=0 or eb<=0:return None
 return {'obs_above':oa,'expected_above':ea,'excess_above':oa-ea,'excess_ratio_above':oa/ea-1,'obs_below':ob,'expected_below':eb,'excess_below':ob-eb,'excess_ratio_below':ob/eb-1,'heaping_adjusted_asymmetry':(oa/ea-1)-(ob/eb-1),'poisson_z_above':(oa-ea)/math.sqrt(max(ea,1)),'poisson_z_below':(ob-eb)/math.sqrt(max(eb,1)),'count_at_cutoff':cmap.get(c,0),'count_first_above':cmap.get(c+1,0),'window':window,'zone':zone}

def main():
 y=os.environ['YEAR'];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/bunching/{y}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect()
 with tempfile.TemporaryDirectory(prefix='bunch_') as td:
  root=Path(td);en=src(extract(repo,tok,y,'enrolment_1',root));p1=src(extract(repo,tok,y,'profile_1',root));ec,pc=cols(con,en),cols(con,p1);ei,pi=ident(ec),ident(pc);f=filt(con,en,ec);es=esum(ec)
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  d=con.execute(f"SELECT CAST(e.enrol AS INTEGER) enrol FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 1 AND 1150").df();cmap=d.enrol.value_counts().to_dict();rows=[]
  for c in TRUE+PLACEBO:
   m=one(cmap,c,40 if c<500 else 120)
   if m:rows.append({'academic_year':y,'threshold_end':c,'threshold_start':c+1,'kind':'true' if c in TRUE else 'placebo',**m})
 write(out/'bunching.csv',rows)
 t250=next((r for r in rows if r['threshold_end']==250),None);ps=[r['heaping_adjusted_asymmetry'] for r in rows if r['kind']=='placebo'];rank=float(np.mean(np.array(ps)<=t250['heaping_adjusted_asymmetry'])) if t250 and ps else None
 (out/'RESULTS.md').write_text(f"# Bunching {y}\n\n250/251 heaping-adjusted asymmetry: {t250['heaping_adjusted_asymmetry'] if t250 else 'NA'}\n\nPercentile among placebo thresholds: {rank}\n\nCount at 250: {t250['count_at_cutoff'] if t250 else 'NA'}; count at 251: {t250['count_first_above'] if t250 else 'NA'}\n",encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True);con.close()
if __name__=='__main__':main()
