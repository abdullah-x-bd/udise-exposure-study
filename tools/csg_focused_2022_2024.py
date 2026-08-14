from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import duckdb
import numpy as np
from huggingface_hub import hf_hub_download

CUTOFFS={100:[15,20,30,40,50],250:[20,30,40,50,75]}
PLACEBO_CUTOFFS={175:[20,30],325:[20,30]}


def qid(x:str)->str: return '"'+x.replace('"','""')+'"'
def lit(x:str)->str: return "'"+x.replace("'","''")+"'"
def norm(x:str)->str: return re.sub(r'[^a-z0-9]+','_',x.lower().replace('\ufeff','')).strip('_')
def num(expr:str)->str: return f"TRY_CAST(NULLIF(TRIM(CAST({expr} AS VARCHAR)),'') AS DOUBLE)"


def extract(repo:str,token:str,year:str,table:str,root:Path)->list[Path]:
    zpath=Path(hf_hub_download(repo_id=repo,filename=f'raw/{year}/{table}.zip',repo_type='dataset',token=token,local_dir=root/'hf'))
    dest=root/year/table; dest.mkdir(parents=True,exist_ok=True); out=[]
    with zipfile.ZipFile(zpath) as zf:
        for m in zf.infolist():
            if m.is_dir() or not m.filename.lower().endswith('.csv'): continue
            if table=='enrolment_1' and 'stream' in m.filename.lower(): continue
            p=dest/Path(m.filename).name
            with zf.open(m) as src,p.open('wb') as dst: shutil.copyfileobj(src,dst,8*1024*1024)
            out.append(p)
    return out


def src(paths:list[Path])->str:
    return "read_csv_auto(["+','.join(lit(str(p)) for p in paths)+"],header=true,all_varchar=true,sample_size=-1,union_by_name=true,strict_mode=false,null_padding=true)"


def cols(con,source:str)->dict[str,str]:
    return {norm(d[0]):d[0] for d in con.execute(f'SELECT * FROM {source} LIMIT 0').description}


def ref(c:dict[str,str],name:str,alias:str|None=None)->str|None:
    a=c.get(name)
    return None if a is None else (f'{alias}.' if alias else '')+qid(a)


def nref(c:dict[str,str],name:str,alias:str|None=None)->str:
    r=ref(c,name,alias); return 'NULL' if r is None else num(r)


def bool_expr(c:dict[str,str],name:str,alias:str)->str:
    r=ref(c,name,alias)
    if not r:return 'NULL'
    v=num(r); return f'CASE WHEN {v}=1 THEN 1.0 WHEN {v}=2 THEN 0.0 ELSE NULL END'


def water_expr(c:dict[str,str],alias:str,functional:bool)->str:
    direct='drinking_water_functional' if functional else 'drinking_water_available'
    if ref(c,direct,alias): return bool_expr(c,direct,alias)
    suffix='_fun_yn' if functional else '_yn'; bases=['hand_pump','well_prot','tap','othsrc','well_unprot','pack_water']
    vals=[]
    for b in bases:
        r=ref(c,b+suffix,alias)
        if r: vals.append(num(r))
    if not vals:return 'NULL'
    return 'CASE WHEN '+ ' OR '.join(f'({v}=1)' for v in vals)+' THEN 1.0 WHEN '+' AND '.join(f'({v}=2 OR {v} IS NULL)' for v in vals)+' THEN 0.0 ELSE NULL END'


def share(numx:str,denx:str)->str:
    return f'CASE WHEN {denx}>0 THEN LEAST(1.0,GREATEST(0.0,{numx}/{denx})) ELSE NULL END'


def weighted_demean(a:np.ndarray,g:np.ndarray,w:np.ndarray)->np.ndarray:
    _,inv=np.unique(g,return_inverse=True); sw=np.bincount(inv,weights=w)
    if a.ndim==1:
        sa=np.bincount(inv,weights=w*a); mu=np.divide(sa,sw,out=np.zeros_like(sa),where=sw>0);return a-mu[inv]
    z=np.empty_like(a,dtype=float)
    for j in range(a.shape[1]):
        sa=np.bincount(inv,weights=w*a[:,j]);mu=np.divide(sa,sw,out=np.zeros_like(sa),where=sw>0);z[:,j]=a[:,j]-mu[inv]
    return z


def rd(y,e,state,cutoff,bw,donut=0)->dict|None:
    y=np.asarray(y,float);e=np.asarray(e,float);state=np.asarray(state,float)
    m=np.isfinite(y)&np.isfinite(e)&np.isfinite(state)&(np.abs(e-cutoff)<=bw)
    if donut:m &= np.abs(e-(cutoff+0.5))>donut
    y,e,state=y[m],e[m],state[m].astype(int)
    if len(y)<500:return None
    d=(e>cutoff).astype(float);x=e-(cutoff+0.5)
    # retain states represented on both sides
    _,inv=np.unique(state,return_inverse=True);l=np.bincount(inv,weights=1-d);r=np.bincount(inv,weights=d);ok=(l>0)&(r>0);keep=ok[inv]
    y,e,state,d,x=y[keep],e[keep],state[keep],d[keep],x[keep]
    if len(y)<500:return None
    w=np.maximum(.001,1-np.abs(x)/(bw+.5));X=np.column_stack([d,x,d*x]);yd=weighted_demean(y,state,w);Xd=weighted_demean(X,state,w)
    sw=np.sqrt(w);Xw=Xd*sw[:,None];yw=yd*sw;bread=np.linalg.pinv(Xw.T@Xw);beta=bread@(Xw.T@yw);res=yw-Xw@beta
    meat=np.zeros((3,3));states=np.unique(state)
    for s in states:
        idx=state==s;score=Xw[idx].T@res[idx];meat+=np.outer(score,score)
    G=len(states);n=len(y);cov=bread@meat@bread
    if G>1:cov*=G/(G-1)*(n-1)/max(1,n-3)
    se=float(math.sqrt(max(0,cov[0,0])));tau=float(beta[0]);z=tau/se if se else math.nan;p=math.erfc(abs(z)/math.sqrt(2)) if math.isfinite(z) else None
    return {'tau':tau,'se':se,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'p':p,'n':n,'states':G,'left_n':int((d==0).sum()),'right_n':int((d==1).sum()),'left_mean':float(y[d==0].mean()),'right_mean':float(y[d==1].mean())}


def write_csv(path:Path,rows:list[dict]):
    if not rows:path.write_text('',encoding='utf-8');return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys:keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def main():
    repo=os.environ['HF_DATASET_REPO'];token=os.environ['HF_TOKEN'];out=Path('outputs/csg_focused_2022_2024');out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csg_focus_') as td:
        root=Path(td);db=Path(hf_hub_download(repo_id=repo,filename='processed/2024_25/database/udise_2024_25.duckdb',repo_type='dataset',token=token,local_dir=root/'hf'))
        enr=src(extract(repo,token,'2022-23','enrolment_1',root));p1=src(extract(repo,token,'2022-23','profile_1',root));fac=src(extract(repo,token,'2022-23','facility',root))
        con=duckdb.connect(str(db),read_only=False);con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
        ec,pc,fc=cols(con,enr),cols(con,p1),cols(con,fac);eid=ref(ec,'pseudocode') or ref(ec,'psuedocode');pid=ref(pc,'pseudocode') or ref(pc,'psuedocode');fid=ref(fc,'pseudocode') or ref(fc,'psuedocode')
        class_terms=[f'COALESCE({nref(ec,f"c{c}_{s}")},0)' for c in range(1,13) for s in ('b','g') if f'c{c}_{s}' in ec]
        con.execute(f"""CREATE TEMP TABLE base_enrol AS SELECT CAST({eid} AS VARCHAR) pseudocode,SUM({' + '.join(class_terms)}) enrol FROM {enr} WHERE {nref(ec,'item_group')}=1 AND {nref(ec,'item_id')} IN (1,2,3,4) GROUP BY 1""")
        # baseline government management and facilities
        base_out={
          'minor_repair_share':share(nref(fc,'classrooms_needs_minor_repair','f'),nref(fc,'total_class_rooms','f')),
          'major_repair_share':share(nref(fc,'classrooms_needs_major_repair','f'),nref(fc,'total_class_rooms','f')),
          'good_classroom_share':share(nref(fc,'classrooms_in_good_condition','f'),nref(fc,'total_class_rooms','f')),
          'girls_toilet_functional_share':share(nref(fc,'total_girls_func_toilet','f'),nref(fc,'total_girls_toilet','f')),
          'boys_toilet_functional_share':share(nref(fc,'total_boys_func_toilet','f'),nref(fc,'total_boys_toilet','f')),
          'water_functional':water_expr(fc,'f',True),
          'handwash_meal':bool_expr(fc,'handwash_facility_for_meal','f'),
          'electricity':bool_expr(fc,'electricity_availability','f'),
          'internet':bool_expr(fc,'internet','f'),
          'library':bool_expr(fc,'library_availability','f'),
        }
        con.execute(f"""CREATE TEMP TABLE base AS SELECT CAST(p.{pid} AS VARCHAR) pseudocode,{nref(pc,'managment','p')} management,{','.join(expr+' b_'+name for name,expr in base_out.items())} FROM {p1} p LEFT JOIN {fac} f ON CAST(p.{pid} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)""")
        tables={r[0] for r in con.execute('SHOW TABLES').fetchall()}; curfac='raw_facility' if 'raw_facility' in tables else ('facility' if 'facility' in tables else None);curp='school_master_base'
        if not curfac or curp not in tables:raise RuntimeError(f'Expected 2024 tables absent: {sorted(tables)[:50]}')
        cc=cols(con,curfac);mc=cols(con,curp)
        mid=ref(mc,'pseudocode') or ref(mc,'psuedocode');cfid=ref(cc,'pseudocode') or ref(cc,'psuedocode')
        current_out={
          'minor_repair_share':share(nref(cc,'classrooms_needs_minor_repair','f'),nref(cc,'total_class_rooms','f')),
          'major_repair_share':share(nref(cc,'classrooms_needs_major_repair','f'),nref(cc,'total_class_rooms','f')),
          'good_classroom_share':share(nref(cc,'classrooms_in_good_condition','f'),nref(cc,'total_class_rooms','f')),
          'girls_toilet_functional_share':share(nref(cc,'total_girls_func_toilet','f'),nref(cc,'total_girls_toilet','f')),
          'boys_toilet_functional_share':share(nref(cc,'total_boys_func_toilet','f'),nref(cc,'total_boys_toilet','f')),
          'water_functional':water_expr(cc,'f',True),
          'handwash_meal':bool_expr(cc,'handwash_facility_for_meal','f'),
          'electricity':bool_expr(cc,'electricity_availability','f'),
          'internet':bool_expr(cc,'internet','f'),
          'library':bool_expr(cc,'library_availability','f'),
        }
        grant=mc.get('grants_receipt');exp=mc.get('grants_expenditure');mgmt=mc.get('managment') or mc.get('management');state=mc.get('state')
        if not all([grant,exp,mgmt,state]):raise RuntimeError('Missing current grant/management/state fields')
        select_out=[]
        for name,expr in current_out.items():select_out += [f'{expr} c_{name}',f'b.b_{name}',f'({expr})-b.b_{name} d_{name}']
        con.execute(f"""CREATE TEMP TABLE sample AS SELECT e.pseudocode,e.enrol,{num('m.'+qid(state))} state,{num('m.'+qid(mgmt))} management_current,b.management management_base,{num('m.'+qid(grant))} receipt,{num('m.'+qid(exp))} expenditure,{','.join(select_out)} FROM base_enrol e JOIN base b USING(pseudocode) JOIN {curp} m ON e.pseudocode=CAST(m.{mid} AS VARCHAR) LEFT JOIN {curfac} f ON e.pseudocode=CAST(f.{cfid} AS VARCHAR) WHERE b.management IN (1,2,3) AND {num('m.'+qid(mgmt))} IN (1,2,3) AND {num('m.'+qid(grant))} IS NOT NULL AND e.enrol>0""")
        n=con.execute('SELECT COUNT(*) FROM sample').fetchone()[0];print('FOCUSED GOVERNMENT SAMPLE',n,flush=True)
        outcomes=list(base_out);rows=[];pre=[]
        for cutoff,bws in {**CUTOFFS,**PLACEBO_CUTOFFS}.items():
            for bw in bws:
                for donut in (0,1,2):
                    for var,family in [('receipt','first_stage_receipt'),('expenditure','first_stage_expenditure')]:
                        arr=con.execute(f'SELECT {var} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND {var} IS NOT NULL').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],cutoff,bw,donut)
                        if est:rows.append({'family':family,'outcome':var,'cutoff':cutoff,'bandwidth':bw,'donut':donut,**est})
                    # probability of positive receipt is an implementation first stage too
                    arr=con.execute(f'SELECT CASE WHEN receipt>0 THEN 1.0 ELSE 0.0 END y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw}').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],cutoff,bw,donut)
                    if est:rows.append({'family':'first_stage_positive_receipt','outcome':'positive_receipt','cutoff':cutoff,'bandwidth':bw,'donut':donut,**est})
                    for name in outcomes:
                        arr=con.execute(f'SELECT d_{name} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND d_{name} IS NOT NULL').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],cutoff,bw,donut)
                        if est:rows.append({'family':'outcome_change','outcome':name,'cutoff':cutoff,'bandwidth':bw,'donut':donut,**est})
                        arr=con.execute(f'SELECT b_{name} y,enrol,state FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} AND b_{name} IS NOT NULL').fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],cutoff,bw,donut)
                        if est:pre.append({'outcome':name,'cutoff':cutoff,'bandwidth':bw,'donut':donut,**est})
        # exact enrolment cell diagnostics
        cells=[]
        for cutoff,bws in CUTOFFS.items():
            bw=max(bws)
            for e,nn,mr,me,pr in con.execute(f'SELECT CAST(enrol AS INT),COUNT(*),AVG(receipt),AVG(expenditure),AVG(CASE WHEN receipt>0 THEN 1.0 ELSE 0.0 END) FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} GROUP BY 1 ORDER BY 1').fetchall():cells.append({'cutoff':cutoff,'enrol':e,'n':nn,'mean_receipt':mr,'mean_expenditure':me,'positive_rate':pr})
        density=[]
        for cutoff,bws in CUTOFFS.items():
            for bw in bws:
                s=[r for r in cells if r['cutoff']==cutoff and abs(r['enrol']-cutoff)<=bw];e=np.array([r['enrol'] for r in s],float);cnt=np.array([r['n'] for r in s],float);x=e-(cutoff+.5);d=(e>cutoff).astype(float);X=np.column_stack([np.ones(len(e)),d,x,d*x]);beta=np.linalg.lstsq(X,np.log(cnt+.5),rcond=None)[0];left=sum(r['n'] for r in s if cutoff-5<=r['enrol']<=cutoff-1);right=sum(r['n'] for r in s if cutoff+1<=r['enrol']<=cutoff+5);density.append({'cutoff':cutoff,'bandwidth':bw,'log_density_jump':float(beta[1]),'implied_pct':float((math.exp(beta[1])-1)*100),'right_left_5_ratio':right/left if left else None,'left5':left,'right5':right})
        write_csv(out/'estimates.csv',rows);write_csv(out/'pretreatment.csv',pre);write_csv(out/'cells.csv',cells);write_csv(out/'density.csv',density)
        central=[]
        for cutoff,bw in ((100,30),(250,30),(175,30),(325,30)):
            central += [r for r in rows if r['cutoff']==cutoff and r['bandwidth']==bw and r['donut']==1]
        summary={'n':int(n),'central_specs':central,'density':density}
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print('CENTRAL SPECS')
        for r in central:print(json.dumps(r),flush=True)
        print('DENSITY')
        for r in density:print(json.dumps(r),flush=True)
        con.close()

if __name__=='__main__':main()
