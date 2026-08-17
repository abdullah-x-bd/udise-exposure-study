from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from common import bh_qvalues


def main() -> None:
    root = Path(os.environ.get("INSPECTION_SHARD_DOWNLOAD", "inspection_shards_download"))
    out = Path("studies/muslim_government_school_equity/outputs/need_inspection_sharded_final")
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(root.rglob("models.csv"))
    if len(files) != 4:
        raise RuntimeError(f"Expected 4 shard model files under {root}, found {len(files)}: {files}")

    frames = [pd.read_csv(p) for p in files]
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise RuntimeError("No inspection models were produced")

    primary = (df["spec"] == "primary") & (df["universe"] == "main_1_2_3_6_89_90")
    if int(primary.sum()) != 10:
        raise RuntimeError(f"Expected 10 primary outcomes, found {int(primary.sum())}")

    qvals = bh_qvalues(df.loc[primary, "need_x_muslim_p"].astype(float).tolist())
    df["need_x_muslim_q"] = float("nan")
    df.loc[primary, "need_x_muslim_q"] = qvals
    df = df.sort_values(["outcome", "spec", "universe"], kind="stable").reset_index(drop=True)
    df.to_csv(out / "need_inspection_models.csv", index=False)

    prim = df.loc[primary].copy().sort_values("outcome")
    lines = [
        "# Need-to-inspection national experiment, sharded corrected inference",
        "",
        "The key coefficient is documented current need x frozen baseline Muslim share. School and district-by-year fixed effects are absorbed. State-clustered inference uses harmonized State lineages. Following-year outcomes are censored when the school leaves the State/local-government universe.",
        "",
    ]
    for _, r in prim.iterrows():
        lines.append(
            f"- {r['outcome']}: need x Muslim = {r['need_x_muslim']:+.4f} "
            f"(95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), "
            f"p={r['need_x_muslim_p']:.4g}, q={r['need_x_muslim_q']:.4g}, "
            f"n={int(r['n']):,}, clusters={int(r['clusters'])}"
        )
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
