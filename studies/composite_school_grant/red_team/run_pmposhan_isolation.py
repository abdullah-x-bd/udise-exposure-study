from __future__ import annotations

import json, os, runpy, tempfile
from pathlib import Path
import duckdb
import numpy as np

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='p')
F=runpy.run_path('tools/csg_focused_2022_2024.py',run_name='f')
C=runpy.run_path('studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py',run_name='c')
extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];rd=F['rd'];component_exprs=C['component_exprs'];ASSETS=C['ASSET_COMPONENTS']

def ident(c):
    x=c.get('pseudocode') or c.get('psuedocode')
    if not x:raise RuntimeError('id missing')
    return x

def efilt(con,s,c):
    if 'item_group' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
    ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def do_rd(con,table,y,where='TRUE'):
    a=con.execute(f'SELECT {y} y,total_enrol enrol,state FROM {table} WHERE ({where}) AND ({y}) IS NOT NULL').fetchnumpy();return rd(a['y'],a['enrol'],a['state'],250,30,1)

def main():
    ay=os.environ['ASSIGN_YEAR'];fys=[x for x in os.environ['FUTURE_YEARS'].split(',') if x];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/red_team/{ay}');out.mkdir(parents=True,exist_ok=True);results=[]
    con=duckdb.connect();con.execute('PRAGMA threads=4');con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);en=src(extract(repo,tok,ay,'enrolment_1',root));pr=src(extract(repo,tok,ay,'profile_1',root));fac=src(extract(repo,tok,ay,'facility',root));ec,pc,fc=cols(con,en),cols(con,pr),cols(con,fac);ei,pi,fi=ident(ec),ident(pc),ident(fc)
        total_terms=[f"COALESCE({nref(ec,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in ec]
        elem_terms=[f"COALESCE({nref(ec,f'c{k}_{s}')},0)" for k in range(1,9) for s in ('b','g') if f'c{k}_{s}' in ec]
        con.execute(f"CREATE TEMP TABLE ee AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({' + '.join(total_terms)}) total_enrol,SUM({' + '.join(elem_terms)}) elem_enrol FROM {en} WHERE {efilt(con,en,ec)} GROUP BY 1")
        low=nref(pc,'lowclass','p');high=nref(pc,'highclass','p')
        con.execute(f"CREATE TEMP TABLE b0 AS SELECT ee.*, {low} lowclass,{high} highclass,DENSE_RANK() OVER(ORDER BY CAST({ref(pc,'state','p')} AS VARCHAR)) state FROM ee JOIN {pr} p ON ee.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN(1,2,3) AND total_enrol BETWEEN 175 AND 325")
        bc=component_exprs(fc,'f');con.execute(f"CREATE TEMP TABLE bfac AS SELECT CAST({qid(fi)} AS VARCHAR) pseudocode,{','.join(x+' b_'+n for n,x in bc.items())} FROM {fac} f")
        joins=[];xs=[]
        for j,fy in enumerate(fys):
            p2=src(extract(repo,tok,fy,'profile_2',root));c2=cols(con,p2);i2=ident(c2);con.execute(f"CREATE TEMP TABLE g{j} AS SELECT CAST({qid(i2)} AS VARCHAR) pseudocode,{nref(c2,'grants_receipt')} r{j},{nref(c2,'grants_expenditure')} x{j} FROM {p2}");joins.append(f'LEFT JOIN g{j} USING(pseudocode)');xs.append(f'x{j}')
        con.execute(f"CREATE TEMP TABLE s AS SELECT b0.*, {','.join([f'r{j}' for j in range(len(fys))]+xs)} FROM b0 {' '.join(joins)}")
        groups={
          'all':'TRUE',
          'pmposhan_safe_elem_le220':'elem_enrol<=220',
          'pmposhan_safe_elem_le200':'elem_enrol<=200',
          'standalone_secondary_lowclass_ge9':'lowclass>=9',
          'has_secondary_students_elem_le220':'highclass>=9 AND elem_enrol<=220'
        }
        for g,w in groups.items():
            n=con.execute(f'SELECT COUNT(*) FROM s WHERE {w} AND total_enrol BETWEEN 220 AND 280').fetchone()[0]
            for y,label in [('CASE WHEN r0>=75000 THEN 1.0 ELSE 0.0 END','receipt_ge75000'),('CASE WHEN x0>=75000 THEN 1.0 ELSE 0.0 END','expenditure_ge75000')]:
                est=do_rd(con,'s',y,w)
                results.append({'group':g,'local_n':int(n),'outcome':label,**(est or {'status':'too_small'})})
            # robust cumulative expenditure with p99 cap computed within subgroup.
            complete=' AND '.join(f'x{j} IS NOT NULL' for j in range(len(fys)));summ=' + '.join(xs)
            vals=con.execute(f'SELECT ({summ}) FROM s WHERE {w} AND {complete}').fetchnumpy()['('+summ+')'] if False else None
            q=con.execute(f'SELECT quantile_cont(({summ}),0.99) FROM s WHERE {w} AND {complete}').fetchone()[0]
            if q is not None:
                est=do_rd(con,'s',f'LEAST(({summ}),{float(q)})',f'({w}) AND ({complete})')
                results.append({'group':g,'local_n':int(n),'outcome':'cumulative_expenditure_winsor99','cap':float(q),**(est or {'status':'too_small'})})
        # First-horizon deterioration for PM-POSHAN-safe subgroup, using facility transition.
        fy=fys[0];ff=src(extract(repo,tok,fy,'facility',root));fcc=cols(con,ff);ffi=ident(fcc);oc=component_exprs(fcc,'f');con.execute(f"CREATE TEMP TABLE ofac AS SELECT CAST({qid(ffi)} AS VARCHAR) pseudocode,{','.join(x+' c_'+n for n,x in oc.items())} FROM {ff} f")
        det_terms=[f"CASE WHEN b.b_{a}=1 AND o.c_{a} IS NOT NULL THEN 1.0-o.c_{a} ELSE 0 END" for a in ASSETS];den=[f"CASE WHEN b.b_{a}=1 AND o.c_{a} IS NOT NULL THEN 1 ELSE 0 END" for a in ASSETS];det=f"CASE WHEN ({' + '.join(den)})>=3 THEN ({' + '.join(det_terms)})/NULLIF(({' + '.join(den)}),0) END"
        con.execute(f"CREATE TEMP TABLE d AS SELECT s.*,{det} deterioration FROM s JOIN bfac b USING(pseudocode) JOIN ofac o USING(pseudocode)")
        for g,w in groups.items():
            est=do_rd(con,'d','deterioration',w);results.append({'group':g,'outcome':'deterioration_first_horizon',**(est or {'status':'too_small'})})
    (out/'pmposhan_isolation.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results,indent=2));con.close()
if __name__=='__main__':main()
