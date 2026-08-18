from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import bh_qvalues

EXPERIMENT_ORDER = ["rte", "rte_timing", "rte_crossing", "repair", "need_onset", "need_inspection"]


def _concat(pattern: str, root: Path) -> pd.DataFrame:
    files = sorted(root.rglob(pattern))
    frames = []
    for p in files:
        try:
            d = pd.read_csv(p)
        except Exception:
            continue
        if len(d):
            d["source_file"] = str(p)
            frames.append(d)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="studies/muslim_government_school_equity/outputs/statewise_causal_combined")
    args = ap.parse_args()
    root = Path(args.root)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    primary = _concat("*_primary_tests.csv", root)
    if len(primary):
        primary["p"] = pd.to_numeric(primary["p"], errors="coerce")
        primary["estimate"] = pd.to_numeric(primary["estimate"], errors="coerce")
        primary["support_ok"] = primary["support_ok"].astype(str).str.lower().isin(["true", "1"])
        primary["experiment_global_q"] = np.nan
        for exp, idx in primary.groupby("experiment").groups.items():
            ids = [i for i in idx if bool(primary.loc[i, "support_ok"]) and np.isfinite(primary.loc[i, "p"])]
            if ids:
                q = bh_qvalues(primary.loc[ids, "p"].tolist())
                primary.loc[ids, "experiment_global_q"] = q
        ids = primary.index[primary["support_ok"] & primary["p"].notna()].tolist()
        primary["all_state_experiment_q"] = np.nan
        if ids:
            primary.loc[ids, "all_state_experiment_q"] = bh_qvalues(primary.loc[ids, "p"].tolist())
        primary["negative_fdr05"] = (
            primary["support_ok"] & primary["experiment_global_q"].lt(0.05) & primary["estimate"].lt(0)
        )
        primary["positive_fdr05"] = (
            primary["support_ok"] & primary["experiment_global_q"].lt(0.05) & primary["estimate"].gt(0)
        )
        primary.to_csv(out / "statewise_primary_tests_combined.csv", index=False)

    dist = _concat("distribution_summary.csv", root)
    if len(dist):
        # One artifact copy per state is expected; keep first if a rerun produced duplicates.
        dist = dist.drop_duplicates(subset=["state"], keep="last")
        dist.to_csv(out / "state_distribution_summary.csv", index=False)

    statuses = _concat("*_status.json", root)  # JSON files are not CSV; handled below separately.
    status_rows = []
    import json
    for p in sorted(root.rglob("*_status.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # infer state from adjacent prep_meta if possible
        meta = p.parent / "prep_meta.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8")); rec["state"] = m.get("state")
            except Exception:
                pass
        rec["source_file"] = str(p)
        status_rows.append(rec)
    status = pd.DataFrame(status_rows)
    if len(status): status.to_csv(out / "statewise_execution_status.csv", index=False)

    if len(primary):
        summary = primary.groupby("state", dropna=False).agg(
            supported_primary_tests=("support_ok", "sum"),
            negative_fdr05=("negative_fdr05", "sum"),
            positive_fdr05=("positive_fdr05", "sum"),
        ).reset_index()
        for exp in EXPERIMENT_ORDER:
            d = primary.loc[primary["experiment"].eq(exp)]
            if len(d):
                z = d.groupby("state").agg(
                    **{f"{exp}_supported": ("support_ok", "sum"),
                       f"{exp}_negative_fdr05": ("negative_fdr05", "sum")}
                ).reset_index()
                summary = summary.merge(z, on="state", how="left")
        if len(dist):
            keep = [c for c in ["state", "schools", "students", "muslim_students", "muslim_majority_schools",
                                "share_muslim_students_in_majority_schools", "share_muslim_students_in_75plus_schools"] if c in dist.columns]
            summary = summary.merge(dist[keep], on="state", how="left")
        summary = summary.sort_values(["negative_fdr05", "supported_primary_tests"], ascending=[False, False])
        summary.to_csv(out / "statewise_state_summary.csv", index=False)

        lines = [
            "# Statewise causal stack", "",
            "Within-State inference clusters by district because a State-specific regression has only one State cluster.",
            "Primary tests with fewer than 8 district clusters, fewer than 500 complete observations, or inadequate Muslim-share variation are flagged as unsupported and excluded from FDR families.",
            "Experiment-level BH/FDR is applied across all supported State-specific headline tests in that experiment.", "",
        ]
        supported = primary.loc[primary["support_ok"]].copy()
        sig = supported.loc[supported["experiment_global_q"].lt(0.05)].copy()
        neg = sig.loc[sig["estimate"].lt(0)].copy()
        lines.append(f"- Supported State-specific headline tests: {len(supported):,}")
        lines.append(f"- Experiment-family FDR < .05: {len(sig):,}")
        lines.append(f"- Negative-direction FDR < .05: {len(neg):,}")
        lines.append("")
        if len(neg):
            lines.append("## Negative-direction FDR-significant tests")
            for _, r in neg.sort_values(["experiment", "experiment_global_q", "state"]).head(100).iterrows():
                lines.append(
                    f"- {r['state']} | {r['experiment']} | {r['test_id']}: estimate={r['estimate']:+.4f}, "
                    f"p={r['p']:.4g}, q={r['experiment_global_q']:.4g}, n={int(r['n']) if pd.notna(r.get('n')) else 'NA'}, "
                    f"district clusters={int(r['clusters']) if pd.notna(r.get('clusters')) else 'NA'}"
                )
        (out / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    else:
        (out / "RESULTS.md").write_text("# Statewise causal stack\n\nNo primary-test files were available.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
