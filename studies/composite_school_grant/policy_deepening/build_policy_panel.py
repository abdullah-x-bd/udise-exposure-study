from __future__ import annotations

import json
import os
import runpy
import shutil
from pathlib import Path

import duckdb

OUT = Path("studies/composite_school_grant/outputs/policy_deepening")
WORK = OUT / "_work"


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    lib = runpy.run_path(
        "studies/composite_school_grant/dynamics_panel_builder.py",
        run_name="csg_policy_panel_builder",
    )
    build = lib["build"]
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    panel = build(con, os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"], WORK)
    qpanel = str(panel).replace("'", "''")
    checks = con.execute(f"""
        SELECT COUNT(*) AS n_rows,
               COUNT(DISTINCT academic_year) AS n_years,
               COUNT(DISTINCT state) FILTER(WHERE state IS NOT NULL) AS n_states,
               COUNT(*) FILTER(WHERE enrol IS NOT NULL) AS n_with_enrol,
               COUNT(*) FILTER(WHERE receipt IS NOT NULL) AS n_with_receipt,
               COUNT(*) FILTER(WHERE expenditure IS NOT NULL) AS n_with_expenditure
        FROM read_parquet('{qpanel}')
    """).fetchone()
    manifest = {
        "panel": str(panel),
        "rows": int(checks[0]),
        "years": int(checks[1]),
        "raw_canonical_state_labels": int(checks[2]),
        "with_enrol": int(checks[3]),
        "with_receipt": int(checks[4]),
        "with_expenditure": int(checks[5]),
    }
    if manifest["years"] != 8:
        raise RuntimeError(f"Expected 8 UDISE years, got {manifest['years']}")
    if manifest["with_enrol"] <= 0 or manifest["with_receipt"] <= 0:
        raise RuntimeError(f"Panel coverage check failed: {manifest}")
    (OUT / "panel_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    con.close()


if __name__ == "__main__":
    main()
