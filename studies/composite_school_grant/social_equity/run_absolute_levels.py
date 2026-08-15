from __future__ import annotations

import csv, json, os, runpy, shutil, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

S = runpy.run_path(
    'studies/composite_school_grant/social_equity/run_social_equity.py',
    run_name='csg_absolute_levels_lib',
)
YEARS=S['YEARS']; GROUPS=S['GROUPS']; build_composition_year=S['build_composition_year']; load_financial_year=S['load_financial_year']; lit=S['lit']; government_universe=S['government_universe']; BROAD_STATE=S['BROAD_STATE']

SOCIAL=['general','sc','st','obc']
RELIG=['muslim','christian','sikh','buddhist','parsi','jain']


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8'); return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)


def qstats(d, scope, family, group, label, mask, target=None):
    x=d.loc[mask].copy()
    if len(x)==0: return None
    rec=pd.to_numeric(x.receipt,errors='coerce')
    keep=rec.notna(); x=x.loc[keep]; rec=rec.loc[keep]
    if len(x)==0: return None
    p99=float(rec.quantile(.99)) if len(rec)>10 else float(rec.max())
    rw=rec.clip(upper=p99)
    out={
        'scope':scope,'family':family,'group':group,'category':label,'n':int(len(x)),
        'states':int(x.state.astype(str).nunique()),'districts':int(x.district.astype(str).nunique()),
        'receipt_positive_rate':float((rec>0).mean()),
        'mean_receipt':float(rec.mean()),'median_receipt':float(rec.median()),
        'mean_receipt_w99':float(rw.mean()),'p99_receipt':p99,
    }
    if target is not None:
        out['target']=target
        out['receipt_ge_target_rate']=float((rec>=target).mean())
        out['receipt_exact_target_rate']=float((rec==target).mean())
        out['mean_receipt_target_ratio_w99']=float((rw/target).mean())
    return out


def majority_rows(d, scope, target=None):
    rows=[]
    # Religion: Muslim-majority vs not Muslim-majority. This is NOT Hindu-majority.
    m=d.prev_muslim_share>=.5
    for label,mask in [('muslim_majority',m),('not_muslim_majority',~m),('muslim_75plus',d.prev_muslim_share>=.75),('muslim_90plus',d.prev_muslim_share>=.90)]:
        r=qstats(d,scope,'religion','muslim',label,mask,target)
        if r: rows.append(r)
    # Social-category majorities. These are separate from religion.
    for g in SOCIAL:
        s=d[f'prev_{g}_share']
        for label,mask in [(f'{g}_majority',s>=.5),(f'not_{g}_majority',s<.5),(f'{g}_75plus',s>=.75)]:
            r=qstats(d,scope,'social_category',g,label,mask,target)
            if r: rows.append(r)
    return rows


def muslim_bins(d, scope, target=None):
    cuts=[0,.10,.25,.50,.75,.90,1.0000001]
    rows=[]
    s=d.prev_muslim_share
    for i in range(len(cuts)-1):
        lo,hi=cuts[i],cuts[i+1]
        mask=(s>=lo)&(s<hi)
        label=f'{int(lo*100)}-{100 if hi>1 else int(hi*100)}pct'
        r=qstats(d,scope,'religion','muslim',label,mask,target)
        if r:
            r['share_low']=lo; r['share_high']=min(1,hi); rows.append(r)
    return rows


def district_overlap_standardized(d, outcome, scope):
    # Compare majority/non-majority only inside district cells containing BOTH groups.
    # Equal cell weighting avoids national composition being driven entirely by large states.
    x=d.copy(); x['maj']=(x.prev_muslim_share>=.5).astype(int)
    x['cell']=x.assignment_year.astype(str)+'|'+x.state.astype(str)+'|'+x.district.astype(str)
    rows=[]
    for cell,g in x.groupby('cell'):
        a=g[g.maj==1]; b=g[g.maj==0]
        if len(a)<5 or len(b)<5: continue
        ya=pd.to_numeric(a[outcome],errors='coerce').dropna(); yb=pd.to_numeric(b[outcome],errors='coerce').dropna()
        if len(ya)<5 or len(yb)<5: continue
        rows.append({'cell':cell,'n_majority':len(ya),'n_nonmajority':len(yb),'rate_majority':float(ya.mean()),'rate_nonmajority':float(yb.mean())})
    if not rows: return None,[]
    z=pd.DataFrame(rows)
    # Three transparent standardizations: equal district cells; overlap-min; harmonic-overlap.
    outs=[]
    for method,w in [
        ('equal_district_cells',np.ones(len(z))),
        ('min_overlap',np.minimum(z.n_majority,z.n_nonmajority).to_numpy(float)),
        ('harmonic_overlap',(2*z.n_majority*z.n_nonmajority/(z.n_majority+z.n_nonmajority)).to_numpy(float)),
    ]:
        w=np.asarray(w,float); w=w/w.sum()
        pm=float(np.sum(w*z.rate_majority)); pn=float(np.sum(w*z.rate_nonmajority))
        outs.append({'scope':scope,'outcome':outcome,'standardization':method,'district_cells':int(len(z)),'muslim_majority_rate':pm,'not_muslim_majority_rate':pn,'difference':pm-pn,'majority_n_in_overlap_cells':int(z.n_majority.sum()),'nonmajority_n_in_overlap_cells':int(z.n_nonmajority.sum())})
    return outs,z.to_dict('records')


def state_muslim_rows(d, scope, target=None):
    rows=[]
    for state,g in d.groupby('state'):
        m=g.prev_muslim_share>=.5
        if m.sum()<20 or (~m).sum()<50: continue
        for label,mask in [('muslim_majority',m),('not_muslim_majority',~m)]:
            r=qstats(g,scope,'religion','muslim',label,mask,target)
            if r:
                r['state']=str(state); rows.append(r)
    return rows


def main():
    ay=os.environ['ASSIGN_YEAR']; ai=YEARS.index(ay); prev=YEARS[ai-1]; ry=YEARS[ai+3]
    repo=os.environ['HF_DATASET_REPO']; tok=os.environ['HF_TOKEN']
    out=Path(f'studies/composite_school_grant/outputs/social_equity_absolute/{ay}'); out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(); con.execute('PRAGMA threads=4'); con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'abs_{ay}_') as td:
        root=Path(td)
        ap,adiag=build_composition_year(con,repo,tok,ay,root,out); shutil.rmtree(root/ay,ignore_errors=True)
        pp,pdiag=build_composition_year(con,repo,tok,prev,root,out); shutil.rmtree(root/prev,ignore_errors=True)
        fp=load_financial_year(con,repo,tok,ry,root,out); shutil.rmtree(root/ry,ignore_errors=True)
        prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS)
        local=out/'analysis.parquet'
        con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,f.expenditure,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df(); con.close()
    d=d[government_universe(d.management,BROAD_STATE)].copy()
    for c in ['enrol','receipt','prev_muslim_share']+[f'prev_{g}_share' for g in SOCIAL]: d[c]=pd.to_numeric(d[c],errors='coerce')
    d=d[np.isfinite(d.enrol)&np.isfinite(d.prev_muslim_share)].copy()
    d['receipt_positive']=(pd.to_numeric(d.receipt,errors='coerce')>0).astype(float)
    d['receipt_ge_75k']=(pd.to_numeric(d.receipt,errors='coerce')>=75000).astype(float)
    d['receipt_ge_50k']=(pd.to_numeric(d.receipt,errors='coerce')>=50000).astype(float)

    scopes={
        'full_universe':(d,None),
        'lower_band_221_250':(d[(d.enrol>=221)&(d.enrol<=250)].copy(),50000),
        'upper_band_251_280':(d[(d.enrol>=251)&(d.enrol<=280)].copy(),75000),
    }
    levels=[]; bins=[]; state=[]; std=[]; overlap=[]
    for scope,(x,target) in scopes.items():
        levels += majority_rows(x,scope,target)
        bins += muslim_bins(x,scope,target)
        state += state_muslim_rows(x,scope,target)
        if scope=='full_universe':
            o,rr=district_overlap_standardized(x,'receipt_positive',scope)
        elif target==75000:
            o,rr=district_overlap_standardized(x,'receipt_ge_75k',scope)
        else:
            o,rr=district_overlap_standardized(x,'receipt_ge_50k',scope)
        if o: std += o
        for r in rr: overlap.append({'scope':scope,**r})

    for r in levels+bins+state+std: r['assignment_year']=ay; r['report_year']=ry
    write_csv(out/'absolute_group_levels.csv',levels)
    write_csv(out/'muslim_share_level_bins.csv',bins)
    write_csv(out/'state_muslim_majority_levels.csv',state)
    write_csv(out/'district_overlap_standardized.csv',std)
    write_csv(out/'district_overlap_cells.csv',overlap)
    (out/'validation.json').write_text(json.dumps({'assignment':adiag,'previous':pdiag,'assignment_year':ay,'previous_year':prev,'report_year':ry,'broad_state_n':len(d)},indent=2,default=float),encoding='utf-8')
    print(json.dumps({'assignment_year':ay,'report_year':ry,'n':len(d),'level_rows':len(levels),'bin_rows':len(bins),'state_rows':len(state),'standardized_rows':len(std)},indent=2),flush=True)

if __name__=='__main__': main()
