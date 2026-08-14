from __future__ import annotations

import csv, json, math, os, re, runpy, tempfile
from pathlib import Path
import duckdb

PANEL=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='panel_lib')
FOCUS=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='focus_lib')
extract_archive=PANEL['extract_archive'];csv_source=PANEL['csv_source'];source_columns=PANEL['source_columns'];identify_early_social_labels=PANEL['identify_early_social_labels'];qid=PANEL['qid'];lit=PANEL['lit'];ref=PANEL['ref'];nref=PANEL['nref'];num=PANEL['num'];rd=FOCUS['rd']
CUTOFF=250;BW=30;DONUT=1
KEYWORDS=('grant','receipt','expend','maintenance','house','teacher','construction','inventory','sports','library','community','preschool','ngo','psu','assistance','repair')
EXCLUDE=('pseudocode','psuedocode','udise','state','district','block','cluster','village','panchayat','management','managment','school_category','school_type')

def norm(s:str)->str:return re.sub(r'[^a-z0-9]+','_',s.lower().replace('\ufeff','')).strip('_')
def write_csv(path:Path,rows:list[dict]):
    if not rows:path.write_text('',encoding='utf-8');return
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys:keys.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def total_enrol(con,src,c):
    terms=[f"COALESCE({nref(c,f'c{x}_{s}')},0)" for x in range(1,13) for s in ('b','g') if f'c{x}_{s}' in c]
    if 'item_group' in c and 'item_id' in c:f=f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN (1,2,3,4)"
    else:
        labs=identify_early_social_labels(con,src,c);d=ref(c,'item_desc');f=f"TRIM(CAST({d} AS VARCHAR)) IN ({','.join(lit(x) for x in labs)})"
    return ' + '.join(terms),f

def main():
    ay=os.environ['ASSIGN_YEAR'];oy=os.environ['OBS_YEAR'];repo=os.environ['HF_DATASET_REPO'];token=os.environ['HF_TOKEN']
    out=Path(f'studies/composite_school_grant/outputs/financial_channels/{ay}_to_{oy}');out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix='csg_fin_') as td:
        root=Path(td)
        a_enr=csv_source(extract_archive(repo,token,ay,'enrolment_1',root));a_p1=csv_source(extract_archive(repo,token,ay,'profile_1',root));a_p2=csv_source(extract_archive(repo,token,ay,'profile_2',root))
        o_p1=csv_source(extract_archive(repo,token,oy,'profile_1',root));o_p2=csv_source(extract_archive(repo,token,oy,'profile_2',root))
        ec,apc,ap2c,opc,op2c=[source_columns(con,x) for x in (a_enr,a_p1,a_p2,o_p1,o_p2)]
        ids=[]
        for c in (ec,apc,ap2c,opc,op2c):ids.append(c.get('pseudocode') or c.get('psuedocode'))
        total,filt=total_enrol(con,a_enr,ec)
        con.execute(f"CREATE TEMP TABLE enr AS SELECT CAST({qid(ids[0])} AS VARCHAR) pseudocode,SUM({total}) enrol FROM {a_enr} WHERE {filt} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE abase AS SELECT CAST({qid(ids[1])} AS VARCHAR) pseudocode,CAST({ref(apc,'state')} AS VARCHAR) state_key,{nref(apc,'managment')} mgmt FROM {a_p1}")
        con.execute(f"CREATE TEMP TABLE obase AS SELECT CAST({qid(ids[3])} AS VARCHAR) pseudocode,{nref(opc,'managment')} mgmt FROM {o_p1}")
        con.execute(f"CREATE TEMP TABLE idsamp AS SELECT e.pseudocode,e.enrol,DENSE_RANK() OVER(ORDER BY a.state_key) state FROM enr e JOIN abase a USING(pseudocode) JOIN obase o USING(pseudocode) WHERE a.mgmt IN (1,2,3) AND o.mgmt IN (1,2,3) AND e.enrol BETWEEN {CUTOFF-BW} AND {CUTOFF+BW}")
        common=[]
        for n in sorted(set(ap2c)&set(op2c)):
            if any(x in n for x in EXCLUDE):continue
            if any(k in n for k in KEYWORDS):common.append(n)
        rows=[]
        for n in common:
            ba=qid(ap2c[n]);oa=qid(op2c[n])
            q=f"SELECT {num('o.'+oa)} y,s.enrol,s.state FROM idsamp s JOIN {o_p2} o ON s.pseudocode=CAST(o.{qid(ids[4])} AS VARCHAR) WHERE {num('o.'+oa)} IS NOT NULL"
            arr=con.execute(q).fetchnumpy();est=rd(arr['y'],arr['enrol'],arr['state'],CUTOFF,BW,DONUT)
            if not est:continue
            qb=f"SELECT {num('b.'+ba)} y,s.enrol,s.state FROM idsamp s JOIN {a_p2} b ON s.pseudocode=CAST(b.{qid(ids[2])} AS VARCHAR) WHERE {num('b.'+ba)} IS NOT NULL"
            barr=con.execute(qb).fetchnumpy();pre=rd(barr['y'],barr['enrol'],barr['state'],CUTOFF,BW,DONUT)
            stats=con.execute(f"SELECT COUNT(*) FILTER(WHERE {num('o.'+oa)} IS NOT NULL),COUNT(DISTINCT {num('o.'+oa)}) FILTER(WHERE {num('o.'+oa)} IS NOT NULL),AVG({num('o.'+oa)}) FILTER(WHERE {num('o.'+oa)} IS NOT NULL) FROM idsamp s JOIN {o_p2} o ON s.pseudocode=CAST(o.{qid(ids[4])} AS VARCHAR)").fetchone()
            rows.append({'field':n,'n_numeric':int(stats[0]),'distinct':int(stats[1]),'mean':stats[2],**est,'baseline_tau':None if not pre else pre['tau'],'baseline_p':None if not pre else pre['p']})
        rows.sort(key=lambda r:r['p'] if r['p'] is not None else 1)
        write_csv(out/'financial_channel_rd.csv',rows)
        (out/'summary.json').write_text(json.dumps({'assignment_year':ay,'observation_year':oy,'fields_considered':common,'results':rows},indent=2),encoding='utf-8')
        print('FIELDS',common,flush=True)
        print('RESULTS',flush=True)
        for r in rows:print(json.dumps(r),flush=True)
    con.close()
if __name__=='__main__':main()
