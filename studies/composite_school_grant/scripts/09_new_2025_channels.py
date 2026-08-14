from __future__ import annotations

import csv, json, math, os, re, runpy, tempfile
from pathlib import Path
import duckdb

PANEL=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='panel_lib')
FOCUS=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='focus_lib')
extract_archive=PANEL['extract_archive'];csv_source=PANEL['csv_source'];source_columns=PANEL['source_columns'];identify_early_social_labels=PANEL['identify_early_social_labels'];qid=PANEL['qid'];lit=PANEL['lit'];ref=PANEL['ref'];nref=PANEL['nref'];num=PANEL['num'];rd=FOCUS['rd']
CUTOFF=250;BW=30;DONUT=1
EXCLUDE=('pseudocode','psuedocode','udise','school_code','state','district','block','cluster','village','panchayat','ward','pin','latitude','longitude','management','managment','school_category','school_type','rural_urban','lowclass','highclass','year_estb','school_name','respondent','mobile','email','loc_desc','location')

def norm(s:str)->str:return re.sub(r'[^a-z0-9]+','_',s.lower().replace('\ufeff','')).strip('_')
def write_csv(path:Path,rows:list[dict]):
    if not rows:path.write_text('',encoding='utf-8');return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys:keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def bh(rows:list[dict]):
    vals=[(i,r['p']) for i,r in enumerate(rows) if r.get('p') is not None and math.isfinite(r['p'])];vals.sort(key=lambda x:x[1]);m=len(vals);run=1.0
    for rank in range(m,0,-1):
        i,p=vals[rank-1];q=min(run,p*m/rank);run=q;rows[i]['q_bh']=q

def total_enrol(con,src,c):
    terms=[f"COALESCE({nref(c,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in c]
    if 'item_group' in c and 'item_id' in c:f=f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN (1,2,3,4)"
    else:
        labs=identify_early_social_labels(con,src,c);d=ref(c,'item_desc');f=f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})"
    return ' + '.join(terms),f

def candidate(n:str)->bool:
    return not any(x in n for x in EXCLUDE)

def main():
    ay=os.environ['ASSIGN_YEAR'];repo=os.environ['HF_DATASET_REPO'];token=os.environ['HF_TOKEN'];oy='2025-26'
    out=Path(f'studies/composite_school_grant/outputs/new_2025_channels/{ay}_to_2025-26');out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix='csg_new25_') as td:
        root=Path(td)
        enr=csv_source(extract_archive(repo,token,ay,'enrolment_1',root));ap1=csv_source(extract_archive(repo,token,ay,'profile_1',root));op1=csv_source(extract_archive(repo,token,oy,'profile_1',root));fac=csv_source(extract_archive(repo,token,oy,'facility',root));safety=csv_source(extract_archive(repo,token,oy,'safety',root));p2=csv_source(extract_archive(repo,token,oy,'profile_2',root))
        ec,ac,oc,fc,sc,p2c=[source_columns(con,x) for x in (enr,ap1,op1,fac,safety,p2)]
        ids=[]
        for c in (ec,ac,oc,fc,sc,p2c):
            x=c.get('pseudocode') or c.get('psuedocode')
            if not x:raise RuntimeError('school id missing')
            ids.append(x)
        total,filt=total_enrol(con,enr,ec)
        con.execute(f"CREATE TEMP TABLE e AS SELECT CAST({qid(ids[0])} AS VARCHAR) pseudocode,SUM({total}) enrol FROM {enr} WHERE {filt} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE a AS SELECT CAST({qid(ids[1])} AS VARCHAR) pseudocode,CAST({ref(ac,'state')} AS VARCHAR) state_key,{nref(ac,'managment')} mgmt FROM {ap1}")
        con.execute(f"CREATE TEMP TABLE o AS SELECT CAST({qid(ids[2])} AS VARCHAR) pseudocode,{nref(oc,'managment')} mgmt FROM {op1}")
        con.execute(f"CREATE TEMP TABLE s AS SELECT e.pseudocode,e.enrol,DENSE_RANK() OVER(ORDER BY a.state_key) state FROM e JOIN a USING(pseudocode) JOIN o USING(pseudocode) WHERE a.mgmt IN(1,2,3) AND o.mgmt IN(1,2,3) AND e.enrol BETWEEN {CUTOFF-BW} AND {CUTOFF+BW}")
        n=con.execute('SELECT COUNT(*) FROM s').fetchone()[0];states=con.execute('SELECT COUNT(DISTINCT state) FROM s').fetchone()[0];print('SAMPLE',ay,n,states,flush=True)
        rows=[]
        for family,source,c,idname in [('facility_2025',fac,fc,ids[3]),('safety_2025',safety,sc,ids[4]),('profile1_2025',op1,oc,ids[2]),('profile2_2025',p2,p2c,ids[5])]:
            for name,actual in c.items():
                if not candidate(name):continue
                expr=num('r.'+qid(actual))
                stats=con.execute(f"SELECT COUNT(*) FILTER(WHERE {expr} IS NOT NULL),COUNT(DISTINCT {expr}) FILTER(WHERE {expr} IS NOT NULL),AVG({expr}) FILTER(WHERE {expr} IS NOT NULL),STDDEV_POP({expr}) FILTER(WHERE {expr} IS NOT NULL),MIN({expr}),MAX({expr}) FROM s JOIN {source} r ON s.pseudocode=CAST(r.{qid(idname)} AS VARCHAR)").fetchone()
                nn,dist,mean,sd,mn,mx=stats
                if nn is None or nn<2000 or (dist or 0)<2:continue
                arr=con.execute(f"SELECT {expr} y,s.enrol,s.state FROM s JOIN {source} r ON s.pseudocode=CAST(r.{qid(idname)} AS VARCHAR) WHERE {expr} IS NOT NULL").fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
                if est:rows.append({'assignment_year':ay,'family':family,'field':name,'n_numeric':int(nn),'distinct':int(dist),'mean':mean,'sd':sd,'min':mn,'max':mx,**est,'std_effect':est['tau']/sd if sd not in (None,0) else None})
        bh(rows);rows.sort(key=lambda r:r.get('q_bh',1))
        write_csv(out/'screen.csv',rows)
        candidates=[r for r in rows if r.get('q_bh',1)<.10]
        (out/'summary.json').write_text(json.dumps({'assignment_year':ay,'n':int(n),'states':int(states),'candidates':candidates,'top20':rows[:20]},indent=2),encoding='utf-8')
        print('CANDIDATES',flush=True)
        for r in candidates:print(json.dumps(r),flush=True)
        print('TOP20',flush=True)
        for r in rows[:20]:print(json.dumps(r),flush=True)
    con.close()
if __name__=='__main__':main()
