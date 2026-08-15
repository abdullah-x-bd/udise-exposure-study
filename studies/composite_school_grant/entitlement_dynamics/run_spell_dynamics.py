from __future__ import annotations

import math
import os
import runpy
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

T = runpy.run_path(
    "studies/composite_school_grant/timing_core/run_timing_core.py",
    run_name="csg_entitlement_spell_lib",
)
YEARS = T["YEARS"]
build = T["build"]
lit = T["lit"]

BROAD = {1, 2, 3, 6, 89, 90}
CYCLES = [
    ("2019-20", "2022-23"),
    ("2020-21", "2023-24"),
    ("2021-22", "2024-25"),
    ("2022-23", "2025-26"),
]
BANDS = [
    (10000, None, None, "baseline_1_30"),
    (25000, 10000, 30, "30_31"),
    (50000, 25000, 100, "100_101"),
    (75000, 50000, 250, "250_251"),
    (100000, 75000, 1000, "1000_1001"),
]
TARGET_TO_LABEL = {x[0]: x[3] for x in BANDS}
LOWER_TARGET = {x[0]: x[1] for x in BANDS}
ENTRY_CUTOFF = {x[0]: x[2] for x in BANDS}
OUT = Path("studies/composite_school_grant/outputs/entitlement_dynamics/spells")


def entitlement_expr(e: str) -> str:
    return (
        f"CASE WHEN {e} BETWEEN 1 AND 30 THEN 10000 "
        f"WHEN {e} BETWEEN 31 AND 100 THEN 25000 "
        f"WHEN {e} BETWEEN 101 AND 250 THEN 50000 "
        f"WHEN {e} BETWEEN 251 AND 1000 THEN 75000 "
        f"WHEN {e}>1000 THEN 100000 END"
    )


def label_expr(target: str = "entitlement") -> str:
    return (
        f"CASE {target} WHEN 10000 THEN 'baseline_1_30' "
        f"WHEN 25000 THEN '30_31' WHEN 50000 THEN '100_101' "
        f"WHEN 75000 THEN '250_251' WHEN 100000 THEN '1000_1001' END"
    )


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def km_curve(spells: pd.DataFrame, event_col: str, group_cols: list[str], min_group: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, summary = [], []
    if spells.empty:
        return pd.DataFrame(), pd.DataFrame()
    for keys, g in spells.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        if len(g) < min_group:
            continue
        base = dict(zip(group_cols, keys))
        last = pd.to_numeric(g["last_age"], errors="coerce").to_numpy(float)
        event = pd.to_numeric(g[event_col], errors="coerce").to_numpy(float)
        max_age = int(np.nanmax(last)) if np.isfinite(last).any() else -1
        surv = 1.0
        curve = []
        for age in range(max_age + 1):
            risk = np.sum((last >= age) & (~np.isfinite(event) | (event >= age)))
            events = np.sum(np.isfinite(event) & (event == age))
            if risk <= 0:
                continue
            hazard = events / risk
            surv *= (1.0 - hazard)
            cif = 1.0 - surv
            censored = np.sum((last == age) & (~np.isfinite(event) | (event > age)))
            rec = {
                **base,
                "age": age,
                "n_risk": int(risk),
                "events": int(events),
                "censored": int(censored),
                "hazard": float(hazard),
                "survival": float(surv),
                "cumulative_incidence": float(cif),
            }
            rows.append(rec)
            curve.append(rec)
        n50 = next((r["age"] for r in curve if r["cumulative_incidence"] >= 0.50), np.nan)
        n80 = next((r["age"] for r in curve if r["cumulative_incidence"] >= 0.80), np.nan)
        n90 = next((r["age"] for r in curve if r["cumulative_incidence"] >= 0.90), np.nan)
        summary.append({
            **base,
            "n_spells": int(len(g)),
            "events_observed": int(np.isfinite(event).sum()),
            "event_share_observed_horizon": float(np.isfinite(event).mean()),
            "km_attainment_end": float(curve[-1]["cumulative_incidence"]) if curve else np.nan,
            "n50": n50,
            "n80": n80,
            "n90": n90,
            "max_followup_age": max_age,
        })
    return pd.DataFrame(rows), pd.DataFrame(summary)


def correlation_table(df: pd.DataFrame, value: str, index: str, column: str, min_pairs: int = 8) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    w = df.pivot_table(index=index, columns=column, values=value, aggfunc="mean")
    cols = list(w.columns)
    out = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            z = w[[a, b]].dropna()
            if len(z) < min_pairs:
                continue
            out.append({
                "metric": value,
                "threshold_a": a,
                "threshold_b": b,
                "n_states": len(z),
                "pearson": float(z[a].corr(z[b], method="pearson")),
                "spearman": float(z[a].corr(z[b], method="spearman")),
            })
    return pd.DataFrame(out)


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    panel_dir = OUT / "_work"
    panel_dir.mkdir(parents=True, exist_ok=True)
    panel = build(con, os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"], panel_dir)

    # A. Correctly aligned entitlement -> reporting cycles.
    parts = []
    for idx, (ay, ry) in enumerate(CYCLES):
        parts.append(f"""
            SELECT {idx} cycle_index, {lit(ay)} assignment_year, {lit(ry)} report_year,
                   a.pseudocode, CAST(a.state AS VARCHAR) state, a.management, a.enrol,
                   {entitlement_expr("a.enrol")} entitlement,
                   f.receipt, f.expenditure
            FROM read_parquet({lit(str(panel))}) a
            LEFT JOIN read_parquet({lit(str(panel))}) f
              ON a.pseudocode=f.pseudocode AND f.academic_year={lit(ry)}
            WHERE a.academic_year={lit(ay)}
              AND a.management IN ({",".join(map(str, sorted(BROAD)))})
              AND a.enrol>=1
        """)
    con.execute("CREATE TEMP TABLE aligned0 AS " + " UNION ALL ".join(parts))
    con.execute(f"""
        CREATE TEMP TABLE aligned AS
        SELECT *,
               {label_expr("entitlement")} threshold_label,
               receipt IS NOT NULL AS receipt_observed,
               CASE WHEN receipt IS NULL THEN NULL ELSE receipt>=entitlement END AS meets_reported,
               COALESCE(receipt,0)>=entitlement AS meets_missing_zero,
               CASE WHEN receipt IS NULL THEN NULL ELSE ABS(receipt-entitlement)<0.5 END AS exact_reported,
               CASE WHEN receipt IS NULL THEN NULL ELSE LEAST(receipt, entitlement*2.0)/entitlement END AS capped_ratio,
               CASE WHEN receipt IS NULL THEN NULL ELSE GREATEST(entitlement-receipt,0)/entitlement END AS shortfall_share
        FROM aligned0
        WHERE entitlement IS NOT NULL
    """)

    con.execute("""
        CREATE TEMP TABLE ord AS
        SELECT *,
          LAG(entitlement) OVER(PARTITION BY pseudocode ORDER BY cycle_index) prev_entitlement,
          LAG(cycle_index) OVER(PARTITION BY pseudocode ORDER BY cycle_index) prev_cycle
        FROM aligned
    """)
    con.execute("""
        CREATE TEMP TABLE marked AS
        SELECT *,
          CASE WHEN prev_cycle=cycle_index-1 AND prev_entitlement=entitlement THEN 0 ELSE 1 END new_spell
        FROM ord
    """)
    con.execute("""
        CREATE TEMP TABLE grouped AS
        SELECT *,
          SUM(new_spell) OVER(PARTITION BY pseudocode ORDER BY cycle_index ROWS UNBOUNDED PRECEDING) spell_no
        FROM marked
    """)
    con.execute("""
        CREATE TEMP TABLE spell_rows AS
        SELECT *,
          cycle_index - MIN(cycle_index) OVER(PARTITION BY pseudocode,spell_no) spell_age,
          MIN(cycle_index) OVER(PARTITION BY pseudocode,spell_no) spell_start_cycle,
          MAX(cycle_index) OVER(PARTITION BY pseudocode,spell_no) spell_end_cycle,
          COUNT(*) OVER(PARTITION BY pseudocode,spell_no) spell_len,
          FIRST_VALUE(prev_entitlement) OVER(
              PARTITION BY pseudocode,spell_no ORDER BY cycle_index
              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          ) entry_prev_entitlement
        FROM grouped
    """)

    spell_level = con.execute("""
        SELECT pseudocode, state, entitlement, threshold_label, spell_no,
               MIN(spell_start_cycle) start_cycle, MAX(spell_end_cycle) end_cycle,
               MAX(spell_age) last_age, MAX(spell_len) spell_len,
               MAX(entry_prev_entitlement) entry_prev_entitlement,
               MIN(CASE WHEN meets_reported THEN spell_age END) first_meet_age_reported,
               MIN(CASE WHEN meets_missing_zero THEN spell_age END) first_meet_age_zero,
               SUM(CASE WHEN meets_reported THEN 1 ELSE 0 END) meet_cycles_reported,
               SUM(CASE WHEN meets_missing_zero THEN 1 ELSE 0 END) meet_cycles_zero,
               SUM(CASE WHEN receipt_observed THEN 1 ELSE 0 END) reported_cycles,
               AVG(CASE WHEN receipt_observed THEN capped_ratio END) mean_capped_ratio,
               AVG(CASE WHEN receipt_observed THEN shortfall_share END) mean_shortfall_share
        FROM spell_rows
        GROUP BY 1,2,3,4,5
    """).df()
    spell_level["lower_entitlement"] = spell_level["entitlement"].map(LOWER_TARGET)
    spell_level["adjacent_entry"] = (
        spell_level["lower_entitlement"].notna()
        & (spell_level["entry_prev_entitlement"] == spell_level["lower_entitlement"])
        & (spell_level["start_cycle"] > 0)
    )
    entrants = spell_level[spell_level["adjacent_entry"]].copy()

    km_nat_rep, lat_nat_rep = km_curve(entrants, "first_meet_age_reported", ["threshold_label"], 1)
    km_state_rep, lat_state_rep = km_curve(entrants, "first_meet_age_reported", ["state", "threshold_label"], 50)
    km_nat_zero, lat_nat_zero = km_curve(entrants, "first_meet_age_zero", ["threshold_label"], 1)
    km_state_zero, lat_state_zero = km_curve(entrants, "first_meet_age_zero", ["state", "threshold_label"], 50)
    for d, mode in [(km_nat_rep, "reported_only"), (km_state_rep, "reported_only"),
                    (km_nat_zero, "missing_as_zero"), (km_state_zero, "missing_as_zero"),
                    (lat_nat_rep, "reported_only"), (lat_state_rep, "reported_only"),
                    (lat_nat_zero, "missing_as_zero"), (lat_state_zero, "missing_as_zero")]:
        if not d.empty:
            d["denominator_mode"] = mode
    save(pd.concat([km_nat_rep, km_nat_zero], ignore_index=True), "aligned_attainment_km_national.csv")
    save(pd.concat([km_state_rep, km_state_zero], ignore_index=True), "aligned_attainment_km_state.csv")
    save(pd.concat([lat_nat_rep, lat_nat_zero], ignore_index=True), "aligned_latency_summary_national.csv")
    save(pd.concat([lat_state_rep, lat_state_zero], ignore_index=True), "aligned_latency_summary_state.csv")

    age_nat = con.execute("""
        SELECT threshold_label, spell_age,
               COUNT(*) n_rows, COUNT(receipt) n_reported,
               AVG(CASE WHEN receipt IS NOT NULL THEN CAST(meets_reported AS DOUBLE) END) p_meets_reported,
               AVG(CAST(meets_missing_zero AS DOUBLE)) p_meets_missing_zero,
               AVG(CASE WHEN receipt IS NOT NULL THEN capped_ratio END) mean_capped_ratio,
               AVG(CASE WHEN receipt IS NOT NULL THEN shortfall_share END) mean_shortfall_share
        FROM spell_rows
        WHERE entry_prev_entitlement IS NOT NULL
          AND ((entitlement=25000 AND entry_prev_entitlement=10000)
            OR (entitlement=50000 AND entry_prev_entitlement=25000)
            OR (entitlement=75000 AND entry_prev_entitlement=50000)
            OR (entitlement=100000 AND entry_prev_entitlement=75000))
        GROUP BY 1,2 ORDER BY 1,2
    """).df()
    age_state = con.execute("""
        SELECT state, threshold_label, spell_age,
               COUNT(*) n_rows, COUNT(receipt) n_reported,
               AVG(CASE WHEN receipt IS NOT NULL THEN CAST(meets_reported AS DOUBLE) END) p_meets_reported,
               AVG(CAST(meets_missing_zero AS DOUBLE)) p_meets_missing_zero
        FROM spell_rows
        WHERE entry_prev_entitlement IS NOT NULL
          AND ((entitlement=25000 AND entry_prev_entitlement=10000)
            OR (entitlement=50000 AND entry_prev_entitlement=25000)
            OR (entitlement=75000 AND entry_prev_entitlement=50000)
            OR (entitlement=100000 AND entry_prev_entitlement=75000))
        GROUP BY 1,2,3 HAVING COUNT(*)>=50 ORDER BY 1,2,3
    """).df()
    save(age_nat, "aligned_current_attainment_by_age_national.csv")
    save(age_state, "aligned_current_attainment_by_age_state.csv")

    # B. Fiscal recovery and fallback while entitlement remains unchanged.
    transitions = con.execute("""
        SELECT a.pseudocode, a.state, a.entitlement, a.threshold_label, a.spell_no,
               a.spell_age age0, b.spell_age age1,
               a.receipt r0, b.receipt r1,
               a.meets_reported m0, b.meets_reported m1,
               a.meets_missing_zero mz0, b.meets_missing_zero mz1
        FROM spell_rows a JOIN spell_rows b
          ON a.pseudocode=b.pseudocode AND a.spell_no=b.spell_no
         AND b.spell_age=a.spell_age+1
    """).df()
    def transition_aggregate(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
        out = []
        for keys, g in df.groupby(groups, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            rec = dict(zip(groups, keys))
            both = g[g["r0"].notna() & g["r1"].notna()]
            met = both[both["m0"] == True]
            below = both[both["m0"] == False]
            metz = g[g["mz0"] == True]
            belowz = g[g["mz0"] == False]
            rec.update({
                "n_pairs": len(g),
                "n_both_reported": len(both),
                "fallback_reported": float((met["m1"] == False).mean()) if len(met) else np.nan,
                "recovery_reported": float((below["m1"] == True).mean()) if len(below) else np.nan,
                "p_meet_both_reported": float(((both["m0"] == True) & (both["m1"] == True)).mean()) if len(both) else np.nan,
                "p_below_both_reported": float(((both["m0"] == False) & (both["m1"] == False)).mean()) if len(both) else np.nan,
                "fallback_missing_zero": float((metz["mz1"] == False).mean()) if len(metz) else np.nan,
                "recovery_missing_zero": float((belowz["mz1"] == True).mean()) if len(belowz) else np.nan,
            })
            out.append(rec)
        return pd.DataFrame(out)

    trans_nat = transition_aggregate(transitions, ["threshold_label", "age0"])
    trans_state = transition_aggregate(transitions, ["state", "threshold_label", "age0"])
    trans_state = trans_state[trans_state["n_pairs"] >= 100].copy()
    save(trans_nat, "fiscal_transition_by_age_national.csv")
    save(trans_state, "fiscal_transition_by_age_state.csv")

    trans_nat_all = transition_aggregate(transitions, ["threshold_label"])
    trans_state_all = transition_aggregate(transitions, ["state", "threshold_label"])
    trans_state_all = trans_state_all[trans_state_all["n_pairs"] >= 100].copy()
    save(trans_nat_all, "fiscal_transition_summary_national.csv")
    save(trans_state_all, "fiscal_transition_summary_state.csv")

    trans_key = transitions.copy()
    trans_key["fallback_rep"] = (
        (trans_key["r0"].notna()) & (trans_key["r1"].notna())
        & (trans_key["m0"] == True) & (trans_key["m1"] == False)
    ).astype(int)
    trans_key["fallback_zero"] = ((trans_key["mz0"] == True) & (trans_key["mz1"] == False)).astype(int)
    fb = trans_key.groupby(["pseudocode", "spell_no"], as_index=False).agg(
        fallback_count_reported=("fallback_rep", "sum"),
        fallback_count_zero=("fallback_zero", "sum"),
    )
    cls = spell_level.merge(fb, on=["pseudocode", "spell_no"], how="left")
    cls[["fallback_count_reported", "fallback_count_zero"]] = cls[
        ["fallback_count_reported", "fallback_count_zero"]
    ].fillna(0)
    cls = cls[cls["spell_len"] >= 2].copy()
    cls["never_attain_reported"] = cls["first_meet_age_reported"].isna()
    cls["delayed_attain_reported"] = cls["first_meet_age_reported"].fillna(0) > 0
    cls["relapser_reported"] = cls["fallback_count_reported"] >= 1
    cls["recurrent_relapser_reported"] = cls["fallback_count_reported"] >= 2
    cls["durable_after_attain_reported"] = cls["first_meet_age_reported"].notna() & ~cls["relapser_reported"]
    cls["never_attain_zero"] = cls["first_meet_age_zero"].isna()
    cls["relapser_zero"] = cls["fallback_count_zero"] >= 1
    cls["recurrent_relapser_zero"] = cls["fallback_count_zero"] >= 2

    def class_agg(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
        vals = [
            "never_attain_reported", "delayed_attain_reported", "relapser_reported",
            "recurrent_relapser_reported", "durable_after_attain_reported",
            "never_attain_zero", "relapser_zero", "recurrent_relapser_zero",
        ]
        g = df.groupby(groups, dropna=False)
        out = g.size().rename("n_spells").reset_index()
        for v in vals:
            x = g[v].mean().rename(v).reset_index()
            out = out.merge(x, on=groups, how="left")
        return out

    cls_nat = class_agg(cls, ["threshold_label"])
    cls_state = class_agg(cls, ["state", "threshold_label"])
    cls_state = cls_state[cls_state["n_spells"] >= 100].copy()
    save(cls_nat, "spell_classification_national.csv")
    save(cls_state, "spell_classification_state.csv")

    # C. Raw annual adjacent-threshold entry cohorts and eligibility fallback.
    # This is descriptive event tracking, not a causal RD.
    year_case = "CASE academic_year " + " ".join(
        f"WHEN {lit(y)} THEN {i}" for i, y in enumerate(YEARS)
    ) + " END"
    con.execute(f"""
        CREATE TEMP TABLE annual AS
        SELECT academic_year, {year_case} year_idx, pseudocode, CAST(state AS VARCHAR) state,
               management, enrol, receipt,
               {entitlement_expr("enrol")} entitlement
        FROM read_parquet({lit(str(panel))})
        WHERE management IN ({",".join(map(str, sorted(BROAD)))}) AND enrol>=1
    """)
    con.execute(f"""
        CREATE TEMP TABLE entries AS
        SELECT b.pseudocode, b.state, b.academic_year entry_year, b.year_idx entry_idx,
               a.entitlement lower_entitlement, b.entitlement entry_entitlement,
               {label_expr("b.entitlement")} threshold_label,
               CASE b.entitlement WHEN 25000 THEN 30 WHEN 50000 THEN 100
                    WHEN 75000 THEN 250 WHEN 100000 THEN 1000 END threshold_end
        FROM annual a JOIN annual b
          ON a.pseudocode=b.pseudocode AND b.year_idx=a.year_idx+1
        WHERE (a.entitlement=10000 AND b.entitlement=25000)
           OR (a.entitlement=25000 AND b.entitlement=50000)
           OR (a.entitlement=50000 AND b.entitlement=75000)
           OR (a.entitlement=75000 AND b.entitlement=100000)
    """)
    tracking = con.execute("""
        SELECT e.pseudocode, e.state, e.entry_year, e.entry_idx, e.threshold_label,
               e.threshold_end, e.entry_entitlement,
               a.academic_year, a.year_idx-e.entry_idx age,
               a.enrol, a.entitlement, a.receipt,
               a.enrol>e.threshold_end AS above_entry_threshold,
               CASE WHEN a.receipt IS NULL THEN NULL ELSE a.receipt>=e.entry_entitlement END AS meets_entry_target_reported,
               COALESCE(a.receipt,0)>=e.entry_entitlement AS meets_entry_target_zero
        FROM entries e JOIN annual a
          ON e.pseudocode=a.pseudocode AND a.year_idx>=e.entry_idx
        ORDER BY e.pseudocode,e.entry_idx,a.year_idx
    """).df()
    if tracking.empty:
        raise RuntimeError("No annual threshold entry events were constructed")

    ev_key = ["pseudocode", "entry_idx", "threshold_label"]
    fallback_age = tracking.loc[~tracking["above_entry_threshold"]].groupby(ev_key)["age"].min().rename("first_fallback_age")
    tr = tracking.merge(fallback_age, on=ev_key, how="left")
    tr["eligible_for_original_target"] = tr["first_fallback_age"].isna() | (tr["age"] < tr["first_fallback_age"])
    before_fb = tr[tr["eligible_for_original_target"]].copy()
    first_att_rep = before_fb.loc[before_fb["meets_entry_target_reported"] == True].groupby(ev_key)["age"].min().rename("first_raw_attain_age_reported")
    first_att_zero = before_fb.loc[before_fb["meets_entry_target_zero"] == True].groupby(ev_key)["age"].min().rename("first_raw_attain_age_zero")
    event_level = tr.groupby(ev_key + ["state", "entry_year", "threshold_end"], as_index=False).agg(
        last_age=("age", "max"),
        first_fallback_age=("first_fallback_age", "min"),
    )
    event_level = event_level.merge(first_att_rep, on=ev_key, how="left").merge(first_att_zero, on=ev_key, how="left")

    elig_rows, elig_sum = [], []
    for groups, min_n, scope in [
        (["threshold_label"], 1, "national"),
        (["state", "threshold_label"], 50, "state"),
    ]:
        for keys, g in event_level.groupby(groups, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            if len(g) < min_n:
                continue
            base = dict(zip(groups, keys))
            max_age = int(g["last_age"].max())
            S = 1.0
            for age in range(max_age + 1):
                last = g["last_age"].to_numpy(float)
                event = g["first_fallback_age"].to_numpy(float)
                risk = np.sum((last >= age) & (~np.isfinite(event) | (event >= age)))
                events = np.sum(np.isfinite(event) & (event == age))
                if risk == 0:
                    continue
                hazard = events / risk
                S *= 1 - hazard
                elig_rows.append({
                    **base, "scope": scope, "age": age, "n_risk": int(risk),
                    "fallback_events": int(events), "fallback_hazard": float(hazard),
                    "eligibility_survival": float(S), "cumulative_fallback": float(1-S),
                })
            ages = [r for r in elig_rows if r.get("scope")==scope and all(r.get(k)==v for k,v in base.items())]
            elig_sum.append({
                **base, "scope": scope, "n_entries": len(g),
                "observed_fallback_share": float(g["first_fallback_age"].notna().mean()),
                "survival_end": float(ages[-1]["eligibility_survival"]) if ages else np.nan,
            })
    elig = pd.DataFrame(elig_rows)
    save(elig[elig["scope"]=="national"], "eligibility_fallback_curve_national.csv")
    save(elig[elig["scope"]=="state"], "eligibility_fallback_curve_state.csv")
    save(pd.DataFrame(elig_sum), "eligibility_fallback_summary.csv")

    # Time to original-target record after entry, censored immediately before first eligibility fallback.
    event_km = event_level.copy()
    event_km["last_age"] = np.where(
        event_km["first_fallback_age"].notna(),
        np.maximum(event_km["first_fallback_age"] - 1, 0),
        event_km["last_age"],
    )
    for mode, ecol in [("reported_only", "first_raw_attain_age_reported"), ("missing_as_zero", "first_raw_attain_age_zero")]:
        kmn, smn = km_curve(event_km, ecol, ["threshold_label"], 1)
        kms, sms = km_curve(event_km, ecol, ["state", "threshold_label"], 50)
        for d in [kmn, smn, kms, sms]:
            if not d.empty:
                d["denominator_mode"] = mode
        save(kmn, f"raw_entry_attainment_km_national_{mode}.csv")
        save(kms, f"raw_entry_attainment_km_state_{mode}.csv")
        save(smn, f"raw_entry_latency_summary_national_{mode}.csv")
        save(sms, f"raw_entry_latency_summary_state_{mode}.csv")

    rates = before_fb.groupby(["threshold_label", "age"], as_index=False).agg(
        n=("pseudocode", "size"),
        n_reported=("receipt", "count"),
        p_meets_reported=("meets_entry_target_reported", "mean"),
        p_meets_missing_zero=("meets_entry_target_zero", "mean"),
        mean_enrol=("enrol", "mean"),
    )
    rates_state = before_fb.groupby(["state", "threshold_label", "age"], as_index=False).agg(
        n=("pseudocode", "size"),
        n_reported=("receipt", "count"),
        p_meets_reported=("meets_entry_target_reported", "mean"),
        p_meets_missing_zero=("meets_entry_target_zero", "mean"),
    )
    rates_state = rates_state[rates_state["n"] >= 50]
    save(rates, "raw_entry_current_attainment_national.csv")
    save(rates_state, "raw_entry_current_attainment_state.csv")

    corrs = []
    corrs.append(correlation_table(trans_state_all, "fallback_reported", "state", "threshold_label"))
    corrs.append(correlation_table(trans_state_all, "recovery_reported", "state", "threshold_label"))
    if not lat_state_rep.empty:
        corrs.append(correlation_table(lat_state_rep, "km_attainment_end", "state", "threshold_label"))
        corrs.append(correlation_table(lat_state_rep, "n50", "state", "threshold_label"))
    corr = pd.concat([x for x in corrs if not x.empty], ignore_index=True) if any(not x.empty for x in corrs) else pd.DataFrame()
    save(corr, "cross_threshold_state_replication_spells.csv")

    if not km_nat_rep.empty:
        fig, ax = plt.subplots(figsize=(9,5))
        for th, g in km_nat_rep.groupby("threshold_label"):
            ax.plot(g["age"], 100*g["cumulative_incidence"], marker="o", label=th)
        ax.set_xlabel("Aligned entitlement cycles since observed adjacent-band entry")
        ax.set_ylabel("Cumulative first recorded attainment, %")
        ax.set_title("Time to first recorded nominal CSG attainment")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "figure_aligned_attainment.png", dpi=180)
        plt.close(fig)

    en = elig[elig["scope"]=="national"]
    if not en.empty:
        fig, ax = plt.subplots(figsize=(9,5))
        for th, g in en.groupby("threshold_label"):
            ax.plot(g["age"], 100*g["eligibility_survival"], marker="o", label=th)
        ax.set_xlabel("Years since crossing into higher entitlement band")
        ax.set_ylabel("Still at or above entry threshold, %")
        ax.set_title("Eligibility survival after crossing a CSG boundary")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "figure_eligibility_survival.png", dpi=180)
        plt.close(fig)

    if not trans_nat_all.empty:
        fig, ax = plt.subplots(figsize=(9,5))
        x = np.arange(len(trans_nat_all))
        ax.bar(x-0.18, 100*trans_nat_all["fallback_reported"], width=0.36, label="Fallback")
        ax.bar(x+0.18, 100*trans_nat_all["recovery_reported"], width=0.36, label="Recovery")
        ax.set_xticks(x, trans_nat_all["threshold_label"])
        ax.set_ylabel("Transition probability, %")
        ax.set_title("Fiscal recovery and fallback under unchanged entitlement")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "figure_fiscal_transitions.png", dpi=180)
        plt.close(fig)

    lines = [
        "# Entitlement spell dynamics audit",
        "",
        "This audit separates three administrative dimensions: attainment, latency, and durability.",
        "All aligned fiscal-spell analyses use the previously reconstructed +3 assignment/report mapping.",
        "Fiscal fallback is only counted while the nominal entitlement is unchanged.",
        "Eligibility fallback is a separate enrolment event: falling back below the threshold after entry.",
        "",
        "## National aligned attainment",
    ]
    if not lat_nat_rep.empty:
        for _, r in lat_nat_rep.sort_values("threshold_label").iterrows():
            lines.append(
                f"- {r.threshold_label}: {int(r.n_spells)} observed adjacent-band entry spells; "
                f"KM attainment by observed horizon {100*r.km_attainment_end:.1f}%; "
                f"N50={r.n50 if pd.notna(r.n50) else 'not reached'}, "
                f"N80={r.n80 if pd.notna(r.n80) else 'not reached'}."
            )
    lines += ["", "## Fiscal durability under unchanged entitlement"]
    for _, r in trans_nat_all.sort_values("threshold_label").iterrows():
        lines.append(
            f"- {r.threshold_label}: fallback {100*r.fallback_reported:.1f}% and recovery "
            f"{100*r.recovery_reported:.1f}% among adjacent aligned cycles with both receipts reported."
        )
    lines += ["", "## Interpretation guardrails",
              "- These spell/event curves are administrative dynamics, not causal treatment effects.",
              "- The separate dynamic RD audit supplies the causal transmission timing diagnostics.",
              "- Receipt refers to the UDISE administrative record and is not independently verified PFMS cash delivery.",
              "- The historical applicability of the <=30 Rs 10,000 band must remain separately verified for older cohorts."]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")

    shutil.rmtree(panel_dir, ignore_errors=True)
    con.close()
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
