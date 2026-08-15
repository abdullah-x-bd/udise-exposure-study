from __future__ import annotations
import csv,json,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='response_time_panel')
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='response_time_stats')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
weighted_demean=S['weighted_demean'];cluster_fit=S['cluster_fit']
BROAD={1,2,3,6,89,90};CUT=250.5;BW=30

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def field(c,names,a='p'):
    for k in names:
        r=ref(c,k,a)
        if r:return r
    return None

def write_csv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def rd_state(d):
    d=d[np.isfinite(d.receipt)&np.isfinite(d.enrol)&(np.abs(d.enrol-CUT)<=BW)].copy()
    if len(d)<300:return None
    d['T']=(d.enrol>=CUT).astype(float);d['z']=d.enrol-CUT;d['Tz']=d['T']*d['z'];d['y']=(d.receipt>=75000).astype(float);d['w']=np.maximum(0,1-np.abs(d.z)/BW);d['fe']=d.district.astype(str)
    if d.fe.nunique()<5:return None
    raw_left=d[(d.enrol>=241)&(d.enrol<=250)].y.mean();raw_right=d[(d.enrol>=251)&(d.enrol<=260)].y.mean()
    dm=weighted_demean(d,['y','T','z','Tz'],'fe','w');fit=cluster_fit(dm[['T','z','Tz']].to_numpy(float),dm.y.to_numpy(float),dm.w.to_numpy(float),dm.district.astype(str).to_numpy())
    if fit is None:return None
    return {'tau':float(fit.params[0]),'se':float(fit.bse[0]),'p':float(fit.pvalues[0]),'n':int(fit.nobs),'districts':int(d.fe.nunique()),'raw_left_241_250':float(raw_left),'raw_right_251_260':float(raw_right),'raw_gap':float(raw_right-raw_left)}

def thresholds(g,value='tau'):
    g=g.sort_values('lag');vals=np.maximum(g[value].to_numpy(float),0);lags=g.lag.to_numpy(int)
    peak=float(np.nanmax(vals)) if len(vals) else np.nan
    out={'peak_'+value:peak,'peak_lag':int(lags[np.nanargmax(vals)]) if len(vals) and np.isfinite(peak) else None}
    for q in (.5,.8,.9):
        target=q*peak if np.isfinite(peak) else np.nan;hit=lags[vals>=target] if np.isfinite(target) and peak>0 else np.array([],int);out[f'first_lag_{int(q*100)}pct_peak']=int(hit[0]) if len(hit) else None
    for q in (.5,.8,.9,.95,1.0):
        hit=g.loc[g.raw_right_251_260>=q,'lag'].to_numpy(int);out[f'first_lag_raw_right_{int(q*100)}pct']=int(hit[0]) if len(hit) else None
    return out

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/state_response_time/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'response_{ay}_') as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));ec,pc=cols(con,en),cols(con,p1);ei,pi=ident(ec),ident(pc);f=efilt(con,en,ec);es=esum(ec);st=field(pc,['state','state_id','state_code','state_cd']);dist=field(pc,['district','district_id','district_code','district_cd']);mg=nref(pc,'managment','p')
        if not st or not dist:raise RuntimeError('state/district missing')
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,CAST(SUM({es}) AS DOUBLE) enrol FROM {en} WHERE {f} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE base AS SELECT e.pseudocode,e.enrol,CAST(p.{qid(pi)} AS VARCHAR) pid,CAST(p.{qid(pi)} AS VARCHAR) pkey,CAST({st} AS VARCHAR) state,CAST({dist} AS VARCHAR) district,CAST({mg} AS INTEGER) management FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE e.enrol BETWEEN 220 AND 281")
        base=con.execute('SELECT pseudocode,enrol,state,district,management FROM base').df();base=base[base.management.isin(BROAD)].copy()
        rows=[]
        for oi in range(ai,min(len(YEARS),ai+7)):
            oy=YEARS[oi];lag=oi-ai;p2=src(extract(repo,tok,oy,'profile_2',root));gc=cols(con,p2);gi=ident(gc);gr=nref(gc,'grants_receipt');fin=con.execute(f"SELECT CAST({qid(gi)} AS VARCHAR) pseudocode,CAST({gr} AS DOUBLE) receipt FROM {p2}").df();d=base.merge(fin,on='pseudocode',how='left')
            nat=rd_state(d.assign(district=d.state.astype(str)+'|'+d.district.astype(str)))
            if nat:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'scope':'national','state':'ALL',**nat})
            for state,z in d.groupby('state'):
                r=rd_state(z)
                if r:rows.append({'assignment_year':ay,'outcome_year':oy,'lag':lag,'scope':'state','state':str(state),**r})
        con.close()
    write_csv(out/'dynamic_state_response.csv',rows);df=pd.DataFrame(rows);summary=[]
    if len(df):
        for (scope,state),g in df[df.lag>=0].groupby(['scope','state']):summary.append({'assignment_year':ay,'scope':scope,'state':state,'lags_available':','.join(map(str,sorted(g.lag.unique()))),**thresholds(g)})
    write_csv(out/'response_time_summary.csv',summary)
    (out/'RESULTS.md').write_text('# State response time '+ay+'\n\nThis replaces a simple maximum-lag interpretation with a full dynamic curve. `first_lag_80pct_peak` is relative to each state/cohort observed response peak; absolute raw-right thresholds are reported separately and may never be reached.\n\n```json\n'+json.dumps(summary,indent=2,default=float)+'\n```\n',encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True)
if __name__=='__main__':main()
