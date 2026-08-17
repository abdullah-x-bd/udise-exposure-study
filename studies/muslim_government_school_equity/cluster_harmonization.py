from __future__ import annotations

import pandas as pd


def canonical_state(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    x = " ".join(str(value).strip().upper().split())
    aliases = {
        "KERLA": "KERALA",
        "ORISSA": "ODISHA",
        "TAMILNADU": "TAMIL NADU",
        "DADRA & NAGAR HAVELI": "DADRA-NAGAR-HAVELI-DAMAN-DIU LINEAGE",
        "DAMAN & DIU": "DADRA-NAGAR-HAVELI-DAMAN-DIU LINEAGE",
        "DAMAN & DIU AND DADRA & NAGAR HAVELI": "DADRA-NAGAR-HAVELI-DAMAN-DIU LINEAGE",
        "DADRA & NAGAR HAVELI AND DAMAN & DIU": "DADRA-NAGAR-HAVELI-DAMAN-DIU LINEAGE",
        "JAMMU & KASHMIR": "JAMMU-KASHMIR-LADAKH LINEAGE",
        "LADAKH": "JAMMU-KASHMIR-LADAKH LINEAGE",
    }
    return aliases.get(x, x)


def canonicalize_state_series(series: pd.Series) -> pd.Series:
    return series.map(canonical_state)


def state_sql(expr: str) -> str:
    x = f"UPPER(TRIM(CAST({expr} AS VARCHAR)))"
    return f"""
    CASE
      WHEN {x}='KERLA' THEN 'KERALA'
      WHEN {x}='ORISSA' THEN 'ODISHA'
      WHEN {x} IN ('TAMILNADU','TAMIL NADU') THEN 'TAMIL NADU'
      WHEN {x} IN (
        'DADRA & NAGAR HAVELI','DAMAN & DIU',
        'DAMAN & DIU AND DADRA & NAGAR HAVELI',
        'DADRA & NAGAR HAVELI AND DAMAN & DIU'
      ) THEN 'DADRA-NAGAR-HAVELI-DAMAN-DIU LINEAGE'
      WHEN {x} IN ('JAMMU & KASHMIR','LADAKH') THEN 'JAMMU-KASHMIR-LADAKH LINEAGE'
      ELSE {x}
    END
    """.strip()
