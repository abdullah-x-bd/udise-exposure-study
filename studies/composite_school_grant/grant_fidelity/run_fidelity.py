from __future__ import annotations

import csv, json, math, os, runpy, tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='fidelity_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
C=250.5;GOV='(1,2,3)'


def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('school id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c,m):
    return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,m+1) for s in ('b','g') if f'c{k}_{s}' in c)

def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def rd(y,x,bw):
    m=np.isfinite(y)&np.isfinite(x)&(np.abs(x-C)<=bw);y=y[m];x=x[m]
    if len(y)<300:return None
    z=x-C;t=(x>=C).astype(float);w=np.maximum(0,1-np.abs(z)/bw);X=np.c_[np.ones(len(x)),t,z,t*z]
    A=X.T@(w[:,None]*X)
    try:B=np.linalg.inv(A)
    except np.linalg.LinAlgError:B=np.linalg.pinv(A)
    b=B@(X.T@(w*y));e=y-X@b;M=X.T@(((w*e)**2)[:,None]*X);V=B@M@B*len(y)/max(1,len(y)-4);se=float(np.sqrt(max(0,V[1,1])));tau=float(b[1]);p=math.erfc(abs(tau/se)/math.sqrt(2)) if se>0 else None
    return {'tau':tau,'se':se,'p':p,'ci_low':tau-1.96*se,'ci_high':tau+1.96*se,'n':len(y)}

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);report=YEARS[ai+3];grant_fy=YEARS[ai+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/grant_fidelity/{ay}');out.mkdir(parents=True,exist_ok=True);rows=[];rates=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4')
    with tempfile.TemporaryDirectory(prefix='fidelity_') as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));p1=src(extract(repo,tok,ay,'profile_1',root));p2=src(extract(repo,tok,report,'profile_2',root));ec,pc,gc=cols(con,en),cols(con,p1),cols(con,p2);ei,pi,gi=ident(ec),ident(pc),ident(gc);e12=esum(ec,12);e8=esum(ec,8);f=efilt(con,en,ec)
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({e12}) enrol,SUM({e8}) enrol18 FROM {en} WHERE {f} GROUP BY 1")
        d=con.execute(f"""SELECT e.enrol,e.enrol18,{nref(gc,'grants_receipt','g')} receipt,{nref(gc,'grants_expenditure','g')} expenditure FROM ee e JOIN {p1} p ON e.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) LEFT JOIN {p2} g ON e.pseudocode=CAST(g.{qid(gi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e.enrol BETWEEN 180 AND 321""").df()
        for sample,mask in [('all',np.ones(len(d),bool)),('pm220',d.enrol18.fillna(99999).to_numpy(float)<=220),('pm200',d.enrol18.fillna(99999).to_numpy(float)<=200)]:
            z=d.loc[mask].copy();x=z.enrol.to_numpy(float);r=z.receipt.to_numpy(float);q=z.expenditure.to_numpy(float);vr=np.isfinite(r);vq=np.isfinite(q)
            outcomes={
                'receipt_exact50000':np.where(vr,np.isclose(r,50000).astype(float),np.nan),
                'receipt_exact75000':np.where(vr,np.isclose(r,75000).astype(float),np.nan),
                'receipt_ge75000':np.where(vr,(r>=75000).astype(float),np.nan),
                'receipt_gt50000':np.where(vr,(r>50000).astype(float),np.nan),
                'receipt_positive':np.where(vr,(r>0).astype(float),np.nan),
                'expenditure_exact50000':np.where(vq,np.isclose(q,50000).astype(float),np.nan),
                'expenditure_exact75000':np.where(vq,np.isclose(q,75000).astype(float),np.nan),
                'expenditure_ge75000':np.where(vq,(q>=75000).astype(float),np.nan),
                'expenditure_gt50000':np.where(vq,(q>50000).astype(float),np.nan),
                'expenditure_positive':np.where(vq,(q>0).astype(float),np.nan),
            }
            if vr.sum()>100:outcomes['receipt_w99']=np.where(vr,np.minimum(r,np.nanquantile(r,.99)),np.nan)
            if vq.sum()>100:outcomes['expenditure_w99']=np.where(vq,np.minimum(q,np.nanquantile(q,.99)),np.nan)
            for name,y in outcomes.items():
                for bw in (15,20,30,40):
                    a=rd(y,x,bw)
                    if a:rows.append({'assignment_year':ay,'grant_financial_year':grant_fy,'udise_report_year':report,'sample':sample,'outcome':name,'bw':bw,**a})
            for lo,hi,label in [(241,250,'241_250'),(251,260,'251_260'),(246,250,'246_250'),(251,255,'251_255')]:
                s=z[(z.enrol>=lo)&(z.enrol<=hi)];rr=s.receipt.to_numpy(float);qq=s.expenditure.to_numpy(float)
                rates.append({'assignment_year':ay,'grant_financial_year':grant_fy,'udise_report_year':report,'sample':sample,'enrolment_window':label,'n':len(s),'receipt_exact50000':float(np.nanmean(np.isclose(rr,50000))) if len(s) else None,'receipt_exact75000':float(np.nanmean(np.isclose(rr,75000))) if len(s) else None,'receipt_ge75000':float(np.nanmean(rr>=75000)) if len(s) else None,'receipt_positive':float(np.nanmean(rr>0)) if len(s) else None,'expenditure_exact50000':float(np.nanmean(np.isclose(qq,50000))) if len(s) else None,'expenditure_exact75000':float(np.nanmean(np.isclose(qq,75000))) if len(s) else None,'expenditure_ge75000':float(np.nanmean(qq>=75000)) if len(s) else None})
    write(out/'fidelity_rd.csv',rows);write(out/'local_band_rates.csv',rates)
    md=['# Grant fidelity '+ay,'',f'Enrolment vintage {ay}; grant financial year {grant_fy}; UDISE financial field year {report}.','']
    for r in rows:
        if r['sample']=='all' and r['bw']==30 and r['outcome'] in ('receipt_exact75000','receipt_ge75000','receipt_w99','expenditure_exact75000','expenditure_ge75000','expenditure_w99'):
            unit=' pp' if 'exact' in r['outcome'] or 'ge' in r['outcome'] else ' Rs'
            val=100*r['tau'] if unit==' pp' else r['tau'];md.append(f"- {r['outcome']}: {val:.2f}{unit}, p={r['p']:.3g}")
    (out/'RESULTS.md').write_text('\n'.join(md),encoding='utf-8');print('\n'.join(md),flush=True);con.close()

if __name__=='__main__':main()
