from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from huggingface_hub import HfApi, HfFileSystem


YEAR_REGEXES = [
    re.compile(r"(?<!\d)(20\d{2})[-_ /](20\d{2})(?!\d)", re.I),
    re.compile(r"(?<!\d)(20\d{2})[-_ /](\d{2})(?!\d)", re.I),
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(?!\d)", re.I),
]

TABLE_KEYWORDS = [
    ("enrolment", ("enrol", "enroll", "student")),
    ("teacher", ("teacher", "staff")),
    ("facility", ("facility", "facilities", "infrastructure", "infra")),
    ("profile", ("profile", "school_profile", "basic_detail", "basicdetail")),
    ("grant", ("grant", "fund", "expenditure", "expense")),
    ("inspection", ("inspection", "visit", "monitor")),
    ("smc", ("smc", "school_management_committee")),
    ("vocational", ("vocational", "voc")),
    ("exam_result", ("result", "exam", "board")),
]

TEXT_EXTS = {".csv", ".tsv", ".txt"}
ARCHIVE_EXTS = {".zip", ".xlsx", ".xlsm"}


def normalize_year(start: str, end: str) -> str | None:
    try:
        s = int(start)
        e = int(end)
    except ValueError:
        return None
    if e < 100:
        e = (s // 100) * 100 + e
        if e < s:
            e += 100
    if e == s + 1:
        return f"{s}-{str(e)[-2:]}"
    return f"{s}-{e}"


def detect_year(text: str) -> str | None:
    for rx in YEAR_REGEXES:
        m = rx.search(text)
        if m:
            return normalize_year(m.group(1), m.group(2))
    return None


def classify_table(text: str) -> str:
    low = re.sub(r"[^a-z0-9]+", "_", text.lower())
    for label, needles in TABLE_KEYWORDS:
        if any(n in low for n in needles):
            return label
    # Common UDISE naming conventions.
    if re.search(r"(^|_)profile[_ -]?[12]?($|_)", low):
        return "profile"
    if "sch" in low and "master" in low:
        return "profile"
    return "other"


def tree_sizes(api: HfApi, repo_id: str) -> dict[str, int | None]:
    sizes: dict[str, int | None] = {}
    try:
        for item in api.list_repo_tree(repo_id=repo_id, repo_type="dataset", recursive=True, expand=True):
            path = getattr(item, "path", None)
            if path and not getattr(item, "type", "") == "directory":
                sizes[path] = getattr(item, "size", None)
    except Exception as exc:  # inventory should never fail solely on metadata expansion
        print(f"WARNING: size metadata unavailable: {exc}")
    return sizes


def inspect_text(fs: HfFileSystem, remote_path: str, ext: str) -> dict:
    out: dict = {}
    try:
        with fs.open(remote_path, "rb") as f:
            raw = f.read(131072)
        text = raw.decode("utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        if lines:
            delimiter = "\t" if ext == ".tsv" else ","
            try:
                row = next(csv.reader([lines[0]], delimiter=delimiter))
                out["header"] = row[:80]
                out["column_count_preview"] = len(row)
            except Exception:
                out["first_line"] = lines[0][:1000]
        out["sample_lines"] = lines[1:4]
    except Exception as exc:
        out["inspection_error"] = repr(exc)
    return out


def inspect_zip_like(fs: HfFileSystem, remote_path: str, ext: str) -> dict:
    out: dict = {}
    try:
        with fs.open(remote_path, "rb") as remote:
            with zipfile.ZipFile(remote) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                out["archive_member_count"] = len(names)
                out["archive_members_preview"] = names[:200]
                years = [detect_year(n) for n in names]
                years = [y for y in years if y]
                if years:
                    out["archive_year_counts"] = dict(Counter(years))
                types = [classify_table(n) for n in names]
                out["archive_table_type_counts"] = dict(Counter(types))
                if ext in {".xlsx", ".xlsm"} and "xl/workbook.xml" in names:
                    xml = zf.read("xl/workbook.xml").decode("utf-8", errors="replace")
                    sheets = re.findall(r'<sheet[^>]+name="([^"]+)"', xml)
                    out["excel_sheets"] = sheets
    except Exception as exc:
        out["inspection_error"] = repr(exc)
    return out


def proposed_destination(path: str, year: str | None, table_type: str) -> str | None:
    if not year:
        return None
    name = PurePosixPath(path).name
    # Preserve original bytes and original filename; organization is structural, not destructive renaming.
    return f"data/{year}/{table_type}/{name}"


def inventory() -> dict:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    fs = HfFileSystem(token=token)

    files = sorted(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    sizes = tree_sizes(api, repo_id)
    records: list[dict] = []

    for path in files:
        ext = PurePosixPath(path).suffix.lower()
        record: dict = {
            "path": path,
            "size": sizes.get(path),
            "extension": ext,
            "year_from_path": detect_year(path),
            "table_type_from_path": classify_table(path),
        }
        remote_path = f"datasets/{repo_id}/{path}"
        if ext in TEXT_EXTS:
            record.update(inspect_text(fs, remote_path, ext))
        elif ext in ARCHIVE_EXTS:
            record.update(inspect_zip_like(fs, remote_path, ext))

        year = record.get("year_from_path")
        if not year and record.get("archive_year_counts"):
            counts = Counter(record["archive_year_counts"])
            if counts:
                year, n = counts.most_common(1)[0]
                if len(counts) == 1 or n > sum(counts.values()) / 2:
                    record["year_from_contents"] = year
                else:
                    year = None
                    record["year_ambiguous"] = True

        table_type = record["table_type_from_path"]
        archive_types = record.get("archive_table_type_counts", {})
        if table_type == "other" and archive_types:
            non_other = [(k, v) for k, v in archive_types.items() if k != "other"]
            if len(non_other) == 1:
                table_type = non_other[0][0]
                record["table_type_from_contents"] = table_type

        record["detected_year"] = year
        record["detected_table_type"] = table_type
        record["proposed_destination"] = proposed_destination(path, year, table_type)
        records.append(record)

    year_counts = Counter(r.get("detected_year") or "UNRESOLVED" for r in records)
    table_counts = Counter(r.get("detected_table_type") or "other" for r in records)
    unresolved = [r["path"] for r in records if not r.get("detected_year")]
    collisions: dict[str, list[str]] = defaultdict(list)
    for r in records:
        if r.get("proposed_destination"):
            collisions[r["proposed_destination"]].append(r["path"])
    collisions = {k: v for k, v in collisions.items() if len(v) > 1}

    payload = {
        "repo_id": repo_id,
        "file_count": len(records),
        "year_counts": dict(sorted(year_counts.items())),
        "table_type_counts": dict(sorted(table_counts.items())),
        "unresolved_year_files": unresolved,
        "destination_collisions": collisions,
        "records": records,
    }

    out = Path("outputs/hf_dataset_organization")
    out.mkdir(parents=True, exist_ok=True)
    (out / "inventory.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    columns = [
        "path", "size", "extension", "detected_year", "detected_table_type",
        "proposed_destination", "inspection_error"
    ]
    with (out / "organization_plan.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    print(json.dumps({
        "repo_id": repo_id,
        "file_count": len(records),
        "year_counts": payload["year_counts"],
        "table_type_counts": payload["table_type_counts"],
        "unresolved_year_files": unresolved,
        "destination_collisions": collisions,
    }, indent=2, ensure_ascii=False))
    print("\nPROPOSED FILE MAP")
    for r in records:
        print(f"- {r['path']} -> {r.get('proposed_destination') or 'UNRESOLVED'}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["inventory"], default="inventory")
    parser.parse_args()
    inventory()


if __name__ == "__main__":
    main()
