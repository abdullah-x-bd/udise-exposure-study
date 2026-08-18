from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from common import (
    YEARS,
    MAIN_GOV_CODES,
    CORE_GOV_CODES,
    extract_archive,
    csv_source,
    source_columns,
    ident,
    qid,
    lit,
    first_ref,
    first_num,
    enrolment_filters,
    class_sum,
    _case_sum,
    _yes_no_from_sources,
    _electricity_ok,
)
from cluster_harmonization import state_sql


def _district_sql(expr: str | None) -> str:
    if not expr:
        return "NULL"
    return f"NULLIF(REGEXP_REPLACE(UPPER(TRIM(CAST({expr} AS VARCHAR))), '\\s+', ' ', 'g'), '')"


def _assert_unique_target_rows(
    con: duckdb.DuckDBPyConnection,
    src: str,
    id_col: str,
    table: str,
    year: str,
) -> dict:
    row = con.execute(
        f"SELECT COUNT(*), COUNT(DISTINCT CAST({qid(id_col)} AS VARCHAR)) "
        f"FROM {src} x JOIN target_school_ids s "
        f"ON CAST(x.{qid(id_col)} AS VARCHAR)=s.pseudocode"
    ).fetchone()
    n, u = int(row[0]), int(row[1])
    if n != u:
        raise RuntimeError(
            f"{year} {table} is not one-row-per-school inside target State: rows={n}, unique_ids={u}"
        )
    return {"table": table, "rows": n, "unique_ids": u}


def build_state_panel(
    con: duckdb.DuckDBPyConnection,
    repo_id: str,
    token: str,
    work: Path,
    output_dir: Path,
    *,
    state_lineage: str,
    teacher: bool = True,
    facility: bool = True,
    profile2: bool = True,
) -> tuple[Path, list[dict]]:
    """Build only one harmonised State/UT lineage.

    The State filter is applied before enrolment aggregation and before year
    Parquets are written. This avoids rebuilding the national panel for every
    State job. School-level output is temporary and must never be uploaded.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    year_paths: list[Path] = []

    for year in YEARS:
        print(f"STATE BUILD {state_lineage} {year}", flush=True)
        tables = ["profile_1", "enrolment_1"]
        if teacher:
            tables.append("teacher")
        if facility:
            tables.append("facility")
        if profile2:
            tables.append("profile_2")

        paths = {t: extract_archive(repo_id, token, year, t, work) for t in tables}
        src = {t: csv_source(paths[t]) for t in tables}
        cols = {t: source_columns(con, src[t]) for t in tables}
        ids = {t: ident(cols[t]) for t in tables}

        p1, pc = src["profile_1"], cols["profile_1"]
        p_id = qid(ids["profile_1"])
        state_ref = first_ref(pc, ("state", "state_id", "state_code", "state_cd"), "p")
        if not state_ref:
            raise RuntimeError(f"{year} profile_1 has no State identifier")
        target = state_lineage.replace("'", "''")

        con.execute("DROP TABLE IF EXISTS target_school_ids")
        con.execute(
            f"CREATE TEMP TABLE target_school_ids AS "
            f"SELECT CAST(p.{p_id} AS VARCHAR) AS pseudocode "
            f"FROM {p1} p WHERE {state_sql(state_ref)}='{target}'"
        )
        target_rows, target_ids = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT pseudocode) FROM target_school_ids"
        ).fetchone()
        target_rows, target_ids = int(target_rows), int(target_ids)
        if target_rows != target_ids:
            raise RuntimeError(
                f"{year} target State profile_1 has duplicate IDs: rows={target_rows}, unique={target_ids}"
            )

        uniqueness = []
        for table in tables:
            if table in {"profile_1", "enrolment_1"}:
                continue
            uniqueness.append(
                _assert_unique_target_rows(con, src[table], ids[table], table, year)
            )

        ec = cols["enrolment_1"]
        filters, early_labels = enrolment_filters(con, src["enrolment_1"], ec)
        p15 = class_sum(ec, 1, 5)
        p15_b = class_sum(ec, 1, 5, "b")
        p15_g = class_sum(ec, 1, 5, "g")
        c112 = class_sum(ec, 1, 12)
        c112_b = class_sum(ec, 1, 12, "b")
        c112_g = class_sum(ec, 1, 12, "g")
        social = ("general", "sc", "st", "obc")
        minority = ("muslim", "christian", "sikh", "buddhist", "parsi", "jain")
        social_cond = " OR ".join(f"({filters[k]})" for k in social)
        e_id = qid(ids["enrolment_1"])

        enrol_cols = [
            f"CAST(e0.{e_id} AS VARCHAR) AS pseudocode",
            f"{_case_sum(social_cond, p15)} AS enrol_primary",
            f"{_case_sum(social_cond, p15_b)} AS boys_primary",
            f"{_case_sum(social_cond, p15_g)} AS girls_primary",
            f"{_case_sum(social_cond, c112)} AS enrol_c1_12",
            f"{_case_sum(social_cond, c112_b)} AS boys_c1_12",
            f"{_case_sum(social_cond, c112_g)} AS girls_c1_12",
        ]
        for group in social + minority:
            enrol_cols.append(f"{_case_sum(filters[group], p15)} AS {group}_primary")
            enrol_cols.append(f"{_case_sum(filters[group], c112)} AS {group}_c1_12")

        # Filters enrolment rows to the target State before the expensive GROUP BY.
        enr_src = src["enrolment_1"]
        con.execute("DROP TABLE IF EXISTS enr")
        con.execute(
            "CREATE TEMP TABLE enr AS SELECT "
            + ",".join(enrol_cols)
            + f" FROM {enr_src} e0 JOIN target_school_ids s "
              f"ON CAST(e0.{e_id} AS VARCHAR)=s.pseudocode GROUP BY 1"
        )

        joins: list[str] = []
        select_extra: list[str] = []
        if teacher:
            tc = cols["teacher"]
            tid = qid(ids["teacher"])
            joins.append(
                f"LEFT JOIN {src['teacher']} t ON CAST(p.{p_id} AS VARCHAR)=CAST(t.{tid} AS VARCHAR)"
            )
            primary_terms = [
                first_num(tc, ("class_taught_pr",), "t"),
                first_num(tc, ("class_taught_pr_upr",), "t"),
                first_num(tc, ("class_taught_pr_and_pre_pri", "class_taught_pr_and_pre_primary"), "t"),
            ]
            primary_terms = [x for x in primary_terms if x != "NULL"]
            primary_expr = " + ".join(f"COALESCE({x},0)" for x in primary_terms) if primary_terms else "NULL"
            select_extra += [
                f"{first_num(tc, ('total_tch','total_teacher','total_teachers'), 't')} AS total_teachers",
                f"{primary_expr} AS primary_serving_teachers",
                f"{first_num(tc, ('regular',), 't')} AS regular_teachers",
                f"{first_num(tc, ('contract',), 't')} AS contract_teachers",
                f"{first_num(tc, ('part_time',), 't')} AS part_time_teachers",
                f"{first_num(tc, ('female',), 't')} AS female_teachers",
                f"{first_num(tc, ('graduate',), 't')} AS graduate_teachers",
                f"{first_num(tc, ('post_graduate_and_above',), 't')} AS postgraduate_teachers",
                f"{first_num(tc, ('bed_equivalent',), 't')} AS bed_teachers",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "total_teachers", "primary_serving_teachers", "regular_teachers", "contract_teachers",
                "part_time_teachers", "female_teachers", "graduate_teachers", "postgraduate_teachers", "bed_teachers"
            )]

        if facility:
            fc = cols["facility"]
            fid = qid(ids["facility"])
            joins.append(
                f"LEFT JOIN {src['facility']} f ON CAST(p.{p_id} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)"
            )
            select_extra += [
                f"{first_num(fc, ('total_class_rooms','total_classrooms'), 'f')} AS total_classrooms",
                f"{first_num(fc, ('classrooms_in_good_condition',), 'f')} AS classrooms_good",
                f"{first_num(fc, ('classrooms_needs_major_repair',), 'f')} AS classrooms_major_repair",
                f"{first_num(fc, ('classrooms_needs_minor_repair',), 'f')} AS classrooms_minor_repair",
                f"{first_num(fc, ('total_boys_toilet',), 'f')} AS boys_toilets",
                f"{first_num(fc, ('total_boys_func_toilet',), 'f')} AS boys_func_toilets",
                f"{first_num(fc, ('total_girls_toilet',), 'f')} AS girls_toilets",
                f"{first_num(fc, ('total_girls_func_toilet',), 'f')} AS girls_func_toilets",
                f"{_yes_no_from_sources(fc, True, 'f')} AS water_functional",
                f"{_electricity_ok(fc, 'f')} AS electricity_functional",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "total_classrooms", "classrooms_good", "classrooms_major_repair", "classrooms_minor_repair",
                "boys_toilets", "boys_func_toilets", "girls_toilets", "girls_func_toilets",
                "water_functional", "electricity_functional"
            )]

        if profile2:
            p2c = cols["profile_2"]
            p2id = qid(ids["profile_2"])
            joins.append(
                f"LEFT JOIN {src['profile_2']} p2 ON CAST(p.{p_id} AS VARCHAR)=CAST(p2.{p2id} AS VARCHAR)"
            )
            select_extra += [
                f"{first_num(p2c, ('acad_inspections',), 'p2')} AS academic_inspections",
                f"{first_num(p2c, ('crc_coordinator',), 'p2')} AS crc_visits",
                f"{first_num(p2c, ('block_level_officers',), 'p2')} AS block_visits",
                f"{first_num(p2c, ('district_officers',), 'p2')} AS district_state_visits",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "academic_inspections", "crc_visits", "block_visits", "district_state_visits"
            )]

        mgmt = first_num(pc, ("managment", "management"), "p")
        district_ref = first_ref(pc, ("district", "district_id", "district_code", "district_cd"), "p")
        district_expr = _district_sql(district_ref)
        block_ref = first_ref(pc, ("block", "block_id", "block_code", "block_cd"), "p")
        block_expr = _district_sql(block_ref)

        select_sql = f"""
            SELECT
                {lit(year)} AS academic_year,
                CAST(p.{p_id} AS VARCHAR) AS pseudocode,
                {lit(state_lineage)} AS state,
                {district_expr} AS district,
                {block_expr} AS block,
                {first_num(pc, ('rural_urban','ruralurban'), 'p')} AS rural_urban,
                {first_num(pc, ('school_category','sch_category'), 'p')} AS school_category,
                {first_num(pc, ('school_type',), 'p')} AS school_type,
                {first_num(pc, ('lowclass','lowest_class'), 'p')} AS lowclass,
                {first_num(pc, ('highclass','highest_class'), 'p')} AS highclass,
                {mgmt} AS management,
                CASE WHEN {mgmt} IN ({','.join(map(str, MAIN_GOV_CODES))}) THEN 1 ELSE 0 END AS is_state_local_government,
                CASE WHEN {mgmt} IN ({','.join(map(str, CORE_GOV_CODES))}) THEN 1 ELSE 0 END AS is_core_government,
                e.* EXCLUDE(pseudocode),
                {','.join(select_extra)}
            FROM {p1} p
            JOIN target_school_ids s ON CAST(p.{p_id} AS VARCHAR)=s.pseudocode
            LEFT JOIN enr e ON CAST(p.{p_id} AS VARCHAR)=e.pseudocode
            {' '.join(joins)}
        """
        year_path = output_dir / f"{year}.parquet"
        con.execute(
            f"COPY ({select_sql}) TO {lit(str(year_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        row = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT pseudocode), "
            f"COUNT(*) FILTER (WHERE is_state_local_government=1), "
            f"COUNT(*) FILTER (WHERE enrol_c1_12 IS NOT NULL), COUNT(DISTINCT district) "
            f"FROM read_parquet({lit(str(year_path))})"
        ).fetchone()
        if int(row[0]) != int(row[1]):
            raise RuntimeError(
                f"{year} State panel row multiplication detected: rows={row[0]}, schools={row[1]}"
            )
        reports.append({
            "year": year,
            "state": state_lineage,
            "rows": int(row[0]),
            "schools": int(row[1]),
            "districts": int(row[4]),
            "state_local_government_rows": int(row[2]),
            "rows_with_enrolment": int(row[3]),
            "early_labels": early_labels,
            "join_uniqueness": uniqueness,
        })
        year_paths.append(year_path)
        shutil.rmtree(work / year, ignore_errors=True)

    panel_path = output_dir / "state_school_year_panel.parquet"
    path_sql = "[" + ",".join(lit(str(p)) for p in year_paths) + "]"
    con.execute(
        f"COPY (SELECT * FROM read_parquet({path_sql}, union_by_name=true)) TO {lit(str(panel_path))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    return panel_path, reports


def compute_national_inspection_caps(
    con: duckdb.DuckDBPyConnection,
    repo_id: str,
    token: str,
    work: Path,
    output_dir: Path,
) -> tuple[dict[str, float], list[dict]]:
    """Compute the pooled national 99.5% inspection winsor caps without a school panel."""
    output_dir.mkdir(parents=True, exist_ok=True)
    year_paths: list[Path] = []
    reports: list[dict] = []

    for year in YEARS:
        print(f"CAP BUILD {year}", flush=True)
        paths = extract_archive(repo_id, token, year, "profile_2", work)
        src = csv_source(paths)
        cols = source_columns(con, src)
        pid = ident(cols)
        n, u = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT CAST({qid(pid)} AS VARCHAR)) FROM {src}"
        ).fetchone()
        if int(n) != int(u):
            raise RuntimeError(f"{year} profile_2 is not one-row-per-school: rows={n}, unique_ids={u}")
        exprs = {
            "academic_inspections": first_num(cols, ("acad_inspections",)),
            "crc_visits": first_num(cols, ("crc_coordinator",)),
            "block_visits": first_num(cols, ("block_level_officers",)),
            "district_state_visits": first_num(cols, ("district_officers",)),
        }
        valid = {
            k: f"CASE WHEN ({v})>=0 THEN ({v}) END"
            for k, v in exprs.items()
        }
        p = output_dir / f"caps_{year}.parquet"
        con.execute(
            f"COPY (SELECT {','.join(f'{v} AS {k}' for k,v in valid.items())} FROM {src}) "
            f"TO {lit(str(p))} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        year_paths.append(p)
        reports.append({"year": year, "rows": int(n), "columns": sorted(cols.keys())})
        shutil.rmtree(work / year, ignore_errors=True)

    path_sql = "[" + ",".join(lit(str(p)) for p in year_paths) + "]"
    union = f"read_parquet({path_sql}, union_by_name=true)"
    caps: dict[str, float] = {}
    for col in ("academic_inspections", "crc_visits", "block_visits", "district_state_visits"):
        val = con.execute(f"SELECT quantile_cont({col},0.995) FROM {union} WHERE {col} IS NOT NULL").fetchone()[0]
        caps[col] = float(val) if val is not None else float("nan")

    total = "+".join(f"COALESCE({c},0)" for c in ("academic_inspections", "crc_visits", "block_visits", "district_state_visits"))
    all_null = " AND ".join(f"{c} IS NULL" for c in ("academic_inspections", "crc_visits", "block_visits", "district_state_visits"))
    senior = "COALESCE(block_visits,0)+COALESCE(district_state_visits,0)"
    senior_null = "block_visits IS NULL AND district_state_visits IS NULL"
    for name, expr, null_cond in (
        ("total_visits", total, all_null),
        ("senior_visits", senior, senior_null),
    ):
        val = con.execute(
            f"SELECT quantile_cont(v,0.995) FROM (SELECT CASE WHEN {null_cond} THEN NULL ELSE {expr} END v FROM {union}) WHERE v IS NOT NULL"
        ).fetchone()[0]
        caps[name] = float(val) if val is not None else float("nan")
    return caps, reports


def write_caps(path: Path, caps: dict[str, float], reports: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"caps": caps, "reports": reports}, indent=2), encoding="utf-8")
