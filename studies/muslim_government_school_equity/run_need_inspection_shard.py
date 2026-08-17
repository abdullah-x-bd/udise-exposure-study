from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path

import duckdb

from common import build_panel, write_json, write_rows
from run_need_inspection_memorysafe import _fit, _prepare

OUT_ROOT = Path("studies/muslim_government_school_equity/outputs/need_inspection_shards")

SHARDS = {
    "summary": [
        "next_log_total_visits",
        "next_log_senior_visits",
        "next_any_senior_visits",
    ],
    "academic": [
        "next_log_academic_inspections",
        "next_log_crc_visits",
        "next_any_academic_inspections",
    ],
    "block": [
        "next_log_block_visits",
        "next_any_block_visits",
    ],
    "district": [
        "next_log_district_state_visits",
        "next_any_district_state_visits",
    ],
}


def main() -> None:
    shard = os.environ.get("INSPECTION_SHARD", "").strip().lower()
    if shard not in SHARDS:
        raise RuntimeError(f"INSPECTION_SHARD must be one of {sorted(SHARDS)}, got {shard!r}")

    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    out = OUT_ROOT / shard
    out.mkdir(parents=True, exist_ok=True)

    print(f"SHARD {shard}: outcomes={SHARDS[shard]}", flush=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='5GB'")

    with tempfile.TemporaryDirectory(prefix=f"muslim_equity_inspection_{shard}_") as td:
        root = Path(td)
        panel, reports = build_panel(
            con, repo, token, root / "work", root / "panel",
            teacher=False, facility=True, profile2=True,
        )
        print(f"SHARD {shard}: panel built; preparing estimation sample", flush=True)
        df = _prepare(panel, con)
        mask = (
            (df["is_state_local_government"] == 1)
            & df["need_index"].notna()
            & df["base_muslim"].notna()
        )
        sample = df.loc[mask]
        del mask, df
        gc.collect()
        core = sample.loc[sample["is_core_government"] == 1]

        counts = sample.groupby("academic_year", observed=True).agg(
            rows=("school_id", "size"),
            schools=("school_id", "nunique"),
            mean_need=("need_index", "mean"),
            mean_base_muslim=("base_muslim", "mean"),
            states=("state_cluster", "nunique"),
            districts=("district_code", "nunique"),
        ).reset_index()
        counts.to_csv(out / "sample_counts.csv", index=False)
        print(
            f"SHARD {shard}: sample rows={len(sample):,}; states={sample['state_cluster'].nunique()}; "
            f"districts={sample['district_code'].nunique()}",
            flush=True,
        )

        specs = [
            ("main_1_2_3_6_89_90", "primary", sample, "state", False),
            ("main_1_2_3_6_89_90", "district_cluster", sample, "district", False),
            ("main_1_2_3_6_89_90", "contemporaneous_exposure", sample, "state", True),
            ("core_1_2_3", "government_universe_robustness", core, "state", False),
        ]

        rows: list[dict] = []
        for outcome in SHARDS[shard]:
            for universe, spec, d, cluster, current in specs:
                print(
                    f"FIT START shard={shard} outcome={outcome} spec={spec} rows={len(d):,}",
                    flush=True,
                )
                ans = _fit(d, outcome, cluster, current)
                if ans is None:
                    print(f"FIT SKIP shard={shard} outcome={outcome} spec={spec}", flush=True)
                    continue
                row = {"shard": shard, "universe": universe, "spec": spec, **ans}
                rows.append(row)
                print(
                    f"FIT DONE shard={shard} outcome={outcome} spec={spec} "
                    f"coef={ans['need_x_muslim']:+.6f} p={ans['need_x_muslim_p']:.6g} "
                    f"n={ans['n']:,} clusters={ans['clusters']}",
                    flush=True,
                )
                gc.collect()

        write_rows(out / "models.csv", rows)
        write_json(out / "source_validation.json", reports)
        (out / "DONE.txt").write_text(
            f"Completed shard {shard} with {len(rows)} fitted specifications.\n",
            encoding="utf-8",
        )
        print(f"SHARD {shard}: complete with {len(rows)} fitted specifications", flush=True)

    con.close()


if __name__ == "__main__":
    main()
