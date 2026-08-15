from __future__ import annotations
import csv,json,os,runpy,tempfile
from pathlib import Path
import duckdb,numpy as np,pandas as pd

P=runpy.run_path('studies/composite_school_grant/scripts/03_build_panel.py',run_name='cross_lib')
YEARS=P['YEARS'];extract=P['extract_archive'];src=P['csv_source'];cols=P['source_columns'];labels=P['identify_early_social_labels'];qid=P['qid'];lit=P['lit'];ref=P['ref'];nref=P['nref'];GOV='(1,2,3)'

def ident(c):
 x=c.get('pseudocode') or c.get('psuedocode');
 if not x:raise RuntimeError('id missing')
 return x

def efilt(con,s,c):
 if 'item_group' in c and 'item_id' in c:return f"{nref(c,'item_group')}=1 AND {nref(c,'item_id')} IN(1,2,3,4)"
 ls=labels(con,s,c);return f"TRIM(CAST({ref(c,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in ls)})"

def esum(c):return ' + '.join(f"COALESCE({nref(c,f'c{k}_{s}')},0)" for k in range(1,13) for s in ('b','g') if f'c{k}_{s}' in c)

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 if not rows:p.write_text('',encoding='utf-8');return
 ks=[]
 for r in rows:
  for k in r:
   if k not in ks:ks.append(k)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=ks);w.writeheader();w.writerows(rows)

def main():
 y0=os.environ['START_YEAR'];i=YEARS.index(y0);y1=YEARS[i+1];y2=YEARS[i+2];repo=os.environ['HF_DATASET_REPO'];tok=os.environ['HF_TOKEN'];out=Path(f'studies/composite_school_grant/outputs/crossing_dynamics/{y0}');out.mkdir(parents=True,exist_ok=True);con=duckdb.connect();rows=[]
 with tempfile.TemporaryDirectory(prefix='cross_') as td:
  root=Path(td);tabs=[]
  for j,y in enumerate((y0,y1,y2)):
   en=src(extract(repo,tok,y,'enrolment_1',root));ec=cols(con,en);ei=ident(ec);f=efilt(con,en,ec);es=esum(ec);con.execute(f"CREATE TEMP TABLE e{j} AS SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,SUM({es}) x{j} FROM {en} WHERE {f} GROUP BY 1")
  p1=src(extract(repo,tok,y0,'profile_1',root));pc=cols(con,p1);pi=ident(pc)
  d=con.execute(f"""SELECT e0.pseudocode,e0.x0,e1.x1,e2.x2 FROM e0 JOIN e1 USING(pseudocode) JOIN e2 USING(pseudocode) JOIN {p1} p ON e0.pseudocode=CAST(p.{qid(pi)} AS VARCHAR) WHERE {nref(pc,'managment','p')} IN {GOV} AND e0.x0 BETWEEN 150 AND 350""").df()
  for c,kind in [(250,'true'),(200,'placebo'),(300,'placebo')]:
   approach=d[(d.x0>=c-20)&(d.x0<=c)];farbelow=d[(d.x0>=c-40)&(d.x0<=c-21)]
   first5=d[(d.x1>=c+1)&(d.x1<=c+5)];second5=d[(d.x1>=c+6)&(d.x1<=c+10)]
   pred=d.x1+(d.x1-d.x0);near_pred=d[(pred>=c-4)&(pred<=c)];left_pred=d[(pred>=c-9)&(pred<=c-5)];right_pred=d[(pred>=c+1)&(pred<=c+5)]
   rows.append({'start_year':y0,'middle_year':y1,'end_year':y2,'threshold_end':c,'kind':kind,'analysis':'approach_and_reversion','n_approach20':len(approach),'p_land_251_255_equiv':float(((approach.x1>=c+1)&(approach.x1<=c+5)).mean()) if len(approach) else None,'p_land_last5_below':float(((approach.x1>=c-5)&(approach.x1<=c-1)).mean()) if len(approach) else None,'n_farbelow20':len(farbelow),'p_farbelow_land_first5_above':float(((farbelow.x1>=c+1)&(farbelow.x1<=c+5)).mean()) if len(farbelow) else None,'n_first5_above':len(first5),'p_first5_above_revert_below':float((first5.x2<=c).mean()) if len(first5) else None,'n_second5_above':len(second5),'p_second5_above_revert_below':float((second5.x2<=c).mean()) if len(second5) else None})
   rows.append({'start_year':y0,'middle_year':y1,'end_year':y2,'threshold_end':c,'kind':kind,'analysis':'predicted_landing','n_pred_last5_below':len(near_pred),'p_actual_first5_above_given_pred_last5_below':float(((near_pred.x2>=c+1)&(near_pred.x2<=c+5)).mean()) if len(near_pred) else None,'n_pred_5_9_below':len(left_pred),'p_actual_analogous_shift_left':float(((left_pred.x2>=c-4)&(left_pred.x2<=c)).mean()) if len(left_pred) else None,'n_pred_first5_above':len(right_pred),'p_actual_second5_above_given_pred_first5':float(((right_pred.x2>=c+6)&(right_pred.x2<=c+10)).mean()) if len(right_pred) else None})
 write(out/'crossing_dynamics.csv',rows);(out/'RESULTS.md').write_text('# Crossing dynamics '+y0+' to '+y2+'\n\n'+json.dumps(rows,indent=2),encoding='utf-8');print((out/'RESULTS.md').read_text(),flush=True);con.close()
if __name__=='__main__':main()
