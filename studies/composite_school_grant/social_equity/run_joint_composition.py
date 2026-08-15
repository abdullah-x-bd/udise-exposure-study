from __future__ import annotations

import csv, json, os, runpy, shutil, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_joint_social_lib')
YEARS=S['YEARS']; build_composition_year=S['build_composition_year']; load_financial_year=S['load_financial_year']; lit=S['lit']
weighted_demean=S['weighted_demean']; cluster_fit=S['cluster_fit']; government_universe=S['government_universe']; BROAD_STATE=S['BROAD_STATE']
SOCIAL=['sc','st','obc']  # General is reference.
RELIG=['muslim','christian','sikh','buddhist','parsi','jain']  # residual religion share is reference.


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)


def fit_joint(df,groups,cutoff,bw,fe,source):
    cols=[(f'prev_{g}_share' if source=='previous' else f'{g}_share') for g in groups]
    d=df.copy()
    keep=np.isfinite(d.receipt)&np.isfinite(d.enrol)
    for c in cols: keep &= np.isfinite(d[c])
    d=d[keep & (np.abs(d.enrol-cutoff)<=bw)].copy()
    if len(d)<1500:return [],None
    d['T']=(d.enrol>=cutoff).astype(float);d['z']=d.enrol-cutoff;d['Tz']=d.T*0
    d['Tz']=d['T']*d['z'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/bw)
    base=['y','T','z','Tz']; xcols=['T','z','Tz']; inter=[]
    for g,c in zip(groups,cols):
        s='S_'+g;ts='TS_'+g;zs='zS_'+g;tzs='TzS_'+g
        d[s]=d[c].astype(float);d[ts]=d['T']*d[s];d[zs]=d['z']*d[s];d[tzs]=d['T']*d['z']*d[s]
        base += [s,ts,zs,tzs];xcols += [s,ts,zs,tzs];inter.append(ts)
    for b in ('management','rural_urban','school_category'):
        v=pd.to_numeric(d[b],errors='coerce').fillna(-999).astype(int);cats=sorted(v.unique())
        for c in cats[1:]:
            n=f'cv_{b}_{c}';d[n]=(v==c).astype(float);base.append(n);xcols.append(n)
    if fe=='state_year':d['fe']=d.state.astype(str)+'|'+d.assignment_year.astype(str)
    else:d['fe']=d.state.astype(str)+'|'+d.district.astype(str)+'|'+d.assignment_year.astype(str)
    d=weighted_demean(d,base,'fe','w')
    fit=cluster_fit(d[xcols].to_numpy(float),d.y.to_numpy(float),d.w.to_numpy(float),d.state.astype(str).to_numpy())
    if fit is None:return [],None
    out=[]
    for g,ts in zip(groups,inter):
        j=xcols.index(ts);coef=float(fit.params[j]);se=float(fit.bse[j]);p=float(fit.pvalues[j])
        out.append({'group':g,'coef_per_10pp':coef*.1,'se_per_10pp':se*.1,'p':p,'ci_low_per_10pp':(coef-1.96*se)*.1,'ci_high_per_10pp':(coef+1.96*se)*.1,'n':int(fit.nobs),'states':int(d.state.nunique())})
    idx=[xcols.index(x) for x in inter]
    b=np.asarray(fit.params)[idx];V=np.asarray(fit.cov_params())[np.ix_(idx,idx)]
    try:
        stat=float(b@np.linalg.pinv(V)@b);dfn=len(idx)
        from scipy.stats import chi2
        jp=float(chi2.sf(stat,dfn))
    except Exception:stat=np.nan;dfn=len(idx);jp=np.nan
    return out,{'joint_wald_chi2':stat,'joint_df':dfn,'joint_p':jp,'n':int(fit.nobs),'states':int(d.state.nunique())}


def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN']
    out=Path(f'studies/composite_school_grant/outputs/social_equity_joint/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'joint_{ay}_') as td:
        root=Path(td);cp,dc=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,dp=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True)
        all_groups=['general','sc','st','obc','muslim','christian','sikh','buddhist','parsi','jain','non_listed_minority_religion']
        prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in all_groups)
        local=out/'local.parquet'
        con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,f.expenditure,{prevcols} FROM read_parquet({lit(str(cp))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode) WHERE a.enrol BETWEEN 150 AND 351) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();d=d[government_universe(d.management,BROAD_STATE)].copy();rows=[];joint=[]
    for family,groups in [('social_category',SOCIAL),('religion',RELIG)]:
        for source in ('previous','assignment'):
            for cutoff,label in [(250.5,'true_250'),(200.5,'placebo_200'),(300.5,'placebo_300')]:
                bw=30 if cutoff==250.5 else 20
                for fe in ('state_year','district_year'):
                    rr,j=fit_joint(d,groups,cutoff,bw,fe,source)
                    for r in rr:rows.append({'assignment_year':ay,'report_year':ry,'family':family,'source':source,'cutoff':cutoff,'cutoff_label':label,'fe':fe,**r})
                    if j:joint.append({'assignment_year':ay,'report_year':ry,'family':family,'source':source,'cutoff':cutoff,'cutoff_label':label,'fe':fe,**j})
    write_csv(out/'joint_coefficients.csv',rows);write_csv(out/'joint_tests.csv',joint);(out/'validation.json').write_text(json.dumps({'assignment':dc,'previous':dp},indent=2,default=float),encoding='utf-8')
    pref=[r for r in rows if r['source']=='previous' and r['cutoff_label']=='true_250' and r['fe']=='district_year']
    lines=[f'# Joint compositional CSG heterogeneity {ay}','', 'General is the omitted social-category reference. Residual/non-listed-minority religion share is the omitted religion reference.','']
    for r in pref:lines.append(f"- {r['family']} {r['group']}: {100*r['coef_per_10pp']:+.3f} pp per +10pp relative share (95% CI {100*r['ci_low_per_10pp']:+.3f} to {100*r['ci_high_per_10pp']:+.3f}), p={r['p']:.4g}")
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8');print('\n'.join(lines),flush=True);con.close()

if __name__=='__main__':main()
