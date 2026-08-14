from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import duckdb
import numpy as np

YEARS=[f"{y}-{str(y+1)[-2:]}" for y in range(2018,2026)]
PRIMARY_CUTOFFS={100:[20,30,40,50],250:[30,50,75,100]}
SECONDARY_CUTOFFS={30:[10,15,20],1000:[100,150,250]}

OUTCOMES={
    "minor_repair_share": ("lower", "direct maintenance"),
    "good_classroom_share": ("higher", "direct maintenance"),
    "girls_toilet_functional_share": ("higher", "sanitation maintenance"),
    "boys_toilet_functional_share": ("higher", "sanitation maintenance"),
    "water_functional": ("higher", "WASH"),
    "handwash_meal": ("higher", "WASH"),
    "electricity": ("higher", "recurring utility / capability"),
    "internet": ("higher", "recurring utility / capability"),
    "major_repair_share": ("placebo", "separate major-repair grant / negative control"),
    "library": ("placebo", "separate library grant / negative control"),
}


def write_csv(path:Path,rows:list[dict])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: path.write_text('',encoding='utf-8'); return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)


def weighted_demean(a:np.ndarray, groups:np.ndarray, w:np.ndarray)->np.ndarray:
    uniq,inv=np.unique(groups,return_inverse=True)
    sw=np.bincount(inv,weights=w,minlength=len(uniq))
    if a.ndim==1:
        sa=np.bincount(inv,weights=w*a,minlength=len(uniq)); means=np.divide(sa,sw,out=np.zeros_like(sa),where=sw>0)
        return a-means[inv]
    out=np.empty_like(a,dtype=float)
    for j in range(a.shape[1]):
        sa=np.bincount(inv,weights=w*a[:,j],minlength=len(uniq)); means=np.divide(sa,sw,out=np.zeros_like(sa),where=sw>0)
        out[:,j]=a[:,j]-means[inv]
    return out


def fit_rd(data:dict[str,np.ndarray], bandwidth:float, donut:int=0)->dict|None:
    y=np.asarray(data['y'],float); e=np.asarray(data['enrol'],float); cutoff=float(data['cutoff'][0])
    state=np.asarray(data['state'],float); yi=np.asarray(data['yi'],int)
    mask=np.isfinite(y)&np.isfinite(e)&np.isfinite(state)
    if donut:
        mask &= (np.abs(e-cutoff)>donut-1e-9)
    y,e,state,yi=y[mask],e[mask],state[mask].astype(int),yi[mask]
    if len(y)<200: return None
    d=(e>cutoff).astype(float); x=e-(cutoff+0.5)
    # Only state-year cells with observations on both sides contribute to a within-cell RD.
    group=state.astype(np.int64)*100+yi.astype(np.int64)
    uniq,inv=np.unique(group,return_inverse=True)
    left=np.bincount(inv,weights=1-d,minlength=len(uniq)); right=np.bincount(inv,weights=d,minlength=len(uniq))
    okg=(left>0)&(right>0); keep=okg[inv]
    y,e,state,yi,d,x,group=y[keep],e[keep],state[keep],yi[keep],d[keep],x[keep],group[keep]
    if len(y)<200 or d.min()==d.max(): return None
    w=np.maximum(0.001,1-np.abs(x)/(bandwidth+0.5))
    X=np.column_stack([d,x,d*x])
    yd=weighted_demean(y,group,w); Xd=weighted_demean(X,group,w)
    sw=np.sqrt(w); Xw=Xd*sw[:,None]; yw=yd*sw
    xtx=Xw.T@Xw
    try: bread=np.linalg.inv(xtx)
    except np.linalg.LinAlgError: return None
    beta=bread@(Xw.T@yw); resid=yw-Xw@beta
    # Cluster by state; state clusters subsume repeated observations for schools nested within state.
    meat=np.zeros((3,3)); states=np.unique(state)
    for s in states:
        idx=state==s; score=Xw[idx].T@resid[idx]; meat+=np.outer(score,score)
    G=len(states); n=len(y); k=3
    if G<5: return None
    cov=bread@meat@bread
    cov*=G/(G-1)*(n-1)/max(1,n-k)
    se=float(math.sqrt(max(0,cov[0,0]))); tau=float(beta[0])
    z=tau/se if se>0 else math.nan; p=math.erfc(abs(z)/math.sqrt(2)) if math.isfinite(z) else None
    return {
        'tau':tau,'se_state_cluster':se,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'p_value':p,
        'n':n,'states':G,'left_n':int((d==0).sum()),'right_n':int((d==1).sum()),
        'left_mean':float(y[d==0].mean()),'right_mean':float(y[d==1].mean()),
    }


def bool_expr(alias:str,name:str)->str:
    return f"CASE WHEN {alias}.{name}=1 THEN 1.0 WHEN {alias}.{name}=2 THEN 0.0 ELSE NULL END"


def share_expr(alias:str,num_name:str,den_name:str)->str:
    return f"CASE WHEN {alias}.{den_name}>0 THEN LEAST(1.0,GREATEST(0.0,{alias}.{num_name}/{alias}.{den_name})) ELSE NULL END"


def classroom_share(alias:str,name:str)->str:
    return f"CASE WHEN {alias}.total_classrooms>0 THEN LEAST(1.0,GREATEST(0.0,{alias}.{name}/{alias}.total_classrooms)) ELSE NULL END"


def outcome_expr(alias:str,name:str)->str:
    if name=='minor_repair_share': return classroom_share(alias,'classrooms_minor_repair')
    if name=='major_repair_share': return classroom_share(alias,'classrooms_major_repair')
    if name=='good_classroom_share': return classroom_share(alias,'classrooms_good')
    if name=='girls_toilet_functional_share': return share_expr(alias,'girls_func_toilets','girls_toilets')
    if name=='boys_toilet_functional_share': return share_expr(alias,'boys_func_toilets','boys_toilets')
    if name=='water_functional': return bool_expr(alias,'water_functional_raw')
    if name=='handwash_meal': return bool_expr(alias,'handwash_meal')
    if name=='electricity': return bool_expr(alias,'electricity_raw')
    if name=='internet': return bool_expr(alias,'internet_raw')
    if name=='library': return bool_expr(alias,'library_raw')
    raise KeyError(name)


def main()->None:
    panel=Path('studies/composite_school_grant/outputs/panel/school_year_panel.parquet')
    out=Path('studies/composite_school_grant/outputs/rd'); out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(); con.execute('PRAGMA threads=4')
    year_case=' '.join(f"WHEN '{y}' THEN {i}" for i,y in enumerate(YEARS))
    con.execute(f"""
      CREATE OR REPLACE TEMP VIEW p AS
      SELECT *, CASE academic_year {year_case} END AS yi
      FROM read_parquet('{panel.as_posix()}')
    """)
    derived=[]
    for name in OUTCOMES:
        cur=outcome_expr('c',name); base=outcome_expr('b',name)
        derived.extend([f"{cur} AS cur_{name}",f"{base} AS base_{name}",f"({cur})-({base}) AS delta_{name}"])
    con.execute(f"""
      CREATE OR REPLACE TEMP TABLE pairs AS
      SELECT c.academic_year AS current_year,b.academic_year AS assignment_year,c.yi,
             c.pseudocode,c.state,c.district,c.management,
             b.enrol_c1_12 AS enrol_c1_12,b.enrol_incl_preprimary AS enrol_incl_preprimary,
             c.csg_receipt,c.csg_expenditure,
             {','.join(derived)}
      FROM p c JOIN p b ON c.pseudocode=b.pseudocode AND c.yi=b.yi+2
      WHERE c.csg_receipt IS NOT NULL
        AND b.enrol_c1_12 IS NOT NULL AND b.enrol_c1_12>0
    """)
    n_pairs=con.execute('SELECT COUNT(*) FROM pairs').fetchone()[0]
    years=con.execute('SELECT current_year,assignment_year,COUNT(*) FROM pairs GROUP BY 1,2 ORDER BY 1').fetchall()
    print('PAIRS',n_pairs,years,flush=True)

    results=[]; pretests=[]; cells=[]
    all_cutoffs={**PRIMARY_CUTOFFS,**SECONDARY_CUTOFFS}
    for cutoff,bws in all_cutoffs.items():
        for bw in bws:
            for donut in (0,1):
                # Fetch common sample once for grant outcomes.
                q=f"""
                  SELECT csg_receipt AS y,enrol_c1_12 AS enrol,state,yi,{cutoff}::DOUBLE AS cutoff
                  FROM pairs WHERE enrol_c1_12 BETWEEN {cutoff-bw} AND {cutoff+bw}
                """
                arr=con.execute(q).fetchnumpy(); est=fit_rd(arr,bw,donut)
                if est:
                    results.append({'family':'first_stage','outcome':'csg_receipt','cutoff':cutoff,'bandwidth':bw,'donut':donut,**est,'statutory_jump':15000 if cutoff==30 else 25000,'first_stage_fraction':est['tau']/(15000 if cutoff==30 else 25000)})
                q=q.replace('csg_receipt AS y','csg_expenditure AS y')
                est_e=fit_rd(con.execute(q).fetchnumpy(),bw,donut)
                if est_e: results.append({'family':'first_stage','outcome':'csg_expenditure','cutoff':cutoff,'bandwidth':bw,'donut':donut,**est_e,'statutory_jump':15000 if cutoff==30 else 25000,'spending_fraction':est_e['tau']/(15000 if cutoff==30 else 25000)})

                for name,(direction,role) in OUTCOMES.items():
                    # Primary reduced form is change from pre-assignment facility status to post-grant facility status.
                    q=f"""
                      SELECT delta_{name} AS y,enrol_c1_12 AS enrol,state,yi,{cutoff}::DOUBLE AS cutoff
                      FROM pairs WHERE enrol_c1_12 BETWEEN {cutoff-bw} AND {cutoff+bw}
                        AND delta_{name} IS NOT NULL
                    """
                    rf=fit_rd(con.execute(q).fetchnumpy(),bw,donut)
                    if rf:
                        rec={'family':'outcome_change','outcome':name,'role':role,'direction':direction,'cutoff':cutoff,'bandwidth':bw,'donut':donut,**rf}
                        # Estimate first stage on exactly the outcome-complete sample for a transparent Wald scaling.
                        qfs=q.replace(f'delta_{name} AS y','csg_receipt AS y')
                        fs=fit_rd(con.execute(qfs).fetchnumpy(),bw,donut)
                        if fs and abs(fs['tau'])>1000:
                            jump=15000 if cutoff==30 else 25000
                            rec['same_sample_first_stage']=fs['tau']; rec['effect_per_statutory_jump']=rf['tau']*jump/fs['tau']
                        results.append(rec)
                    # Pre-treatment continuity test: baseline outcome at the assignment threshold.
                    qb=f"""
                      SELECT base_{name} AS y,enrol_c1_12 AS enrol,state,yi,{cutoff}::DOUBLE AS cutoff
                      FROM pairs WHERE enrol_c1_12 BETWEEN {cutoff-bw} AND {cutoff+bw}
                        AND base_{name} IS NOT NULL
                    """
                    pre=fit_rd(con.execute(qb).fetchnumpy(),bw,donut)
                    if pre: pretests.append({'outcome':name,'cutoff':cutoff,'bandwidth':bw,'donut':donut,**pre})

        # Enrollment cell counts / grant means for density and visual diagnostics.
        maxbw=max(bws)
        rows=con.execute(f"""
          SELECT enrol_c1_12 enrol,COUNT(*) n,AVG(csg_receipt) mean_receipt,AVG(csg_expenditure) mean_expenditure
          FROM pairs WHERE enrol_c1_12 BETWEEN {cutoff-maxbw} AND {cutoff+maxbw}
          GROUP BY 1 ORDER BY 1
        """).fetchall()
        for e,n,mr,me in rows: cells.append({'cutoff':cutoff,'enrol':e,'n':n,'mean_receipt':mr,'mean_expenditure':me})

    # Discrete density diagnostics using local log-count regressions over cells and simple near-boundary ratios.
    density=[]
    for cutoff,bws in all_cutoffs.items():
        for bw in bws:
            sub=[r for r in cells if r['cutoff']==cutoff and abs(r['enrol']-cutoff)<=bw]
            if len(sub)<8: continue
            e=np.array([r['enrol'] for r in sub],float); cnt=np.array([r['n'] for r in sub],float)
            x=e-(cutoff+0.5); d=(e>cutoff).astype(float); X=np.column_stack([np.ones(len(e)),d,x,d*x])
            y=np.log(cnt+0.5); beta=np.linalg.lstsq(X,y,rcond=None)[0]
            left=sum(r['n'] for r in sub if cutoff-5<=r['enrol']<=cutoff-1)
            right=sum(r['n'] for r in sub if cutoff+1<=r['enrol']<=cutoff+5)
            density.append({'cutoff':cutoff,'bandwidth':bw,'log_density_jump':float(beta[1]),'implied_percent_jump':float((math.exp(beta[1])-1)*100),'five_cell_right_left_ratio':right/left if left else None,'left_5_n':left,'right_5_n':right})

    write_csv(out/'rd_estimates.csv',results); write_csv(out/'pretreatment_continuity.csv',pretests); write_csv(out/'enrolment_cells.csv',cells); write_csv(out/'density_diagnostics.csv',density)
    # Headline extraction uses the central prespecified bandwidths and donut=1 robustness.
    headline=[]
    central={100:40,250:75,30:15,1000:150}
    for cutoff,bw in central.items():
        for r in results:
            if r['cutoff']==cutoff and r['bandwidth']==bw and r['donut']==1 and (r['family']=='first_stage' or r['outcome'] in OUTCOMES): headline.append(r)
    payload={'pair_count':int(n_pairs),'pair_years':[list(x) for x in years],'headline_specs':headline,'density':density}
    (out/'rd_summary.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print('\nHEADLINE RD SPECS')
    for r in headline: print(json.dumps(r),flush=True)
    print('\nDENSITY')
    for r in density: print(json.dumps(r),flush=True)
    con.close()

if __name__=='__main__': main()
