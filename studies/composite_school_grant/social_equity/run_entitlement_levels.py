from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb, numpy as np, pandas as pd, statsmodels.api as sm
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_entitlement_lib')
YEARS=S['YEARS'];GROUPS=S['GROUPS'];build_composition_year=S['build_composition_year'];load_financial_year=S['load_financial_year'];lit=S['lit'];government_universe=S['government_universe'];BROAD_STATE=S['BROAD_STATE'];weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
SOCIAL=['general','sc','st','obc']

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def target(e):
    e=np.asarray(e,float)
    return np.select([(e>=31)&(e<=100),(e>=101)&(e<=250),(e>=251)&(e<=1000),e>1000],[25000.,50000.,75000.,100000.],default=np.nan)

def summarize(x,label,family='religion',group='muslim'):
    if len(x)==0:return None
    rec=pd.to_numeric(x.receipt,errors='coerce');obs=rec.notna();xo=x.loc[obs].copy();r=rec.loc[obs]
    out={'family':family,'group':group,'category':label,'n_total':len(x),'n_observed':int(obs.sum()),'receipt_observed_rate':float(obs.mean())}
    if len(r):
        rat=r/xo.target;cap=float(rat.quantile(.99));out.update({'positive_rate':float((r>0).mean()),'meet_target_rate':float((r>=xo.target).mean()),'exact_target_rate':float((r==xo.target).mean()),'mean_target_ratio_w99':float(rat.clip(upper=cap).mean()),'median_target_ratio':float(rat.median()),'mean_receipt_w99':float(r.clip(upper=float(r.quantile(.99))).mean())})
    return out

def overlap_cells(x):
    x=x.copy();x=x[x.prev_muslim_share!=.5];x['maj']=(x.prev_muslim_share>.5).astype(int);x['cell']=x.assignment_year.astype(str)+'|'+x.state.astype(str)+'|'+x.district.astype(str)+'|'+x.target.astype(int).astype(str);rows=[]
    for cell,g in x.groupby('cell'):
        a=g[g.maj==1];b=g[g.maj==0]
        if len(a)<5 or len(b)<5:continue
        ya=a.meet_target.dropna();yb=b.meet_target.dropna()
        if len(ya)<5 or len(yb)<5:continue
        p=cell.split('|');rows.append({'cell':cell,'year':p[0],'state':p[1],'district':p[2],'target':int(p[3]),'n_majority':len(ya),'n_nonmajority':len(yb),'rate_majority':float(ya.mean()),'rate_nonmajority':float(yb.mean())})
    return rows

def standardized(rows):
    if not rows:return []
    z=pd.DataFrame(rows);out=[]
    for method,w in [('equal_cells',np.ones(len(z))),('min_overlap',np.minimum(z.n_majority,z.n_nonmajority).to_numpy(float)),('harmonic_overlap',(2*z.n_majority*z.n_nonmajority/(z.n_majority+z.n_nonmajority)).to_numpy(float))]:
        w=np.asarray(w,float);w=w/w.sum();pm=float(np.sum(w*z.rate_majority));pn=float(np.sum(w*z.rate_nonmajority));out.append({'standardization':method,'cells':len(z),'states':z.state.nunique(),'districts':z.district.nunique(),'muslim_majority_rate':pm,'non_muslim_majority_rate':pn,'difference':pm-pn})
    return out

def continuous_model(x):
    # Within district x target-band comparison across all four cohorts handled one cohort at a time here.
    d=x[np.isfinite(x.prev_muslim_share)&np.isfinite(x.meet_target)].copy()
    if len(d)<2000:return None
    d['S']=d.prev_muslim_share.astype(float);d['z_band']=0.0;d['w']=1.0;d['y']=d.meet_target.astype(float);d['fe']=d.district.astype(str)+'|'+d.target.astype(int).astype(str)
    base=['y','S']
    for b in ('management','rural_urban','school_category'):
        v=pd.to_numeric(d[b],errors='coerce').fillna(-999).astype(int);cats=sorted(v.unique())
        for c in cats[1:]:n=f'cv_{b}_{c}';d[n]=(v==c).astype(float);base.append(n)
    d=weighted_demean(d,base,'fe','w');xcols=['S']+[c for c in base if c.startswith('cv_')]
    fit=cluster_fit(d[xcols].to_numpy(float),d.y.to_numpy(float),d.w.to_numpy(float),d.state.astype(str).to_numpy())
    if fit is None:return None
    b=float(fit.params[0]);se=float(fit.bse[0]);p=float(fit.pvalues[0]);return {'coef_per_10pp':b*.1,'se_per_10pp':se*.1,'p':p,'ci_low_per_10pp':(b-1.96*se)*.1,'ci_high_per_10pp':(b+1.96*se)*.1,'n':int(fit.nobs),'states':d.state.astype(str).nunique(),'district_band_fe':d.fe.nunique()}

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_entitlement/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'ent_{ay}_') as td:
        root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd0=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d.prev_muslim_share=pd.to_numeric(d.prev_muslim_share,errors='coerce');d['target']=target(d.enrol);d=d[np.isfinite(d.target)&np.isfinite(d.prev_muslim_share)].copy();rec=pd.to_numeric(d.receipt,errors='coerce');d['meet_target']=np.where(rec.notna(),(rec>=d.target).astype(float),np.nan)
    rows=[];m=d.prev_muslim_share>.5;n=d.prev_muslim_share<.5
    for label,mask in [('muslim_majority',m),('non_muslim_majority',n),('muslim_75plus',d.prev_muslim_share>=.75),('muslim_90plus',d.prev_muslim_share>=.9)]:
        r=summarize(d.loc[mask],label)
        if r:rows.append(r)
    for g in SOCIAL:
        s=pd.to_numeric(d[f'prev_{g}_share'],errors='coerce')
        for label,mask in [(f'{g}_majority',s>.5),(f'non_{g}_majority',s<.5)]:
            r=summarize(d.loc[mask],label,'social_category',g)
            if r:rows.append(r)
    binrows=[]
    cuts=[0,.10,.25,.50,.75,.90,1.0000001]
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        x=d[(d.prev_muslim_share>=lo)&(d.prev_muslim_share<hi)];r=summarize(x,f'{int(lo*100)}-{100 if hi>1 else int(hi*100)}pct')
        if r:r['share_low']=lo;r['share_high']=min(1,hi);binrows.append(r)
    cells=overlap_cells(d);std=standardized(cells);cm=continuous_model(d)
    for collection in (rows,binrows,std,cells):
        for r in collection:r['assignment_year']=ay;r['report_year']=ry
    if cm:cm.update({'assignment_year':ay,'report_year':ry})
    write_csv(out/'band_normalized_levels.csv',rows);write_csv(out/'band_normalized_muslim_bins.csv',binrows);write_csv(out/'band_district_overlap_cells.csv',cells);write_csv(out/'band_district_standardized.csv',std);write_csv(out/'band_continuous_model.csv',[cm] if cm else []);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd0,'assignment_year':ay,'report_year':ry,'n_gt30':len(d)},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'n':len(d),'cells':len(cells),'continuous':cm},indent=2,default=float))
if __name__=='__main__':main()
