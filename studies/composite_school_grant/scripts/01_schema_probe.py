from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from huggingface_hub import HfApi, HfFileSystem


YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]
KEYWORDS = [
    "grant", "fund", "expend", "utili", "enrol", "enroll", "student", "school", "udise",
    "manage", "toilet", "water", "wash", "electric", "internet", "library", "repair",
    "classroom", "building", "computer", "desktop", "laptop", "tablet", "ict", "inspect",
    "visit", "smc", "committee", "functional", "minor", "major", "condition", "rural", "urban",
    "district", "block", "village", "panchayat", "category", "class_from", "class_to",
]


def sniff_header(sample: bytes) -> tuple[list[str], str]:
    text = sample.decode("utf-8-sig", errors="replace")
    first = text.splitlines()[0] if text.splitlines() else ""
    candidates = [",", "\t", "|", ";"]
    delim = max(candidates, key=lambda d: first.count(d)) if first else ","
    row = next(csv.reader([first], delimiter=delim), [])
    return [c.strip() for c in row], delim


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    fs = HfFileSystem(token=token)
    files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")

    archives = [p for p in files if p.startswith("raw/") and p.lower().endswith(".zip")]
    records: list[dict] = []
    relevant: list[dict] = []
    errors: list[dict] = []

    for path in sorted(archives):
        parts = PurePosixPath(path).parts
        year = parts[1] if len(parts) > 2 else None
        table = PurePosixPath(path).stem
        remote = f"datasets/{repo_id}/{path}"
        try:
            with fs.open(remote, "rb") as fh, zipfile.ZipFile(fh) as zf:
                members = [n for n in zf.namelist() if not n.endswith("/") and n.lower().endswith((".csv", ".txt", ".tsv"))]
                for member in members:
                    try:
                        with zf.open(member) as mf:
                            sample = mf.read(262144)
                        header, delim = sniff_header(sample)
                        norm = [re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in header]
                        hits = [c for c, n in zip(header, norm) if any(k in n for k in KEYWORDS)]
                        rec = {
                            "year": year,
                            "archive": path,
                            "table": table,
                            "member": member,
                            "member_size": zf.getinfo(member).file_size,
                            "column_count": len(header),
                            "delimiter": repr(delim),
                            "columns": header,
                            "relevant_columns": hits,
                        }
                        records.append(rec)
                        if hits:
                            relevant.append(rec)
                    except Exception as exc:
                        errors.append({"archive": path, "member": member, "error": repr(exc)})
        except Exception as exc:
            errors.append({"archive": path, "member": None, "error": repr(exc)})

    # Cross-year column occurrence table.
    occurrence: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    original_labels: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        for col in rec["columns"]:
            n = re.sub(r"[^a-z0-9]+", "_", col.lower()).strip("_")
            occurrence[n][rec["year"]].add(rec["table"])
            original_labels[n].add(col)

    crosswalk = []
    for norm, year_map in occurrence.items():
        if any(k in norm for k in KEYWORDS):
            crosswalk.append({
                "normalized_column": norm,
                "original_labels": sorted(original_labels[norm]),
                "years": sorted(year_map),
                "tables_by_year": {y: sorted(v) for y, v in sorted(year_map.items())},
            })
    crosswalk.sort(key=lambda x: (x["normalized_column"]))

    out = Path("studies/composite_school_grant/outputs/schema_probe")
    out.mkdir(parents=True, exist_ok=True)
    (out / "all_members.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "relevant_columns.json").write_text(json.dumps(relevant, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "cross_year_column_crosswalk.json").write_text(json.dumps(crosswalk, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "errors.json").write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"archives={len(archives)} members={len(records)} errors={len(errors)}")
    for year in YEARS:
        year_recs = [r for r in records if r["year"] == year]
        print(f"\n=== {year}: {len(year_recs)} data members ===")
        for r in year_recs:
            print(f"[{r['table']}] {r['member']} ({r['column_count']} cols)")
            if r["relevant_columns"]:
                print("  " + " | ".join(r["relevant_columns"]))

    print("\n=== GRANT/FUND/EXPENDITURE CANDIDATES ===")
    for r in relevant:
        grant_cols = [c for c in r["relevant_columns"] if any(k in re.sub(r"[^a-z0-9]+", "_", c.lower()) for k in ("grant", "fund", "expend", "utili"))]
        if grant_cols:
            print(r["year"], r["table"], r["member"], "::", " | ".join(grant_cols))

    if errors:
        print("\nERRORS")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
