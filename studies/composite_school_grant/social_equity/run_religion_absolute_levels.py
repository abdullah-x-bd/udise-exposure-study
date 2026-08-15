from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_relig_abs_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE']
RELIG=['muslim','christian','sikh','buddhist','parsi','jain']

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

def raw_summary(x,g,label):
 if len(x)==0:return None
 rec=pd.to_numeric(x.receipt,errors='coerce');obs=rec.notna();r={'group':g,'category':label,'n_total':len(x),'n_observed':int(obs.sum()),'receipt_observed_rate':float(obs.mean()),'states':x.state.astype(str).nunique(),'districts':x.district.astype(str).nunique()}
 if obs.any():
  rr=rec[obs];xx=x.loc[obs];ratio=rr/xx.target;r.update({'positive_rate':float((rr>0).mean()),'meet_target_rate':float((rr>=xx.target).mean()),'exact_target_rate':float((rr==xx.target).mean()),'mean_target_ratio_w99':float(ratio.clip(upper=float(ratio.quantile(.99))).mean()),'mean_receipt_w99':float(rr.clip(upper=float(rr.quantile(.99))).mean())})
 return r

def cells_for_group(d,g):
 s=f'prev_{g}_share';x=d[np.isfinite(d[s])&(d[s]!=.5)].copy();x['maj']=(x[s]>.5).astype(int);x['cell']=x.state.astype(str)+'|'+x.district.astype(str)+'|'+x.target.astype(int).astype(str);rows=[]
 for cell,z in x.groupby('cell'):
  a=z[z.maj==1];b=z[z.maj==0]
  ya=a.meet_target.dropna();yb=b.meet_target.dropna()
  if len(ya)<5 or len(yb)<5:continue
  q=cell.split('|');rows.append({'group':g,'state':q[0],'district':q[1],'target':int(q[2]),'cell':cell,'n_majority':len(ya),'n_nonmajority':len(yb),'majority_rate':float(ya.mean()),'nonmajority_rate':float(yb.mean())})
 return rows

def standardize(z):
 if len(z)==0:return None
 z=pd.DataFrame(z);w=(2*z.n_majority*z.n_nonmajority/(z.n_majority+z.n_nonmajority)).to_numpy(float);w=w/w.sum();pm=float(np.sum(w*z.majority_rate));pn=float(np.sum(w*z.nonmajority_rate));return {'cells':len(z),'states':z.state.nunique(),'districts':z.district.nunique(),'majority_rate':pm,'nonmajority_rate':pn,'difference':pm-pn}

def state_standardize(rows,g):
 z=pd.DataFrame([r for r in rows if r['group']==g]);out=[]
 if len(z)==0:return out
 for st,q in z.groupby('state'):
  if len(q)<3 or q.n_majority.sum()<20 or q.n_nonmajority.sum()<50:continue
  w=(2*q.n_majority*q.n_nonmajority/(q.n_majority+q.n_nonmajority)).to_numpy(float);w=w/w.sum();pm=float(np.sum(w*q.majority_rate));pn=float(np.sum(w*q.nonmajority_rate));out.append({'group':g,'state':st,'cells':len(q),'districts':q.district.nunique(),'majority_n':int(q.n_majority.sum()),'nonmajority_n':int(q.n_nonmajority.sum()),'majority_rate':pm,'nonmajority_rate':pn,'difference':pm-pn})
 return out

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/religion_absolute_levels/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
 with tempfile.TemporaryDirectory(prefix=f'religabs_{ay}_') as td:
  root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
 d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d['target']=target(d.enrol);d=d[np.isfinite(d.target)].copy();rec=pd.to_numeric(d.receipt,errors='coerce');d['meet_target']=np.where(rec.notna(),(rec>=d.target).astype(float),np.nan)
 raw=[];cells=[];std=[];states=[]
 for g in RELIG:
  s=f'prev_{g}_share';d[s]=pd.to_numeric(d[s],errors='coerce');m=d[s]>.5;n=d[s]<.5
  for label,mask in [(f'{g}_majority',m),(f'not_{g}_majority',n),(f'{g}_75plus',d[s]>=.75)]:
   r=raw_summary(d.loc[mask],g,label)
   if r:raw.append(r)
  cr=cells_for_group(d,g);cells+=cr;sr=standardize(cr)
  if sr:std.append({'group':g,**sr})
  states+=state_standardize(cr,g)
 for coll in (raw,cells,std,states):
  for r in coll:r['assignment_year']=ay;r['report_year']=ry
 write_csv(out/'religion_raw_levels.csv',raw);write_csv(out/'religion_overlap_cells.csv',cells);write_csv(out/'religion_standardized.csv',std);write_csv(out/'religion_state_standardized.csv',states);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry,'n':len(d)},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'raw':len(raw),'cells':len(cells),'std':len(std),'states':len(states)},indent=2))
if __name__=='__main__':main()
