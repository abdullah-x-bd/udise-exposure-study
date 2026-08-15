from __future__ import annotations
import csv, json, math, os, runpy, tempfile
from pathlib import Path
import duckdb, numpy as np, pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='gov_univ_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
CUT=250.5
UNIVERSES={
 'core_123':(1,2,3),
 'broad_state_123_6_89_90':(1,2,3,6,89,90),
 'all_udise_government_sensitivity':(1,2,3,6,89,90,92,93,94,95,96,101),
}

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode')
 if not x: raise RuntimeError('school id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{sex}')},0)" for k in range(1,13) for sex in ('b','g') if f'c{k}_{sex}' in c)

def statex(c,a):
 for k in ('state','state_id','state_code','state_cd'):
  r=ref(c,k,a)
  if r:return f"CAST({r} AS VARCHAR)"
 return "'unknown'"

def fit(y,x,cluster,bw=30):
 m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-CUT)<=bw)&pd.Series(cluster,dtype='object').notna().to_numpy();y=y[m];x=x[m];cl=np.asarray(cluster,dtype=object)[m]
 if len(y)<500:return None
 z=x-CUT;t=(x>=CUT).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z]
 A=X.T@(w[:,None]*X)
 try:B=np.linalg.inv(A)
 except np.linalg.LinAlgError:B=np.linalg.pinv(A)
 b=B@(X.T@(w*y));e=y-X@b
 # State-clustered sandwich for the discontinuity coefficient.
 meat=np.zeros((4,4));
 for g in pd.unique(cl):
  ix=np.where(cl==g)[0];sg=X[ix].T@(w[ix]*e[ix]);meat+=np.outer(sg,sg)
 G=len(pd.unique(cl));N=len(y);K=4
 V=B@meat@B
 if G>1:V*=G/(G-1)*(N-1)/(N-K)
 se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se>0 else None
 return {'tau':tau,'se':se,'p':p,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'n':N,'states':G,'n_left':int((x<CUT).sum()),'n_right':int((x>=CUT).sum())}

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);ry=YEARS[ai+3];gfy=YEARS[ai+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/government_universe/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();rows=[];counts=[]
 with tempfile.TemporaryDirectory(prefix='govuniv_') as td:
  root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));p2=src(extract(repo,tok,ry,'profile_2',root));ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);f=efilt(con,en,ec);es=esum(ec);st=statex(pc,'p')
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  d=con.execute(f"SELECT e.pseudocode,e.enrol,{nref(pc,'managment','p')} management,{st} state,{nref(gc,'grants_receipt','g')} receipt,{nref(gc,'grants_expenditure','g')} expenditure FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {p2} g ON e.pseudocode=CAST(g.{qid(gi)} AS VARCHAR)").df()
  for name,codes in UNIVERSES.items():
   z=d[pd.to_numeric(d.management,errors='coerce').isin(codes)].copy();counts.append({'assignment_year':ay,'universe':name,'school_rows':len(z),'unique_schools':int(z.pseudocode.nunique()),'codes':','.join(map(str,codes))})
   r=pd.to_numeric(z.receipt,errors='coerce').to_numpy(float);e=pd.to_numeric(z.expenditure,errors='coerce').to_numpy(float);x=z.enrol.to_numpy(float);cl=z.state.to_numpy(object)
   vr=np.isfinite(r);ve=np.isfinite(e)
   # winsorize globally within universe for stable amount outcome.
   rw=r.copy();ew=e.copy()
   if vr.any():rw[vr]=np.clip(r[vr],np.nanquantile(r[vr],.01),np.nanquantile(r[vr],.99))
   if ve.any():ew[ve]=np.clip(e[ve],np.nanquantile(e[ve],.01),np.nanquantile(e[ve],.99))
   outs={
    'receipt_ge75000':np.where(vr,(r>=75000).astype(float),np.nan),
    'receipt_positive':np.where(vr,(r>0).astype(float),np.nan),
    'receipt_w99':rw,
    'expenditure_ge75000':np.where(ve,(e>=75000).astype(float),np.nan),
    'expenditure_w99':ew,
   }
   for outcome,y in outs.items():
    a=fit(y,x,cl)
    if a:rows.append({'assignment_year':ay,'grant_financial_year':gfy,'udise_report_year':ry,'universe':name,'outcome':outcome,'bw':30,**a})
 write(out/'government_universe_rd.csv',rows);write(out/'government_universe_counts.csv',counts)
 md=['# Government-universe robustness '+ay,'',f'Grant FY {gfy}; UDISE report year {ry}.','']
 for r in rows:
  if r['outcome']=='receipt_ge75000':md.append(f"- {r['universe']}: {100*r['tau']:+.2f} pp (95% CI {100*r['ci_low']:+.2f} to {100*r['ci_high']:+.2f}), n={r['n']}")
 (out/'RESULTS.md').write_text('\n'.join(md),encoding='utf-8');print('\n'.join(md),flush=True);con.close()
if __name__=='__main__':main()
