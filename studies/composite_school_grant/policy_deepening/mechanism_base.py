from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("panel_views", ROOT / "panel_views.py")
pv = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pv)

OUT = Path("studies/composite_school_grant/outputs/policy_deepening/mechanism_base")


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = pv.open_connection()

    formula = con.execute("""
        SELECT state,academic_year,
               COUNT(*) AS n_schools,
               COUNT(*) FILTER(WHERE enrol BETWEEN 1 AND 30) AS n_1_30,
               COUNT(*) FILTER(WHERE enrol>30 AND enrol<=100) AS n_31_100,
               COUNT(*) FILTER(WHERE enrol>100 AND enrol<=250) AS n_101_250,
               COUNT(*) FILTER(WHERE enrol>250 AND enrol<=1000) AS n_251_1000,
               COUNT(*) FILTER(WHERE enrol>1000) AS n_gt1000,
               SUM(entitlement) AS formula_total_small10_rupees,
               SUM(entitlement_small25) AS formula_total_small25_rupees,
               SUM(CASE WHEN enrol>30 THEN entitlement ELSE 0 END) AS formula_total_31plus_rupees
        FROM annual
        GROUP BY 1,2
        ORDER BY 1,2
    """).df()
    save(formula, "formula_totals_state_year.csv")

    recorded = con.execute("""
        SELECT state,academic_year,
               COUNT(*) AS n_schools,
               COUNT(receipt) AS n_receipt_reported,
               COUNT(expenditure) AS n_expenditure_reported,
               SUM(receipt) AS recorded_receipt_total_rupees,
               SUM(expenditure) AS recorded_expenditure_total_rupees,
               AVG(CAST(receipt IS NOT NULL AS DOUBLE)) AS receipt_reporting_rate,
               AVG(CAST(expenditure IS NOT NULL AS DOUBLE)) AS expenditure_reporting_rate
        FROM annual
        GROUP BY 1,2
        ORDER BY 1,2
    """).df()
    save(recorded, "recorded_totals_state_year.csv")

    rows = []
    for assignment_year, grant_fy, report_year in [
        ("2019-20", "2021-22", "2022-23"),
        ("2020-21", "2022-23", "2023-24"),
        ("2021-22", "2023-24", "2024-25"),
        ("2022-23", "2024-25", "2025-26"),
    ]:
        f = formula[formula.academic_year == assignment_year].copy()
        r = recorded[recorded.academic_year == report_year].copy()
        z = f.merge(r, on="state", how="outer", suffixes=("_assignment", "_report"))
        z["assignment_year"] = assignment_year
        z["grant_financial_year"] = grant_fy
        z["report_year"] = report_year
        rows.append(z)
    aligned = pd.concat(rows, ignore_index=True)
    save(aligned, "aligned_formula_record_state_cycle.csv")

    validation = {
        "formula_states": int(formula.state.nunique()),
        "formula_years": sorted(formula.academic_year.unique().tolist()),
        "recorded_states": int(recorded.state.nunique()),
        "recorded_years": sorted(recorded.academic_year.unique().tolist()),
        "aligned_cycles": 4,
        "small_school_schedules_both_preserved": True,
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    con.close()


if __name__ == "__main__":
    main()
