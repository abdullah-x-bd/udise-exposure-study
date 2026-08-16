from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
spec_pv = importlib.util.spec_from_file_location("panel_views", ROOT / "panel_views.py")
pv = importlib.util.module_from_spec(spec_pv)
assert spec_pv.loader is not None
spec_pv.loader.exec_module(pv)

spec_logic = importlib.util.spec_from_file_location("logic", ROOT / "logic.py")
logic = importlib.util.module_from_spec(spec_logic)
assert spec_logic.loader is not None
spec_logic.loader.exec_module(logic)

OUT = Path("studies/composite_school_grant/outputs/policy_deepening/threshold_churn")


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def quality(n: pd.Series) -> np.ndarray:
    return np.select([n < 30, n < 100], ["very_small", "small"], default="standard")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = pv.open_connection()

    con.execute("""
        CREATE TEMP TABLE seq0 AS
        SELECT *,
               LAG(year_idx) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev_year_idx,
               LAG(enrol) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev_enrol,
               LAG(entitlement) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev_entitlement
        FROM annual
    """)
    prev_boundary = (
        "CASE prev_entitlement WHEN 25000 THEN 30 WHEN 50000 THEN 100 "
        "WHEN 75000 THEN 250 WHEN 100000 THEN 1000 END"
    )
    avg_ent = logic.entitlement_sql("(enrol+prev_enrol)/2.0", 10_000)
    con.execute(f"""
        CREATE TEMP TABLE cf AS
        SELECT *,
               prev_year_idx=year_idx-1 AS adjacent,
               entitlement AS actual_cf,
               CASE WHEN prev_year_idx=year_idx-1 THEN {avg_ent} ELSE entitlement END AS avg2_cf,
               CASE WHEN prev_year_idx=year_idx-1 AND entitlement<prev_entitlement
                    THEN prev_entitlement ELSE entitlement END AS hold1_cf,
               CASE WHEN prev_year_idx=year_idx-1 AND entitlement<prev_entitlement
                          AND {prev_boundary} IS NOT NULL
                          AND enrol>=({prev_boundary})-5
                    THEN prev_entitlement ELSE entitlement END AS near5_cf,
               CASE WHEN prev_year_idx=year_idx-1 AND entitlement<prev_entitlement
                          AND {prev_boundary} IS NOT NULL
                          AND enrol>=({prev_boundary})-10
                    THEN prev_entitlement ELSE entitlement END AS near10_cf,
               CASE WHEN prev_year_idx=year_idx-1 AND entitlement<prev_entitlement
                          AND {prev_boundary} IS NOT NULL
                          AND enrol>=({prev_boundary})-20
                    THEN prev_entitlement ELSE entitlement END AS near20_cf
        FROM seq0
    """)
    schedules = ["actual_cf", "avg2_cf", "hold1_cf", "near5_cf", "near10_cf", "near20_cf"]
    lag_terms = ",\n".join(
        f"LAG({s}) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev_{s}, "
        f"LAG({s},2) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev2_{s}"
        for s in schedules
    )
    con.execute(f"""
        CREATE TEMP TABLE cf_lag AS
        SELECT *,
               LAG(year_idx,2) OVER(PARTITION BY pseudocode ORDER BY year_idx) AS prev2_year_idx,
               {lag_terms}
        FROM cf
    """)

    school = con.execute("""
        SELECT pseudocode, ANY_VALUE(state) AS state,
               COUNT(*) AS n_observed_years,
               SUM(CASE WHEN adjacent AND entitlement<>prev_entitlement THEN 1 ELSE 0 END) AS n_band_changes,
               SUM(CASE WHEN adjacent AND entitlement>prev_entitlement THEN 1 ELSE 0 END) AS n_up_changes,
               SUM(CASE WHEN adjacent AND entitlement<prev_entitlement THEN 1 ELSE 0 END) AS n_down_changes
        FROM cf
        GROUP BY 1
    """).df()
    ping = con.execute("""
        SELECT pseudocode,
               SUM(CASE WHEN prev2_year_idx=year_idx-2
                             AND prev_actual_cf<>actual_cf
                             AND prev2_actual_cf=actual_cf
                        THEN 1 ELSE 0 END) AS n_pingpong
        FROM cf_lag
        GROUP BY 1
    """).df()
    school = school.merge(ping, on="pseudocode", how="left").fillna({"n_pingpong": 0})

    def school_summary(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
        rows = []
        grouped = [((), df)] if not groups else df.groupby(groups, dropna=False)
        for keys, g in grouped:
            if not isinstance(keys, tuple):
                keys = (keys,)
            rec = dict(zip(groups, keys))
            rec.update({
                "n_schools": len(g),
                "p_any_band_change": float((g.n_band_changes >= 1).mean()),
                "p_two_plus_band_changes": float((g.n_band_changes >= 2).mean()),
                "p_three_plus_band_changes": float((g.n_band_changes >= 3).mean()),
                "p_any_pingpong": float((g.n_pingpong >= 1).mean()),
                "mean_band_changes": float(g.n_band_changes.mean()),
                "mean_down_changes": float(g.n_down_changes.mean()),
            })
            rows.append(rec)
        return pd.DataFrame(rows)

    state_school = school_summary(school, ["state"])
    state_school["quality_flag"] = quality(state_school["n_schools"])
    save(state_school, "school_churn_state.csv")
    save(school_summary(school, []), "school_churn_national.csv")

    crossing_parts = []
    for th in logic.THRESHOLDS:
        caution = 1 if th == 30 else 0
        crossing_parts.append(f"""
            SELECT pseudocode,state,academic_year,year_idx,{th} AS threshold_end,
                   'up' AS direction,
                   enrol-{th} AS distance_after_crossing,
                   {caution} AS historical_rule_caution
            FROM cf
            WHERE adjacent AND prev_enrol<={th} AND enrol>{th}
        """)
        crossing_parts.append(f"""
            SELECT pseudocode,state,academic_year,year_idx,{th} AS threshold_end,
                   'down' AS direction,
                   {th}-enrol AS distance_after_crossing,
                   {caution} AS historical_rule_caution
            FROM cf
            WHERE adjacent AND prev_enrol>{th} AND enrol<={th}
        """)
    con.execute("CREATE TEMP TABLE crossings0 AS " + " UNION ALL ".join(crossing_parts))
    con.execute("""
        CREATE TEMP TABLE crossings AS
        SELECT *, ROW_NUMBER() OVER() AS event_id
        FROM crossings0
    """)
    con.execute("""
        CREATE TEMP TABLE crossing_follow AS
        SELECT e.*,
               MIN(CASE
                     WHEN e.direction='down' AND a.enrol>e.threshold_end THEN a.year_idx-e.year_idx
                     WHEN e.direction='up' AND a.enrol<=e.threshold_end THEN a.year_idx-e.year_idx
                   END) AS reverse_cross_lag
        FROM crossings e
        LEFT JOIN annual a
          ON e.pseudocode=a.pseudocode AND a.year_idx>e.year_idx
        GROUP BY ALL
    """)

    cross_state = con.execute("""
        SELECT state,threshold_end,direction,historical_rule_caution,
               COUNT(*) AS n_crossings,
               AVG(CAST(distance_after_crossing<=5 AS DOUBLE)) AS p_within_5,
               AVG(CAST(distance_after_crossing<=10 AS DOUBLE)) AS p_within_10,
               AVG(CAST(distance_after_crossing<=20 AS DOUBLE)) AS p_within_20,
               MEDIAN(distance_after_crossing) AS median_distance,
               AVG(CAST(reverse_cross_lag<=1 AS DOUBLE)) AS p_reverse_within_1y,
               AVG(CAST(reverse_cross_lag<=2 AS DOUBLE)) AS p_reverse_within_2y,
               AVG(CAST(reverse_cross_lag<=3 AS DOUBLE)) AS p_reverse_within_3y
        FROM crossing_follow
        GROUP BY 1,2,3,4
        ORDER BY 1,2,3
    """).df()
    cross_nat = con.execute("""
        SELECT threshold_end,direction,historical_rule_caution,
               COUNT(*) AS n_crossings,
               AVG(CAST(distance_after_crossing<=5 AS DOUBLE)) AS p_within_5,
               AVG(CAST(distance_after_crossing<=10 AS DOUBLE)) AS p_within_10,
               AVG(CAST(distance_after_crossing<=20 AS DOUBLE)) AS p_within_20,
               MEDIAN(distance_after_crossing) AS median_distance,
               AVG(CAST(reverse_cross_lag<=1 AS DOUBLE)) AS p_reverse_within_1y,
               AVG(CAST(reverse_cross_lag<=2 AS DOUBLE)) AS p_reverse_within_2y,
               AVG(CAST(reverse_cross_lag<=3 AS DOUBLE)) AS p_reverse_within_3y
        FROM crossing_follow
        GROUP BY 1,2,3
        ORDER BY 1,2
    """).df()
    cross_state["quality_flag"] = quality(cross_state["n_crossings"])
    save(cross_state, "threshold_crossings_state.csv")
    save(cross_nat, "threshold_crossings_national.csv")

    cf_state_rows = []
    cf_nat_rows = []
    down_state_rows = []
    down_nat_rows = []
    for s in schedules:
        prev = f"prev_{s}"
        prev2 = f"prev2_{s}"
        state = con.execute(f"""
            SELECT state,
                   COUNT(*) AS n_school_years,
                   SUM({s}) AS nominal_total,
                   SUM(CASE WHEN adjacent AND {s}<>{prev} THEN 1 ELSE 0 END) AS n_band_changes,
                   SUM(CASE WHEN adjacent THEN ABS({s}-{prev}) ELSE 0 END) AS absolute_nominal_volatility,
                   SUM(CASE WHEN prev2_year_idx=year_idx-2
                                  AND {prev}<>{s} AND {prev2}={s}
                            THEN 1 ELSE 0 END) AS n_pingpong
            FROM cf_lag
            GROUP BY 1
        """).df()
        state["schedule"] = s.replace("_cf", "")
        cf_state_rows.append(state)
        nat = con.execute(f"""
            SELECT COUNT(*) AS n_school_years,
                   SUM({s}) AS nominal_total,
                   SUM(CASE WHEN adjacent AND {s}<>{prev} THEN 1 ELSE 0 END) AS n_band_changes,
                   SUM(CASE WHEN adjacent THEN ABS({s}-{prev}) ELSE 0 END) AS absolute_nominal_volatility,
                   SUM(CASE WHEN prev2_year_idx=year_idx-2
                                  AND {prev}<>{s} AND {prev2}={s}
                            THEN 1 ELSE 0 END) AS n_pingpong
            FROM cf_lag
        """).df()
        nat["schedule"] = s.replace("_cf", "")
        cf_nat_rows.append(nat)

        if s != "actual_cf":
            ds = con.execute(f"""
                SELECT state,
                       COUNT(*) FILTER(WHERE adjacent AND entitlement<prev_entitlement) AS n_actual_down_changes,
                       COUNT(*) FILTER(WHERE adjacent AND entitlement<prev_entitlement
                                             AND {s}=prev_entitlement) AS n_down_changes_delayed
                FROM cf
                GROUP BY 1
            """).df()
            ds["schedule"] = s.replace("_cf", "")
            down_state_rows.append(ds)
            dn = con.execute(f"""
                SELECT COUNT(*) FILTER(WHERE adjacent AND entitlement<prev_entitlement) AS n_actual_down_changes,
                       COUNT(*) FILTER(WHERE adjacent AND entitlement<prev_entitlement
                                             AND {s}=prev_entitlement) AS n_down_changes_delayed
                FROM cf
            """).df()
            dn["schedule"] = s.replace("_cf", "")
            down_nat_rows.append(dn)

    cf_state = pd.concat(cf_state_rows, ignore_index=True)
    cf_nat = pd.concat(cf_nat_rows, ignore_index=True)
    actual_state_cost = cf_state[cf_state.schedule == "actual"].set_index("state")["nominal_total"]
    cf_state["incremental_nominal_cost_vs_actual"] = cf_state.apply(
        lambda r: r.nominal_total - actual_state_cost.get(r.state, np.nan), axis=1
    )
    actual_nat_cost = float(cf_nat.loc[cf_nat.schedule == "actual", "nominal_total"].iloc[0])
    cf_nat["incremental_nominal_cost_vs_actual"] = cf_nat["nominal_total"] - actual_nat_cost
    cf_state["band_changes_reduction_vs_actual"] = cf_state.apply(
        lambda r: np.nan if r.schedule == "actual" else
        1 - r.n_band_changes / cf_state.loc[(cf_state.state == r.state) & (cf_state.schedule == "actual"), "n_band_changes"].iloc[0]
        if cf_state.loc[(cf_state.state == r.state) & (cf_state.schedule == "actual"), "n_band_changes"].iloc[0] > 0
        else np.nan,
        axis=1,
    )
    actual_nat_changes = float(cf_nat.loc[cf_nat.schedule == "actual", "n_band_changes"].iloc[0])
    cf_nat["band_changes_reduction_vs_actual"] = np.where(
        cf_nat.schedule == "actual",
        np.nan,
        1 - cf_nat.n_band_changes / actual_nat_changes if actual_nat_changes > 0 else np.nan,
    )
    save(cf_state, "counterfactual_formula_state.csv")
    save(cf_nat, "counterfactual_formula_national.csv")

    down_state = pd.concat(down_state_rows, ignore_index=True)
    down_nat = pd.concat(down_nat_rows, ignore_index=True)
    down_state["p_actual_down_changes_delayed"] = np.where(
        down_state.n_actual_down_changes > 0,
        down_state.n_down_changes_delayed / down_state.n_actual_down_changes,
        np.nan,
    )
    down_nat["p_actual_down_changes_delayed"] = np.where(
        down_nat.n_actual_down_changes > 0,
        down_nat.n_down_changes_delayed / down_nat.n_actual_down_changes,
        np.nan,
    )
    save(down_state, "counterfactual_downcross_state.csv")
    save(down_nat, "counterfactual_downcross_national.csv")

    validation = {
        "distinct_states": int(con.execute("SELECT COUNT(DISTINCT state) FROM annual WHERE state IS NOT NULL").fetchone()[0]),
        "crossings": int(con.execute("SELECT COUNT(*) FROM crossings").fetchone()[0]),
        "schools": int(len(school)),
        "counterfactual_schedules": [s.replace("_cf", "") for s in schedules],
        "thirty_boundary_historical_caution_preserved": bool((cross_nat.loc[cross_nat.threshold_end == 30, "historical_rule_caution"] == 1).all()),
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    lines = [
        "# Threshold churn and smoothing counterfactuals",
        "",
        f"Schools observed: {len(school):,}.",
        f"Threshold crossing events across all four boundaries: {validation['crossings']:,}.",
        "",
        "## National current-rule churn",
    ]
    nrow = school_summary(school, []).iloc[0]
    lines.append(f"- Any band change: {100*nrow.p_any_band_change:.1f}% of schools.")
    lines.append(f"- Two or more band changes: {100*nrow.p_two_plus_band_changes:.1f}%.")
    lines.append(f"- At least one A-B-A ping-pong: {100*nrow.p_any_pingpong:.1f}%.")
    lines += ["", "## Counterfactuals"]
    for _, r in cf_nat.iterrows():
        lines.append(
            f"- {r.schedule}: {int(r.n_band_changes):,} band changes; "
            f"nominal cost difference versus actual Rs {r.incremental_nominal_cost_vs_actual:,.0f}."
        )
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    con.close()


if __name__ == "__main__":
    main()
