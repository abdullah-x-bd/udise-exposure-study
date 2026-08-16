from __future__ import annotations

import json
import runpy
import shutil
import tempfile
from pathlib import Path

T = runpy.run_path(
    "studies/composite_school_grant/timing_core/run_timing_core.py",
    run_name="csg_dynamics_panel_helpers",
)

YEARS = T["YEARS"]
extract = T["extract"]
src = T["src"]
cols = T["cols"]
qid = T["qid"]
lit = T["lit"]
ref = T["ref"]
nref = T["nref"]
ident = T["ident"]
efilt = T["efilt"]
esum = T["esum"]


def build(con, repo: str, tok: str, out: Path) -> Path:
    """Build the annual CSG panel while preserving and canonicalizing State/UT names.

    The older timing-core builder used nref() on profile_1.state. Because state is a
    text field (for example, 'Uttar Pradesh'), nref() coerced it to numeric and
    silently produced NULL. This builder deliberately uses ref() + VARCHAR instead.

    State labels also change capitalization and separator style across UDISE vintages.
    We therefore canonicalize case, whitespace, and AND/& spelling before any
    state-by-year pooling. Genuine historical State/UT changes remain distinct.
    """
    paths = []
    manifest = []
    with tempfile.TemporaryDirectory(prefix="csg_dynamics_panel_") as td:
        root = Path(td)
        for year in YEARS:
            print("BUILD", year, flush=True)
            en = src(extract(repo, tok, year, "enrolment_1", root))
            p1 = src(extract(repo, tok, year, "profile_1", root))
            p2 = src(extract(repo, tok, year, "profile_2", root))
            ec, pc, gc = cols(con, en), cols(con, p1), cols(con, p2)
            ei, pi, gi = ident(ec), ident(pc), ident(gc)
            filt = efilt(con, en, ec)
            e12 = esum(ec, 12)
            e8 = esum(ec, 8)
            state_expr = ref(pc, "state", "a") or "NULL"
            state_canonical = (
                f"REPLACE(REGEXP_REPLACE(UPPER(TRIM(CAST({state_expr} AS VARCHAR))), "
                "'\\s+', ' ', 'g'), ' AND ', ' & ')"
            )

            q = out / "year" / f"{year}.parquet"
            q.parent.mkdir(parents=True, exist_ok=True)
            con.execute(f"""
                COPY (
                    WITH e AS (
                        SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,
                               SUM({e12}) enrol,
                               SUM({e8}) enrol18
                        FROM {en}
                        WHERE {filt}
                        GROUP BY 1
                    )
                    SELECT {lit(year)} academic_year,
                           CAST(a.{qid(pi)} AS VARCHAR) pseudocode,
                           {state_canonical} state,
                           {nref(pc, 'managment', 'a')} management,
                           e.enrol,
                           e.enrol18,
                           {nref(gc, 'grants_receipt', 'g')} receipt,
                           {nref(gc, 'grants_expenditure', 'g')} expenditure
                    FROM {p1} a
                    LEFT JOIN {p2} g
                      ON CAST(a.{qid(pi)} AS VARCHAR)=CAST(g.{qid(gi)} AS VARCHAR)
                    LEFT JOIN e
                      ON CAST(a.{qid(pi)} AS VARCHAR)=e.pseudocode
                ) TO {lit(str(q))} (FORMAT PARQUET, COMPRESSION ZSTD)
            """)
            r = con.execute(f"""
                SELECT COUNT(*) AS n_rows,
                       COUNT(*) FILTER(WHERE enrol IS NOT NULL) AS n_with_enrol,
                       COUNT(*) FILTER(WHERE receipt IS NOT NULL) AS n_with_receipt,
                       COUNT(DISTINCT state) FILTER(WHERE state IS NOT NULL) AS n_distinct_states
                FROM read_parquet({lit(str(q))})
            """).fetchone()
            manifest.append({
                "year": year,
                "rows": r[0],
                "with_enrol": r[1],
                "with_receipt": r[2],
                "distinct_states": r[3],
            })
            paths.append(q)
            shutil.rmtree(root / year, ignore_errors=True)

    panel = out / "panel.parquet"
    ls = "[" + ",".join(lit(str(p)) for p in paths) + "]"
    con.execute(f"""
        COPY (
            SELECT * FROM read_parquet({ls}, union_by_name=true)
        ) TO {lit(str(panel))} (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    nstates = int(con.execute(f"""
        SELECT COUNT(DISTINCT state)
        FROM read_parquet({lit(str(panel))})
        WHERE state IS NOT NULL
    """).fetchone()[0])
    examples = [r[0] for r in con.execute(f"""
        SELECT DISTINCT state
        FROM read_parquet({lit(str(panel))})
        WHERE state IS NOT NULL
        ORDER BY 1
        LIMIT 12
    """).fetchall()]

    manifest.append({"panel_distinct_states": nstates, "state_examples": examples})
    (out / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if not (20 <= nstates <= 50):
        raise RuntimeError(
            f"State validation failed: expected roughly 20-50 State/UT labels, got {nstates}; examples={examples}"
        )
    if examples and all(str(x).strip().isdigit() for x in examples):
        raise RuntimeError(
            f"State validation failed: state labels appear numeric rather than names; examples={examples}"
        )

    print("STATE VALIDATION", nstates, examples, flush=True)
    return panel
