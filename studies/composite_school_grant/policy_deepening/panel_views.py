from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("logic", ROOT / "logic.py")
logic = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(logic)

PANEL_PATH = Path(
    os.environ.get(
        "CSG_POLICY_PANEL",
        "studies/composite_school_grant/outputs/policy_deepening/_work/panel.parquet",
    )
)


def sql_lit(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def open_connection() -> duckdb.DuckDBPyConnection:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Policy-deepening panel not found: {PANEL_PATH}")
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    state = logic.canonical_state_sql("state")
    year_case = "CASE academic_year " + " ".join(
        f"WHEN {sql_lit(y)} THEN {i}" for i, y in enumerate(logic.YEARS)
    ) + " END"
    mgmt = ",".join(map(str, logic.BROAD_MANAGEMENT))
    ent10 = logic.entitlement_sql("enrol", 10_000)
    ent25 = logic.entitlement_sql("enrol", 25_000)
    con.execute(f"""
        CREATE TEMP TABLE annual AS
        SELECT academic_year,
               {year_case} AS year_idx,
               pseudocode,
               {state} AS state,
               management,
               enrol,
               enrol18,
               receipt,
               expenditure,
               {ent10} AS entitlement,
               {ent25} AS entitlement_small25
        FROM read_parquet({sql_lit(str(PANEL_PATH))})
        WHERE management IN ({mgmt}) AND enrol>=1
    """)
    return con


def add_aligned_tables(con: duckdb.DuckDBPyConnection) -> None:
    parts = []
    for idx, (assignment_year, grant_fy, report_year) in enumerate(logic.ALIGNED_CYCLES):
        parts.append(f"""
            SELECT {idx} AS cycle_index,
                   {sql_lit(assignment_year)} AS assignment_year,
                   {sql_lit(grant_fy)} AS grant_financial_year,
                   {sql_lit(report_year)} AS report_year,
                   a.pseudocode,
                   a.state,
                   a.enrol,
                   a.entitlement,
                   a.entitlement_small25,
                   f.receipt,
                   f.expenditure
            FROM annual a
            LEFT JOIN annual f
              ON a.pseudocode=f.pseudocode
             AND f.academic_year={sql_lit(report_year)}
            WHERE a.academic_year={sql_lit(assignment_year)}
        """)
    con.execute("CREATE TEMP TABLE aligned0 AS " + " UNION ALL ".join(parts))
    con.execute("""
        CREATE TEMP TABLE aligned AS
        SELECT *,
               receipt IS NOT NULL AS receipt_observed,
               expenditure IS NOT NULL AS expenditure_observed,
               CASE WHEN receipt IS NULL THEN NULL ELSE receipt>=entitlement END AS meets,
               COALESCE(receipt,0)>=entitlement AS meets_zero,
               CASE WHEN expenditure IS NULL THEN NULL ELSE expenditure/entitlement END AS expenditure_ratio,
               CASE WHEN receipt IS NULL THEN NULL ELSE receipt/entitlement END AS receipt_ratio
        FROM aligned0
        WHERE entitlement IS NOT NULL
    """)
    con.execute("""
        CREATE TEMP TABLE ordered AS
        SELECT *,
               LAG(entitlement) OVER(PARTITION BY pseudocode ORDER BY cycle_index) AS prev_entitlement,
               LAG(cycle_index) OVER(PARTITION BY pseudocode ORDER BY cycle_index) AS prev_cycle
        FROM aligned
    """)
    con.execute("""
        CREATE TEMP TABLE marked AS
        SELECT *,
               CASE WHEN prev_cycle=cycle_index-1 AND prev_entitlement=entitlement
                    THEN 0 ELSE 1 END AS new_spell
        FROM ordered
    """)
    con.execute("""
        CREATE TEMP TABLE grouped AS
        SELECT *,
               SUM(new_spell) OVER(
                   PARTITION BY pseudocode ORDER BY cycle_index
                   ROWS UNBOUNDED PRECEDING
               ) AS spell_no
        FROM marked
    """)
    con.execute("""
        CREATE TEMP TABLE spell_rows AS
        SELECT *,
               cycle_index-MIN(cycle_index) OVER(
                   PARTITION BY pseudocode,spell_no
               ) AS spell_age,
               COUNT(*) OVER(PARTITION BY pseudocode,spell_no) AS spell_len
        FROM grouped
    """)


def threshold_label_sql(expr: str = "entitlement") -> str:
    return (
        f"CASE {expr} WHEN 10000 THEN '1_30' WHEN 25000 THEN '30_31' "
        f"WHEN 50000 THEN '100_101' WHEN 75000 THEN '250_251' "
        f"WHEN 100000 THEN '1000_1001' END"
    )
