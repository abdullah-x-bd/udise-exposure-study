from __future__ import annotations
import csv,json,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='minimal_cross_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref']
CORE={1,2,3};BROAD={1,2,3,6,89,90};THRESHOLDS=[(250,'true'),(200,'placebo'),(300,'placebo')]

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def statex(c,a='p'):
    for k in ('state','state_id','state_code','state_cd'):
        r=ref(c,k,a)
        if r:return f"CAST({r} AS VARCHAR)"
    return "'NA'"

def write_csv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def summarize(z,c,label,scope='national',state=None):
    a=z[(z.x0>=c-20)&(z.x0<=c)].copy()
    if len(a)<50:return None
    a['distance_below']=c-a.x0
    a['needed_increment']=(c+1)-a.x0
    a['actual_increment']=a.x1-a.x0
    a['landing_offset']=a.x1-(c+1)
    exact=a[a.x1==c+1];first5=a[(a.x1>=c+1)&(a.x1<=c+5)];next5=a[(a.x1>=c+6)&(a.x1<=c+10)]
    # Equal-weight standardization over starting distances that have at least five schools.
    per=[]
    for d,g in a.groupby('distance_below'):
        if len(g)>=5:per.append({'d':int(d),'n':len(g),'p_exact':float((g.x1==c+1).mean()),'p_first5':float(((g.x1>=c+1)&(g.x1<=c+5)).mean())})
    std_exact=float(np.mean([r['p_exact'] for r in per])) if per else np.nan
    std_first5=float(np.mean([r['p_first5'] for r in per])) if per else np.nan
    return {'scope':scope,'state':state,'threshold_end':c,'threshold_start':c+1,'kind':label,'n_approach20':len(a),'raw_p_land_exact_first_above':float((a.x1==c+1).mean()),'distance_standardized_p_land_exact_first_above':std_exact,'raw_p_land_first5_above':float(((a.x1>=c+1)&(a.x1<=c+5)).mean()),'distance_standardized_p_land_first5_above':std_first5,'p_increment_exactly_minimum_needed':float((a.actual_increment==a.needed_increment).mean()),'n_exact_first_above':len(exact),'p_exact_first_above_revert_below_next_year':float((exact.x2<=c).mean()) if len(exact) else np.nan,'n_first5_above':len(first5),'p_first5_above_revert_below_next_year':float((first5.x2<=c).mean()) if len(first5) else np.nan,'n_next5_above':len(next5),'p_next5_above_revert_below_next_year':float((next5.x2<=c).mean()) if len(next5) else np.nan,'mean_next_year_change_exact_first_above':float((exact.x2-exact.x1).mean()) if len(exact) else np.nan,'median_next_year_change_exact_first_above':float((exact.x2-exact.x1).median()) if len(exact) else np.nan}

def main():
    y0=os.environ['START_YEAR'];i=YEARS.index(y0);y1,y2=YEARS[i+1],YEARS[i+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/minimal_crossing/{y0}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect()
    with tempfile.TemporaryDirectory(prefix=f'mincross_{y0}_') as td:
        root=Path(td)
        for j,y in enumerate((y0,y1,y2)):
            en=src(extract(repo,tok,y,'enrolment_1',root));ec=cols(con,en);ei=ident(ec);f=efilt(con,en,ec);es=esum(ec);con.execute(f"CREATE TEMP TABLE e{j} AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,CAST(SUM({es}) AS INTEGER) x{j} FROM {en} WHERE {f} GROUP BY 1")
        p1=src(extract(repo,tok,y0,'profile_1',root));pc=cols(con,p1);pi=ident(pc);st=statex(pc,'p')
        d=con.execute(f"SELECT e0.pseudocode,e0.x0,e1.x1,e2.x2,{st} state,CAST({nref(pc,'managment','p')} AS INTEGER) management FROM e0 JOIN e1 USING(pseudocode) JOIN e2 USING(pseudocode) JOIN {p1} p ON e0.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE e0.x0 BETWEEN 170 AND 320").df();con.close()
    rows=[];state_rows=[];offset_rows=[]
    for universe,codes in [('core_123',CORE),('broad_state',BROAD)]:
        x=d[d.management.isin(codes)].copy()
        for c,label in THRESHOLDS:
            r=summarize(x,c,label)
            if r:rows.append({'start_year':y0,'middle_year':y1,'end_year':y2,'universe':universe,**r})
            a=x[(x.x0>=c-20)&(x.x0<=c)].copy();a['landing_offset']=a.x1-(c+1)
            for off,n in a.landing_offset.value_counts().sort_index().items():
                if -20<=off<=20:offset_rows.append({'start_year':y0,'universe':universe,'threshold_end':c,'kind':label,'landing_offset_from_first_above':int(off),'school_count':int(n)})
        if universe=='broad_state':
            for state,g in x.groupby('state'):
                for c,label in THRESHOLDS:
                    r=summarize(g,c,label,scope='state',state=str(state))
                    if r and r['n_approach20']>=100:state_rows.append({'start_year':y0,'middle_year':y1,'end_year':y2,'universe':universe,**r})
    write_csv(out/'minimal_crossing_national.csv',rows);write_csv(out/'minimal_crossing_states.csv',state_rows);write_csv(out/'landing_offset_histogram.csv',offset_rows)
    true=next((r for r in rows if r['universe']=='broad_state' and r['threshold_end']==250),None);pls=[r for r in rows if r['universe']=='broad_state' and r['kind']=='placebo']
    result={'start_year':y0,'true_250_251':true,'placebos':pls,'interpretation':'An excess of exact minimum crossings plus unusually high next-year reversion would be consistent with threshold-targeting, but cannot distinguish aggressive recruitment from false reporting without additional evidence.'}
    (out/'RESULTS.md').write_text('# Minimal crossing audit '+y0+'\n\n```json\n'+json.dumps(result,indent=2,default=float)+'\n```\n',encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True)
if __name__=='__main__':main()
