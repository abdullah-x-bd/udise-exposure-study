from __future__ import annotations

import csv
import json
import os
import runpy
import shutil
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

S = runpy.run_path(
    'studies/composite_school_grant/social_equity/run_social_equity.py',
    run_name='csg_social_fast_lib',
)

YEARS = S['YEARS']
GROUPS = S['GROUPS']
UNIVERSES = S['UNIVERSES']
build_composition_year = S['build_composition_year']
load_financial_year = S['load_financial_year']
rd_interaction = S['rd_interaction']
rd_level_in_bin = S['rd_level_in_bin']
government_universe = S['government_universe']
lit = S['lit']


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)


def main() -> None:
    ay=os.environ['ASSIGN_YEAR']
    ai=YEARS.index(ay)
    prev=YEARS[ai-1]
    ry=YEARS[ai+3]
    repo=os.environ['HF_DATASET_REPO']; token=os.environ['HF_TOKEN']
    out=Path(f'studies/composite_school_grant/outputs/social_equity_fast/{ay}')
    out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(); con.execute('PRAGMA threads=4'); con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'csg_social_fast_{ay}_') as td:
        root=Path(td)
        cp,dc=build_composition_year(con,repo,token,ay,root,out)
        shutil.rmtree(root/ay,ignore_errors=True)
        pp,dp=build_composition_year(con,repo,token,prev,root,out)
        shutil.rmtree(root/prev,ignore_errors=True)
        fp=load_financial_year(con,repo,token,ry,root,out)
        shutil.rmtree(root/ry,ignore_errors=True)
        prev_cols=','.join(f'p.{g}_share AS prev_{g}_share' for g in GROUPS)
        local=out/'local_cutoff.parquet'
        con.execute(f"""
          COPY (
            SELECT a.*, {lit(ay)} assignment_year, {lit(ry)} report_year,
                   f.receipt,f.expenditure,{prev_cols}
            FROM read_parquet({lit(str(cp))}) a
            LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode)
            LEFT JOIN read_parquet({lit(str(pp))}) p USING(pseudocode)
            WHERE a.enrol BETWEEN 220 AND 281
          ) TO {lit(str(local))} (FORMAT PARQUET,COMPRESSION ZSTD)
        """)
    d0=con.execute(f'SELECT * FROM read_parquet({lit(str(local))})').df()
    interactions=[]; bins=[]; counts=[]; balance=[]
    for uname,codes in UNIVERSES.items():
        d=d0[government_universe(d0.management,codes)].copy()
        counts.append({'assignment_year':ay,'report_year':ry,'universe':uname,'n_local':len(d),'unique_schools':int(d.pseudocode.nunique())})
        for g in GROUPS:
            for source,col in [('assignment',f'{g}_share'),('predetermined_previous_year',f'prev_{g}_share')]:
                for fe in ('state_year','district_year'):
                    for adjusted in (False,True):
                        r=rd_interaction(d,col,fe,adjusted)
                        if r: interactions.append({'assignment_year':ay,'report_year':ry,'universe':uname,'group':g,'composition_source':source,**r})
            # Covariate continuity check: does PREVIOUS-year composition itself jump at the current cutoff?
            col=f'prev_{g}_share'
            z=d[np.isfinite(d[col]) & np.isfinite(d.enrol)].copy()
            if len(z)>=1200:
                z['receipt_dummy_for_helper']=z[col]
                # Reuse local linear helper logic through a small weighted regression written here.
                z=z[np.abs(z.enrol-250.5)<=30].copy(); z['T']=(z.enrol>=250.5).astype(float); z['x']=z.enrol-250.5; z['Tx']=z.T*0
                z['Tx']=z['T']*z['x']; z['w']=np.maximum(0,1-np.abs(z['x'])/30)
                X=np.c_[np.ones(len(z)),z['T'],z['x'],z['Tx']]; y=z[col].to_numpy(float); w=z.w.to_numpy(float)
                try:
                    b=np.linalg.lstsq(X*np.sqrt(w)[:,None],y*np.sqrt(w),rcond=None)[0]
                    balance.append({'assignment_year':ay,'universe':uname,'group':g,'previous_share_jump':float(b[1]),'n':len(z)})
                except Exception: pass
            if uname=='broad_state':
                for b in range(20):
                    r=rd_level_in_bin(d,f'{g}_share',b,'state_year')
                    if r: bins.append({'assignment_year':ay,'group':g,**r})
    write_csv(out/'interactions.csv',interactions)
    write_csv(out/'bins_5pp.csv',bins)
    write_csv(out/'counts.csv',counts)
    write_csv(out/'previous_composition_balance.csv',balance)
    (out/'validation.json').write_text(json.dumps({'assignment':dc,'previous':dp},indent=2,default=float),encoding='utf-8')
    preferred=[r for r in interactions if r['universe']=='broad_state' and r['composition_source']=='predetermined_previous_year' and r['fe']=='district_year' and r['adjusted']]
    lines=[f'# Fast CSG social heterogeneity {ay}','',f'Financial report field: {ry}. Preferred rows are broad State/UT-government, previous-year composition, district fixed effects, adjusted.','']
    for r in sorted(preferred,key=lambda x:x['group']):
        lines.append(f"- {r['group']}: {100*r['interaction_per_10pp']:+.3f} pp per +10pp composition (95% CI {100*r['ci_low_per_10pp']:+.3f} to {100*r['ci_high_per_10pp']:+.3f}), p={r['p']:.4g}, n={r['n']}")
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8'); print('\n'.join(lines),flush=True)
    con.close()

if __name__=='__main__': main()
