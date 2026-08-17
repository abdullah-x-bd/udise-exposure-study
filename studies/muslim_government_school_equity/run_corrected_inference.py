from __future__ import annotations

import importlib
import sys
from pathlib import Path

import duckdb

import common
from cluster_harmonization import state_sql


_ORIG_BUILD_PANEL = common.build_panel


def _harmonized_build_panel(*args, **kwargs):
    panel, reports = _ORIG_BUILD_PANEL(*args, **kwargs)
    panel = Path(panel)
    out = panel.with_name(panel.stem + "_state_lineage.parquet")
    con = args[0] if args and isinstance(args[0], duckdb.DuckDBPyConnection) else duckdb.connect()
    qin = str(panel).replace("'", "''")
    qout = str(out).replace("'", "''")
    state_expr = state_sql("state")
    con.execute(
        f"COPY (SELECT * REPLACE ({state_expr} AS state) FROM read_parquet('{qin}')) "
        f"TO '{qout}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    return out, reports


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"rte", "repair"}:
        raise SystemExit("usage: run_corrected_inference.py [rte|repair]")
    common.build_panel = _harmonized_build_panel
    module_name = {
        "rte": "run_rte_staffing",
        "repair": "run_failure_to_repair",
    }[sys.argv[1]]
    module = importlib.import_module(module_name)
    module.main()


if __name__ == "__main__":
    main()
