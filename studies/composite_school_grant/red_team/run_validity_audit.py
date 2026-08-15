from __future__ import annotations

import csv
import json
import math
import os
import runpy
import tempfile
from pathlib import Path

import duckdb
import numpy as np

PANEL = runpy.run_path("studies/composite_school_grant/scripts/03_build_panel.py", run_name="panel_lib")
CONF = runpy.run_path("studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py", run_name="confirm_lib")

extract_archive = PANEL["extract_archive"]
csv_source = PANEL["csv_source"]
source_columns = PANEL["source_columns"]
qid = PANEL["qid"]
lit = PANEL["lit"]
ref = PANEL["ref"]
nref = PANEL["nref"]
num = PANEL["num"]
identify_early_social_labels = PANEL["identify_early_social_labels"]
component_exprs = CONF["component_exprs"]
ASSETS = CONF["ASSET_COMPONENTS"]

CUTOFF = 250
GOV = "(1,2,3)"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)


def weighted_demean(a: np.ndarray, g: np.ndarray, w: np.ndarray) -> np.ndarray:
    _, inv = np.unique(g, return_inverse=True)
    sw = np.bincount(inv, weights=w)
    if a.ndim == 1:
        sa = np.bincount(inv, weights=w*a)
        mu = np.divide(sa, sw, out=np.zeros_like(sa), where=sw>0)
        return a-mu[inv]
    out = np.empty_like(a, dtype=float)
    for j in range(a.shape[1]):
        sa = np.bincount(inv, weights=w*a[:,j])
        mu = np.divide(sa, sw, out=np.zeros_like(sa), where=sw>0)
        out[:,j] = a[:,j]-mu[inv]
    return out


def rd_general(y, e, state, cutoff=CUTOFF, bw=30, donut=1, kernel="triangular", degree=1, omit_state=None):
    y=np.asarray(y,float); e=np.asarray(e,float); state=np.asarray(state,float)
    m=np.isfinite(y)&np.isfinite(e)&np.isfinite(state)&(np.abs(e-cutoff)<=bw)
    if omit_state is not None: m &= state != float(omit_state)
    if donut: m &= np.abs(e-(cutoff+0.5))>donut
    y,e,state=y[m],e[m],state[m].astype(int)
    if len(y)<500: return None
    d=(e>cutoff).astype(float); x=e-(cutoff+0.5)
    _,inv=np.unique(state,return_inverse=True)
    left=np.bincount(inv,weights=1-d); right=np.bincount(inv,weights=d)
    keep=((left>0)&(right>0))[inv]
    y,e,state,d,x=y[keep],e[keep],state[keep],d[keep],x[keep]
    if len(y)<500 or d.min()==d.max(): return None
    if kernel=="triangular": w=np.maximum(.001,1-np.abs(x)/(bw+.5))
    elif kernel=="uniform": w=np.ones(len(y))
    else: raise ValueError(kernel)
    cols=[d]
    for p in range(1,degree+1): cols += [x**p, d*(x**p)]
    X=np.column_stack(cols)
    yd=weighted_demean(y,state,w); Xd=weighted_demean(X,state,w)
    sw=np.sqrt(w); Xw=Xd*sw[:,None]; yw=yd*sw
    bread=np.linalg.pinv(Xw.T@Xw); beta=bread@(Xw.T@yw); res=yw-Xw@beta
    meat=np.zeros((X.shape[1],X.shape[1])); states=np.unique(state)
    for s in states:
        ix=state==s; score=Xw[ix].T@res[ix]; meat += np.outer(score,score)
    G=len(states); n=len(y); k=X.shape[1]; cov=bread@meat@bread
    if G>1: cov *= G/(G-1)*(n-1)/max(1,n-k)
    se=float(math.sqrt(max(0,cov[0,0]))); tau=float(beta[0]); z=tau/se if se else math.nan
    p=math.erfc(abs(z)/math.sqrt(2)) if math.isfinite(z) else None
    return {"tau":tau,"se":se,"ci_low":tau-1.96*se,"ci_high":tau+1.96*se,"p":p,"n":n,"states":G,
            "left_n":int((d==0).sum()),"right_n":int((d==1).sum()),"left_mean":float(y[d==0].mean()),"right_mean":float(y[d==1].mean())}


def estimate(con, table, yexpr, cutoff=CUTOFF, bw=30, donut=1, kernel="triangular", degree=1, where="TRUE", omit_state=None):
    arr=con.execute(f"SELECT {yexpr} y,enrol,state FROM {table} WHERE ({where}) AND ({yexpr}) IS NOT NULL").fetchnumpy()
    return rd_general(arr['y'],arr['enrol'],arr['state'],cutoff,bw,donut,kernel,degree,omit_state)


def bh(rows):
    v=[(i,float(r['p'])) for i,r in enumerate(rows) if r.get('p') is not None and math.isfinite(float(r['p']))]
    v.sort(key=lambda x:x[1]); m=len(v); run=1.0
    for rank in range(m,0,-1):
        i,p=v[rank-1]; q=min(run,p*m/rank); run=q; rows[i]['q_bh']=q


def total_enrol_setup(con, source, c):
    terms=[f"COALESCE({nref(c,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in c]
    if 'item_group' in c and 'item_id' in c:
        filt=f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN (1,2,3,4)"
    else:
        labs=identify_early_social_labels(con,source,c); d=ref(c,'item_desc')
        filt=f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})"
    return ' + '.join(terms),filt


def idcol(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x: raise RuntimeError('school id missing')
    return x


def main():
    ay=os.environ['ASSIGN_YEAR']; future=[x for x in os.environ['FUTURE_YEARS'].split(',') if x]
    repo=os.environ['HF_DATASET_REPO']; token=os.environ['HF_TOKEN']
    out=Path(f"studies/composite_school_grant/outputs/red_team/{ay}"); out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(); con.execute('PRAGMA threads=4'); con.execute("PRAGMA memory_limit='10GB'")
    attr=[]; ids=[]; balance=[]; robustness=[]; placebos=[]; loo=[]; state_fs=[]
    with tempfile.TemporaryDirectory(prefix='csg_red_') as td:
        root=Path(td)
        ae=csv_source(extract_archive(repo,token,ay,'enrolment_1',root)); ap1=csv_source(extract_archive(repo,token,ay,'profile_1',root)); af=csv_source(extract_archive(repo,token,ay,'facility',root)); at=csv_source(extract_archive(repo,token,ay,'teacher',root))
        ec,pc,fc,tc=[source_columns(con,x) for x in (ae,ap1,af,at)]; eid,pid,fid,tid=map(idcol,(ec,pc,fc,tc))
        total,filt=total_enrol_setup(con,ae,ec)
        con.execute(f"CREATE TEMP TABLE enr0 AS SELECT CAST({qid(eid)} AS VARCHAR) pseudocode,SUM({total}) enrol FROM {ae} WHERE {filt} GROUP BY 1")
        attrs=[]
        for n in ('state','district','block','school_category','school_type','lowclass','highclass','rural_urban'):
            r=ref(pc,n,'p')
            if r: attrs.append(f"CAST({r} AS VARCHAR) a_{n}")
        con.execute(f"CREATE TEMP TABLE b0 AS SELECT e.pseudocode,e.enrol,CAST({ref(pc,'state','p')} AS VARCHAR) state_key,{','.join(attrs)} FROM enr0 e JOIN {ap1} p ON e.pseudocode=CAST(p.{qid(pid)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 175 AND 325")
        con.execute("CREATE TEMP TABLE base AS SELECT *,DENSE_RANK() OVER(ORDER BY state_key) state FROM b0")

        # Baseline covariate balance, restricted to interpretable counts/availability fields.
        facvars=['total_class_rooms','classrooms_in_good_condition','classrooms_needs_minor_repair','classrooms_needs_major_repair','total_boys_toilet','total_boys_func_toilet','total_girls_toilet','total_girls_func_toilet','laptop','tablet','desktop','teachdev_tot','server_tot','smart_class_tv_tot','projector','printer']
        tvars=['total_tch','male','female','gen_tch','sc_tch','st_tch','obc_tch','regular','contract','part_time','trained_comp','below_graduate','graduate','post_graduate_and_above','trained_cwsn']
        con.execute(f"CREATE TEMP TABLE bf AS SELECT CAST({qid(fid)} AS VARCHAR) pseudocode,* EXCLUDE({qid(fid)}) FROM {af}")
        con.execute(f"CREATE TEMP TABLE bt AS SELECT CAST({qid(tid)} AS VARCHAR) pseudocode,* EXCLUDE({qid(tid)}) FROM {at}")
        for family,c,table,vars_ in [('facility',fc,'bf',facvars),('teacher',tc,'bt',tvars)]:
            for v in vars_:
                if v not in c: continue
                expr=num('x.'+qid(c[v]))
                arr=con.execute(f"SELECT {expr} y,b.enrol,b.state FROM base b JOIN {table} x USING(pseudocode) WHERE {expr} IS NOT NULL").fetchnumpy()
                est=rd_general(arr['y'],arr['enrol'],arr['state'],CUTOFF,30,1)
                if est: balance.append({'family':family,'field':v,**est})
        for v in ('lowclass','highclass','rural_urban'):
            if v in pc:
                expr=num('p.'+qid(pc[v])); arr=con.execute(f"SELECT {expr} y,b.enrol,b.state FROM base b JOIN {ap1} p ON b.pseudocode=CAST(p.{qid(pid)} AS VARCHAR) WHERE {expr} IS NOT NULL").fetchnumpy(); est=rd_general(arr['y'],arr['enrol'],arr['state'],CUTOFF,30,1)
                if est: balance.append({'family':'profile1','field':v,**est})
        bh(balance)

        future_p2=[]; future_prof=[]; future_fac=[]
        for i,fy in enumerate(future):
            p1=csv_source(extract_archive(repo,token,fy,'profile_1',root)); p2=csv_source(extract_archive(repo,token,fy,'profile_2',root)); fac=csv_source(extract_archive(repo,token,fy,'facility',root)); teach=csv_source(extract_archive(repo,token,fy,'teacher',root)); en1=csv_source(extract_archive(repo,token,fy,'enrolment_1',root)); en2=csv_source(extract_archive(repo,token,fy,'enrolment_2',root))
            p1c,p2c,fcc,tcc,e1c,e2c=[source_columns(con,x) for x in (p1,p2,fac,teach,en1,en2)]; p1id,p2id,fcid,tcid,e1id,e2id=map(idcol,(p1c,p2c,fcc,tcc,e1c,e2c))
            safe=fy.replace('-','_')
            # Presence tables for differential attrition.
            for fam,source,sid in [('profile1',p1,p1id),('profile2',p2,p2id),('facility',fac,fcid),('teacher',teach,tcid),('enrolment1',en1,e1id),('enrolment2',en2,e2id)]:
                tn=f"pres_{fam}_{i}"; con.execute(f"CREATE TEMP TABLE {tn} AS SELECT DISTINCT CAST({qid(sid)} AS VARCHAR) pseudocode,1 present FROM {source}")
                est=estimate(con,f"(SELECT b.*,COALESCE(x.present,0)::DOUBLE present FROM base b LEFT JOIN {tn} x USING(pseudocode))",'present',bw=30,donut=1)
                if est: attr.append({'outcome_year':fy,'table':fam,**est})
            # Profile invariant checks among matched IDs.
            fattrs=[]
            for n in ('state','district','block','school_category','school_type','lowclass','highclass','rural_urban'):
                if n in p1c: fattrs.append(f"CAST({qid(p1c[n])} AS VARCHAR) f_{n}")
            pt=f"prof_{i}"; con.execute(f"CREATE TEMP TABLE {pt} AS SELECT CAST({qid(p1id)} AS VARCHAR) pseudocode,{nref(p1c,'managment')} mgmt,{','.join(fattrs)} FROM {p1}"); future_prof.append(pt)
            for n in ('state','district','block','school_category','school_type','lowclass','highclass','rural_urban'):
                if n in pc and n in p1c:
                    ex=f"CASE WHEN b.a_{n}=p.f_{n} THEN 1.0 ELSE 0.0 END"
                    row=con.execute(f"SELECT AVG({ex}),COUNT(*) FROM base b JOIN {pt} p USING(pseudocode) WHERE b.a_{n} IS NOT NULL AND p.f_{n} IS NOT NULL").fetchone()
                    est=estimate(con,f"(SELECT b.*,{ex} stable FROM base b JOIN {pt} p USING(pseudocode) WHERE b.a_{n} IS NOT NULL AND p.f_{n} IS NOT NULL)",'stable')
                    ids.append({'outcome_year':fy,'attribute':n,'overall_stability':row[0],'matched_n':int(row[1]),**(est or {})})
            gp=f"gp_{i}"; con.execute(f"CREATE TEMP TABLE {gp} AS SELECT CAST({qid(p2id)} AS VARCHAR) pseudocode,{nref(p2c,'grants_receipt')} receipt_{i},{nref(p2c,'grants_expenditure')} expenditure_{i} FROM {p2}"); future_p2.append(gp)
            cf=component_exprs(fcc,'f'); fs=f"faccomp_{i}"; con.execute(f"CREATE TEMP TABLE {fs} AS SELECT CAST({qid(fcid)} AS VARCHAR) pseudocode,{','.join(expr+' c_'+n for n,expr in cf.items())} FROM {fac} f"); future_fac.append(fs)

        # Baseline components for deterioration robustness.
        bc=component_exprs(fc,'f'); con.execute(f"CREATE TEMP TABLE bcomp AS SELECT CAST({qid(fid)} AS VARCHAR) pseudocode,{','.join(expr+' b_'+n for n,expr in bc.items())} FROM {af} f")
        # Cumulative financial complete-case table, assignment-government sample without post-treatment management conditioning.
        joins=[]; obs=[]; sums=[]
        for i,g in enumerate(future_p2): joins.append(f"LEFT JOIN {g} g{i} USING(pseudocode)"); obs.append(f"g{i}.expenditure_{i} IS NOT NULL"); sums.append(f"COALESCE(g{i}.expenditure_{i},0)")
        con.execute(f"CREATE TEMP TABLE cumulative AS SELECT b.*,CASE WHEN {' AND '.join(obs)} THEN {' + '.join(sums)} END cumexp FROM base b {' '.join(joins)}")
        # Robustness grid for cumulative expenditure.
        arr=con.execute('SELECT cumexp y,enrol,state FROM cumulative WHERE cumexp IS NOT NULL').fetchnumpy()
        for bw in (15,20,25,30,40,50,75):
            for donut in (0,1,2,3):
                for kernel in ('triangular','uniform'):
                    for degree in (1,2):
                        est=rd_general(arr['y'],arr['enrol'],arr['state'],CUTOFF,bw,donut,kernel,degree)
                        if est: robustness.append({'outcome':'cumulative_expenditure','bw':bw,'donut':donut,'kernel':kernel,'degree':degree,**est})
        # Placebo cutoffs within the same CSG bands.
        for cut in (150,175,200,300,325,350):
            est=rd_general(arr['y'],arr['enrol'],arr['state'],cut,25,1,'triangular',1)
            if est: placebos.append({'outcome':'cumulative_expenditure','cutoff':cut,'bw':25,**est})
        # Leave one assignment-state cluster out.
        for s in sorted(set(np.asarray(arr['state'],int))):
            est=rd_general(arr['y'],arr['enrol'],arr['state'],CUTOFF,30,1,'triangular',1,omit_state=int(s))
            if est: loo.append({'outcome':'cumulative_expenditure','omitted_state_code':int(s),**est})
        # State-specific raw/local first stages as heterogeneity diagnostic for first observable grant year.
        g0=future_p2[0]; a=con.execute(f"SELECT g.receipt_0 receipt,g.expenditure_0 exp,b.enrol,b.state FROM base b JOIN {g0} g USING(pseudocode) WHERE b.enrol BETWEEN 220 AND 280").fetchnumpy()
        for s in sorted(set(np.asarray(a['state'],int))):
            m=np.asarray(a['state'],int)==s; e=np.asarray(a['enrol'],float)[m]
            for key in ('receipt','exp'):
                y=np.asarray(a[key],float)[m]; ok=np.isfinite(y)&np.isfinite(e); y=y[ok]; ee=e[ok]
                if len(y)<80 or not ((ee<=250).any() and (ee>250).any()): continue
                state_fs.append({'state_code':int(s),'variable':key,'n':int(len(y)),'left_mean':float(y[ee<=250].mean()),'right_mean':float(y[ee>250].mean()),'raw_diff':float(y[ee>250].mean()-y[ee<=250].mean())})

        # Deterioration composite robustness for first outcome year.
        f0=future_fac[0]
        det_terms=[f"CASE WHEN b.b_{a}=1 AND o.c_{a} IS NOT NULL THEN 1.0-o.c_{a} ELSE 0.0 END" for a in ASSETS]
        det_den=[f"CASE WHEN b.b_{a}=1 AND o.c_{a} IS NOT NULL THEN 1 ELSE 0 END" for a in ASSETS]
        det=f"CASE WHEN ({' + '.join(det_den)})>=3 THEN ({' + '.join(det_terms)})/NULLIF(({' + '.join(det_den)}),0) END"
        con.execute(f"CREATE TEMP TABLE detsample AS SELECT x.*,{det} deterioration FROM base x JOIN bcomp b USING(pseudocode) JOIN {f0} o USING(pseudocode)")
        darr=con.execute('SELECT deterioration y,enrol,state FROM detsample WHERE deterioration IS NOT NULL').fetchnumpy()
        for bw in (15,20,25,30,40,50,75):
            for donut in (0,1,2,3):
                for kernel in ('triangular','uniform'):
                    for degree in (1,2):
                        est=rd_general(darr['y'],darr['enrol'],darr['state'],CUTOFF,bw,donut,kernel,degree)
                        if est: robustness.append({'outcome':'deterioration_composite_first_horizon','bw':bw,'donut':donut,'kernel':kernel,'degree':degree,**est})

    bh(attr)
    write_csv(out/'attrition_rd.csv',attr); write_csv(out/'id_stability.csv',ids); write_csv(out/'predetermined_balance.csv',balance); write_csv(out/'specification_grid.csv',robustness); write_csv(out/'placebo_cutoffs.csv',placebos); write_csv(out/'leave_one_state_out.csv',loo); write_csv(out/'state_first_stage.csv',state_fs)
    def summarize_grid(name):
        r=[x for x in robustness if x['outcome']==name]
        return {'n_specs':len(r),'positive_share':sum(x['tau']>0 for x in r)/len(r) if r else None,'significant_positive_share':sum(x['tau']>0 and x.get('p',1)<.05 for x in r)/len(r) if r else None,'tau_min':min((x['tau'] for x in r),default=None),'tau_max':max((x['tau'] for x in r),default=None),'median_tau':float(np.median([x['tau'] for x in r])) if r else None}
    summary={'assignment_year':ay,'future_years':future,'attrition_fdr_hits':[x for x in attr if x.get('q_bh',1)<.10],'balance_fdr_hits':[x for x in balance if x.get('q_bh',1)<.10],
             'id_stability':ids,'cumulative_grid':summarize_grid('cumulative_expenditure'),'deterioration_grid':summarize_grid('deterioration_composite_first_horizon'),
             'placebos':placebos,'loo_range':{'min':min((x['tau'] for x in loo),default=None),'max':max((x['tau'] for x in loo),default=None),'n':len(loo)},'state_first_stage':state_fs}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('RED TEAM SUMMARY')
    print(json.dumps(summary,indent=2),flush=True)
    con.close()

if __name__=='__main__': main()
