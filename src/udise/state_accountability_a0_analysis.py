from __future__ import annotations

import argparse, csv, json, math, os, shutil
from pathlib import Path
from typing import Any

import duckdb
from huggingface_hub import hf_hub_download

REMOTE = "processed/2024_25/analysis/school_indicator_base.parquet"
STATES = ("BIHAR", "UTTAR PRADESH", "JHARKHAND", "UTTARAKHAND", "ASSAM")
GROUPS = (("A0","Muslim"),("B0","General"),("C0","SC"),("D0","ST"),("E0","OBC"))
SCOPES = {
    "all_recognised": "TRUE",
    "state_local_government": "managment IN (1,2,3,6,89,90)",
    "government_aided": "managment IN (4,7,99)",
    "private_unaided": "managment IN (5,97)",
}
BANDS={0:"0%",1:">0-5%",2:">5-10%",3:">10-20%",4:">20-30%",5:">30-40%",6:">40-50%",7:">50-75%",8:">75-100%"}

# code, label, components, weight, mechanism
BUNDLES = (
("major_repair","Classroom major repair",("any_major_repair",),"students","capital deterioration"),
("incomplete_furniture","Incomplete or absent furniture",("incomplete_furniture",),"students","capital under-provision"),
("girls_toilet_failure","No functional girls' toilet",("no_functional_girls_toilet",),"girls","WASH under-provision"),
("water_failure","No functional drinking-water source",("no_functional_water_source",),"students","WASH under-provision"),
("water_maintenance_failure","Water source exists but none functions",("water_source_present_but_none_functional",),"students","maintenance failure"),
("electricity_failure","No functional electricity",("no_functional_electricity",),"students","power under-provision"),
("electricity_maintenance_failure","Electricity connection exists but does not function",("electricity_connection_nonfunctional",),"students","maintenance failure"),
("digital_void","No internet and no laptop, tablet or desktop",("no_internet","no_core_digital_device"),"students","digital underinvestment"),
("learning_resource_void","No library, reading corner or core digital device",("no_library","no_reading_corner","no_core_digital_device"),"students","learning-resource underinvestment"),
("wash_collapse","No girls' toilet, water or toilet handwashing",("no_functional_girls_toilet","no_functional_water_source","no_handwash_near_toilet"),"girls","WASH system failure"),
("basic_services_collapse","No water, electricity or girls' toilet",("no_functional_water_source","no_functional_electricity","no_functional_girls_toilet"),"girls","basic-services collapse"),
("digital_exclusion_from_power","No electricity, internet or core device",("no_functional_electricity","no_internet","no_core_digital_device"),"students","infrastructure-rooted digital exclusion"),
("physical_learning_neglect","Major repair, incomplete furniture and no library",("any_major_repair","incomplete_furniture","no_library"),"students","physical and learning-resource neglect"),
("deferred_maintenance","Major repair plus non-functional water and electricity assets",("any_major_repair","water_source_present_but_none_functional","electricity_connection_nonfunctional"),"students","deferred maintenance"),
("repair_no_grant","Major repair and no grant",("any_major_repair","no_grant_received"),"students","need without finance"),
("repair_no_inspection","Major repair and no academic inspection",("any_major_repair","no_academic_inspection"),"students","need without oversight"),
("repair_no_district_visit","Major repair and no district or state officer visit",("any_major_repair","no_district_state_officer_visit"),"students","need without senior oversight"),
("repair_no_response","Major repair, no grant and no district or state officer visit",("any_major_repair","no_grant_received","no_district_state_officer_visit"),"students","physical need without response"),
("wash_no_grant","No girls' toilet and no grant",("no_functional_girls_toilet","no_grant_received"),"girls","WASH need without finance"),
("wash_no_response","No girls' toilet or water, plus no block or district visit",("no_functional_girls_toilet","no_functional_water_source","no_block_officer_visit","no_district_state_officer_visit"),"girls","WASH need without oversight"),
("digital_no_grant","No internet or device, plus no grant",("no_internet","no_core_digital_device","no_grant_received"),"students","digital need without finance"),
("digital_no_response","No electricity, internet or device, plus no grant",("no_functional_electricity","no_internet","no_core_digital_device","no_grant_received"),"students","digital system failure without response"),
("learning_no_response","No library or reading corner, plus no academic inspection",("no_library","no_reading_corner","no_academic_inspection"),"students","learning-resource need without oversight"),
("physical_decay_no_response","Major repair, incomplete furniture, no grant and no inspection",("any_major_repair","incomplete_furniture","no_grant_received","no_academic_inspection"),"students","physical decay without response"),
("state_investment_failure","Major repair, no water, electricity, library or internet",("any_major_repair","no_functional_water_source","no_functional_electricity","no_library","no_internet"),"students","compound public-investment failure"),
("state_maintenance_oversight_failure","Major repair, non-functional water and electricity, no grant or senior visit",("any_major_repair","water_source_present_but_none_functional","electricity_connection_nonfunctional","no_grant_received","no_district_state_officer_visit"),"students","maintenance and oversight failure"),
)

def args():
 p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=Path('outputs/state_accountability_a0')); p.add_argument('--dataset-repo',default=os.getenv('HF_DATASET_REPO','')); p.add_argument('--token',default=os.getenv('HF_TOKEN','')); p.add_argument('--school-indicator-path',type=Path); return p.parse_args()
def qs(s): return "'"+s.replace("'","''")+"'"
def band(s): return f"CASE WHEN {s}=0 THEN 0 WHEN {s}<=.05 THEN 1 WHEN {s}<=.1 THEN 2 WHEN {s}<=.2 THEN 3 WHEN {s}<=.3 THEN 4 WHEN {s}<=.4 THEN 5 WHEN {s}<=.5 THEN 6 WHEN {s}<=.75 THEN 7 ELSE 8 END"
def flag(parts): return "CASE WHEN "+" AND ".join(f"{x} IS NOT NULL" for x in parts)+" THEN CASE WHEN "+" AND ".join(f"{x}=1" for x in parts)+" THEN 1 ELSE 0 END ELSE NULL END"
def query(c,sql):
 cur=c.execute(sql); cols=[x[0] for x in cur.description]; return [dict(zip(cols,r,strict=True)) for r in cur.fetchall()]
def write(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not rows: path.write_text('',encoding='utf-8'); return
 cols=[]
 for r in rows:
  for k in r:
   if k not in cols: cols.append(k)
 with path.open('w',encoding='utf-8',newline='') as h:
  w=csv.DictWriter(h,fieldnames=cols); w.writeheader(); w.writerows(rows)
def checkpoint(o,work):
 if o.school_indicator_path: return o.school_indicator_path
 if not o.dataset_repo or not o.token: raise RuntimeError('HF_DATASET_REPO and HF_TOKEN required')
 return Path(hf_hub_download(repo_id=o.dataset_repo,filename=REMOTE,repo_type='dataset',token=o.token,local_dir=work))

def calculate(c):
 states=','.join(qs(x) for x in STATES); exposures=[]; gradients=[]
 for scope,where in SCOPES.items():
  for group,label in GROUPS:
   p=group.lower()
   terms=[]
   for code,_,parts,weight,_ in BUNDLES:
    f=flag(parts); w=f'{p}_{weight}'
    terms += [f"SUM(CASE WHEN ({f}) IS NOT NULL THEN {w} ELSE 0 END) AS {code}_e",f"SUM(CASE WHEN ({f})=1 THEN {w} ELSE 0 END) AS {code}_a",f"SUM(CASE WHEN ({f}) IS NOT NULL THEN 1 ELSE 0 END) AS {code}_s"]
   wide=query(c,f"SELECT state,{','.join(terms)} FROM school_indicator_base WHERE state IN ({states}) AND {where} GROUP BY state")
   for r in wide:
    for code,blabel,parts,weight,mechanism in BUNDLES:
     e=r[f'{code}_e']; a=r[f'{code}_a']; exposures.append({'management_scope':scope,'state':r['state'],'group_code':group,'group_label':label,'bundle_code':code,'bundle_label':blabel,'mechanism':mechanism,'components':'|'.join(parts),'weight_type':weight,'eligible_weight':e,'affected_weight':a,'eligible_schools':r[f'{code}_s'],'exposure_percent':a*100/e if e else None})
 for scope in ('all_recognised','state_local_government'):
  where=SCOPES[scope]
  for group,label in GROUPS:
   p=group.lower(); terms=[]
   for code,_,parts,weight,_ in BUNDLES:
    f=flag(parts); w=f'{p}_{weight}'; terms += [f"SUM(CASE WHEN ({f}) IS NOT NULL THEN {w} ELSE 0 END) AS {code}_e",f"SUM(CASE WHEN ({f})=1 THEN {w} ELSE 0 END) AS {code}_a",f"SUM(CASE WHEN ({f}) IS NOT NULL THEN 1 ELSE 0 END) AS {code}_s"]
   wide=query(c,f"SELECT state,{band(f'{p}_share')} AS band_order,{','.join(terms)} FROM school_indicator_base WHERE state IN ({states}) AND {where} AND {p}_share IS NOT NULL GROUP BY state,band_order")
   for r in wide:
    for code,blabel,parts,weight,mechanism in BUNDLES:
     e=r[f'{code}_e']; a=r[f'{code}_a']; gradients.append({'management_scope':scope,'state':r['state'],'group_code':group,'group_label':label,'band_order':int(r['band_order']),'band':BANDS[int(r['band_order'])],'bundle_code':code,'bundle_label':blabel,'mechanism':mechanism,'components':'|'.join(parts),'weight_type':weight,'eligible_weight':e,'affected_weight':a,'eligible_schools':r[f'{code}_s'],'exposure_percent':a*100/e if e else None})
 return exposures,gradients

def compare(exposures,gradients):
 ex={(r['management_scope'],r['state'],r['group_code'],r['bundle_code']):r for r in exposures}; gr={(r['management_scope'],r['state'],r['group_code'],r['bundle_code'],r['band_order']):r for r in gradients}; rows=[]
 for scope in ('all_recognised','state_local_government'):
  for state in STATES:
   for base,base_label in GROUPS[1:]:
    for code,label,parts,weight,mechanism in BUNDLES:
     ae=ex[(scope,state,'A0',code)]; be=ex[(scope,state,base,code)]; al=gr.get((scope,state,'A0',code,1),{}); ah=gr.get((scope,state,'A0',code,8),{}); bl=gr.get((scope,state,base,code,1),{}); bh=gr.get((scope,state,base,code,8),{})
     av,bv=ae['exposure_percent'],be['exposure_percent']; alv,ahv=al.get('exposure_percent'),ah.get('exposure_percent'); blv,bhv=bl.get('exposure_percent'),bh.get('exposure_percent'); ac=ahv-alv if ahv is not None and alv is not None else None; bc=bhv-blv if bhv is not None and blv is not None else None
     rows.append({'management_scope':scope,'state':state,'baseline_code':base,'baseline_label':base_label,'bundle_code':code,'bundle_label':label,'mechanism':mechanism,'statewide_a0_percent':av,'statewide_baseline_percent':bv,'statewide_gap_pp':av-bv if av is not None and bv is not None else None,'a0_low_percent':alv,'a0_high_percent':ahv,'baseline_low_percent':blv,'baseline_high_percent':bhv,'high_gap_pp':ahv-bhv if ahv is not None and bhv is not None else None,'a0_change_pp':ac,'baseline_change_pp':bc,'difference_in_differences_pp':ac-bc if ac is not None and bc is not None else None,'a0_high_eligible_weight':ah.get('eligible_weight'),'baseline_high_eligible_weight':bh.get('eligible_weight'),'a0_high_eligible_schools':ah.get('eligible_schools'),'baseline_high_eligible_schools':bh.get('eligible_schools')})
 return rows

def rankings(rows):
 out=[]
 for scope in ('all_recognised','state_local_government'):
  for state in STATES:
   for code,label,_,_,mechanism in BUNDLES:
    x=[r for r in rows if r['management_scope']==scope and r['state']==state and r['bundle_code']==code]; gaps=[r['high_gap_pp'] for r in x]; did=[r['difference_in_differences_pp'] for r in x]; complete=all(v is not None and math.isfinite(v) for v in gaps+did); adequate=all((r['a0_high_eligible_weight'] or 0)>=10000 and (r['baseline_high_eligible_weight'] or 0)>=10000 and (r['a0_high_eligible_schools'] or 0)>=25 and (r['baseline_high_eligible_schools'] or 0)>=25 for r in x)
    out.append({'management_scope':scope,'state':state,'bundle_code':code,'bundle_label':label,'mechanism':mechanism,'a0_high_percent':x[0]['a0_high_percent'],'a0_change_pp':x[0]['a0_change_pp'],'minimum_high_gap_all_baselines_pp':min(gaps) if complete else None,'minimum_did_all_baselines_pp':min(did) if complete else None,'worse_than_all_baselines':complete and min(gaps)>0,'steeper_than_all_baselines':complete and min(did)>0,'adequate_cell_size':adequate})
 return out

def report(rank):
 x=[r for r in rank if r['management_scope']=='state_local_government' and r['adequate_cell_size'] and r['worse_than_all_baselines'] and r['steeper_than_all_baselines']]; x.sort(key=lambda r:(r['minimum_high_gap_all_baselines_pp'],r['minimum_did_all_baselines_pp']),reverse=True)
 lines=['# State-accountability analysis','','This analysis restricts direct accountability to state/local-government-managed schools and reports aided, private and all-school scopes separately. It focuses on physical capital, maintenance, WASH, electricity, digital provision, grants and administrative oversight.','','| State | Mechanism | Compound failure | A0 above 75% | Smallest gap vs all baselines | Smallest gradient DiD |','|---|---|---|---:|---:|---:|']
 for r in x[:20]: lines.append(f"| {r['state'].title()} | {r['mechanism']} | {r['bundle_label']} | {r['a0_high_percent']:.2f} | {r['minimum_high_gap_all_baselines_pp']:.2f} | {r['minimum_did_all_baselines_pp']:.2f} |")
 lines += ['','These are cross-sectional exposure and concentration-gradient comparisons. They strengthen a public underinvestment or maintenance interpretation but do not prove intent, identify a specific budget decision, or separate current from inherited neglect without longitudinal expenditure data.']
 return '\n'.join(lines)

def main():
 o=args(); out=o.output; work=out/'work'; work.mkdir(parents=True,exist_ok=True)
 try:
  pq=checkpoint(o,work); temp=work/'temp'; temp.mkdir(exist_ok=True); c=duckdb.connect(str(work/'a.duckdb')); c.execute("SET threads=2"); c.execute("SET memory_limit='4GB'"); c.execute(f"SET temp_directory={qs(str(temp))}"); c.execute("CREATE VIEW school_indicator_base AS SELECT * FROM read_parquet("+qs(str(pq))+")")
  try: ex,gr=calculate(c)
  finally: c.close()
  co=compare(ex,gr); ra=rankings(co); t=out/'tables'; write(t/'state_accountability_group_exposures.csv',ex); write(t/'state_accountability_concentration_gradients.csv',gr); write(t/'state_accountability_baseline_contrasts.csv',co); write(t/'state_accountability_robust_rankings.csv',ra); (out/'state_accountability_report.md').write_text(report(ra),encoding='utf-8'); (out/'analysis_manifest.json').write_text(json.dumps({'states':STATES,'groups':[x[0] for x in GROUPS],'management_scopes':SCOPES,'bundle_count':len(BUNDLES),'exposure_rows':len(ex),'gradient_rows':len(gr)},indent=2),encoding='utf-8')
 finally: shutil.rmtree(work,ignore_errors=True)
 return 0
if __name__=='__main__': raise SystemExit(main())
