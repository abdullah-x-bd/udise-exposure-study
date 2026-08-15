from __future__ import annotations
import csv,json,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='cross_rec_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
BROAD={1,2,3,6,89,90}

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

def load_enrol(con,repo,tok,year,root):
    en=src(extract(repo,tok,year,'enrolment_1',root));ec=cols(con,en);ei=ident(ec);f=efilt(con,en,ec);es=esum(ec)
    return con.execute(f"SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,CAST(SUM({es}) AS DOUBLE) enrol FROM {en} WHERE {f} GROUP BY 1").df()

def load_receipt(con,repo,tok,year,root):
    p2=src(extract(repo,tok,year,'profile_2',root));pc=cols(con,p2);pi=ident(pc)
    return con.execute(f"SELECT CAST({qid(pi)} AS VARCHAR) pseudocode,CAST({nref(pc,'grants_receipt')} AS DOUBLE) receipt FROM {p2}").df()

def km_curve(panel,ids,group,state):
    z=panel[panel.pseudocode.isin(ids)].copy();risk=set(ids);surv=1.0;rows=[]
    for lag in sorted(z.lag.unique()):
        q=z[(z.lag==lag)&(z.pseudocode.isin(risk))].copy();n_risk=len(risk)
        if n_risk==0:break
        if group=='crosser':eligible=q.enrol>=251
        else:eligible=q.enrol<=250
        # Eligibility changes are censoring events before financial recognition at that lag.
        cens=set(q.loc[~eligible.fillna(False),'pseudocode'].astype(str))
        qr=q[eligible.fillna(False)].copy();events=set(qr.loc[pd.to_numeric(qr.receipt,errors='coerce')>=75000,'pseudocode'].astype(str))
        denom=max(1,n_risk-len(cens));haz=len(events)/denom;surv*=1-haz;cum=1-surv
        rows.append({'state':state,'group':group,'lag':int(lag),'n_initial':len(ids),'n_at_risk':n_risk,'n_censored_this_lag':len(cens),'n_events_this_lag':len(events),'hazard_first_report_ge75000':haz,'cum_first_report_ge75000':cum})
        risk-=cens;risk-=events
    return rows

def summarize(curves):
    d=pd.DataFrame(curves);out=[]
    if len(d)==0:return out
    for (state,group),g in d.groupby(['state','group']):
        g=g.sort_values('lag');plateau=float(g.cum_first_report_ge75000.max());r={'state':state,'group':group,'n_initial':int(g.n_initial.iloc[0]),'max_lag':int(g.lag.max()),'observed_plateau':plateau}
        for q in (.5,.8,.9,.95,1.0):
            h=g.loc[g.cum_first_report_ge75000>=q,'lag'];r[f'N{int(q*100)}_absolute']=int(h.iloc[0]) if len(h) else None
        for q in (.5,.8,.9):
            h=g.loc[g.cum_first_report_ge75000>=q*plateau,'lag'];r[f'N{int(q*100)}_relative_to_plateau']=int(h.iloc[0]) if len(h) and plateau>0 else None
        out.append(r)
    return out

def main():
    ay=os.environ['ASSIGN_YEAR'];ai=YEARS.index(ay);prev=YEARS[ai-1];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/crossing_recognition/{ay}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix=f'crossrec_{ay}_') as td:
        root=Path(td);em1=load_enrol(con,repo,tok,prev,root).rename(columns={'enrol':'enrol_prev'});e0=load_enrol(con,repo,tok,ay,root).rename(columns={'enrol':'enrol_now'});p1=src(extract(repo,tok,ay,'profile_1',root));pc=cols(con,p1);pi=ident(pc);st=field(pc,['state','state_id','state_code','state_cd']);mg=nref(pc,'managment','p')
        prof=con.execute(f"SELECT CAST({qid(pi)} AS VARCHAR) pseudocode,CAST({st} AS VARCHAR) state,CAST({mg} AS INTEGER) management FROM {p1}").df();base=em1.merge(e0,on='pseudocode').merge(prof,on='pseudocode');base=base[base.management.isin(BROAD)].copy();base['group']=np.where((base.enrol_prev>=221)&(base.enrol_prev<=250)&(base.enrol_now>=251)&(base.enrol_now<=280),'crosser',np.where((base.enrol_prev>=221)&(base.enrol_prev<=250)&(base.enrol_now>=221)&(base.enrol_now<=250),'control','other'));base=base[base.group!='other'].copy()
        pieces=[]
        for oi in range(ai,len(YEARS)):
            oy=YEARS[oi];lag=oi-ai;e=load_enrol(con,repo,tok,oy,root);r=load_receipt(con,repo,tok,oy,root);q=base[['pseudocode','state','group']].merge(e,on='pseudocode',how='left').merge(r,on='pseudocode',how='left');q['outcome_year']=oy;q['lag']=lag;pieces.append(q)
        con.close();panel=pd.concat(pieces,ignore_index=True)
    curves=[]
    for group in ('crosser','control'):
        ids=base.loc[base.group==group,'pseudocode'].astype(str).tolist()
        if len(ids)>=50:curves+=km_curve(panel,ids,group,'ALL')
    for state,b in base.groupby('state'):
        for group in ('crosser','control'):
            ids=b.loc[b.group==group,'pseudocode'].astype(str).tolist()
            if len(ids)>=20:curves+=km_curve(panel,ids,group,str(state))
    for r in curves:r['assignment_year']=ay
    summary=summarize(curves)
    for r in summary:r['assignment_year']=ay
    write_csv(out/'time_to_first_higher_band_report.csv',curves);write_csv(out/'recognition_time_summary.csv',summary)
    # side-by-side state comparison at each lag where both groups exist
    d=pd.DataFrame(curves);diff=[]
    if len(d):
        a=d[d.group=='crosser'];b=d[d.group=='control'];m=a.merge(b,on=['assignment_year','state','lag'],suffixes=('_crosser','_control'))
        for _,r in m.iterrows():diff.append({'assignment_year':ay,'state':r.state,'lag':int(r.lag),'crosser_cumulative':float(r.cum_first_report_ge75000_crosser),'control_cumulative':float(r.cum_first_report_ge75000_control),'net_cumulative_difference':float(r.cum_first_report_ge75000_crosser-r.cum_first_report_ge75000_control),'n_crosser_initial':int(r.n_initial_crosser),'n_control_initial':int(r.n_initial_control)})
    write_csv(out/'crosser_control_difference.csv',diff)
    (out/'RESULTS.md').write_text('# Time to first higher-band report '+ay+'\n\nCrossers are schools moving from 221-250 to 251-280. They are censored if they subsequently fall back to <=250. Controls remain below and are censored if they cross above. The event is the first later UDISE report of receipt >= Rs 75,000. This measures recorded recognition, not audited cash arrival.\n\n```json\n'+json.dumps(summary,indent=2,default=float)+'\n```\n',encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True)
if __name__=='__main__':main()
