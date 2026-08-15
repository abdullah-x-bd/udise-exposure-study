from __future__ import annotations

import csv, json, os, runpy, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from rdrobust import rdrobust

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='fuzzy_panel_lib')
C=runpy.run_path('studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py',run_name='fuzzy_confirm_lib')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
component_exprs=C['component_exprs'];total_enrolment_setup=C['total_enrolment_setup']
YEARS=P['YEARS'];CUT=250.5;GOV='(1,2,3)'
ASSETS=['water_functional','handwash_meal','electricity','internet','library','ramps','handrails','girls_toilet_full','boys_toilet_full']


def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('school identifier missing')
    return x


def cluster_expr(c,alias):
    for name in ('state','state_id','state_code','state_cd'):
        r=ref(c,name,alias)
        if r:return f"CAST({r} AS VARCHAR)"
    for name in ('district','district_id','district_code','district_cd'):
        r=ref(c,name,alias)
        if r:return f"'district:' || CAST({r} AS VARCHAR)"
    raise RuntimeError('no usable cluster field')


def e8expr(c):
    q=[f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,9) for s in ('b','g') if f'c{k}_{s}' in c]
    return ' + '.join(q)


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)


def pull_last(r,attr):
    a=np.asarray(getattr(r,attr),dtype=float)
    if attr=='ci':return a.reshape(-1,2)[-1].tolist()
    return float(a.reshape(-1)[-1])


def fit(y,x,d,state,fuzzy=False):
    state=pd.Series(state,dtype='object')
    m=np.isfinite(y)&np.isfinite(x)&np.isfinite(d)&state.notna().to_numpy()&(np.abs(x-CUT)<=30)
    y=y[m];x=x[m];d=d[m];state=state.to_numpy()[m]
    if len(y)<500 or pd.Series(state).nunique()<10:return None
    kw=dict(y=y,x=x,c=CUT,p=1,q=2,kernel='tri',h=30,b=45,cluster=pd.Categorical(state).codes,vce='cr3',masspoints='adjust',bwcheck=15)
    if fuzzy:kw['fuzzy']=d
    r=rdrobust(**kw);ci=pull_last(r,'ci')
    return {'tau':pull_last(r,'coef'),'se':pull_last(r,'se'),'p':pull_last(r,'pv'),'ci_low':ci[0],'ci_high':ci[1],'n':len(y),'first_stage_mean_treatment':float(np.mean(d)),'clusters':int(pd.Series(state).nunique())}


def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay)
    grant_financial_year=YEARS[ai+2]
    report_year=YEARS[ai+3]
    future=YEARS[ai+3:]
    repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/fuzzy_rd/{ay}');out.mkdir(parents=True,exist_ok=True);rows=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'fuzzy_{ay}_') as td:
        root=Path(td)
        en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));fac=src(extract(repo,tok,ay,'facility',root));ec,pc,fc=cols(con,en),cols(con,p1),cols(con,fac);ei,pi,fi=ident(ec),ident(pc);es,filt,_=total_enrolment_setup(con,en,ec);e8=e8expr(ec);bc=component_exprs(fc,'f');ce=cluster_expr(pc,'p')
        bsel=','.join(f'{v} b_{k}' for k,v in bc.items() if k in ASSETS)
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) enrol,SUM({e8}) enrol18 FROM {en} WHERE {filt} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT e.pseudocode,e.enrol,e.enrol18,{ce} state,{bsel} FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {fac} f ON e.pseudocode=CAST(f.{qid(fi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 180 AND 321")
        gp=src(extract(repo,tok,report_year,'profile_2',root));gc=cols(con,gp);gi=ident(gc);con.execute(f"CREATE TEMP TABLE grant AS SELECT CAST({qid(gi)} AS VARCHAR) pseudocode,{nref(gc,'grants_receipt')} receipt FROM {gp}")
        for oy in future:
            of=src(extract(repo,tok,oy,'facility',root));oc=cols(con,of);oi=ident(oc);cc=component_exprs(oc,'o');osel=','.join(f'{v} o_{k}' for k,v in cc.items() if k in ASSETS)
            con.execute(f"CREATE OR REPLACE TEMP TABLE fut AS SELECT CAST({qid(oi)} AS VARCHAR) pseudocode,{osel} FROM {of}")
            d=con.execute('SELECT b.*,g.receipt,f.* EXCLUDE(pseudocode) FROM base b LEFT JOIN grant g USING(pseudocode) LEFT JOIN fut f USING(pseudocode)').df()
            rec=d.receipt.to_numpy(float);t=np.where(np.isfinite(rec),(rec>=75000).astype(float),np.nan)
            det=[];up=[]
            for _,r in d.iterrows():
                aa=[];bb=[]
                for k in ASSETS:
                    bv=r.get('b_'+k);ov=r.get('o_'+k)
                    if pd.isna(bv) or pd.isna(ov):continue
                    if bv>=.5:aa.append(1.0 if ov<.5 else 0.0)
                    else:bb.append(1.0 if ov>=.5 else 0.0)
                det.append(np.mean(aa) if aa else np.nan);up.append(np.mean(bb) if bb else np.nan)
            d['deterioration']=det;d['upgrade']=up
            for sample,mask in [('all',np.ones(len(d),bool)),('pm220',d.enrol18.fillna(99999).to_numpy(float)<=220),('pm200',d.enrol18.fillna(99999).to_numpy(float)<=200)]:
                z=d.loc[mask];tt=t[mask];x=z.enrol.to_numpy(float);st=z.state.to_numpy(dtype=object)
                for outcome in ['deterioration','upgrade']:
                    y=z[outcome].to_numpy(float)
                    m=np.isfinite(y)&np.isfinite(tt)
                    if m.sum()<500:continue
                    fs=fit(tt[m],x[m],tt[m],st[m],False)
                    rf=fit(y[m],x[m],tt[m],st[m],False)
                    fr=fit(y[m],x[m],tt[m],st[m],True)
                    common={'assignment_year':ay,'grant_financial_year':grant_financial_year,'udise_financial_report_year':report_year,'outcome_year':oy,'event_time_since_report_year':YEARS.index(oy)-YEARS.index(report_year),'sample':sample,'outcome':outcome}
                    if fs:rows.append({**common,'estimand':'first_stage_receipt_ge75000',**fs})
                    if rf:rows.append({**common,'estimand':'reduced_form_threshold',**rf})
                    if fr:rows.append({**common,'estimand':'fuzzy_RD_reported_high_receipt',**fr})
            print(json.dumps({'assignment':ay,'grant_financial_year':grant_financial_year,'report_year':report_year,'outcome_year':oy,'n':len(d),'clusters':int(d.state.nunique(dropna=True))}),flush=True)
    write(out/'fuzzy_results.csv',rows)
    md=['# Fuzzy RD sensitivity '+ay,'',f'Assignment enrolment {ay}; grant financial year {grant_financial_year}; UDISE field reporting that prior financial year is {report_year}.','', 'Treatment is UDISE-reported receipt >= Rs 75,000, not independently audited PFMS receipt.']
    for r in rows:
        if r['sample']=='all' and r['estimand']=='fuzzy_RD_reported_high_receipt':md.append(f"- {r['outcome_year']} {r['outcome']}: LATE {r['tau']:.4f} (95% CI {r['ci_low']:.4f} to {r['ci_high']:.4f}), p={r['p']:.4g}")
    (out/'RESULTS.md').write_text('\n'.join(md),encoding='utf-8');print('\n'.join(md),flush=True);con.close()

if __name__=='__main__':main()
