from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from common import bh_qvalues

OUT = Path("studies/muslim_government_school_equity/outputs/need_inspection_final")


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: combine_need_inspection_pyhdfe.py PRIMARY_DIR CURRENT_DIR CORE_DIR")
    primary_dir, current_dir, core_dir = map(Path, sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)

    frames = []
    for d in (primary_dir, current_dir, core_dir):
        p = d / "models.csv"
        if not p.exists():
            raise RuntimeError(f"missing models file: {p}")
        frames.append(pd.read_csv(p))
    models = pd.concat(frames, ignore_index=True, sort=False)

    primary_mask = models["spec"].eq("primary") & models["universe"].eq("main_1_2_3_6_89_90")
    pvals = pd.to_numeric(models.loc[primary_mask, "need_x_muslim_p"], errors="coerce").to_numpy(float)
    qvals = bh_qvalues(pvals)
    models["need_x_muslim_q"] = np.nan
    models.loc[primary_mask, "need_x_muslim_q"] = qvals
    models.to_csv(OUT / "need_inspection_models.csv", index=False)

    for name in ("sample_counts.csv", "five_pp_high_need_response.csv", "source_validation.json"):
        src = primary_dir / name
        if src.exists():
            shutil.copy2(src, OUT / name)

    engine = {
        "engine": "pyhdfe 0.2.0",
        "residualize_method": "sw",
        "fixed_effects": ["school", "district_by_year"],
        "primary_cluster": "stable State lineage",
        "primary_family_size": int(primary_mask.sum()),
        "families": {},
    }
    for label, d in (("primary", primary_dir), ("current", current_dir), ("core", core_dir)):
        p = d / "engine.json"
        if p.exists():
            engine["families"][label] = json.loads(p.read_text(encoding="utf-8"))
    (OUT / "engine.json").write_text(json.dumps(engine, indent=2), encoding="utf-8")

    primary = models.loc[primary_mask].copy()
    primary = primary.sort_values("outcome")
    lines = [
        "# Need-to-inspection national experiment, final corrected inference",
        "",
        "Primary inference uses stable State-lineage clusters and PyHDFE Somaini-Wolak absorption for school and district-by-year fixed effects.",
        "The ten primary outcomes are corrected jointly using Benjamini-Hochberg FDR.",
        "",
    ]
    for _, r in primary.iterrows():
        lines.append(
            f"- {r['outcome']}: need x Muslim = {r['need_x_muslim']:+.4f} "
            f"(95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), "
            f"p={r['need_x_muslim_p']:.4g}, q={r['need_x_muslim_q']:.4g}, "
            f"n={int(r['n']):,}, clusters={int(r['clusters'])}"
        )
    lines += ["", "## Robustness availability", ""]
    for outcome in primary["outcome"]:
        sub = models.loc[models["outcome"].eq(outcome)]
        specs = ", ".join(sorted(sub["spec"].dropna().astype(str).unique()))
        lines.append(f"- {outcome}: {specs}")
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
