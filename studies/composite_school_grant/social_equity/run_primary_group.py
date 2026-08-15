from __future__ import annotations

import csv, json, os, runpy, shutil, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

S = runpy.run_path(
    'studies/composite_school_grant/social_equity/run_social_equity.py',
    run_name='csg_social_group_lib',
)

YEARS=S['YEARS']; PRIMARY=S['PRIMARY_ASSIGNMENT_YEARS']; GROUPS=S['GROUPS']
UNIVERSES=S['UNIVERSES']; build_composition_year=S['build_composition_year']; load_financial_year=S['load_financial_year']
rd_interaction=S['rd_interaction']; rd_level_in_bin=S['rd_level_in_bin']; fidelity_gradient=S['fidelity_gradient']
state_descriptive_gradients=S['state_descriptive_gradients']; first_difference_panel=S['first_difference_panel']; fidelity_amount=S['fidelity_amount']; government_universe=S['government_universe']; lit=S['lit']


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8'); return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)


def main() -> None:
    group=os.environ['SOCIAL_GROUP'].strip().lower()
    if group not in GROUPS: raise RuntimeError(f'unknown group {group}; valid={GROUPS}')
    repo=os.environ['HF_DATASET_REPO']; token=os.environ['HF_TOKEN']
    out=Path(f'studies/composite_school_grant/outputs/social_equity_primary/{group}'); out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(); con.execute('PRAGMA threads=4'); con.execute("PRAGMA memory_limit='10GB'")
    cps={}; fps={}; validation=[]
    needed_comp=['2018-19','2019-20','2020-21','2021-22','2022-23']
    needed_fin=[YEARS[YEARS.index(y)+3] for y in PRIMARY]
    with tempfile.TemporaryDirectory(prefix=f'csg_social_{group}_') as td:
        root=Path(td)
        for y in needed_comp:
            p,d=build_composition_year(con,repo,token,y,root,out); cps[y]=p; validation.append(d); shutil.rmtree(root/y,ignore_errors=True)
        for y in needed_fin:
            fps[y]=load_financial_year(con,repo,token,y,root,out); shutil.rmtree(root/y,ignore_errors=True)
    (out/'composition_validation.json').write_text(json.dumps(validation,indent=2,default=float),encoding='utf-8')

    cohorts=[]
    gcol=f'{group}_share'; pgcol=f'prev_{group}_share'
    for ay in PRIMARY:
        ry=YEARS[YEARS.index(ay)+3]; prev=YEARS[YEARS.index(ay)-1]
        cp=cps[ay]; pp=cps[prev]; fp=fps[ry]
        cohort=out/f'cohort_{ay}.parquet'
        con.execute(f"""
          COPY (
            SELECT a.*, {lit(ay)} assignment_year, {lit(ry)} report_year,
                   f.receipt, f.expenditure, pr.{gcol} AS {pgcol}
            FROM read_parquet({lit(str(cp))}) a
            LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode)
            LEFT JOIN read_parquet({lit(str(pp))}) pr USING(pseudocode)
          ) TO {lit(str(cohort))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        cohorts.append(cohort)
    panel=out/'panel.parquet'
    con.execute(f"COPY (SELECT * FROM read_parquet([{','.join(lit(str(x)) for x in cohorts)}],union_by_name=true)) TO {lit(str(panel))} (FORMAT PARQUET,COMPRESSION ZSTD)")
    all_df=con.execute(f'SELECT * FROM read_parquet({lit(str(panel))})').df()

    interactions=[]; bins=[]; fidelity=[]; states=[]; fd=[]; counts=[]
    for uname,codes in UNIVERSES.items():
        d=all_df[government_universe(all_df.management,codes)].copy()
        counts.append({'group':group,'universe':uname,'school_year_rows':len(d),'unique_schools':int(d.pseudocode.nunique())})
        # Core pooled specifications.
        for source,col in [('assignment',gcol),('predetermined_previous_year',pgcol)]:
            for fe in ('year','state_year','district_year'):
                r=rd_interaction(d,col,fe,True)
                if r: interactions.append({'group':group,'universe':uname,'composition_source':source,'cohort':'pooled',**r})
            # Cohort-specific state-FE specifications to test replication.
            for ay in PRIMARY:
                r=rd_interaction(d[d.assignment_year==ay].copy(),col,'state_year',True)
                if r: interactions.append({'group':group,'universe':uname,'composition_source':source,'cohort':ay,**r})
        # 5 percentage point visualization bins; pooled broad/core only.
        if uname in ('core_state_local','broad_state'):
            for b in range(20):
                r=rd_level_in_bin(d,gcol,b,'state_year')
                if r: bins.append({'group':group,'universe':uname,**r})
        # Descriptive formula-fidelity gradients, explicitly secondary to the RD interaction.
        d['entitlement']=fidelity_amount(d.enrol)
        d['reported_meets_nominal_band']=(d.receipt>=d.entitlement).astype(float)
        d['reported_exact_nominal_band']=np.isclose(d.receipt,d.entitlement).astype(float)
        d['reported_shortfall_share']=np.maximum(d.entitlement-d.receipt,0)/d.entitlement
        d['reported_receipt_ratio_c2']=np.clip(d.receipt/d.entitlement,0,2)
        if uname in ('core_state_local','broad_state'):
            for outcome in ('reported_meets_nominal_band','reported_exact_nominal_band','reported_shortfall_share','reported_receipt_ratio_c2'):
                for fe in ('state_year','district_year'):
                    r=fidelity_gradient(d,gcol,outcome,fe)
                    if r: fidelity.append({'group':group,'universe':uname,**r})
        if uname=='broad_state':
            states.extend({'group':group,**r} for r in state_descriptive_gradients(d,gcol))
            r=first_difference_panel(d,gcol)
            if r: fd.append({'group':group,**r})

    write_csv(out/'rd_interactions.csv',interactions); write_csv(out/'rd_5pp_bins.csv',bins)
    write_csv(out/'fidelity_gradients.csv',fidelity); write_csv(out/'state_gradients.csv',states)
    write_csv(out/'school_first_differences.csv',fd); write_csv(out/'counts.csv',counts)
    primary=[r for r in interactions if r['universe']=='broad_state' and r['composition_source']=='predetermined_previous_year' and r['cohort']=='pooled' and r['fe'] in ('state_year','district_year')]
    lines=[f'# CSG primary social-equity result: {group}','', 'Primary outcome: heterogeneity in the correctly timed 250/251 jump in P(reported receipt >= Rs 75,000).', 'Preferred composition is prior-year share. Effects below are changes in the threshold first stage per +10 percentage points composition.', '']
    for r in primary:
        lines.append(f"- {r['fe']}: {100*r['interaction_per_10pp']:+.3f} pp (95% CI {100*r['ci_low_per_10pp']:+.3f} to {100*r['ci_high_per_10pp']:+.3f}), p={r['p']:.4g}, n={r['n']}")
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8'); print('\n'.join(lines),flush=True)
    con.close()

if __name__=='__main__': main()
