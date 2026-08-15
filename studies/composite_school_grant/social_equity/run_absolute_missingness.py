from __future__ import annotations
import csv,json,os,runpy,shutil,tempfile
from pathlib import Path
import duckdb, numpy as np, pandas as pd
S=runpy.run_path('studies/composite_school_grant/social_equity/run_social_equity.py',run_name='csg_abs_missing_lib')
YEARS=S['YEARS']; GROUPS=S['GROUPS']; build_composition_year=S['build_composition_year']; load_financial_year=S['load_financial_year']; lit=S['lit']; government_universe=S['government_universe']; BROAD_STATE=S['BROAD_STATE']

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def stats(x,scope,label,target=None):
    if len(x)==0:return None
    rec=pd.to_numeric(x.receipt,errors='coerce');obs=rec.notna();n=len(x);no=int(obs.sum())
    r={'scope':scope,'category':label,'n_total':int(n),'n_receipt_observed':no,'receipt_observed_rate':float(obs.mean()),'states':int(x.state.astype(str).nunique()),'districts':int(x.district.astype(str).nunique())}
    if no:
        rr=rec[obs];r['positive_among_observed']=float((rr>0).mean());r['positive_treat_missing_zero']=float(((rec.fillna(0)>0)).mean())
        if target is not None:
            r['target']=target;r['ge_target_among_observed']=float((rr>=target).mean());r['ge_target_treat_missing_zero']=float((rec.fillna(0)>=target).mean())
    return r

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];ry=YEARS[ai+3];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/social_equity_missingness/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'miss_{ay}_') as td:
        root=Path(td);ap,ad=build_composition_year(con,repo,tok,ay,root,out);shutil.rmtree(root/ay,ignore_errors=True);pp,pd=build_composition_year(con,repo,tok,prev,root,out);shutil.rmtree(root/prev,ignore_errors=True);fp=load_financial_year(con,repo,tok,ry,root,out);shutil.rmtree(root/ry,ignore_errors=True);prevcols=','.join(f'p.{g}_share prev_{g}_share' for g in GROUPS);local=out/'analysis.parquet';con.execute(f"COPY (SELECT a.*,{lit(ay)} assignment_year,{lit(ry)} report_year,f.receipt,{prevcols} FROM read_parquet({lit(str(ap))}) a LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode) LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    d=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df();con.close();d=d[government_universe(d.management,BROAD_STATE)].copy();d.enrol=pd.to_numeric(d.enrol,errors='coerce');d.prev_muslim_share=pd.to_numeric(d.prev_muslim_share,errors='coerce');d=d[np.isfinite(d.enrol)&np.isfinite(d.prev_muslim_share)].copy()
    scopes={'full_universe':(d,None),'lower_band_221_250':(d[(d.enrol>=221)&(d.enrol<=250)],50000),'upper_band_251_280':(d[(d.enrol>=251)&(d.enrol<=280)],75000)};rows=[];states=[]
    for scope,(x,target) in scopes.items():
        m=x.prev_muslim_share>.5;n=x.prev_muslim_share<.5;tie=x.prev_muslim_share==.5
        for label,mask in [('muslim_majority',m),('non_muslim_majority',n),('exact_50_50',tie),('muslim_75plus',x.prev_muslim_share>=.75),('muslim_90plus',x.prev_muslim_share>=.9)]:
            r=stats(x.loc[mask],scope,label,target)
            if r:rows.append({'assignment_year':ay,'report_year':ry,**r})
        for state,g in x.groupby('state'):
            mm=g.prev_muslim_share>.5;nn=g.prev_muslim_share<.5
            if mm.sum()<20 or nn.sum()<50:continue
            for label,mask in [('muslim_majority',mm),('non_muslim_majority',nn)]:
                r=stats(g.loc[mask],scope,label,target)
                if r:states.append({'assignment_year':ay,'report_year':ry,'state':str(state),**r})
    write_csv(out/'missingness_and_rates.csv',rows);write_csv(out/'state_missingness_and_rates.csv',states);(out/'validation.json').write_text(json.dumps({'assignment':ad,'previous':pd,'assignment_year':ay,'report_year':ry},indent=2,default=float),encoding='utf-8');print(json.dumps({'assignment_year':ay,'rows':len(rows),'state_rows':len(states)},indent=2))
if __name__=='__main__':main()
