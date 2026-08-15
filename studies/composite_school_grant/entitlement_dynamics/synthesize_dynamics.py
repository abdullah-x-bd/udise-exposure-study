from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("INPUT_ROOT","inputs"))
OUT = Path("studies/composite_school_grant/outputs/entitlement_dynamics/final")
OUT.mkdir(parents=True,exist_ok=True)


def gather(name):
    fs=list(ROOT.rglob(name))
    if not fs:
        return pd.DataFrame()
    arr=[]
    for f in fs:
        try:
            d=pd.read_csv(f)
            if len(d):
                arr.append(d)
        except Exception:
            pass
    return pd.concat(arr,ignore_index=True) if arr else pd.DataFrame()


def write(df,name):
    df.to_csv(OUT/name,index=False)


lat = gather("aligned_latency_summary_state.csv")
trans = gather("fiscal_transition_summary_state.csv")
cls = gather("spell_classification_state.csv")
elig = gather("eligibility_fallback_summary.csv")
dyn = gather("transmission_latency_summary_state.csv")
rep_spell = gather("cross_threshold_state_replication_spells.csv")
rep_dyn = gather("cross_threshold_state_replication_transmission.csv")
lat_nat = gather("aligned_latency_summary_national.csv")
trans_nat = gather("fiscal_transition_summary_national.csv")
dyn_nat = gather("transmission_latency_summary_national.csv")

required = {
    "aligned_latency_summary_state.csv":lat,
    "fiscal_transition_summary_state.csv":trans,
    "spell_classification_state.csv":cls,
    "transmission_latency_summary_state.csv":dyn,
}
missing=[k for k,v in required.items() if v.empty]
if missing:
    raise RuntimeError("Missing required audit inputs: "+", ".join(missing))

latp=lat[lat["denominator_mode"]=="reported_only"].copy()
dash=latp.merge(trans,on=["state","threshold_label"],how="outer",suffixes=("","_dur"))
dash=dash.merge(cls,on=["state","threshold_label"],how="left",suffixes=("","_class"))
dash=dash.merge(dyn,on=["state","threshold_label"],how="left",suffixes=("","_trans"))
write(dash,"state_threshold_administrative_dashboard.csv")

n80_col = "n80_trans" if "n80_trans" in dash.columns else "n80"
state_summary=dash.groupby("state",as_index=False).agg(
    thresholds_observed=("threshold_label","nunique"),
    mean_attainment_horizon=("km_attainment_end","mean"),
    mean_fallback=("fallback_reported","mean"),
    mean_recovery=("recovery_reported","mean"),
    mean_never_attain=("never_attain_reported","mean"),
    mean_transmission_peak_pp=("peak_pp","mean"),
    mean_transmission_n80=(n80_col,"mean"),
)
write(state_summary,"state_administrative_summary.csv")

rep=[]
if not rep_spell.empty:
    x=rep_spell.copy();x["family"]="spell_dynamics";rep.append(x)
if not rep_dyn.empty:
    x=rep_dyn.copy();x["family"]="causal_transmission";rep.append(x)
repall=pd.concat(rep,ignore_index=True) if rep else pd.DataFrame()
write(repall,"cross_threshold_state_replication_all.csv")

head=[]
for _,r in dyn_nat.iterrows():
    head.append({
        "family":"causal_transmission","threshold":r.threshold_label,
        "metric":"peak_formula_response_pp","value":r.peak_pp,
        "secondary":f"peak lag +{int(r.peak_lag)}; N80={r.n80 if pd.notna(r.n80) else 'NA'}"
    })
for _,r in lat_nat[lat_nat["denominator_mode"]=="reported_only"].iterrows():
    head.append({
        "family":"attainment_latency","threshold":r.threshold_label,
        "metric":"km_attainment_by_horizon_pct","value":100*r.km_attainment_end,
        "secondary":f"N50={r.n50 if pd.notna(r.n50) else 'NA'}; N80={r.n80 if pd.notna(r.n80) else 'NA'}"
    })
for _,r in trans_nat.iterrows():
    head.append({
        "family":"durability","threshold":r.threshold_label,
        "metric":"fallback_pct","value":100*r.fallback_reported,
        "secondary":f"recovery={100*r.recovery_reported:.1f}%"
    })
head=pd.DataFrame(head)
write(head,"headline_metrics.csv")

lines=[
    "# Administrative Dynamics of the Composite School Grant",
    "",
    "## Core framework",
    "",
    "This audit evaluates three distinct dimensions of administrative realization:",
    "",
    "1. **Attainment**: whether a continuously entitled school ever records at least its nominal grant.",
    "2. **Latency**: how many aligned entitlement cycles pass before first recorded attainment.",
    "3. **Durability**: whether attainment persists, measured by fallback while entitlement remains unchanged.",
    "",
    "A fourth diagnostic, **causal transmission latency**, is estimated separately from unconditional local-linear threshold curves. This separation matters because conditioning an RD on future enrolment survival would condition on a post-assignment variable.",
    "",
    "## National attainment and durability",
]
lpn=lat_nat[lat_nat["denominator_mode"]=="reported_only"]
for _,r in lpn.sort_values("threshold_label").iterrows():
    lines.append(
        f"- **{r.threshold_label}**: observed-entry KM attainment by the available horizon {100*r.km_attainment_end:.1f}%; "
        f"N50 {r.n50 if pd.notna(r.n50) else 'not reached'}; N80 {r.n80 if pd.notna(r.n80) else 'not reached'}."
    )
for _,r in trans_nat.sort_values("threshold_label").iterrows():
    lines.append(
        f"- **{r.threshold_label} durability**: among consecutive aligned cycles with the same entitlement and both receipts reported, "
        f"{100*r.fallback_reported:.1f}% of schools that met the target fall below it in the next cycle; "
        f"{100*r.recovery_reported:.1f}% of schools below target recover in the next cycle."
    )

lines += ["","## Causal transmission timing"]
for _,r in dyn_nat.sort_values("threshold_label").iterrows():
    lines.append(
        f"- **{r.threshold_label}**: pooled formula signal peaks at lag +{int(r.peak_lag)} with {r.peak_pp:+.1f} pp; "
        f"transmission N80 is {r.n80 if pd.notna(r.n80) else 'not reached/undefined'}."
    )

if not repall.empty:
    lines += ["","## Cross-threshold state replication"]
    best=repall.dropna(subset=["pearson"]).sort_values("pearson",ascending=False).head(8)
    for _,r in best.iterrows():
        lines.append(
            f"- {r.family}, {r.metric}, {r.threshold_a} vs {r.threshold_b}: Pearson {r.pearson:.2f}, "
            f"Spearman {r.spearman:.2f}, {int(r.n_states)} states."
        )

lines += [
    "",
    "## Policy interpretation",
    "",
    "The policy question is not whether every deviation in UDISE proves non-payment. It does not. The question is whether a national entitlement can be traced into a timely and durable school-level administrative realization.",
    "",
    "The most policy-relevant failure mode is therefore a reconciliation gap: if a school remains entitled but the record is late, repeatedly below target, or repeatedly falls back after attainment, the current data do not identify whether the reason is delayed release, accounting treatment, balances, reporting practice, or actual fiscal shortfall.",
    "",
    "## Guardrails",
    "",
    "- UDISE grant receipt is an administrative report, not an independently audited PFMS cash ledger.",
    "- Spell dynamics are descriptive administrative performance measures. They are not causal effects of crossing a threshold.",
    "- Causal transmission diagnostics are estimated without conditioning on future entitlement survival.",
    "- The 30/31 historical band retains a cohort-specific validity caveat until its historical applicability is independently documented.",
]
(OUT/"DYNAMIC_ADMINISTRATIVE_AUDIT.md").write_text("\n".join(lines),encoding="utf-8")
print("\n".join(lines),flush=True)
