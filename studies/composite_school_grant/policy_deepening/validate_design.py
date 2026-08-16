from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("logic", ROOT / "logic.py")
logic = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(logic)

pspec = importlib.util.spec_from_file_location("pab_parser", ROOT / "pab_parser.py")
pab = importlib.util.module_from_spec(pspec)
assert pspec.loader is not None
pspec.loader.exec_module(pab)


def boundary_gate() -> None:
    expected = {
        1: 10_000, 30: 10_000, 31: 25_000, 100: 25_000,
        101: 50_000, 250: 50_000, 251: 75_000, 1000: 75_000,
        1001: 100_000,
    }
    for enrol, amount in expected.items():
        got = logic.entitlement_amount(enrol)
        assert got == amount, (enrol, got, amount)


def spell_gate() -> None:
    ent = [75_000, 75_000]
    rec = [75_000, 60_000]
    assert ent[0] == ent[1] and rec[0] >= ent[0] and rec[1] < ent[1]
    ent2 = [75_000, 50_000]
    rec2 = [75_000, 45_000]
    assert not (ent2[0] == ent2[1] and rec2[0] >= ent2[0] and rec2[1] < ent2[1])


def catchup_gate() -> None:
    assert logic.cumulative_caught_up([50_000, 100_000], 75_000)
    assert not logic.cumulative_caught_up([50_000, 70_000], 75_000)
    # Persistence must never be inferred without the required future horizon.
    fallback_only = [50_000]
    assert not logic.cumulative_caught_up(fallback_only, 75_000)


def churn_gate() -> None:
    assert logic.is_pingpong(50_000, 75_000, 50_000)
    assert not logic.is_pingpong(50_000, 75_000, 75_000)
    assert logic.one_year_hold_harmless(50_000, 75_000) == 75_000
    assert logic.near_threshold_hold_harmless(248, 50_000, 75_000, 5) == 75_000
    assert logic.near_threshold_hold_harmless(220, 50_000, 75_000, 5) == 50_000


def state_gate() -> None:
    assert logic.canonical_state("TamilNadu") == "TAMIL NADU"
    assert logic.canonical_state("  orissa ") == "ODISHA"
    assert logic.canonical_state("Daman and Diu and Dadra and Nagar Haveli") == "DADRA & NAGAR HAVELI & DAMAN & DIU"
    assert logic.canonical_state("Dadra and Nagar Haveli") == "DADRA & NAGAR HAVELI"


def historical_small_band_gate() -> None:
    assert logic.entitlement_amount(30, 10_000) == 10_000
    assert logic.entitlement_amount(30, 25_000) == 25_000
    for n in (31, 100, 101, 250, 251, 1000, 1001):
        assert logic.entitlement_amount(n, 10_000) == logic.entitlement_amount(n, 25_000)


def pab_parser_gate() -> None:
    sample = """
    Budget Demand - Test State F. Y. - 2024-2025
    1-School Grant - (Enrol > 30 and <=100 )
    R 56197 0.25000 14049.25000 56197 0.25000 14049.25000 Recommended as Proposed
    2-School Grant - (Enrol > 100 and <= 250 )
    R 57080 0.50000 28540.00000 57080 0.50000 28540.00000 Recommended as Proposed
    3-School Grant - (Enrol > 250 and <= 1000 )
    R 12353 0.75000 9264.75000 12353 0.75000 9264.75000 Recommended as Proposed
    4-School Grant - (Enrol > 1000)
    R 34 1.00000 34.00000 34 1.00000 34.00000 Recommended as Proposed
    5-School Grant (Enrol >= 1 and <= 30)
    R 6265 0.25000 1566.25000 6265 0.25000 1566.25000 Recommended as Proposed
    Total of Composite School Grant 131929 53454.25000 131929 53454.25000

    1-School Grant - (Enrol > 30 and <=100 )
    R 1038 0.25000 259.50000 1038 0.25000 259.50000 Recommended as Proposed
    2-School Grant - (Enrol > 100 and <= 250 )
    R 774 0.50000 387.00000 774 0.50000 387.00000 Recommended as Proposed
    3-School Grant - (Enrol > 250 and <= 1000 )
    R 404 0.75000 303.00000 404 0.75000 303.00000 Recommended as Proposed
    4-School Grant - (Enrol > 1000)
    R 90 1.00000 90.00000 90 1.00000 90.00000 Recommended as Proposed
    Total of Composite School Grant 2306 1039.50000 2306 1039.50000
    """
    assert pab.normalize_financial_year(sample) == "2024-25"
    totals, confidence, _ = pab.extract_csg_totals_from_text(sample)
    assert totals == [53454.25, 1039.5], totals
    assert confidence == "high"
    rec = pab.reconcile_band_rows_to_totals(sample)
    assert len(rec["band_rows"]) == 9, rec["band_rows"]
    assert rec["band_arithmetic_ok"], rec
    small = [r for r in rec["band_rows"] if r["band"] == "1_30"]
    assert len(small) == 1 and small[0]["recommended_unit_lakh"] == 0.25


def main() -> None:
    gates = [
        boundary_gate,
        spell_gate,
        catchup_gate,
        churn_gate,
        state_gate,
        historical_small_band_gate,
        pab_parser_gate,
    ]
    for gate in gates:
        gate()
        print("PASS", gate.__name__)
    print(f"ALL {len(gates)} PRE-LAUNCH DESIGN GATES PASSED")


if __name__ == "__main__":
    main()
