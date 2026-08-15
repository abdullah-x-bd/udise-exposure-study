from __future__ import annotations
import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='density_audit_lib')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
CORE={1,2,3};BROAD={1,2,3,6,89,90};TRUE=[30,100,250];PLACEBO=[50,75,125,150,175,200,225,275,300,325,350,375,400]

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x: raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:
        return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c)
    return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):
    return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def statex(c,a='p'):
    for k in ('state','state_id','state_code','state_cd'):
        r=ref(c,k,a)
        if r:return f"CAST({r} AS VARCHAR)"
    return "'NA'"

def heap(v):
    if v%100==0:return 5
    if v%50==0:return 4
    if v%25==0:return 3
    if v%10==0:return 2
    if v%5==0:return 1
    return 0

def fit_counterfactual(cmap,c,window=40,zone=5):
    xs=np.arange(max(1,c-window),min(400,c+window+1)+1)
    y=np.array([cmap.get(int(x),0) for x in xs],float)
    z=(xs-(c+.5))/window
    h=np.array([heap(int(x)) for x in xs])
    sensitive=(xs>=c-zone)&(xs<=c+zone)
    X=np.column_stack([np.ones(len(xs)),z,z*z,z*z*z]+[(h==k).astype(float) for k in range(1,6)])
    fit=~sensitive
    try:
        m=sm.GLM(y[fit],X[fit],family=sm.families.Poisson()).fit(maxiter=200,disp=0)
        pred=m.predict(X)
    except Exception:
        b=np.linalg.lstsq(X[fit],np.log1p(y[fit]),rcond=None)[0]
        pred=np.maximum(0,np.expm1(X@b))
    above=(xs>=c+1)&(xs<=c+zone);below=(xs>=c-zone)&(xs<=c-1)
    oa,ea=float(y[above].sum()),float(pred[above].sum());ob,eb=float(y[below].sum()),float(pred[below].sum())
    if ea<=0 or eb<=0:return None,None
    summary={'threshold_end':c,'threshold_start':c+1,'obs_above':oa,'expected_above':ea,'excess_ratio_above':oa/ea-1,'obs_below':ob,'expected_below':eb,'excess_ratio_below':ob/eb-1,'heaping_adjusted_asymmetry':(oa/ea-1)-(ob/eb-1),'count_at_threshold_end':cmap.get(c,0),'count_first_above':cmap.get(c+1,0)}
    detail=pd.DataFrame({'enrolment':xs,'observed':y,'expected':pred,'residual':y-pred,'ratio':np.divide(y,pred,out=np.full_like(y,np.nan),where=pred>0)})
    return summary,detail

def bh(rows,pkey='p'):
    vals=[(i,r[pkey]) for i,r in enumerate(rows) if r.get(pkey) is not None and np.isfinite(r[pkey])]
    if not vals:return rows
    vals=sorted(vals,key=lambda t:t[1]);m=len(vals);q=[0.0]*m;running=1.0
    for j in range(m-1,-1,-1):
        rank=j+1;running=min(running,vals[j][1]*m/rank);q[j]=running
    for (pair,qq) in zip(vals,q):rows[pair[0]]['bh_q']=qq
    return rows

def write_csv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def draw_density(df,year,universe,out):
    g=df.groupby('enrolment').size().reindex(range(0,401),fill_value=0)
    fig,ax=plt.subplots(figsize=(13,5))
    ax.plot(g.index,g.values,linewidth=1)
    for x in (30.5,100.5,250.5):ax.axvline(x,linestyle='--',linewidth=1)
    ax.set_xlim(0,400);ax.set_xlabel('Reported total enrolment, Classes I-XII');ax.set_ylabel('Number of schools')
    ax.set_title(f'{year}: school count by reported enrolment ({universe})')
    fig.tight_layout();fig.savefig(out/f'density_0_400_{universe}.png',dpi=180);plt.close(fig)

def draw_local(detail,year,universe,out):
    if detail is None:return
    d=detail[(detail.enrolment>=220)&(detail.enrolment<=280)]
    fig,ax=plt.subplots(figsize=(11,5));ax.plot(d.enrolment,d.observed,label='Observed');ax.plot(d.enrolment,d.expected,label='Heaping-adjusted counterfactual');ax.axvline(250.5,linestyle='--',linewidth=1);ax.set_xlabel('Reported enrolment');ax.set_ylabel('Number of schools');ax.set_title(f'{year}: local density around 250/251 ({universe})');ax.legend();fig.tight_layout();fig.savefig(out/f'local_250_counterfactual_{universe}.png',dpi=180);plt.close(fig)

def main():
    year=os.environ['YEAR'];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/enrolment_integrity/{year}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect()
    with tempfile.TemporaryDirectory(prefix=f'density_{year}_') as td:
        root=Path(td);en=src(extract(repo,tok,year,'enrolment_1',root));p1=src(extract(repo,tok,year,'profile_1',root));ec,pc=cols(con,en),cols(con,p1);ei,pi=ident(ec),ident(pc);f=efilt(con,en,ec);es=esum(ec);st=statex(pc,'p')
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,CAST(SUM({es}) AS INTEGER) enrol FROM {en} WHERE {f} GROUP BY 1")
        d=con.execute(f"SELECT e.pseudocode,e.enrol,{st} state,CAST({nref(pc,'managment','p')} AS INTEGER) management FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE e.enrol BETWEEN 0 AND 400").df();con.close()
    all_counts=[];all_thresh=[];state_rows=[]
    for universe,codes in [('core_123',CORE),('broad_state',BROAD)]:
        x=d[d.management.isin(codes)].copy();draw_density(x,year,universe,out);cmap=x.enrol.value_counts().to_dict();local250=None
        for c in TRUE+PLACEBO:
            s,detail=fit_counterfactual(cmap,c)
            if s:
                s.update({'academic_year':year,'universe':universe,'kind':'true' if c in TRUE else 'placebo'});all_thresh.append(s)
                if c==250:local250=detail
        draw_local(local250,year,universe,out)
        g=x.groupby('enrolment').size().reindex(range(0,401),fill_value=0)
        for e,n in g.items():all_counts.append({'academic_year':year,'universe':universe,'enrolment':int(e),'school_count':int(n)})
        if universe=='broad_state':
            for state,z in x.groupby('state'):
                if len(z)<500:continue
                s,_=fit_counterfactual(z.enrol.value_counts().to_dict(),250)
                if s:
                    # rough normal-score diagnostic for ranking only
                    den=max(s['expected_above']+s['expected_below'],1);se=math.sqrt(2/den);p=math.erfc(abs(s['heaping_adjusted_asymmetry']/se)/math.sqrt(2));state_rows.append({'academic_year':year,'state':str(state),'n_schools_0_400':len(z),'p':p,**s})
    bh(state_rows)
    write_csv(out/'density_counts_0_400.csv',all_counts);write_csv(out/'threshold_excess.csv',all_thresh);write_csv(out/'state_250_excess.csv',state_rows)
    t=[r for r in all_thresh if r['universe']=='broad_state' and r['threshold_end']==250]
    result={'academic_year':year,'n_rows':len(d),'broad_250':t[0] if t else None,'note':'Density irregularities are not by themselves evidence of recruitment manipulation or false reporting.'}
    (out/'RESULTS.md').write_text('# Enrolment integrity '+year+'\n\n```json\n'+json.dumps(result,indent=2,default=float)+'\n```\n',encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True)
if __name__=='__main__':main()
