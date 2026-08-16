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

OUT = Path("studies/composite_school_grant/outputs/policy_deepening/cumulative_catchup")


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def add_quality_flag(df: pd.DataFrame, ncol: str) -> pd.DataFrame:
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

    # A. Cumulative fidelity for every continuous same-entitlement spell.
    con.execute("""
        CREATE TEMP TABLE cumulative AS
        SELECT *,
               SUM(entitlement) OVER w AS cumulative_entitlement,
               SUM(COALESCE(receipt,0)) OVER w AS cumulative_receipt_zero,
               SUM(receipt) OVER w AS cumulative_receipt_reported_sum,
               COUNT(receipt) OVER w AS cumulative_reported_cycles,
               COUNT(*) OVER w AS cumulative_cycles
        FROM spells
        WINDOW w AS (
            PARTITION BY pseudocode,spell_no
            ORDER BY spell_age
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    """)
    con.execute("""
        CREATE TEMP TABLE cumulative2 AS
        SELECT *,
               cumulative_reported_cycles=cumulative_cycles AS complete_reporting,
               CASE WHEN cumulative_reported_cycles=cumulative_cycles
                    THEN cumulative_receipt_reported_sum/cumulative_entitlement END AS cumulative_ratio_complete,
               CASE WHEN cumulative_reported_cycles=cumulative_cycles
                    THEN GREATEST(cumulative_entitlement-cumulative_receipt_reported_sum,0) END AS cumulative_gap_complete,
               CASE WHEN cumulative_reported_cycles=cumulative_cycles
                    THEN cumulative_receipt_reported_sum>=cumulative_entitlement END AS cumulative_caught_up_complete,
               cumulative_receipt_zero/cumulative_entitlement AS cumulative_ratio_zero,
               GREATEST(cumulative_entitlement-cumulative_receipt_zero,0) AS cumulative_gap_zero,
               cumulative_receipt_zero>=cumulative_entitlement AS cumulative_caught_up_zero
        FROM cumulative
    """)

    state_cum = con.execute("""
        SELECT state,threshold_label,entitlement,spell_age,
               COUNT(*) AS n_rows,
               COUNT(*) FILTER(WHERE complete_reporting) AS n_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(cumulative_caught_up_complete AS DOUBLE) END) AS p_cumulative_caught_up_complete,
               AVG(CASE WHEN complete_reporting THEN cumulative_ratio_complete END) AS mean_cumulative_ratio_complete,
               MEDIAN(CASE WHEN complete_reporting THEN cumulative_gap_complete END) AS median_cumulative_gap_complete,
               AVG(CAST(cumulative_caught_up_zero AS DOUBLE)) AS p_cumulative_caught_up_missing_zero,
               AVG(cumulative_ratio_zero) AS mean_cumulative_ratio_missing_zero
        FROM cumulative2
        GROUP BY 1,2,3,4
        ORDER BY 1,3,4
    """).df()
    nat_cum = con.execute("""
        SELECT threshold_label,entitlement,spell_age,
               COUNT(*) AS n_rows,
               COUNT(*) FILTER(WHERE complete_reporting) AS n_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(cumulative_caught_up_complete AS DOUBLE) END) AS p_cumulative_caught_up_complete,
               AVG(CASE WHEN complete_reporting THEN cumulative_ratio_complete END) AS mean_cumulative_ratio_complete,
               MEDIAN(CASE WHEN complete_reporting THEN cumulative_gap_complete END) AS median_cumulative_gap_complete,
               AVG(CAST(cumulative_caught_up_zero AS DOUBLE)) AS p_cumulative_caught_up_missing_zero,
               AVG(cumulative_ratio_zero) AS mean_cumulative_ratio_missing_zero
        FROM cumulative2
        GROUP BY 1,2,3
        ORDER BY 2,3
    """).df()
    save(add_quality_flag(state_cum, "n_rows"), "spell_cumulative_state.csv")
    save(nat_cum, "spell_cumulative_national.csv")

    # B. Event study beginning exactly at a fiscal fallback, Meets -> Below,
    # while the entitlement remains unchanged. The same spell join guarantees this.
    con.execute("""
        CREATE TEMP TABLE fallback_events AS
        SELECT b.pseudocode,b.state,b.entitlement,b.threshold_label,b.spell_no,
               b.spell_age AS event_age,b.cycle_index AS event_cycle,
               b.assignment_year,b.report_year,
               b.receipt AS event_receipt,
               b.entitlement-b.receipt AS initial_deficit,
               b.pseudocode || ':' || CAST(b.spell_no AS VARCHAR) || ':' ||
                   CAST(b.spell_age AS VARCHAR) AS event_id
        FROM spells a
        JOIN spells b
          ON a.pseudocode=b.pseudocode
         AND a.spell_no=b.spell_no
         AND b.spell_age=a.spell_age+1
        WHERE a.receipt IS NOT NULL
          AND b.receipt IS NOT NULL
          AND a.receipt>=a.entitlement
          AND b.receipt<b.entitlement
    """)
    n_events = int(con.execute("SELECT COUNT(*) FROM fallback_events").fetchone()[0])
    if n_events <= 0:
        raise RuntimeError("Cumulative catch-up audit constructed zero fiscal fallback events")

    con.execute("""
        CREATE TEMP TABLE event_follow AS
        SELECT e.*, f.spell_age-e.event_age AS h,
               f.receipt AS follow_receipt,
               f.expenditure AS follow_expenditure
        FROM fallback_events e
        JOIN spells f
          ON e.pseudocode=f.pseudocode
         AND e.spell_no=f.spell_no
         AND f.spell_age BETWEEN e.event_age AND e.event_age+2
    """)
    con.execute("""
        CREATE TEMP TABLE event_h AS
        SELECT *,
               COUNT(*) OVER w AS observed_horizon_rows,
               COUNT(follow_receipt) OVER w AS reported_horizon_rows,
               SUM(follow_receipt) OVER w AS cumulative_receipt_reported,
               SUM(COALESCE(follow_receipt,0)) OVER w AS cumulative_receipt_zero
        FROM event_follow
        WINDOW w AS (
            PARTITION BY event_id
            ORDER BY h
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    """)
    con.execute("""
        CREATE TEMP TABLE event_h2 AS
        SELECT *,
               entitlement*(h+1) AS cumulative_expected,
               reported_horizon_rows=observed_horizon_rows AS complete_reporting,
               CASE WHEN reported_horizon_rows=observed_horizon_rows
                    THEN cumulative_receipt_reported>=entitlement*(h+1) END AS caught_up_complete,
               CASE WHEN reported_horizon_rows=observed_horizon_rows
                    THEN GREATEST(entitlement*(h+1)-cumulative_receipt_reported,0) END AS cumulative_gap_complete,
               CASE WHEN reported_horizon_rows=observed_horizon_rows
                    THEN cumulative_receipt_reported/(entitlement*(h+1)) END AS cumulative_ratio_complete,
               cumulative_receipt_zero>=entitlement*(h+1) AS caught_up_zero,
               GREATEST(entitlement*(h+1)-cumulative_receipt_zero,0) AS cumulative_gap_zero,
               cumulative_receipt_zero/(entitlement*(h+1)) AS cumulative_ratio_zero
        FROM event_h
    """)

    state_h = con.execute("""
        SELECT state,threshold_label,entitlement,h,
               COUNT(DISTINCT event_id) AS n_events_available,
               COUNT(DISTINCT event_id) FILTER(WHERE complete_reporting) AS n_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(caught_up_complete AS DOUBLE) END) AS p_caught_up_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(cumulative_gap_complete<initial_deficit AS DOUBLE) END) AS p_gap_reduced_complete,
               MEDIAN(CASE WHEN complete_reporting THEN cumulative_gap_complete END) AS median_gap_complete,
               AVG(CAST(caught_up_zero AS DOUBLE)) AS p_caught_up_missing_zero,
               MEDIAN(cumulative_gap_zero) AS median_gap_missing_zero
        FROM event_h2
        GROUP BY 1,2,3,4
        ORDER BY 1,3,4
    """).df()
    nat_h = con.execute("""
        SELECT threshold_label,entitlement,h,
               COUNT(DISTINCT event_id) AS n_events_available,
               COUNT(DISTINCT event_id) FILTER(WHERE complete_reporting) AS n_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(caught_up_complete AS DOUBLE) END) AS p_caught_up_complete,
               AVG(CASE WHEN complete_reporting THEN CAST(cumulative_gap_complete<initial_deficit AS DOUBLE) END) AS p_gap_reduced_complete,
               MEDIAN(CASE WHEN complete_reporting THEN cumulative_gap_complete END) AS median_gap_complete,
               AVG(CAST(caught_up_zero AS DOUBLE)) AS p_caught_up_missing_zero,
               MEDIAN(cumulative_gap_zero) AS median_gap_missing_zero
        FROM event_h2
        GROUP BY 1,2,3
        ORDER BY 2,3
    """).df()
    save(add_quality_flag(state_h, "n_events_available"), "fallback_catchup_by_h_state.csv")
    save(nat_h, "fallback_catchup_by_h_national.csv")

    # Fixed-horizon event classifications. A fallback is called persistent at h=1
    # or h=2 only when that exact future horizon exists and receipt is complete
    # through it. Shorter spells are censored, never called persistent.
    fixed = con.execute("""
        SELECT e.event_id,e.state,e.threshold_label,e.entitlement,e.initial_deficit,
               MAX(h) AS max_followup_h,
               MAX(CASE WHEN h=1 THEN 1 ELSE 0 END) AS available_h1,
               MAX(CASE WHEN h=2 THEN 1 ELSE 0 END) AS available_h2,
               MAX(CASE WHEN h=1 AND complete_reporting THEN 1 ELSE 0 END) AS complete_h1,
               MAX(CASE WHEN h=2 AND complete_reporting THEN 1 ELSE 0 END) AS complete_h2,
               MAX(CASE WHEN h=1 AND complete_reporting THEN CAST(caught_up_complete AS INTEGER) END) AS caught_up_h1,
               MAX(CASE WHEN h=2 AND complete_reporting THEN CAST(caught_up_complete AS INTEGER) END) AS caught_up_h2,
               MAX(CASE WHEN h=1 AND complete_reporting THEN cumulative_gap_complete END) AS gap_h1,
               MAX(CASE WHEN h=2 AND complete_reporting THEN cumulative_gap_complete END) AS gap_h2
        FROM fallback_events e
        JOIN event_h2 h USING(event_id)
        GROUP BY 1,2,3,4,5
    """).df()
    save(fixed, "fallback_event_fixed_horizons.csv")

    def fixed_summary(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
        rows = []
        for horizon in (1, 2):
            avail = f"available_h{horizon}"
            complete = f"complete_h{horizon}"
            caught = f"caught_up_h{horizon}"
            gap = f"gap_h{horizon}"
            grouped = [((), df)] if not groups else df.groupby(groups, dropna=False)
            for keys, g in grouped:
                if not isinstance(keys, tuple):
                    keys = (keys,)
                rec = dict(zip(groups, keys))
                g_av = g[g[avail] == 1]
                g_comp = g[g[complete] == 1]
                persistent = g_comp[caught].fillna(0) == 0
                partial = persistent & g_comp[gap].notna() & (g_comp[gap] < g_comp["initial_deficit"])
                rec.update({
                    "horizon": horizon,
                    "n_events_total": len(g),
                    "n_events_with_horizon": len(g_av),
                    "n_complete_reporting_horizon": len(g_comp),
                    "p_caught_up_complete": float(g_comp[caught].mean()) if len(g_comp) else np.nan,
                    "p_persistent_gap_complete": float(persistent.mean()) if len(g_comp) else np.nan,
                    "p_partial_catchup_among_persistent": float(partial[persistent].mean()) if persistent.any() else np.nan,
                    "median_initial_deficit": float(g_comp.initial_deficit.median()) if len(g_comp) else np.nan,
                    "median_gap_complete": float(g_comp[gap].median()) if g_comp[gap].notna().any() else np.nan,
                })
                rows.append(rec)
        return pd.DataFrame(rows)

    state_fixed = fixed_summary(fixed, ["state", "threshold_label", "entitlement"])
    nat_fixed = fixed_summary(fixed, ["threshold_label", "entitlement"])
    save(add_quality_flag(state_fixed, "n_events_with_horizon"), "fallback_fixed_horizon_summary_state.csv")
    save(nat_fixed, "fallback_fixed_horizon_summary_national.csv")

    distinct_states = int(con.execute("SELECT COUNT(DISTINCT state) FROM annual WHERE state IS NOT NULL").fetchone()[0])
    validation = {
        "fallback_events": n_events,
        "annual_distinct_states": distinct_states,
        "states_with_fallback_events": int(fixed.state.nunique()),
        "state_rows_are_not_filtered": True,
        "primary_missing_rule": "complete reporting only",
        "sensitivity_missing_rule": "missing as zero",
        "persistence_requires_fixed_future_horizon": True,
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    lines = [
        "# Cumulative catch-up audit",
        "",
        f"Fiscal fallback events constructed under unchanged entitlement: {n_events:,}.",
        "Primary cumulative catch-up estimates require complete receipt reporting through the stated horizon.",
        "Persistence is assessed only at fixed h=1 or h=2 follow-up; shorter spells are censored.",
        "Missing-as-zero estimates are retained only as sensitivity analysis.",
        "",
        "## National catch-up after fiscal fallback",
    ]
    for _, r in nat_h.sort_values(["entitlement", "h"]).iterrows():
        lines.append(
            f"- {r.threshold_label}, h={int(r.h)}: "
            f"{100*r.p_caught_up_complete:.1f}% caught up cumulatively "
            f"among {int(r.n_complete):,} complete-reporting events."
        )
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    con.close()


if __name__ == "__main__":
    main()
