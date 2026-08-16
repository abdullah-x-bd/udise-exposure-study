from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_ROOT = Path("studies/composite_school_grant/outputs/policy_deepening")
FORBIDDEN_STATE_ALIASES = {"KERLA", "ORISSA", "TAMILNADU", "DAMAN & DIU & DADRA & NAGAR HAVELI"}


def req(path: Path) -> Path:
    if not path.exists():
        raise AssertionError(f"Required output missing: {path}")
    return path


def close(a: float, b: float, rtol: float = 1e-9, atol: float = 1e-6) -> bool:
    return bool(np.isclose(float(a), float(b), rtol=rtol, atol=atol, equal_nan=False))


def check_unique(df: pd.DataFrame, keys: list[str], name: str) -> None:
    dup = df.duplicated(keys, keep=False)
    if dup.any():
        raise AssertionError(f"{name} has duplicate keys {keys}: {df.loc[dup, keys].head(10).to_dict('records')}")


def check_states(df: pd.DataFrame, name: str) -> None:
    if "state" not in df:
        return
    if df.state.isna().any():
        raise AssertionError(f"{name} contains null State/UT labels")
    bad = sorted(set(df.state.astype(str)) & FORBIDDEN_STATE_ALIASES)
    if bad:
        raise AssertionError(f"{name} contains uncanonicalized State/UT aliases: {bad}")


def validate_core(root: Path) -> None:
    churn_dir = root / "threshold_churn"
    catch_dir = root / "cumulative_catchup"
    fiscal_dir = root / "fiscal_consequence"
    mech_dir = root / "mechanism_base"

    cf_nat = pd.read_csv(req(churn_dir / "counterfactual_formula_national.csv"))
    cf_state = pd.read_csv(req(churn_dir / "counterfactual_formula_state.csv"))
    check_states(cf_state, "counterfactual_formula_state")
    expected_schedules = {"actual", "avg2", "hold1", "near5", "near10", "near20"}
    if set(cf_nat.schedule) != expected_schedules:
        raise AssertionError(f"Unexpected counterfactual schedules: {set(cf_nat.schedule)}")
    if not close(cf_nat.loc[cf_nat.schedule == "actual", "incremental_nominal_cost_vs_actual"].iloc[0], 0):
        raise AssertionError("Actual schedule has nonzero cost difference from itself")
    for schedule in expected_schedules:
        n = cf_nat[cf_nat.schedule == schedule].iloc[0]
        s = cf_state[cf_state.schedule == schedule]
        if not close(n.nominal_total, s.nominal_total.sum()):
            raise AssertionError(f"National nominal total != State/UT sum for schedule {schedule}")
        if int(n.n_band_changes) != int(s.n_band_changes.sum()):
            raise AssertionError(f"National band changes != State/UT sum for schedule {schedule}")
        if int(n.n_pingpong) != int(s.n_pingpong.sum()):
            raise AssertionError(f"National ping-pong count != State/UT sum for schedule {schedule}")

    cross_nat = pd.read_csv(req(churn_dir / "threshold_crossings_national.csv"))
    c30 = cross_nat[cross_nat.threshold_end == 30]
    if c30.empty or not (c30.historical_rule_caution == 1).all():
        raise AssertionError("30/31 historical-rule caution was lost")

    catch_h_nat = pd.read_csv(req(catch_dir / "fallback_catchup_by_h_national.csv"))
    catch_h_state = pd.read_csv(req(catch_dir / "fallback_catchup_by_h_state.csv"))
    check_states(catch_h_state, "fallback_catchup_by_h_state")
    h0 = catch_h_nat[catch_h_nat.h == 0]
    if h0.empty:
        raise AssertionError("Catch-up audit has no h=0 fallback rows")
    vals = h0.p_caught_up_complete.dropna().to_numpy(float)
    if len(vals) and not np.allclose(vals, 0, atol=1e-12):
        raise AssertionError(f"Fiscal fallback is already caught up at h=0: {vals}")
    for keys, g in catch_h_nat.groupby(["threshold_label", "entitlement", "h"]):
        s = catch_h_state[
            (catch_h_state.threshold_label == keys[0])
            & (catch_h_state.entitlement == keys[1])
            & (catch_h_state.h == keys[2])
        ]
        if int(g.n_events_available.iloc[0]) != int(s.n_events_available.sum()):
            raise AssertionError(f"Catch-up event count does not reconcile for {keys}")
        if int(g.n_complete.iloc[0]) != int(s.n_complete.sum()):
            raise AssertionError(f"Catch-up complete-reporting count does not reconcile for {keys}")

    fixed = pd.read_csv(req(catch_dir / "fallback_fixed_horizon_summary_national.csv"))
    if not set(fixed.horizon.unique()).issubset({1, 2}):
        raise AssertionError("Persistent-gap classifications use a non-fixed horizon")
    good = fixed[fixed.n_complete_reporting_horizon > 0]
    if not np.allclose(
        good.p_caught_up_complete.to_numpy(float) + good.p_persistent_gap_complete.to_numpy(float),
        1.0, atol=1e-10,
    ):
        raise AssertionError("Caught-up and persistent-gap shares do not sum to one at fixed horizons")

    fiscal_nat = pd.read_csv(req(fiscal_dir / "transition_expenditure_national.csv"))
    fiscal_state = pd.read_csv(req(fiscal_dir / "transition_expenditure_state.csv"))
    check_states(fiscal_state, "transition_expenditure_state")
    for keys, g in fiscal_nat.groupby(["threshold_label", "entitlement", "transition_type"]):
        s = fiscal_state[
            (fiscal_state.threshold_label == keys[0])
            & (fiscal_state.entitlement == keys[1])
            & (fiscal_state.transition_type == keys[2])
        ]
        if int(g.n_transitions.iloc[0]) != int(s.n_transitions.sum()):
            raise AssertionError(f"Fiscal transition count does not reconcile for {keys}")
    contrasts = pd.read_csv(req(fiscal_dir / "matched_contrasts_national.csv"))
    if contrasts.empty or 30 not in set(contrasts.min_per_arm):
        raise AssertionError("Primary min-30-per-arm fiscal consequence contrast is absent")
    if not set(contrasts.min_per_arm.unique()).issubset({10, 30, 50}):
        raise AssertionError("Unexpected fiscal contrast support threshold")

    formula = pd.read_csv(req(mech_dir / "formula_totals_state_year.csv"))
    recorded = pd.read_csv(req(mech_dir / "recorded_totals_state_year.csv"))
    check_unique(formula, ["state", "academic_year"], "formula_totals_state_year")
    check_unique(recorded, ["state", "academic_year"], "recorded_totals_state_year")
    check_states(formula, "formula_totals_state_year")
    check_states(recorded, "recorded_totals_state_year")
    if formula.academic_year.nunique() != 8 or recorded.academic_year.nunique() != 8:
        raise AssertionError("Mechanism base does not contain all eight UDISE years")
    if set(formula[["state", "academic_year"]].itertuples(index=False, name=None)) != set(recorded[["state", "academic_year"]].itertuples(index=False, name=None)):
        raise AssertionError("Formula and recorded mechanism bases have different State/UT-year keys")

    print("PASS core accounting and denominator validation")


def validate_pab(root: Path) -> None:
    d = root / "pab_mechanism"
    archive = pd.read_csv(req(d / "pab_archive_inventory.csv"))
    selected = pd.read_csv(req(d / "pab_state_year_selected.csv"))
    recon = pd.read_csv(req(d / "all_state_mechanism_reconciliation.csv"))
    best = pd.read_csv(req(d / "best_global_alignment_by_pab_year.csv"))
    band = pd.read_csv(req(d / "pab_band_validation.csv"))
    for name, df in [("archive", archive), ("selected", selected), ("reconciliation", recon), ("band", band)]:
        check_states(df, name)

    archive_keys = archive[["state", "financial_year"]].drop_duplicates()
    check_unique(selected, ["state", "financial_year"], "pab_state_year_selected")
    check_unique(recon, ["state", "financial_year"], "all_state_mechanism_reconciliation")
    if set(archive_keys.itertuples(index=False, name=None)) != set(selected[["state", "financial_year"]].itertuples(index=False, name=None)):
        raise AssertionError("A State/UT-year disappeared between PAB inventory and selection")
    if set(selected[["state", "financial_year"]].itertuples(index=False, name=None)) != set(recon[["state", "financial_year"]].itertuples(index=False, name=None)):
        raise AssertionError("A State/UT-year disappeared between PAB selection and reconciliation")

    target = {"2021-22", "2022-23", "2023-24", "2024-25"}
    if set(best.financial_year) != target:
        raise AssertionError(f"Best PAB alignment missing target years: got {set(best.financial_year)}")
    rate = selected.groupby("financial_year").pab_csg_rupees.apply(lambda x: x.notna().mean())
    if (rate < 0.50).any():
        raise AssertionError(f"PAB parse coverage below 50%: {rate.to_dict()}")
    if "band_arithmetic_ok" not in band or int(band.band_arithmetic_ok.fillna(False).sum()) <= 0:
        raise AssertionError("No selected PAB State/UT-year has band-level arithmetic reconciliation")

    print("PASS PAB preservation, coverage, and arithmetic validation")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["core", "final"], required=True)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = ap.parse_args()
    validate_core(args.root)
    if args.stage == "final":
        validate_pab(args.root)
    print(f"ALL {args.stage.upper()} OUTPUT VALIDATION GATES PASSED")


if __name__ == "__main__":
    main()
