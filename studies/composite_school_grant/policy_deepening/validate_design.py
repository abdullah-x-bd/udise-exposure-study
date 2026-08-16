from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("logic", ROOT / "logic.py")
logic = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(logic)


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


def main() -> None:
    gates = [
        boundary_gate,
        spell_gate,
        catchup_gate,
        churn_gate,
        state_gate,
        historical_small_band_gate,
    ]
    for gate in gates:
        gate()
        print("PASS", gate.__name__)
    print(f"ALL {len(gates)} PRE-LAUNCH DESIGN GATES PASSED")


if __name__ == "__main__":
    main()
