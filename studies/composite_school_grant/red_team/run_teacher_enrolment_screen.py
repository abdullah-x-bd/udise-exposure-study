from __future__ import annotations

import csv,json,math,os,runpy,tempfile
from pathlib import Path
import duckdb

PANEL=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='panel_lib')
FOCUS=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='focus_lib')
extract_archive=PANEL['extract_archive'];csv_source=PANEL['csv_source'];source_columns=PANEL['source_columns'];identify_early_social_labels=PANEL['identify_early_social_labels'];qid=PANEL['qid'];lit=PANEL['lit'];ref=PANEL['ref'];nref=PANEL['nref'];num=PANEL['num'];rd=FOCUS['rd']
CUTOFF=250;BW=30;DONUT=1

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def write_csv(p,rows):
    if not rows:p.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def bh(rows):
    v=[(i,float(r['p'])) for i,r in enumerate(rows) if r.get('p') is not None and math.isfinite(float(r['p']))];v.sort(key=lambda x:x[1]);m=len(v);run=1
    for rank in range(m,0,-1):
        i,p=v[rank-1];q=min(run,p*m/rank);run=q;rows[i]['q_bh']=q

def enrol_filter(con,src,c):
    if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN (1,2,3,4)"
    labs=identify_early_social_labels(con,src,c);d=ref(c,'item_desc');return f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})"

def make_enrol(con,src,c,name):
    i=ident(c);f=enrol_filter(con,src,c);sels=[]
    for cl in range(1,13):
        terms=[f"COALESCE({nref(c,f'c{cl}_{s}')},0)" for s in ('b','g') if f'c{cl}_{s}' in c]
        if terms:sels.append(f"SUM({' + '.join(terms)}) e_c{cl}")
    pp=[f"COALESCE({nref(c,k)},0)" for k in ('cpp_b','cpp_g') if k in c]
    if pp:sels.append(f"SUM({' + '.join(pp)}) e_preprimary")
    con.execute(f"CREATE TEMP TABLE {name} AS SELECT CAST({qid(i)} AS VARCHAR) pseudocode,{','.join(sels)} FROM {src} WHERE {f} GROUP BY 1")
    return [x.split()[-1] for x in sels]

def make_teacher(con,src,c,name):
    i=ident(c); fields=[x for x in ('total_tch','male','female','transgender','gen_tch','sc_tch','st_tch','obc_tch','regular','contract','part_time','below_graduate','graduate','post_graduate_and_above','trained_comp','trained_cwsn','teacher_involve_non_training_assignment') if x in c]
    con.execute(f"CREATE TEMP TABLE {name} AS SELECT CAST({qid(i)} AS VARCHAR) pseudocode,{','.join(nref(c,x)+' t_'+x for x in fields)} FROM {src}")
    return ['t_'+x for x in fields]

def main():
    ay=os.environ['ASSIGN_YEAR'];future=[x for x in os.environ['FUTURE_YEARS'].split(',') if x];repo=os.environ['HF_DATASET_REPO'];token=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    rows=[]
    with tempfile.TemporaryDirectory(prefix='csg_people_') as td:
        root=Path(td); ae=csv_source(extract_archive(repo,token,ay,'enrolment_1',root));ap=csv_source(extract_archive(repo,token,ay,'profile_1',root));at=csv_source(extract_archive(repo,token,ay,'teacher',root));ec,pc,tc=map(lambda x:source_columns(con,x),(ae,ap,at));eid,pid=ident(ec),ident(pc)
        make_enrol(con,ae,ec,'be');make_teacher(con,at,tc,'bt')
        total=' + '.join(f'COALESCE(be.e_c{x},0)' for x in range(1,13))
        con.execute(f"CREATE TEMP TABLE base AS SELECT CAST(p.{qid(pid)} AS VARCHAR) pseudocode,({total}) enrol,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state FROM {ap} p JOIN be ON CAST(p.{qid(pid)} AS VARCHAR)=be.pseudocode WHERE {nref(pc,'managment','p')} IN(1,2,3) AND ({total}) BETWEEN 220 AND 280")
        for j,fy in enumerate(future):
            en=csv_source(extract_archive(repo,token,fy,'enrolment_1',root));te=csv_source(extract_archive(repo,token,fy,'teacher',root));prof=csv_source(extract_archive(repo,token,fy,'profile_1',root));ecc,tcc,pcc=map(lambda x:source_columns(con,x),(en,te,prof));make_enrol(con,en,ecc,f'oe{j}');make_teacher(con,te,tcc,f'ot{j}');pfi=ident(pcc)
            con.execute(f"CREATE TEMP TABLE mg{j} AS SELECT CAST({qid(pfi)} AS VARCHAR) pseudocode,{nref(pcc,'managment')} mgmt FROM {prof}")
            # Common teacher count fields and meaningful ratios.
            bcols={d[0] for d in con.execute('SELECT * FROM bt LIMIT 0').description};ocols={d[0] for d in con.execute(f'SELECT * FROM ot{j} LIMIT 0').description}
            common=sorted((bcols&ocols)-{'pseudocode'})
            for field in common:
                arr=con.execute(f"SELECT (o.{field}-b.{field}) y,s.enrol,s.state FROM base s JOIN bt b USING(pseudocode) JOIN ot{j} o USING(pseudocode) JOIN mg{j} m USING(pseudocode) WHERE m.mgmt IN(1,2,3) AND b.{field} IS NOT NULL AND o.{field} IS NOT NULL").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                if est:rows.append({'outcome_year':fy,'family':'teacher_count','field':field,**est})
            for nm,numer,den in [('female_teacher_share','t_female','t_total_tch'),('trained_computer_teacher_share','t_trained_comp','t_total_tch'),('contract_teacher_share','t_contract','t_total_tch')]:
                if numer in common and den in common:
                    arr=con.execute(f"SELECT ((o.{numer}/NULLIF(o.{den},0))-(b.{numer}/NULLIF(b.{den},0))) y,s.enrol,s.state FROM base s JOIN bt b USING(pseudocode) JOIN ot{j} o USING(pseudocode) JOIN mg{j} m USING(pseudocode) WHERE m.mgmt IN(1,2,3) AND b.{den}>0 AND o.{den}>0").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                    if est:rows.append({'outcome_year':fy,'family':'teacher_ratio','field':nm,**est})
            # Class-specific enrolment outcomes. These can reveal retention/composition changes, but not achievement.
            bcols={d[0] for d in con.execute('SELECT * FROM be LIMIT 0').description};ocols={d[0] for d in con.execute(f'SELECT * FROM oe{j} LIMIT 0').description}
            for field in sorted((bcols&ocols)-{'pseudocode'}):
                arr=con.execute(f"SELECT (o.{field}-b.{field}) y,s.enrol,s.state FROM base s JOIN be b USING(pseudocode) JOIN oe{j} o USING(pseudocode) JOIN mg{j} m USING(pseudocode) WHERE m.mgmt IN(1,2,3) AND b.{field} IS NOT NULL AND o.{field} IS NOT NULL").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                if est:rows.append({'outcome_year':fy,'family':'enrolment_class','field':field,**est})
            # PTR combines later enrolment and teachers.
            if 't_total_tch' in common:
                etot=' + '.join(f'COALESCE(o.e_c{x},0)' for x in range(1,13)); btot=' + '.join(f'COALESCE(b.e_c{x},0)' for x in range(1,13))
                arr=con.execute(f"SELECT ((({etot})/NULLIF(t2.t_total_tch,0))-(({btot})/NULLIF(t1.t_total_tch,0))) y,s.enrol,s.state FROM base s JOIN be b USING(pseudocode) JOIN oe{j} o USING(pseudocode) JOIN bt t1 USING(pseudocode) JOIN ot{j} t2 USING(pseudocode) JOIN mg{j} m USING(pseudocode) WHERE m.mgmt IN(1,2,3) AND t1.t_total_tch>0 AND t2.t_total_tch>0").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                if est:rows.append({'outcome_year':fy,'family':'staffing','field':'pupil_teacher_ratio_change',**est})
    for fy in future:
        for fam in set(r['family'] for r in rows if r['outcome_year']==fy):bh([r for r in rows if r['outcome_year']==fy and r['family']==fam])
    write_csv(out/'teacher_enrolment_screen.csv',rows)
    hits=[r for r in rows if r.get('q_bh',1)<.10]
    (out/'teacher_enrolment_summary.json').write_text(json.dumps({'assignment_year':ay,'future_years':future,'tested':len(rows),'fdr_hits':hits},indent=2),encoding='utf-8')
    print('TEACHER/ENROLMENT SCREEN',ay,'tested',len(rows),'FDR hits',len(hits),flush=True)
    for r in hits:print(json.dumps(r),flush=True)
    con.close()
if __name__=='__main__':main()
