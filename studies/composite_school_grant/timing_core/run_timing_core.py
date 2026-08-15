from __future__ import annotations

import csv, json, math, os, runpy, shutil, tempfile
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from rdrobust import rdrobust

P = runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py', run_name='csg_timing_panel_lib')
YEARS=P['YEARS']; extract=P['extract_archive']; src=P['csv_source']; cols=P['source_columns']; labels=P['identify_early_social_labels']; qid=P['qid']; lit=P['lit']; ref=P['ref']; nref=P['nref']
C=250.5; GOV='(1,2,3)'; BW=30


def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x: raise RuntimeError('school id missing')
    return x


def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:
        return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c)
    if not ls: raise RuntimeError('social rows not identified')
    return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"


def esum(c,m):
    z=[f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,m+1) for s in ('b','g') if f'c{k}_{s}' in c]
    if not z: raise RuntimeError('class columns absent')
    return ' + '.join(z)


def write_csv(p, rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows: p.write_text('',encoding='utf-8'); return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks: ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)


def fast_rd(y,x,bw=30,c=C):
    m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-c)<=bw)
    y=y[m];x=x[m]
    L=int((x<c).sum());R=int((x>=c).sum())
    if len(y)<300 or min(L,R)<80:return None
    z=x-c;t=(x>=c).astype(float);w=np.maximum(0,1-np.abs(z)/bw)
    X=np.column_stack([np.ones(len(x)),t,z,t*z]);keep=w>0;X=X[keep];y=y[keep];w=w[keep]
    A=X.T@(w[:,None]*X)
    try:B=np.linalg.inv(A)
    except np.linalg.LinAlgError:B=np.linalg.pinv(A)
    b=B@(X.T@(w*y));e=y-X@b
    M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4)
    se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se>0 else None
    return dict(tau=tau,se=se,p=p,ci_low=tau-1.96*se,ci_high=tau+1.96*se,n=len(y),n_left=L,n_right=R,bw=bw)


def pub_rd(y,x,state,bw=30,c=C):
    m=np.isfinite(y)&np.isfinite(x)&np.isfinite(state)&(np.abs(x-c)<=bw)
    y=y[m];x=x[m];state=state[m]
    if len(y)<500:return None
    try:
        r=rdrobust(y=y,x=x,c=c,p=1,q=2,kernel='tri',h=bw,b=max(45,bw*1.5),cluster=pd.Categorical(state).codes,vce='cr3',masspoints='adjust',bwcheck=15)
        co=np.asarray(r.coef,dtype=float).reshape(-1)[-1];se=np.asarray(r.se,dtype=float).reshape(-1)[-1];pv=np.asarray(r.pv,dtype=float).reshape(-1)[-1];ci=np.asarray(r.ci,dtype=float).reshape(-1,2)[-1]
        return dict(tau=float(co),se=float(se),p=float(pv),ci_low=float(ci[0]),ci_high=float(ci[1]),n=len(y),bw=bw)
    except Exception as e:return {'error':repr(e),'n':len(y),'bw':bw}


def build(con,repo,tok,out):
    paths=[]; manifest=[]
    with tempfile.TemporaryDirectory(prefix='csg_timing_core_') as td:
        root=Path(td)
        for y in YEARS:
            print('BUILD',y,flush=True)
            en=src(extract(repo,tok,y,'enrolment_1',root));p1=src(extract(repo,tok,y,'profile_1',root));p2=src(extract(repo,tok,y,'profile_2',root))
            ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);f=efilt(con,en,ec);e12=esum(ec,12);e8=esum(ec,8)
            q=out/'year'/f'{y}.parquet';q.parent.mkdir(parents=True,exist_ok=True)
            con.execute(f"""COPY (
                WITH e AS (SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({e12}) enrol,SUM({e8}) enrol18 FROM {en} WHERE {f} GROUP BY 1)
                SELECT {lit(y)} academic_year,CAST(a.{qid(pi)} AS VARCHAR) pseudocode,{nref(pc,'state','a')} state,{nref(pc,'managment','a')} management,e.enrol,e.enrol18,
                       {nref(gc,'grants_receipt','g')} receipt,{nref(gc,'grants_expenditure','g')} expenditure
                FROM {p1} a LEFT JOIN {p2} g ON CAST(a.{qid(pi)} AS VARCHAR)=CAST(g.{qid(gi)} AS VARCHAR) LEFT JOIN e ON CAST(a.{qid(pi)} AS VARCHAR)=e.pseudocode
            ) TO {lit(str(q))} (FORMAT PARQUET,COMPRESSION ZSTD)""")
            r=con.execute(f"SELECT COUNT(*),COUNT(*) FILTER(WHERE enrol IS NOT NULL),COUNT(*) FILTER(WHERE receipt IS NOT NULL) FROM read_parquet({lit(str(q))})").fetchone();manifest.append({'year':y,'rows':r[0],'with_enrol':r[1],'with_receipt':r[2]});paths.append(q);shutil.rmtree(root/y,ignore_errors=True)
    panel=out/'panel.parquet';ls='['+','.join(lit(str(p)) for p in paths)+']';con.execute(f"COPY (SELECT * FROM read_parquet({ls},union_by_name=true)) TO {lit(str(panel))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    (out/'build_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return panel


def timing(con,panel,out):
    rows=[]; yi={y:i for i,y in enumerate(YEARS)}
    for ay in YEARS:
      for oy in YEARS:
        lag=yi[oy]-yi[ay]
        if lag < -3 or lag > 4:continue
        d=con.execute(f"""SELECT a.enrol x,a.enrol18 x18,a.state,f.receipt,f.expenditure FROM read_parquet({lit(str(panel))}) a LEFT JOIN read_parquet({lit(str(panel))}) f ON a.pseudocode=f.pseudocode AND f.academic_year={lit(oy)} WHERE a.academic_year={lit(ay)} AND a.management IN {GOV} AND a.enrol BETWEEN 180 AND 321""").df()
        for sample,mask in [('all',np.ones(len(d),bool)),('pm220',d.x18.fillna(99999).to_numpy(float)<=220)]:
          z=d.loc[mask];x=z.x.to_numpy(float);st=z.state.to_numpy(float);rr=z.receipt.to_numpy(float);ee=z.expenditure.to_numpy(float)
          outcomes={'receipt_ge75':np.where(np.isfinite(rr),(rr>=75000).astype(float),np.nan),'receipt_gt50':np.where(np.isfinite(rr),(rr>50000).astype(float),np.nan),'expenditure_ge75':np.where(np.isfinite(ee),(ee>=75000).astype(float),np.nan)}
          if np.isfinite(rr).sum()>100:outcomes['receipt_w99']=np.where(np.isfinite(rr),np.minimum(rr,np.nanquantile(rr,.99)),np.nan)
          if np.isfinite(ee).sum()>100:outcomes['expenditure_w99']=np.where(np.isfinite(ee),np.minimum(ee,np.nanquantile(ee,.99)),np.nan)
          for name,yv in outcomes.items():
            f=fast_rd(yv,x); 
            if f:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'sample':sample,'outcome':name,**f})
          # publication-grade estimator for the primary categorical first stage only
          if sample=='all':
            f=pub_rd(outcomes['receipt_ge75'],x,st)
            if f:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'sample':sample,'outcome':'receipt_ge75','estimator':'rdrobust_cr3',**f})
        print('TIMING',ay,oy,lag,flush=True)
    write_csv(out/'timing_core.csv',rows)
    # pooled simple summaries, intentionally not used as substitute for cohort results
    df=pd.DataFrame([r for r in rows if r.get('estimator')=='rdrobust_cr3' and 'tau' in r])
    metas=[]
    if len(df):
      for lag,g in df.groupby('lag'):
        s=g.se.to_numpy(float);v=g.tau.to_numpy(float);w=1/np.maximum(s*s,1e-12);t=float((w*v).sum()/w.sum());se=float(np.sqrt(1/w.sum()));metas.append({'lag':int(lag),'cohorts':len(g),'tau_ivw':t,'se_ivw':se,'ci_low':t-1.96*se,'ci_high':t+1.96*se})
    write_csv(out/'timing_meta.csv',metas);return rows,metas


def bunch(con,panel,out):
    rows=[]
    for y in YEARS:
      c=dict(con.execute(f"SELECT CAST(enrol AS INTEGER),COUNT(*) FROM read_parquet({lit(str(panel))}) WHERE academic_year={lit(y)} AND management IN {GOV} AND enrol BETWEEN 1 AND 1100 GROUP BY 1").fetchall())
      for k,kind in [(30,'true'),(100,'true'),(250,'true'),(1000,'true'),(150,'pseudo'),(200,'pseudo'),(300,'pseudo'),(350,'pseudo'),(400,'pseudo'),(450,'pseudo'),(500,'pseudo'),(600,'pseudo'),(700,'pseudo'),(800,'pseudo'),(900,'pseudo')]:
        zone=5; obsA=sum(c.get(i,0) for i in range(k+1,k+zone+1));obsB=sum(c.get(i,0) for i in range(k-zone,k));
        # symmetric local controls excluding +/-5 and controlling by same offsets around +/-[6,20]
        ctlA=[c.get(k+j,0) for j in range(6,21)];ctlB=[c.get(k-j,0) for j in range(6,21)];ea=np.mean(ctlA)*zone if ctlA else np.nan;eb=np.mean(ctlB)*zone if ctlB else np.nan
        rows.append({'year':y,'threshold_end':k,'kind':kind,'obs_first5_above':obsA,'obs_last5_below':obsB,'expected_above_local':ea,'expected_below_local':eb,'excess_ratio_above':obsA/ea-1 if ea>0 else None,'excess_ratio_below':obsB/eb-1 if eb>0 else None,'asymmetry':(obsA/ea-1)-(obsB/eb-1) if ea>0 and eb>0 else None,'count_at_end':c.get(k,0),'count_first_above':c.get(k+1,0)})
    write_csv(out/'bunching_core.csv',rows);return rows


def crossing(con,panel,out):
    rows=[]
    for a,b in zip(YEARS[:-1],YEARS[1:]):
      d=con.execute(f"SELECT x.enrol x0,y.enrol x1 FROM read_parquet({lit(str(panel))}) x JOIN read_parquet({lit(str(panel))}) y ON x.pseudocode=y.pseudocode AND y.academic_year={lit(b)} WHERE x.academic_year={lit(a)} AND x.management IN {GOV}").df()
      for k,kind in [(250,'true'),(200,'pseudo'),(300,'pseudo')]:
        z=d[(d.x0>=k-20)&(d.x0<=k)]; rows.append({'from_year':a,'to_year':b,'threshold_end':k,'kind':kind,'n':len(z),'land_first5_above':float(((z.x1>=k+1)&(z.x1<=k+5)).mean()) if len(z) else None,'land_last5_below':float(((z.x1>=k-5)&(z.x1<=k-1)).mean()) if len(z) else None,'cross_above':float((z.x1>=k+1).mean()) if len(z) else None})
    write_csv(out/'crossing_core.csv',rows);return rows


def main():
    out=Path('studies/composite_school_grant/outputs/timing_core');shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    panel=build(con,os.environ['HF_DATASET_REPO'],os.environ['HF_TOKEN'],out);tr,meta=timing(con,panel,out);br=bunch(con,panel,out);cr=crossing(con,panel,out)
    lines=['# Timing core results','','Primary threshold coordinate: 250.5.','', '## Pooled publication-grade receipt >= 75k first stage by lag']
    for r in sorted(meta,key=lambda x:x['lag']):lines.append(f"- lag {r['lag']:+d}: {100*r['tau_ivw']:.2f} pp (95% CI {100*r['ci_low']:.2f} to {100*r['ci_high']:.2f}), {r['cohorts']} cohorts")
    b250=[r for r in br if r['threshold_end']==250 and r['kind']=='true'];lines+=['','## 250/251 distribution diagnostics'];
    for r in b250:lines.append(f"- {r['year']}: first-5-above excess ratio {r['excess_ratio_above']:.3f}; below ratio {r['excess_ratio_below']:.3f}; asymmetry {r['asymmetry']:.3f}; count251 {r['count_first_above']}")
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8');print('\n'.join(lines),flush=True);con.close()

if __name__=='__main__':main()
