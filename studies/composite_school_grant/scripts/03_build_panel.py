from __future__ import annotations

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


def sql_list(paths: list[str | Path]) -> str:
    return "[" + ",".join(lit(str(p)) for p in paths) + "]"


def csv_source(paths: list[Path]) -> str:
    return (
        f"read_csv_auto({sql_list(paths)}, header=true, all_varchar=true, sample_size=-1, "
        "parallel=true, union_by_name=true, strict_mode=false, null_padding=true)"
    )


def source_columns(con: duckdb.DuckDBPyConnection, src: str) -> dict[str, str]:
    cols = [d[0] for d in con.execute(f"SELECT * FROM {src} LIMIT 0").description]
    return {norm(c): c for c in cols}


def num(expr: str) -> str:
    return f"TRY_CAST(NULLIF(TRIM(CAST({expr} AS VARCHAR)), '') AS DOUBLE)"


def ref(cols: dict[str, str], name: str, alias: str | None = None) -> str | None:
    actual = cols.get(name)
    if not actual:
        return None
    return (f"{alias}." if alias else "") + qid(actual)


def nref(cols: dict[str, str], name: str, alias: str | None = None) -> str:
    r = ref(cols, name, alias)
    return "NULL" if r is None else num(r)


def extract_archive(repo_id: str, token: str, year: str, table: str, work: Path) -> list[Path]:
    archive = Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=f"raw/{year}/{table}.zip",
            repo_type="dataset",
            token=token,
            local_dir=work / "hf",
        )
    )
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
    d = ref(cols, "item_desc")
    if not d:
        return []
    rows = con.execute(
        f"SELECT DISTINCT TRIM(CAST({d} AS VARCHAR)) FROM {src} WHERE {d} IS NOT NULL"
    ).fetchall()
    labels: list[str] = []
    for (raw,) in rows:
        if raw is None:
            continue
        n = re.sub(r"[^a-z0-9]+", " ", str(raw).lower()).strip()
        positive = (
            n in {
                "general", "gen", "sc", "st", "obc", "scheduled caste", "scheduled tribe",
                "other backward class", "other backward classes",
            }
            or "general" in n
            or "scheduled caste" in n
            or "scheduled tribe" in n
            or "other backward" in n
        )
        negative = any(k in n for k in ("muslim", "christian", "sikh", "buddh", "jain", "parsi", "relig"))
        if positive and not negative:
            labels.append(str(raw).strip())
    return sorted(set(labels))


def water_expr(cols: dict[str, str], alias: str, functional: bool) -> str:
    early = "drinking_water_functional" if functional else "drinking_water_available"
    r = ref(cols, early, alias)
    if r:
        return num(r)
    suffix = "_fun_yn" if functional else "_yn"
    bases = ["hand_pump", "well_prot", "tap", "othsrc", "well_unprot", "pack_water"]
    terms = [num(ref(cols, b + suffix, alias)) for b in bases if ref(cols, b + suffix, alias)]
    if not terms:
        return "NULL"
    yes = " OR ".join(f"({t}=1)" for t in terms)
    no = " AND ".join(f"({t}=2 OR {t} IS NULL)" for t in terms)
    return f"CASE WHEN {yes} THEN 1 WHEN {no} THEN 2 ELSE NULL END"


def build_year(
    con: duckdb.DuckDBPyConnection,
    repo_id: str,
    token: str,
    year: str,
    work: Path,
    out: Path,
) -> dict:
    paths = {t: extract_archive(repo_id, token, year, t, work) for t in TABLES}
    src = {t: csv_source(paths[t]) for t in TABLES}
    cols = {t: source_columns(con, src[t]) for t in TABLES}
    ids: dict[str, str] = {}
    for t in TABLES:
        ids[t] = cols[t].get("pseudocode") or cols[t].get("psuedocode") or ""
        if not ids[t]:
            raise RuntimeError(f"No school identifier in {year} {t}")

    ec = cols["enrolment_1"]
    class_terms = [
        f"COALESCE({nref(ec, f'c{c}_{s}')},0)"
        for c in range(1, 13)
        for s in ("b", "g")
        if f"c{c}_{s}" in ec
    ]
    pp_terms = [f"COALESCE({nref(ec,k)},0)" for k in ("cpp_b", "cpp_g") if k in ec]
    class_sum = " + ".join(class_terms) or "0"
    pp_sum = " + ".join(pp_terms) or "0"

    if "item_group" in ec and "item_id" in ec:
        social_filter = f"{nref(ec,'item_group')}=1 AND {nref(ec,'item_id')} IN (1,2,3,4)"
        early_labels: list[str] = []
    else:
        early_labels = identify_early_social_labels(con, src["enrolment_1"], ec)
        if not early_labels:
            raise RuntimeError(f"Could not identify early social-category labels in {year}")
        d = ref(ec, "item_desc")
        social_filter = (
            f"TRIM(CAST({d} AS VARCHAR)) IN (" + ",".join(lit(x) for x in early_labels) + ")"
        )

    eid = qid(ids["enrolment_1"])
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE enr AS
        SELECT
            CAST({eid} AS VARCHAR) AS pseudocode,
            SUM({class_sum}) AS enrol_c1_12,
            SUM(({class_sum}) + ({pp_sum})) AS enrol_incl_preprimary,
            SUM({pp_sum}) AS enrol_preprimary
        FROM {src['enrolment_1']}
        WHERE {social_filter}
        GROUP BY 1
        """
    )

    pc, p2c, fc = cols["profile_1"], cols["profile_2"], cols["facility"]
    p1id, p2id, fid = qid(ids["profile_1"]), qid(ids["profile_2"]), qid(ids["facility"])

    select_sql = f"""
        SELECT
            {lit(year)} AS academic_year,
            CAST(p1.{p1id} AS VARCHAR) AS pseudocode,
            {nref(pc,'state','p1')} AS state,
            {nref(pc,'district','p1')} AS district,
            {nref(pc,'block','p1')} AS block,
            {nref(pc,'rural_urban','p1')} AS rural_urban,
            {nref(pc,'school_category','p1')} AS school_category,
            {nref(pc,'school_type','p1')} AS school_type,
            {nref(pc,'lowclass','p1')} AS lowclass,
            {nref(pc,'highclass','p1')} AS highclass,
            {nref(pc,'managment','p1')} AS management,
            e.enrol_c1_12,
            e.enrol_incl_preprimary,
            e.enrol_preprimary,
            {nref(p2c,'grants_receipt','p2')} AS csg_receipt,
            {nref(p2c,'grants_expenditure','p2')} AS csg_expenditure,
            {nref(p2c,'acad_inspections','p2')} AS acad_inspections,
            {nref(p2c,'smc_exists','p2')} AS smc_exists,
            {nref(p2c,'smc_smdc_meetings','p2')} AS smc_meetings,
            {nref(fc,'building_status','f')} AS building_status,
            {nref(fc,'total_class_rooms','f')} AS total_classrooms,
            {nref(fc,'classrooms_in_good_condition','f')} AS classrooms_good,
            {nref(fc,'classrooms_needs_minor_repair','f')} AS classrooms_minor_repair,
            {nref(fc,'classrooms_needs_major_repair','f')} AS classrooms_major_repair,
            {nref(fc,'total_boys_toilet','f')} AS boys_toilets,
            {nref(fc,'total_boys_func_toilet','f')} AS boys_func_toilets,
            {nref(fc,'total_girls_toilet','f')} AS girls_toilets,
            {nref(fc,'total_girls_func_toilet','f')} AS girls_func_toilets,
            {water_expr(fc,'f',False)} AS water_available_raw,
            {water_expr(fc,'f',True)} AS water_functional_raw,
            {nref(fc,'handwash_near_toilet','f')} AS handwash_near_toilet,
            {nref(fc,'handwash_facility_for_meal','f')} AS handwash_meal,
            {nref(fc,'electricity_availability','f')} AS electricity_raw,
            {nref(fc,'library_availability','f')} AS library_raw,
            {nref(fc,'internet','f')} AS internet_raw,
            {nref(fc,'laptop','f')} AS laptops,
            {nref(fc,'tablet','f')} AS tablets,
            {nref(fc,'desktop','f')} AS desktops
        FROM {src['profile_1']} p1
        LEFT JOIN {src['profile_2']} p2
          ON CAST(p1.{p1id} AS VARCHAR)=CAST(p2.{p2id} AS VARCHAR)
        LEFT JOIN {src['facility']} f
          ON CAST(p1.{p1id} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)
        LEFT JOIN enr e ON CAST(p1.{p1id} AS VARCHAR)=e.pseudocode
    """

    year_out = out / "year_parquet" / f"{year}.parquet"
    year_out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY ({select_sql}) TO {lit(str(year_out))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    n, n_enr = con.execute(
        f"SELECT COUNT(*), COUNT(*) FILTER (WHERE enrol_c1_12 IS NOT NULL) "
        f"FROM read_parquet({lit(str(year_out))})"
    ).fetchone()
    return {
        "year": year,
        "rows": int(n),
        "rows_with_enrolment": int(n_enr),
        "early_social_labels": early_labels,
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
            print(json.dumps(rep, ensure_ascii=False), flush=True)
            shutil.rmtree(work / year, ignore_errors=True)

    year_paths = [out / "year_parquet" / f"{y}.parquet" for y in YEARS]
    panel = out / "school_year_panel.parquet"
    con.execute(
        f"COPY (SELECT * FROM read_parquet({sql_list(year_paths)}, union_by_name=true)) "
        f"TO {lit(str(panel))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )

    summary = []
    for year in YEARS:
        r = con.execute(
            f"""
            SELECT COUNT(*) n, COUNT(DISTINCT pseudocode) schools,
                   COUNT(*) FILTER (WHERE enrol_c1_12 IS NOT NULL) with_enrol,
                   COUNT(*) FILTER (WHERE csg_receipt IS NOT NULL) with_grant,
                   AVG(csg_receipt) FILTER (WHERE csg_receipt IS NOT NULL) avg_grant
            FROM read_parquet({lit(str(panel))}) WHERE academic_year={lit(year)}
            """
        ).fetchone()
        summary.append({
            "year": year, "rows": int(r[0]), "schools": int(r[1]),
            "with_enrolment": int(r[2]), "with_grant": int(r[3]), "avg_grant": r[4],
        })

    continuity = []
    for a, b in zip(YEARS[:-1], YEARS[1:]):
        r = con.execute(
            f"""
            WITH a AS (SELECT DISTINCT pseudocode FROM read_parquet({lit(str(panel))}) WHERE academic_year={lit(a)}),
                 b AS (SELECT DISTINCT pseudocode FROM read_parquet({lit(str(panel))}) WHERE academic_year={lit(b)})
            SELECT (SELECT COUNT(*) FROM a), (SELECT COUNT(*) FROM b),
                   (SELECT COUNT(*) FROM a INNER JOIN b USING(pseudocode))
            """
        ).fetchone()
        continuity.append({
            "from": a, "to": b, "schools_from": int(r[0]), "schools_to": int(r[1]),
            "matched": int(r[2]), "match_rate_from": float(r[2] / r[0]) if r[0] else None,
        })

    manifest = {"build_reports": reports, "year_summary": summary, "continuity": continuity}
    (out / "panel_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nYEAR SUMMARY\n" + json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print("\nCONTINUITY\n" + json.dumps(continuity, indent=2, ensure_ascii=False), flush=True)
    con.close()


if __name__ == "__main__":
    main()
