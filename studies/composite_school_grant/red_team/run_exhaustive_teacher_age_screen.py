from __future__ import annotations

import csv,json,math,os,re,runpy,tempfile
from pathlib import Path
import duckdb

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
F=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='f')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];num=P['num'];rd=F['rd']
CUTOFF=250;BW=30;DONUT=1
EXCL=('pseudocode','psuedocode','state','district','block','cluster','code','name','mobile','email','item_group','item_id','item_desc','year','management','managment')

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def bh(rows,key='p'):
    v=[(i,float(r[key])) for i,r in enumerate(rows) if r.get(key) is not None and math.isfinite(float(r[key]))];v.sort(key=lambda z:z[1]);m=len(v);run=1.0
    for rank in range(m,0,-1):
        i,p=v[rank-1];q=min(run,p*m/rank);run=q;rows[i]['q_bh']=q

def wr(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    ks=[]
    for r in rows:
        for k in r:
            if k not in ks:ks.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def assignment_enrol(con,s,c):
    terms=[f"COALESCE({nref(c,f'c{k}_{sex}')},0)" for k in range(1,13) for sex in ('b','g') if f'c{k}_{sex}' in c]
    if 'item_group' in c and 'item_id' in c:filt=f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    else:
        ls=labels(con,s,c);filt=f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"
    return ' + '.join(terms),filt

def estimate(con,sql):
    a=con.execute(sql).fetchnumpy();return rd(a['y'],a['enrol'],a['state'],CUTOFF,BW,DONUT)

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=[x for x in os.environ['FUTURE_YEARS'].split(',') if x];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'");rows=[]
    with tempfile.TemporaryDirectory(prefix='csg_exhaust_') as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));pr=src(extract(repo,tok,ay,'profile_1',root));bt=src(extract(repo,tok,ay,'teacher',root));be2=src(extract(repo,tok,ay,'enrolment_2',root));ec,pc,btc,be2c=map(lambda s:cols(con,s),(en,pr,bt,be2));ei,pi,bti,be2i=map(ident,(ec,pc,btc,be2c));tot,filt=assignment_enrol(con,en,ec)
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({tot}) enrol FROM {en} WHERE {filt} GROUP BY 1")
        con.execute(f"CREATE TEMP TABLE sample AS SELECT ee.pseudocode,ee.enrol,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state FROM ee JOIN {pr} p ON ee.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND ee.enrol BETWEEN 220 AND 280")
        # Small baseline teacher table with every numerically parseable candidate field.
        teacher_fields=[n for n in btc if not any(x in n for x in EXCL)]
        bsel=','.join(f'{nref(btc,n,"t")} b__{n}' for n in teacher_fields)
        con.execute(f"CREATE TEMP TABLE bteacher AS SELECT CAST(t.{qid(bti)} AS VARCHAR) pseudocode,{bsel} FROM {bt} t JOIN sample s ON CAST(t.{qid(bti)} AS VARCHAR)=s.pseudocode")
        # Baseline enrolment_2 remains long by item group/id so each age/category cell can be compared like-for-like.
        e2fields=[n for n in be2c if re.fullmatch(r'(cpp|c(?:[1-9]|1[0-2]))_[bg]',n)]
        bg=nref(be2c,'item_group','e');bi=nref(be2c,'item_id','e');bvals=','.join(f'{nref(be2c,n,"e")} b__{n}' for n in e2fields)
        con.execute(f"CREATE TEMP TABLE be2long AS SELECT CAST(e.{qid(be2i)} AS VARCHAR) pseudocode,{bg} item_group,{bi} item_id,{bvals} FROM {be2} e JOIN sample s ON CAST(e.{qid(be2i)} AS VARCHAR)=s.pseudocode")
        for j,fy in enumerate(fys):
            ot=src(extract(repo,tok,fy,'teacher',root));oe2=src(extract(repo,tok,fy,'enrolment_2',root));otc,oe2c=cols(con,ot),cols(con,oe2);oti,oe2i=ident(otc),ident(oe2c)
            common_t=sorted(set(teacher_fields)&set(n for n in otc if not any(x in n for x in EXCL)))
            osel=','.join(f'{nref(otc,n,"t")} o__{n}' for n in common_t)
            con.execute(f"CREATE TEMP TABLE oteacher{j} AS SELECT CAST(t.{qid(oti)} AS VARCHAR) pseudocode,{osel} FROM {ot} t JOIN sample s ON CAST(t.{qid(oti)} AS VARCHAR)=s.pseudocode")
            fam=[]
            for n in common_t:
                b=f'b.b__{n}';o=f'o.o__{n}'
                st=con.execute(f"SELECT COUNT(*) FILTER(WHERE {b} IS NOT NULL AND {o} IS NOT NULL),COUNT(DISTINCT {b}),COUNT(DISTINCT {o}) FROM sample s LEFT JOIN bteacher b USING(pseudocode) LEFT JOIN oteacher{j} o USING(pseudocode)").fetchone()
                if st[0]<1000 or st[1]<2 or st[2]<2:continue
                pre=estimate(con,f"SELECT {b} y,s.enrol,s.state FROM sample s JOIN bteacher b USING(pseudocode) WHERE {b} IS NOT NULL")
                ch=estimate(con,f"SELECT ({o}-{b}) y,s.enrol,s.state FROM sample s JOIN bteacher b USING(pseudocode) JOIN oteacher{j} o USING(pseudocode) WHERE {b} IS NOT NULL AND {o} IS NOT NULL")
                if ch:fam.append({'assignment_year':ay,'outcome_year':fy,'family':'teacher_exhaustive','field':n,'n_pair':int(st[0]),'baseline_p':pre.get('p') if pre else None,**ch})
            bh(fam);rows.extend(fam)
            # Enrolment_2 exhaustive cell screen. Match item_group,item_id and every class/sex cell.
            common_e=sorted(set(e2fields)&set(n for n in oe2c if re.fullmatch(r'(cpp|c(?:[1-9]|1[0-2]))_[bg]',n)))
            og=nref(oe2c,'item_group','e');oi=nref(oe2c,'item_id','e');ovals=','.join(f'{nref(oe2c,n,"e")} o__{n}' for n in common_e)
            con.execute(f"CREATE TEMP TABLE oe2long{j} AS SELECT CAST(e.{qid(oe2i)} AS VARCHAR) pseudocode,{og} item_group,{oi} item_id,{ovals} FROM {oe2} e JOIN sample s ON CAST(e.{qid(oe2i)} AS VARCHAR)=s.pseudocode")
            keys=con.execute(f"SELECT DISTINCT b.item_group,b.item_id FROM be2long b JOIN oe2long{j} o USING(pseudocode,item_group,item_id) WHERE b.item_group IS NOT NULL AND b.item_id IS NOT NULL ORDER BY 1,2").fetchall()
            efam=[]
            for ig,ii in keys:
                for n in common_e:
                    b=f'b.b__{n}';o=f'o.o__{n}';where=f'b.item_group={float(ig)} AND b.item_id={float(ii)}'
                    st=con.execute(f"SELECT COUNT(*) FILTER(WHERE {b} IS NOT NULL AND {o} IS NOT NULL),COUNT(DISTINCT {b}),COUNT(DISTINCT {o}) FROM sample s JOIN be2long b USING(pseudocode) JOIN oe2long{j} o USING(pseudocode,item_group,item_id) WHERE {where}").fetchone()
                    if st[0]<750 or st[1]<2 or st[2]<2:continue
                    pre=estimate(con,f"SELECT {b} y,s.enrol,s.state FROM sample s JOIN be2long b USING(pseudocode) WHERE {where} AND {b} IS NOT NULL")
                    ch=estimate(con,f"SELECT ({o}-{b}) y,s.enrol,s.state FROM sample s JOIN be2long b USING(pseudocode) JOIN oe2long{j} o USING(pseudocode,item_group,item_id) WHERE {where} AND {b} IS NOT NULL AND {o} IS NOT NULL")
                    if ch:efam.append({'assignment_year':ay,'outcome_year':fy,'family':'enrolment2_exhaustive','item_group':float(ig),'item_id':float(ii),'field':n,'n_pair':int(st[0]),'baseline_p':pre.get('p') if pre else None,**ch})
            bh(efam);rows.extend(efam)
    wr(out/'exhaustive_teacher_enrolment2.csv',rows)
    hits=[r for r in rows if r.get('q_bh',1)<.10 and (r.get('baseline_p') is None or r.get('baseline_p',0)>.10)]
    summary={'assignment_year':ay,'future_years':fys,'n_tests':len(rows),'replication_candidates':hits};(out/'exhaustive_teacher_enrolment2_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('TESTS',len(rows),'HITS',len(hits));
    for r in hits:print(json.dumps(r),flush=True)
    con.close()
if __name__=='__main__':main()
