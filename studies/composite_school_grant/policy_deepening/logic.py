from __future__ import annotations

from typing import Iterable

BROAD_MANAGEMENT = (1, 2, 3, 6, 89, 90)
YEARS = (
    "2018-19", "2019-20", "2020-21", "2021-22",
    "2022-23", "2023-24", "2024-25", "2025-26",
)
ALIGNED_CYCLES = (
    ("2019-20", "2021-22", "2022-23"),
    ("2020-21", "2022-23", "2023-24"),
    ("2021-22", "2023-24", "2024-25"),
    ("2022-23", "2024-25", "2025-26"),
)
THRESHOLDS = (30, 100, 250, 1000)

STATE_ALIASES = {
    "TAMILNADU": "TAMIL NADU",
    "KERLA": "KERALA",
    "ORISSA": "ODISHA",
    "DAMAN & DIU & DADRA & NAGAR HAVELI": "DADRA & NAGAR HAVELI & DAMAN & DIU",
}


def canonical_state(value: str | None) -> str | None:
    if value is None:
        return None
    s = " ".join(str(value).strip().upper().replace(" AND ", " & ").split())
    return STATE_ALIASES.get(s, s)


def canonical_state_sql(expr: str) -> str:
    base = f"REPLACE(REGEXP_REPLACE(UPPER(TRIM(CAST({expr} AS VARCHAR))), '\\s+', ' ', 'g'), ' AND ', ' & ')"
    cases = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in STATE_ALIASES.items())
    return f"(CASE {base} {cases} ELSE {base} END)"


def entitlement_amount(enrol: float | int | None, small_amount: int = 10_000) -> int | None:
    if enrol is None:
        return None
    x = float(enrol)
    if x < 1:
        return None
    if x <= 30:
        return int(small_amount)
    if x <= 100:
        return 25_000
    if x <= 250:
        return 50_000
    if x <= 1000:
        return 75_000
    return 100_000


def entitlement_sql(expr: str, small_amount: int = 10_000) -> str:
    return (
        f"CASE WHEN {expr} BETWEEN 1 AND 30 THEN {int(small_amount)} "
        f"WHEN {expr}>30 AND {expr}<=100 THEN 25000 "
        f"WHEN {expr}>100 AND {expr}<=250 THEN 50000 "
        f"WHEN {expr}>250 AND {expr}<=1000 THEN 75000 "
        f"WHEN {expr}>1000 THEN 100000 END"
    )


def band_id_from_amount(amount: int | float | None) -> int | None:
    mapping = {10_000: 1, 25_000: 2, 50_000: 3, 75_000: 4, 100_000: 5}
    return mapping.get(int(amount)) if amount is not None else None


def entry_threshold_for_amount(amount: int | float | None) -> int | None:
    mapping = {25_000: 30, 50_000: 100, 75_000: 250, 100_000: 1000}
    return mapping.get(int(amount)) if amount is not None else None


def one_year_hold_harmless(current_amount: int, previous_amount: int | None) -> int:
    if previous_amount is not None and current_amount < previous_amount:
        return int(previous_amount)
    return int(current_amount)


def near_threshold_hold_harmless(
    current_enrol: float,
    current_amount: int,
    previous_amount: int | None,
    margin: int,
) -> int:
    if previous_amount is None or current_amount >= previous_amount:
        return int(current_amount)
    boundary = entry_threshold_for_amount(previous_amount)
    if boundary is not None and float(current_enrol) >= boundary - margin:
        return int(previous_amount)
    return int(current_amount)


def cumulative_caught_up(receipts: Iterable[float], entitlement: float) -> bool:
    vals = list(receipts)
    if not vals:
        return False
    return sum(vals) >= float(entitlement) * len(vals)


def is_pingpong(a: int | None, b: int | None, c: int | None) -> bool:
    return a is not None and b is not None and c is not None and a == c and a != b
