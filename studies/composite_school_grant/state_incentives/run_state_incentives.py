from __future__ import annotations
import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='state_inc_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
C=250.5;GOV='(1,2,3)';RNG=np.random.default_rng(20260815)

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode');
 if not x:raise RuntimeError('id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def cluster_expr(c,a):
 for k in ('state','state_id','state_code','state_cd'):
  r=ref(c,k,a)
  if r:return f"CAST({r} AS VARCHAR)"
 raise RuntimeError('state field absent')

def local(y,x,bw=30):
 m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-C)<=bw);y=y[m];x=x[m]
 if len(y)<80 or (x<C).sum()<25 or (x>=C).sum()<25:return None
 z=x-C;t=(x>=C).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z];A=X.T@(w[:,None]*X)
 try:B=np.linalg.inv(A)
 except np.linalg.LinAlgError:B=np.linalg.pinv(A)
 b=B@(X.T@(w*y));e=y-X@b;M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4);se=float(np.sqrt(max(0,V[1,1])));return {'first_stage':float(b[1]),'se':se,'n':len(y),'n_left':int((x<C).sum()),'n_right':int((x>=C).sum())}

def bunch(x):
 v=pd.Series(x).dropna().astype(int).value_counts().to_dict();oa=sum(v.get(i,0) for i in range(251,256));ob=sum(v.get(i,0) for i in range(246,251));ca=np.mean([v.get(i,0) for i in range(256,271)]);cb=np.mean([v.get(i,0) for i in range(231,246)]);ea=ca*5;eb=cb*5
 if ea<=0 or eb<=0:return None
 return {'obs_above':oa,'obs_below':ob,'excess_ratio_above':oa/ea-1,'excess_ratio_below':ob/eb-1,'asymmetry':(oa/ea-1)-(ob/eb-1),'count251':v.get(251,0),'count250':v.get(250,0)}

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def corr_perm(d,reps=5000):
 x=d.first_stage.to_numpy(float);y=d.asymmetry.to_numpy(float);w=np.sqrt(d.n.to_numpy(float));
 def wc(a,b):
  ma=np.average(a,weights=w);mb=np.average(b,weights=w);aa=a-ma;bb=b-mb;den=math.sqrt(np.average(aa*aa,weights=w)*np.average(bb*bb,weights=w));return np.average(aa*bb,weights=w)/den if den else np.nan
 obs=wc(x,y);ge=0
 for _ in range(reps):
  if abs(wc(x,RNG.permutation(y)))>=abs(obs):ge+=1
 return {'corr':float(obs),'permutation_p':(ge+1)/(reps+1),'reps':reps,'states':len(d)}

def main():
 ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);report=YEARS[ai+3];grant=YEARS[ai+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/state_incentives/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();rows=[]
 with tempfile.TemporaryDirectory(prefix='stateinc_') as td:
  root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));p2=src(extract(repo,tok,report,'profile_2',root));ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);f=efilt(con,en,ec);es=esum(ec);st=cluster_expr(pc,'p')
  con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol FROM {en} WHERE {f} GROUP BY 1")
  d=con.execute(f"""SELECT {st} state,e.enrol,{nref(gc,'grants_receipt','g')} receipt FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {p2} g ON e.pseudocode=CAST(g.{qid(gi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 210 AND 291""").df()
  for state,z in d.groupby('state'):
   r=z.receipt.to_numpy(float);y=np.where(np.isfinite(r),(r>=75000).astype(float),np.nan);a=local(y,z.enrol.to_numpy(float));b=bunch(z.enrol)
   if a and b:rows.append({'assignment_year':ay,'grant_financial_year':grant,'udise_report_year':report,'state':state,**a,**b})
 write(out/'state_year.csv',rows);dd=pd.DataFrame(rows);summary=corr_perm(dd) if len(dd)>=10 else {'states':len(dd)};(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(out/'RESULTS.md').write_text(f"# State incentives {ay}\n\nGrant FY {grant}; UDISE report year {report}.\n\n{json.dumps(summary,indent=2)}\n",encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True);con.close()
if __name__=='__main__':main()
