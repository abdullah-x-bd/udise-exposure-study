from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download


def lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main() -> None:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path("outputs/csg_first_stage_pilot")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="csg_pilot_") as td:
        work=Path(td)
        db=Path(hf_hub_download(repo_id=repo,filename="processed/2024_25/database/udise_2024_25.duckdb",repo_type="dataset",token=token,local_dir=work/'hf'))
        ez=Path(hf_hub_download(repo_id=repo,filename="raw/2022-23/enrolment_1.zip",repo_type="dataset",token=token,local_dir=work/'hf'))
        edir=work/'enr'; edir.mkdir()
        with zipfile.ZipFile(ez) as zf:
            members=[m for m in zf.infolist() if not m.is_dir() and m.filename.lower().endswith('.csv') and 'stream' not in m.filename.lower()]
            paths=[]
            for m in members:
                p=edir/Path(m.filename).name
                with zf.open(m) as src,p.open('wb') as dst: shutil.copyfileobj(src,dst,8*1024*1024)
                paths.append(p)
        con=duckdb.connect(str(db),read_only=True)
        src="read_csv_auto(["+','.join(lit(str(p)) for p in paths)+"],header=true,all_varchar=true,sample_size=-1,union_by_name=true,strict_mode=false,null_padding=true)"
        cols=[d[0] for d in con.execute(f"SELECT * FROM {src} LIMIT 0").description]
        lower={c.lower():c for c in cols}
        pid=lower.get('pseudocode') or lower.get('psuedocode')
        class_terms=[]
        for c in range(1,13):
            for s in ('b','g'):
                k=f'c{c}_{s}'
                if k in lower: class_terms.append(f"COALESCE(TRY_CAST(\"{lower[k]}\" AS DOUBLE),0)")
        total=' + '.join(class_terms)
        con.execute(f"""
          CREATE TEMP TABLE assignment AS
          SELECT CAST(\"{pid}\" AS VARCHAR) pseudocode, SUM({total}) enrol
          FROM {src}
          WHERE TRY_CAST(item_group AS INTEGER)=1 AND TRY_CAST(item_id AS INTEGER) IN (1,2,3,4)
          GROUP BY 1
        """)
        smcols=[d[0] for d in con.execute("SELECT * FROM school_master_base LIMIT 0").description]
        grant='grants_receipt' if 'grants_receipt' in smcols else None
        if not grant: raise RuntimeError('grants_receipt missing from school_master_base')
        state='state' if 'state' in smcols else None
        mgmt='managment' if 'managment' in smcols else ('management' if 'management' in smcols else None)
        if not mgmt: raise RuntimeError('management field missing')
        q_all=f"""
          SELECT a.enrol, m.{grant} receipt{',m.'+state+' state' if state else ''},m.{mgmt} management
          FROM assignment a JOIN school_master_base m USING(pseudocode)
          WHERE a.enrol BETWEEN 1 AND 1300 AND m.{grant} IS NOT NULL
        """
        con.execute(f"CREATE TEMP TABLE sample_all AS {q_all}")
        # Samagra CSG is for government schools. UDISE managements 1,2,3 are Department of Education,
        # Tribal/Social Welfare and Local Body government schools. Government-aided and private schools are excluded.
        con.execute("CREATE TEMP TABLE sample AS SELECT * FROM sample_all WHERE management IN (1,2,3)")
        n_all=con.execute('SELECT COUNT(*) FROM sample_all').fetchone()[0]
        n=con.execute('SELECT COUNT(*) FROM sample').fetchone()[0]
        cells=[]
        for cutoff,bw in ((30,20),(100,50),(250,100),(1000,250)):
            cr=con.execute(f"""SELECT CAST(enrol AS INTEGER),COUNT(*),AVG(receipt),AVG(CASE WHEN receipt>0 THEN receipt END),AVG(CASE WHEN receipt>0 THEN 1.0 ELSE 0.0 END) FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw} GROUP BY 1 ORDER BY 1""").fetchall()
            for e,nn,mean,posmean,pr in cr: cells.append({'cutoff':cutoff,'enrol':e,'n':nn,'mean_receipt':mean,'positive_mean':posmean,'positive_rate':pr})
        estimates=[]
        for cutoff,bws in {30:[10,15,20],100:[20,30,40,50],250:[30,50,75,100],1000:[100,150,250]}.items():
            for bw in bws:
                r=con.execute(f"""
                  WITH s AS (SELECT *, enrol-({cutoff}+0.5) x, CASE WHEN enrol>{cutoff} THEN 1.0 ELSE 0.0 END d FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw})
                  SELECT COUNT(*), AVG(receipt) FILTER (WHERE d=0), AVG(receipt) FILTER (WHERE d=1) FROM s
                """).fetchone()
                arr=con.execute(f"SELECT receipt,enrol{',state' if state else ''} FROM sample WHERE enrol BETWEEN {cutoff-bw} AND {cutoff+bw}").fetchnumpy()
                import numpy as np
                y=np.asarray(arr['receipt'],float); e=np.asarray(arr['enrol'],float); d=(e>cutoff).astype(float); x=e-(cutoff+0.5); w=np.maximum(.001,1-np.abs(x)/(bw+.5)); X=np.column_stack([np.ones(len(y)),d,x,d*x]); sw=np.sqrt(w); beta=np.linalg.lstsq(X*sw[:,None],y*sw,rcond=None)[0]
                estimates.append({'cutoff':cutoff,'bandwidth':bw,'n':int(r[0]),'left_mean':r[1],'right_mean':r[2],'local_linear_jump':float(beta[1]),'statutory_jump':15000 if cutoff==30 else 25000,'fraction_of_statutory':float(beta[1]/(15000 if cutoff==30 else 25000))})
        with (out/'cells.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(cells[0]));w.writeheader();w.writerows(cells)
        (out/'first_stage.json').write_text(json.dumps(estimates,indent=2),encoding='utf-8')
        print('N_ALL',n_all,'N_GOV',n,'management_field',mgmt)
        print('GOVERNMENT-SCHOOL ESTIMATES')
        for r in estimates: print(json.dumps(r),flush=True)
        print('TOP GRANT VALUES GOV')
        print(con.execute("SELECT receipt,COUNT(*) n FROM sample GROUP BY 1 ORDER BY n DESC LIMIT 30").fetchall())
        print('MANAGEMENT ALL')
        print(con.execute("SELECT management,COUNT(*),AVG(receipt),AVG(CASE WHEN receipt>0 THEN 1.0 ELSE 0.0 END) FROM sample_all GROUP BY 1 ORDER BY 2 DESC").fetchall())
        con.close()

if __name__=='__main__': main()
