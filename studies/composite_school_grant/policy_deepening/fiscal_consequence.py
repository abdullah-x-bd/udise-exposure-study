from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("panel_views", ROOT / "panel_views.py")
pv = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pv)

OUT = Path("studies/composite_school_grant/outputs/policy_deepening/fiscal_consequence")


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def add_quality(df: pd.DataFrame, ncol: str) -> pd.DataFrame:
    z = df.copy()
    z["quality_flag"] = np.select(
        [z[ncol] < 30, z[ncol] < 100],
        ["very_small", "small"],
        default="standard",
    )
    return z


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = pv.open_connection()
    pv.add_aligned_tables(con)
    label = pv.threshold_label_sql("entitlement")
    con.execute(f"""
        CREATE TEMP TABLE spells AS
        SELECT *, {label} AS threshold_label
        FROM spell_rows
    """)
    con.execute("""
        CREATE TEMP TABLE transitions AS
        SELECT b.pseudocode,b.state,b.threshold_label,b.entitlement,b.spell_no,
               a.spell_age AS age0,b.spell_age AS age1,b.cycle_index AS event_cycle,
               a.report_year AS report_year0,b.report_year AS report_year1,
               a.receipt AS receipt0,b.receipt AS receipt1,
               a.expenditure AS expenditure0,b.expenditure AS expenditure1,
               a.meets AS meets0,b.meets AS meets1,
               CASE
                 WHEN a.receipt IS NULL OR b.receipt IS NULL THEN 'receipt_missing'
                 WHEN a.meets AND b.meets THEN 'meets_to_meets'
                 WHEN a.meets AND NOT b.meets THEN 'meets_to_below'
                 WHEN NOT a.meets AND b.meets THEN 'below_to_meets'
                 WHEN NOT a.meets AND NOT b.meets THEN 'below_to_below'
               END AS transition_type,
               CASE WHEN a.expenditure IS NOT NULL THEN a.expenditure/a.entitlement END AS exp_ratio0,
               CASE WHEN b.expenditure IS NOT NULL THEN b.expenditure/b.entitlement END AS exp_ratio1,
               CASE WHEN a.expenditure IS NOT NULL AND b.expenditure IS NOT NULL
                    THEN b.expenditure/b.entitlement-a.expenditure/a.entitlement END AS delta_exp_ratio,
               CASE WHEN b.expenditure IS NOT NULL
                    THEN GREATEST(b.entitlement-b.expenditure,0)/b.entitlement END AS exp_shortfall_share1,
               CASE WHEN b.expenditure IS NOT NULL
                    THEN b.expenditure<b.entitlement END AS expenditure_below_entitlement1
        FROM spells a
        JOIN spells b
          ON a.pseudocode=b.pseudocode
         AND a.spell_no=b.spell_no
         AND b.spell_age=a.spell_age+1
    """)
    n_trans = int(con.execute("SELECT COUNT(*) FROM transitions WHERE transition_type<>'receipt_missing'").fetchone()[0])
    if n_trans <= 0:
        raise RuntimeError("Fiscal consequence audit constructed zero observed receipt transitions")

    state = con.execute("""
        SELECT state,threshold_label,entitlement,transition_type,
               COUNT(*) AS n_transitions,
               COUNT(expenditure1) AS n_exp1,
               COUNT(delta_exp_ratio) AS n_delta_exp,
               AVG(exp_ratio1) AS mean_exp_ratio_destination,
               MEDIAN(exp_ratio1) AS median_exp_ratio_destination,
               AVG(delta_exp_ratio) AS mean_delta_exp_ratio,
               AVG(exp_shortfall_share1) AS mean_exp_shortfall_share_destination,
               AVG(CAST(expenditure_below_entitlement1 AS DOUBLE)) AS p_expenditure_below_entitlement_destination
        FROM transitions
        WHERE transition_type<>'receipt_missing'
        GROUP BY 1,2,3,4
        ORDER BY 1,3,4
    """).df()
    nat = con.execute("""
        SELECT threshold_label,entitlement,transition_type,
               COUNT(*) AS n_transitions,
               COUNT(expenditure1) AS n_exp1,
               COUNT(delta_exp_ratio) AS n_delta_exp,
               AVG(exp_ratio1) AS mean_exp_ratio_destination,
               MEDIAN(exp_ratio1) AS median_exp_ratio_destination,
               AVG(delta_exp_ratio) AS mean_delta_exp_ratio,
               AVG(exp_shortfall_share1) AS mean_exp_shortfall_share_destination,
               AVG(CAST(expenditure_below_entitlement1 AS DOUBLE)) AS p_expenditure_below_entitlement_destination
        FROM transitions
        WHERE transition_type<>'receipt_missing'
        GROUP BY 1,2,3
        ORDER BY 2,3
    """).df()
    save(add_quality(state, "n_transitions"), "transition_expenditure_state.csv")
    save(nat, "transition_expenditure_national.csv")

    cell = con.execute("""
        SELECT state,threshold_label,entitlement,event_cycle,transition_type,
               COUNT(delta_exp_ratio) AS n_delta,
               AVG(delta_exp_ratio) AS mean_delta_exp_ratio,
               AVG(exp_ratio1) AS mean_exp_ratio_destination
        FROM transitions
        WHERE transition_type<>'receipt_missing'
        GROUP BY 1,2,3,4,5
    """).df()
    save(cell, "transition_cells_state_cycle.csv")

    def contrast(a: str, b: str, name: str) -> pd.DataFrame:
        x = cell[cell.transition_type == a].copy()
        y = cell[cell.transition_type == b].copy()
        keys = ["state", "threshold_label", "entitlement", "event_cycle"]
        z = x.merge(y, on=keys, suffixes=("_a", "_b"), how="outer")
        z["contrast"] = name
        z["delta_exp_ratio_contrast"] = z["mean_delta_exp_ratio_a"] - z["mean_delta_exp_ratio_b"]
        z["destination_exp_ratio_contrast"] = z["mean_exp_ratio_destination_a"] - z["mean_exp_ratio_destination_b"]
        z["harmonic_weight"] = np.where(
            (z["n_delta_a"].fillna(0) > 0) & (z["n_delta_b"].fillna(0) > 0),
            2 * z["n_delta_a"] * z["n_delta_b"] / (z["n_delta_a"] + z["n_delta_b"]),
            np.nan,
        )
        return z

    fallback_contrast = contrast("meets_to_below", "meets_to_meets", "fallback_minus_stable_meet")
    recovery_contrast = contrast("below_to_meets", "below_to_below", "recovery_minus_persistent_below")
    contrasts = pd.concat([fallback_contrast, recovery_contrast], ignore_index=True)
    save(contrasts, "matched_cell_contrasts.csv")

    pooled_rows = []
    for (contrast_name, th), g in contrasts.groupby(["contrast", "threshold_label"], dropna=False):
        good = g[g.harmonic_weight.notna() & g.delta_exp_ratio_contrast.notna()]
        if good.empty:
            continue
        w = good.harmonic_weight.to_numpy(float)
        d = good.delta_exp_ratio_contrast.to_numpy(float)
        dest = good.destination_exp_ratio_contrast.to_numpy(float)
        pooled_rows.append({
            "contrast": contrast_name,
            "threshold_label": th,
            "n_state_cycle_cells": len(good),
            "weighted_delta_exp_ratio_contrast": float(np.average(d, weights=w)),
            "equal_cell_delta_exp_ratio_contrast": float(np.mean(d)),
            "weighted_destination_exp_ratio_contrast": float(np.average(dest, weights=w)),
        })
    pooled = pd.DataFrame(pooled_rows)
    save(pooled, "matched_contrasts_national.csv")

    corr_state = con.execute("""
        SELECT state,threshold_label,entitlement,
               COUNT(*) FILTER(WHERE receipt IS NOT NULL AND expenditure IS NOT NULL) AS n_both,
               CORR(receipt/entitlement,expenditure/entitlement)
                   FILTER(WHERE receipt IS NOT NULL AND expenditure IS NOT NULL) AS corr_receipt_expenditure_ratio,
               AVG(CASE WHEN receipt IS NOT NULL AND expenditure IS NOT NULL
                        THEN ABS(receipt-expenditure)/entitlement END) AS mean_abs_receipt_expenditure_gap_ratio
        FROM spells
        GROUP BY 1,2,3
        ORDER BY 1,3
    """).df()
    corr_nat = con.execute("""
        SELECT threshold_label,entitlement,
               COUNT(*) FILTER(WHERE receipt IS NOT NULL AND expenditure IS NOT NULL) AS n_both,
               CORR(receipt/entitlement,expenditure/entitlement)
                   FILTER(WHERE receipt IS NOT NULL AND expenditure IS NOT NULL) AS corr_receipt_expenditure_ratio,
               AVG(CASE WHEN receipt IS NOT NULL AND expenditure IS NOT NULL
                        THEN ABS(receipt-expenditure)/entitlement END) AS mean_abs_receipt_expenditure_gap_ratio
        FROM spells
        GROUP BY 1,2
        ORDER BY 2
    """).df()
    save(add_quality(corr_state, "n_both"), "receipt_expenditure_comovement_state.csv")
    save(corr_nat, "receipt_expenditure_comovement_national.csv")

    con.execute("""
        CREATE TEMP TABLE fallback_events AS
        SELECT pseudocode,state,threshold_label,entitlement,spell_no,age1 AS event_age,
               pseudocode || ':' || CAST(spell_no AS VARCHAR) || ':' ||
                   CAST(age1 AS VARCHAR) AS event_id
        FROM transitions
        WHERE transition_type='meets_to_below'
    """)
    con.execute("""
        CREATE TEMP TABLE fallback_exp_follow AS
        SELECT e.*,s.spell_age-e.event_age AS h,s.expenditure
        FROM fallback_events e
        JOIN spells s
          ON e.pseudocode=s.pseudocode
         AND e.spell_no=s.spell_no
         AND s.spell_age BETWEEN e.event_age AND e.event_age+2
    """)
    con.execute("""
        CREATE TEMP TABLE fallback_exp_h AS
        SELECT *,
               COUNT(*) OVER w AS horizon_rows,
               COUNT(expenditure) OVER w AS reported_exp_rows,
               SUM(expenditure) OVER w AS cumulative_expenditure_reported,
               SUM(COALESCE(expenditure,0)) OVER w AS cumulative_expenditure_zero
        FROM fallback_exp_follow
        WINDOW w AS (
            PARTITION BY event_id ORDER BY h
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    """)
    state_follow = con.execute("""
        SELECT state,threshold_label,entitlement,h,
               COUNT(DISTINCT event_id) AS n_events,
               COUNT(DISTINCT event_id) FILTER(WHERE reported_exp_rows=horizon_rows) AS n_complete_exp,
               AVG(CASE WHEN reported_exp_rows=horizon_rows
                        THEN cumulative_expenditure_reported/(entitlement*(h+1)) END) AS mean_cumulative_exp_ratio_complete,
               AVG(CASE WHEN reported_exp_rows=horizon_rows
                        THEN CAST(cumulative_expenditure_reported>=entitlement*(h+1) AS DOUBLE) END) AS p_cumulative_exp_atleast_entitlement_complete,
               AVG(cumulative_expenditure_zero/(entitlement*(h+1))) AS mean_cumulative_exp_ratio_missing_zero
        FROM fallback_exp_h
        GROUP BY 1,2,3,4
        ORDER BY 1,3,4
    """).df()
    nat_follow = con.execute("""
        SELECT threshold_label,entitlement,h,
               COUNT(DISTINCT event_id) AS n_events,
               COUNT(DISTINCT event_id) FILTER(WHERE reported_exp_rows=horizon_rows) AS n_complete_exp,
               AVG(CASE WHEN reported_exp_rows=horizon_rows
                        THEN cumulative_expenditure_reported/(entitlement*(h+1)) END) AS mean_cumulative_exp_ratio_complete,
               AVG(CASE WHEN reported_exp_rows=horizon_rows
                        THEN CAST(cumulative_expenditure_reported>=entitlement*(h+1) AS DOUBLE) END) AS p_cumulative_exp_atleast_entitlement_complete,
               AVG(cumulative_expenditure_zero/(entitlement*(h+1))) AS mean_cumulative_exp_ratio_missing_zero
        FROM fallback_exp_h
        GROUP BY 1,2,3
        ORDER BY 2,3
    """).df()
    save(add_quality(state_follow, "n_events"), "fallback_expenditure_followup_state.csv")
    save(nat_follow, "fallback_expenditure_followup_national.csv")

    validation = {
        "observed_receipt_transitions": n_trans,
        "fiscal_fallback_events": int(con.execute("SELECT COUNT(*) FROM fallback_events").fetchone()[0]),
        "entitlement_change_cannot_enter_transition_table": True,
        "primary_expenditure_missing_rule": "reported-only",
        "sensitivity_expenditure_missing_rule": "missing-as-zero in follow-up only",
        "interpretation": "descriptive fiscal consequence; not causal effect",
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    lines = [
        "# Fiscal consequence audit",
        "",
        f"Observed same-entitlement receipt transitions: {n_trans:,}.",
        f"Receipt fallback events followed for expenditure: {validation['fiscal_fallback_events']:,}.",
        "",
        "Primary comparisons are within State x entitlement band x aligned cycle and are descriptive, not causal.",
        "",
        "## National matched contrasts",
    ]
    for _, r in pooled.iterrows():
        lines.append(
            f"- {r.contrast}, {r.threshold_label}: "
            f"weighted change-in-expenditure-ratio contrast {r.weighted_delta_exp_ratio_contrast:.3f} "
            f"across {int(r.n_state_cycle_cells)} State-cycle cells."
        )
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    con.close()


if __name__ == "__main__":
    main()
