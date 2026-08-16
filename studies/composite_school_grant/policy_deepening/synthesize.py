from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("studies/composite_school_grant/outputs/policy_deepening")
OUT = ROOT / "final"


def read(rel: str) -> pd.DataFrame:
    p = ROOT / rel
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_csv(p)


def wavg(df: pd.DataFrame, value: str, weight: str) -> float:
    z = df[df[value].notna() & df[weight].notna() & (df[weight] > 0)]
    if z.empty:
        return np.nan
    return float(np.average(z[value].to_numpy(float), weights=z[weight].to_numpy(float)))


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)

    catch_nat = read("cumulative_catchup/fallback_fixed_horizon_summary_national.csv")
    catch_state = read("cumulative_catchup/fallback_fixed_horizon_summary_state.csv")
    catch_curve = read("cumulative_catchup/fallback_catchup_by_h_national.csv")
    churn_nat = read("threshold_churn/school_churn_national.csv")
    churn_state = read("threshold_churn/school_churn_state.csv")
    crossing_nat = read("threshold_churn/threshold_crossings_national.csv")
    cf_nat = read("threshold_churn/counterfactual_formula_national.csv")
    cf_state = read("threshold_churn/counterfactual_formula_state.csv")
    fiscal_nat = read("fiscal_consequence/matched_contrasts_national.csv")
    fiscal_state = read("fiscal_consequence/transition_expenditure_state.csv")
    fiscal_cells = read("fiscal_consequence/matched_cell_contrasts.csv")
    pab_best = read("pab_mechanism/best_global_alignment_by_pab_year.csv")
    pab_rec = read("pab_mechanism/all_state_mechanism_reconciliation.csv")
    pab_selected = read("pab_mechanism/pab_state_year_selected.csv")

    headline = []
    for _, r in catch_nat.iterrows():
        headline.append({
            "study": "cumulative_catchup",
            "metric": "p_caught_up_complete",
            "threshold": r.threshold_label,
            "horizon": int(r.horizon),
            "value": r.p_caught_up_complete,
            "n": r.n_complete_reporting_horizon,
            "unit": "share",
        })
        headline.append({
            "study": "cumulative_catchup",
            "metric": "p_persistent_gap_complete",
            "threshold": r.threshold_label,
            "horizon": int(r.horizon),
            "value": r.p_persistent_gap_complete,
            "n": r.n_complete_reporting_horizon,
            "unit": "share",
        })
    c = churn_nat.iloc[0]
    for metric in ["p_any_band_change", "p_two_plus_band_changes", "p_three_plus_band_changes", "p_any_pingpong"]:
        headline.append({
            "study": "threshold_churn", "metric": metric, "threshold": "all",
            "horizon": np.nan, "value": c[metric], "n": c.n_schools, "unit": "share",
        })
    actual = cf_nat[cf_nat.schedule == "actual"].iloc[0]
    for _, r in cf_nat[cf_nat.schedule != "actual"].iterrows():
        headline.append({
            "study": "threshold_churn", "metric": f"band_change_reduction_{r.schedule}",
            "threshold": "all", "horizon": np.nan,
            "value": r.band_changes_reduction_vs_actual,
            "n": actual.n_band_changes, "unit": "share_reduction",
        })
        headline.append({
            "study": "threshold_churn", "metric": f"incremental_nominal_cost_{r.schedule}",
            "threshold": "all", "horizon": np.nan,
            "value": r.incremental_nominal_cost_vs_actual,
            "n": actual.n_school_years, "unit": "rupees",
        })
    primary_fiscal = fiscal_nat[fiscal_nat.min_per_arm == 30]
    for _, r in primary_fiscal.iterrows():
        headline.append({
            "study": "fiscal_consequence",
            "metric": r.contrast,
            "threshold": r.threshold_label,
            "horizon": np.nan,
            "value": r.weighted_delta_exp_ratio_contrast_capped2,
            "n": r.n_state_cycle_cells,
            "unit": "change_in_expenditure_to_entitlement_ratio",
        })
    for _, r in pab_best.iterrows():
        headline.append({
            "study": "pab_mechanism",
            "metric": "best_alignment_median_state_abs_gap",
            "threshold": r.schedule,
            "horizon": int(r.lag_from_enrolment_to_pab_fy),
            "value": r.median_state_abs_pct_gap,
            "n": r.n_states,
            "unit": "share",
            "financial_year": r.financial_year,
        })
    headline_df = pd.DataFrame(headline)
    headline_df.to_csv(OUT / "headline_metrics.csv", index=False)

    # State summary. No composite quality score is created.
    states = sorted(set(churn_state.state.dropna()) | set(catch_state.state.dropna()) | set(fiscal_state.state.dropna()) | set(pab_rec.state.dropna()))
    dashboard = pd.DataFrame({"state": states})
    dashboard = dashboard.merge(
        churn_state[[
            "state", "n_schools", "p_any_band_change", "p_two_plus_band_changes",
            "p_three_plus_band_changes", "p_any_pingpong", "mean_band_changes",
        ]], on="state", how="left"
    )

    for schedule in ("avg2", "hold1", "near10"):
        z = cf_state[cf_state.schedule == schedule][[
            "state", "incremental_nominal_cost_vs_actual", "band_changes_reduction_vs_actual"
        ]].copy()
        z = z.rename(columns={
            "incremental_nominal_cost_vs_actual": f"{schedule}_incremental_nominal_cost_rupees",
            "band_changes_reduction_vs_actual": f"{schedule}_band_change_reduction",
        })
        dashboard = dashboard.merge(z, on="state", how="left")

    for horizon in (1, 2):
        z = catch_state[catch_state.horizon == horizon]
        rows = []
        for state, g in z.groupby("state"):
            rows.append({
                "state": state,
                f"catchup_h{horizon}_n_complete": int(g.n_complete_reporting_horizon.sum()),
                f"catchup_h{horizon}_weighted": wavg(g, "p_caught_up_complete", "n_complete_reporting_horizon"),
                f"persistent_gap_h{horizon}_weighted": wavg(g, "p_persistent_gap_complete", "n_complete_reporting_horizon"),
            })
        dashboard = dashboard.merge(pd.DataFrame(rows), on="state", how="left")

    fallback = fiscal_state[fiscal_state.transition_type == "meets_to_below"]
    rows = []
    for state, g in fallback.groupby("state"):
        rows.append({
            "state": state,
            "fiscal_fallback_transition_n": int(g.n_transitions.sum()),
            "fallback_destination_exp_ratio_capped2": wavg(g, "mean_exp_ratio_destination_capped2", "n_exp1"),
            "fallback_destination_exp_below_entitlement": wavg(g, "p_expenditure_below_entitlement_destination", "n_exp1"),
        })
    dashboard = dashboard.merge(pd.DataFrame(rows), on="state", how="left")

    # Primary supported State-cycle fiscal contrasts, weighted within state.
    fc = fiscal_cells[
        fiscal_cells.harmonic_weight.notna()
        & (fiscal_cells.n_delta_a >= 30)
        & (fiscal_cells.n_delta_b >= 30)
    ]
    rows = []
    for state, g in fc.groupby("state"):
        rec = {"state": state}
        for contrast, h in g.groupby("contrast"):
            rec[f"{contrast}_exp_change_capped2"] = wavg(h, "delta_exp_ratio_contrast_capped2", "harmonic_weight")
            rec[f"{contrast}_supported_cells"] = len(h)
        rows.append(rec)
    if rows:
        dashboard = dashboard.merge(pd.DataFrame(rows), on="state", how="left")

    rows = []
    for state, g in pab_rec.groupby("state"):
        rows.append({
            "state": state,
            "pab_state_years": len(g),
            "pab_resolved_years": int(g.pab_csg_rupees.notna().sum()),
            "median_abs_formula_pab_gap": float(g.formula_pab_gap_fraction.abs().median()) if "formula_pab_gap_fraction" in g and g.formula_pab_gap_fraction.notna().any() else np.nan,
            "median_abs_pab_recorded_receipt_gap": float(g.pab_recorded_receipt_gap_fraction.abs().median()) if "pab_recorded_receipt_gap_fraction" in g and g.pab_recorded_receipt_gap_fraction.notna().any() else np.nan,
            "n_divergence_after_pab_or_reporting": int((g.mechanism_status == "divergence_after_PAB_or_reporting").sum()),
            "n_formula_to_pab_difference": int((g.mechanism_status == "formula_to_PAB_difference").sum()),
            "n_broadly_reconciled": int((g.mechanism_status == "broadly_reconciled").sum()),
            "n_unresolved": int((g.mechanism_status == "unresolved").sum()),
        })
    dashboard = dashboard.merge(pd.DataFrame(rows), on="state", how="left")
    dashboard.to_csv(OUT / "state_policy_deepening_dashboard.csv", index=False)

    # Preserve policy-relevant long tables in the definitive folder.
    catch_curve.to_csv(OUT / "catchup_curve_national.csv", index=False)
    crossing_nat.to_csv(OUT / "threshold_crossings_national.csv", index=False)
    cf_nat.to_csv(OUT / "formula_smoothing_counterfactuals_national.csv", index=False)
    primary_fiscal.to_csv(OUT / "fiscal_consequence_primary_national.csv", index=False)
    pab_best.to_csv(OUT / "pab_alignment_national.csv", index=False)
    pab_selected.to_csv(OUT / "pab_state_year_source_audit.csv", index=False)

    lines = [
        "# CSG policy-deepening audit",
        "",
        "Four studies are kept separate because they identify different policy failures: cumulative catch-up under unchanged entitlement, threshold-driven entitlement churn, recorded expenditure consequences, and formula-to-PAB-to-UDISE reconciliation.",
        "",
        "## 1. Cumulative catch-up after recorded fiscal fallback",
    ]
    for _, r in catch_nat.sort_values(["entitlement", "horizon"]).iterrows():
        lines.append(
            f"- {r.threshold_label}, h={int(r.horizon)}: {100*r.p_caught_up_complete:.1f}% cumulatively caught up; "
            f"{100*r.p_persistent_gap_complete:.1f}% still cumulatively below nominal entitlement among "
            f"{int(r.n_complete_reporting_horizon):,} events with the required complete follow-up."
        )
    lines += ["", "## 2. Threshold churn and formula smoothing"]
    lines.append(f"- {100*c.p_any_band_change:.1f}% of observed schools change CSG bands at least once; {100*c.p_any_pingpong:.1f}% show at least one A-B-A return pattern.")
    for _, r in cf_nat[cf_nat.schedule != "actual"].iterrows():
        lines.append(
            f"- {r.schedule}: changes band-switch count by {100*r.band_changes_reduction_vs_actual:.1f}% "
            f"with nominal fiscal difference Rs {r.incremental_nominal_cost_vs_actual:,.0f} over the observed panel."
        )
    lines += ["", "## 3. Recorded expenditure consequences"]
    if primary_fiscal.empty:
        lines.append("- No transition contrast met the primary minimum of 30 observations per arm within State x band x cycle cells.")
    else:
        for _, r in primary_fiscal.iterrows():
            lines.append(
                f"- {r.contrast}, {r.threshold_label}: capped expenditure-ratio change contrast "
                f"{r.weighted_delta_exp_ratio_contrast_capped2:+.3f} across {int(r.n_state_cycle_cells)} supported State-cycle cells."
            )
    lines += ["", "## 4. Formula to PAB alignment"]
    for _, r in pab_best.iterrows():
        lines.append(
            f"- PAB {r.financial_year}: best common mapping uses lag {int(r.lag_from_enrolment_to_pab_fy)} and {r.schedule}; "
            f"median State/UT formula-PAB discrepancy {100*r.median_state_abs_pct_gap:.1f}% across {int(r.n_states)} jurisdictions."
        )
    lines += [
        "",
        "## Interpretation guardrails",
        "- Receipt and expenditure are UDISE administrative records, not independently verified bank transactions.",
        "- Catch-up and expenditure studies condition only on unchanged nominal entitlement; enrolment-driven entitlement changes end the spell.",
        "- The expenditure transition comparison is descriptive, not a causal estimate of spending effects.",
        "- The 30/31 boundary remains historically uncertain and is never used alone to establish a policy conclusion.",
        "- PAB document extraction preserves unresolved and ambiguous State/UT-years rather than imputing them.",
        "- The mechanism-status labels are diagnostics; continuous formula-PAB and PAB-record gaps are the primary quantities.",
    ]
    (OUT / "POLICY_DEEPENING_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
