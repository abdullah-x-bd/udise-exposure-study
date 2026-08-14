from __future__ import annotations

import csv
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]
TABLES = ["profile_1", "profile_2", "facility", "enrolment_1"]


def qid(x: str) -> str:
    return '"' + x.replace('"', '""') + '"'


def lit(x: str) -> str:
    return "'" + x.replace("'", "''") + "'"


def norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", x.lower().replace("\ufeff", "")).strip("_")


def csv_source(paths: list[Path]) -> str:
    parts = ",".join(lit(str(p)) for p in paths)
    return f"read_csv_auto([{parts}], header=true, all_varchar=true, sample_size=-1, parallel=true, union_by_name=true, strict_mode=false, null_padding=true)"


def source_columns(con: duckdb.DuckDBPyConnection, src: str) -> dict[str, str]:
    cols = [d[0] for d in con.execute(f"SELECT * FROM {src} LIMIT 0").description]
    return {norm(c): c for c in cols}


def col(cols: dict[str, str], name: str, default: str = "NULL") -> str:
    actual = cols.get(name)
    return qid(actual) if actual else default


def num(expr: str) -> str:
    return f"TRY_CAST(NULLIF(TRIM(CAST({expr} AS VARCHAR)), '') AS DOUBLE)"


def txt(expr: str) -> str:
    return f"NULLIF(TRIM(CAST({expr} AS VARCHAR)), '')"


def extract_archive(repo_id: str, token: str, year: str, table: str, work: Path) -> list[Path]:
    archive = Path(hf_hub_download(
        repo_id=repo_id,
        filename=f"raw/{year}/{table}.zip",
        repo_type="dataset",
        token=token,
        local_dir=work / "hf",
    ))
    dest = work / year / table
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            if member.is_dir() or not member.filename.lower().endswith(".csv"):
                continue
            if table == "enrolment_1" and "stream" in member.filename.lower():
                continue
            out = dest / Path(member.filename).name
            with zf.open(member) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
            paths.append(out)
    if not paths:
        raise RuntimeError(f"No usable CSVs in {year}/{table}.zip")
    return paths


def identify_early_social_labels(con: duckdb.DuckDBPyConnection, src: str, cols: dict[str, str]) -> list[str]:
    if "item_desc" not in cols:
        return []
    actual = qid(cols["item_desc"])
    rows = con.execute(f"SELECT DISTINCT TRIM(CAST({actual} AS VARCHAR)) FROM {src} WHERE {actual} IS NOT NULL").fetchall()
    labels = []
    for (raw,) in rows:
        if raw is None:
            continue
        n = re.sub(r"[^a-z0-9]+", " ", str(raw).lower()).strip()
        # UDISE early enrolment item descriptions represent social/religious group rows.
        # Select only the four mutually exclusive social-category rows used to reconstruct total enrolment.
        positive = (
            n in {"general", "gen", "sc", "st", "obc", "scheduled caste", "scheduled tribe", "other backward class", "other backward classes"}
            or "general" in n
            or "scheduled caste" in n
            or "scheduled tribe" in n
            or "other backward" in n
        )
        negative = any(k in n for k in ("muslim", "christian", "sikh", "buddh", "jain", "parsi", "relig"))
        if positive and not negative:
            labels.append(str(raw).strip())
    return sorted(set(labels))


def water_expr(cols: dict[str, str], functional: bool) -> str:
    early = "drinking_water_functional" if functional else "drinking_water_available"
    if early in cols:
        return num(col(cols, early))
    suffix = "_fun_yn" if functional else "_yn"
    bases = ["hand_pump", "well_prot", "tap", "othsrc", "well_unprot", "pack_water"]
    terms = [num(col(cols, b + suffix)) for b in bases if b + suffix in cols]
    if not terms:
        return "NULL"
    # preserve coding information while providing an indicator assuming UDISE yes=1, no=2;
    # final analysis cross-checks this against empirical encodings.
    return "CASE WHEN " + " OR ".join(f"({t}=1)" for t in terms) + " THEN 1 WHEN " + " AND ".join(f"({t}=2 OR {t} IS NULL)" for t in terms) + " THEN 2 ELSE NULL END"


def build_year(con: duckdb.DuckDBPyConnection, repo_id: str, token: str, year: str, work: Path, out: Path) -> dict:
    paths = {t: extract_archive(repo_id, token, year, t, work) for t in TABLES}
    src = {t: csv_source(paths[t]) for t in TABLES}
    cols = {t: source_columns(con, src[t]) for t in TABLES}
    id_names = {}
    for t in TABLES:
        id_names[t] = cols[t].get("pseudocode") or cols[t].get("psuedocode")
        if not id_names[t]:
            raise RuntimeError(f"No school identifier in {year} {t}")

    ec = cols["enrolment_1"]
    class_terms = []
    for c in range(1, 13):
        for s in ("b", "g"):
            k = f"c{c}_{s}"
            if k in ec:
                class_terms.append(f"COALESCE({num(col(ec,k))},0)")
    pp_terms = [f"COALESCE({num(col(ec,k))},0)" for k in ("cpp_b","cpp_g") if k in ec]
    class_sum = " + ".join(class_terms) or "0"
    pp_sum = " + ".join(pp_terms) or "0"

    if "item_group" in ec and "item_id" in ec:
        social_filter = f"{num(col(ec,'item_group'))}=1 AND {num(col(ec,'item_id'))} IN (1,2,3,4)"
        early_labels = []
    else:
        early_labels = identify_early_social_labels(con, src["enrolment_1"], ec)
        if not early_labels:
            raise RuntimeError(f"Could not identify early social-category labels in {year}")
        social_filter = f"TRIM(CAST({col(ec,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in early_labels)})"

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE enr AS
        SELECT
            CAST({col(ec, norm(id_names['enrolment_1']))} AS VARCHAR) AS pseudocode,
            SUM({class_sum}) AS enrol_c1_12,
            SUM({class_sum} + {pp_sum}) AS enrol_incl_preprimary,
            SUM({pp_sum}) AS enrol_preprimary
        FROM {src['enrolment_1']}
        WHERE {social_filter}
        GROUP BY 1
    """)

    pc = cols["profile_1"]
    p2c = cols["profile_2"]
    fc = cols["facility"]
    p1id = qid(id_names["profile_1"])
    p2id = qid(id_names["profile_2"])
    fid = qid(id_names["facility"])

    # Raw codes are retained. Analysis creates harmonized binaries only after empirical code validation.
    select_sql = f"""
        SELECT
            {lit(year)} AS academic_year,
            CAST(p1.{p1id} AS VARCHAR) AS pseudocode,
            {num('p1.'+col(pc,'state'))} AS state,
            {num('p1.'+col(pc,'district'))} AS district,
            {num('p1.'+col(pc,'block'))} AS block,
            {num('p1.'+col(pc,'rural_urban'))} AS rural_urban,
            {num('p1.'+col(pc,'school_category'))} AS school_category,
            {num('p1.'+col(pc,'school_type'))} AS school_type,
            {num('p1.'+col(pc,'lowclass'))} AS lowclass,
            {num('p1.'+col(pc,'highclass'))} AS highclass,
            {num('p1.'+col(pc,'managment'))} AS management,
            e.enrol_c1_12,
            e.enrol_incl_preprimary,
            e.enrol_preprimary,
            {num('p2.'+col(p2c,'grants_receipt'))} AS csg_receipt,
            {num('p2.'+col(p2c,'grants_expenditure'))} AS csg_expenditure,
            {num('p2.'+col(p2c,'acad_inspections'))} AS acad_inspections,
            {num('p2.'+col(p2c,'smc_exists'))} AS smc_exists,
            {num('p2.'+col(p2c,'smc_smdc_meetings'))} AS smc_meetings,
            {num('f.'+col(fc,'building_status'))} AS building_status,
            {num('f.'+col(fc,'total_class_rooms'))} AS total_classrooms,
            {num('f.'+col(fc,'classrooms_in_good_condition'))} AS classrooms_good,
            {num('f.'+col(fc,'classrooms_needs_minor_repair'))} AS classrooms_minor_repair,
            {num('f.'+col(fc,'classrooms_needs_major_repair'))} AS classrooms_major_repair,
            {num('f.'+col(fc,'total_boys_toilet'))} AS boys_toilets,
            {num('f.'+col(fc,'total_boys_func_toilet'))} AS boys_func_toilets,
            {num('f.'+col(fc,'total_girls_toilet'))} AS girls_toilets,
            {num('f.'+col(fc,'total_girls_func_toilet'))} AS girls_func_toilets,
            {water_expr(fc, False).replace('"','f."') if False else water_expr(fc, False)} AS water_available_raw,
            {water_expr(fc, True).replace('"','f."') if False else water_expr(fc, True)} AS water_functional_raw,
            {num('f.'+col(fc,'handwash_near_toilet'))} AS handwash_near_toilet,
            {num('f.'+col(fc,'handwash_facility_for_meal'))} AS handwash_meal,
            {num('f.'+col(fc,'electricity_availability'))} AS electricity_raw,
            {num('f.'+col(fc,'library_availability'))} AS library_raw,
            {num('f.'+col(fc,'internet'))} AS internet_raw,
            {num('f.'+col(fc,'laptop'))} AS laptops,
            {num('f.'+col(fc,'tablet'))} AS tablets,
            {num('f.'+col(fc,'desktop'))} AS desktops
        FROM {src['profile_1']} p1
        LEFT JOIN {src['profile_2']} p2 ON CAST(p1.{p1id} AS VARCHAR)=CAST(p2.{p2id} AS VARCHAR)
        LEFT JOIN {src['facility']} f ON CAST(p1.{p1id} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)
        LEFT JOIN enr e ON CAST(p1.{p1id} AS VARCHAR)=e.pseudocode
    """

    # water expressions above need facility alias qualification; construct them separately by string substitution.
    def qualify(expr: str) -> str:
        # Quote identifiers generated from facility schema, without touching SQL keywords.
        for actual in sorted(fc.values(), key=len, reverse=True):
            expr = expr.replace(qid(actual), "f." + qid(actual))
        return expr
    select_sql = select_sql.replace(water_expr(fc, False), qualify(water_expr(fc, False)), 1)
    select_sql = select_sql.replace(water_expr(fc, True), qualify(water_expr(fc, True)), 1)

    year_out = out / "year_parquet" / f"{year}.parquet"
    year_out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY ({select_sql}) TO {lit(str(year_out))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)")
    n = con.execute(f"SELECT COUNT(*) FROM read_parquet({lit(str(year_out))})").fetchone()[0]
    n_enr = con.execute(f"SELECT COUNT(*) FROM read_parquet({lit(str(year_out))}) WHERE enrol_c1_12 IS NOT NULL").fetchone()[0]
    return {
        "year": year,
        "rows": int(n),
        "rows_with_enrolment": int(n_enr),
        "early_social_labels": early_labels,
        "source_columns": {k: sorted(v) for k,v in cols.items()},
    }


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path("studies/composite_school_grant/outputs/panel")
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    reports = []
    with tempfile.TemporaryDirectory(prefix="csg_panel_") as td:
        work = Path(td)
        for year in YEARS:
            print(f"BUILDING {year}", flush=True)
            rep = build_year(con, repo_id, token, year, work, out)
            reports.append(rep)
            print(json.dumps({k:rep[k] for k in ('year','rows','rows_with_enrolment','early_social_labels')}, ensure_ascii=False), flush=True)
            shutil.rmtree(work / year, ignore_errors=True)

    paths = [str(out / 'year_parquet' / f'{y}.parquet') for y in YEARS]
    con.execute(f"COPY (SELECT * FROM read_parquet({json.dumps(paths)}, union_by_name=true)) TO {lit(str(out/'school_year_panel.parquet'))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)")

    summary = []
    for year in YEARS:
        r = con.execute(f"""
            SELECT COUNT(*) n, COUNT(DISTINCT pseudocode) schools,
                   COUNT(*) FILTER (WHERE enrol_c1_12 IS NOT NULL) with_enrol,
                   COUNT(*) FILTER (WHERE csg_receipt IS NOT NULL) with_grant,
                   AVG(csg_receipt) FILTER (WHERE csg_receipt IS NOT NULL) avg_grant
            FROM read_parquet({lit(str(out/'school_year_panel.parquet'))})
            WHERE academic_year={lit(year)}
        """).fetchone()
        summary.append({"year":year,"rows":int(r[0]),"schools":int(r[1]),"with_enrolment":int(r[2]),"with_grant":int(r[3]),"avg_grant":r[4]})

    continuity = []
    for a,b in zip(YEARS[:-1], YEARS[1:]):
        r=con.execute(f"""
          WITH a AS (SELECT DISTINCT pseudocode FROM read_parquet({lit(str(out/'school_year_panel.parquet'))}) WHERE academic_year={lit(a)}),
               b AS (SELECT DISTINCT pseudocode FROM read_parquet({lit(str(out/'school_year_panel.parquet'))}) WHERE academic_year={lit(b)})
          SELECT (SELECT COUNT(*) FROM a), (SELECT COUNT(*) FROM b), COUNT(*) FROM a INNER JOIN b USING(pseudocode)
        """).fetchone()
        continuity.append({"from":a,"to":b,"schools_from":int(r[0]),"schools_to":int(r[1]),"matched":int(r[2]),"match_rate_from":float(r[2]/r[0]) if r[0] else None})

    manifest={"build_reports":reports,"year_summary":summary,"continuity":continuity}
    (out/'panel_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print("\nYEAR SUMMARY")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nCONTINUITY")
    print(json.dumps(continuity, indent=2, ensure_ascii=False))
    con.close()

if __name__ == '__main__':
    main()
