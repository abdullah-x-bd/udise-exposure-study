from __future__ import annotations

import runpy
import shutil
from pathlib import Path

import duckdb


def main() -> None:
    panel = Path("studies/composite_school_grant/outputs/panel/school_year_panel.parquet")
    backup = panel.with_name("school_year_panel_all_managements.parquet")
    if not panel.exists():
        raise FileNotFoundError(panel)
    if backup.exists():
        backup.unlink()
    panel.rename(backup)
    con = duckdb.connect()
    try:
        # Composite School Grant under Samagra Shiksha is a government-school grant.
        # UDISE management codes 1, 2 and 3 correspond to Department of Education,
        # Tribal/Social Welfare and Local Body government schools. Filtering the entire
        # school-year panel ensures both assignment-year and outcome-year observations
        # are government managed before the original RD code forms longitudinal pairs.
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{backup.as_posix()}') WHERE management IN (1,2,3)) "
            f"TO '{panel.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        n_all = con.execute(f"SELECT COUNT(*) FROM read_parquet('{backup.as_posix()}')").fetchone()[0]
        n_gov = con.execute(f"SELECT COUNT(*) FROM read_parquet('{panel.as_posix()}')").fetchone()[0]
        print(f"RD SAMPLE FILTER: all school-years={n_all:,}; government school-years={n_gov:,}", flush=True)
        runpy.run_path("studies/composite_school_grant/scripts/05_rd_analysis.py", run_name="__main__")
    finally:
        con.close()
        if panel.exists():
            panel.unlink()
        backup.rename(panel)


if __name__ == "__main__":
    main()
