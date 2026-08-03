from __future__ import annotations

from udise import comprehensive_a0_staged as staged
from udise.low_memory_indicator_builder import (
    create_indicator_tables_low_memory,
    export_school_indicator_direct,
)


staged.create_indicator_tables = create_indicator_tables_low_memory
staged.export_school_indicator_parquet = (
    lambda connection, output_path: export_school_indicator_direct(
        connection,
        str(output_path),
    )
)
staged.THREADS = 1


if __name__ == "__main__":
    raise SystemExit(staged.main())
