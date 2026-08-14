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

from huggingface_hub import (
    CommitOperationAdd,
    CommitOperationCopy,
    CommitOperationDelete,
    HfApi,
    HfFileSystem,
)

YEAR_REGEXES = [
    re.compile(r"(?<!\d)(20\d{2})[-_ /](20\d{2})(?!\d)", re.I),
    re.compile(r"(?<!\d)(20\d{2})[-_ /](\d{2})(?!\d)", re.I),
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(?!\d)", re.I),
]

CANONICAL_RAW_NAMES = (
    (re.compile(r"^enrolment_data_1_", re.I), "enrolment_1.zip"),
    (re.compile(r"^enrolment_data_2_", re.I), "enrolment_2.zip"),
    (re.compile(r"^facility_data_", re.I), "facility.zip"),
    (re.compile(r"^profile_data_1_", re.I), "profile_1.zip"),
    (re.compile(r"^profile_data_2_", re.I), "profile_2.zip"),
    (re.compile(r"^teacher_data_", re.I), "teacher.zip"),
    (re.compile(r"^safety_", re.I), "safety.zip"),
)

TABLE_KEYWORDS = [
    ("enrolment", ("enrol", "enroll", "student")),
    ("teacher", ("teacher", "staff", "tch")),
    ("facility", ("facility", "facilities", "infrastructure", "infra", "_fac")),
    ("profile", ("profile", "school_profile", "basic_detail", "basicdetail", "prof1", "prof2")),
    ("grant", ("grant", "fund", "expenditure", "expense")),
    ("inspection", ("inspection", "visit", "monitor")),
    ("smc", ("smc", "school_management_committee")),
    ("vocational", ("vocational", "voc")),
    ("exam_result", ("result", "exam", "board")),
    ("safety", ("safety",)),
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
    return "other"


def canonical_raw_destination(path: str) -> str | None:
    """Map original top-level all-India ZIP uploads to a stable raw layout."""
    if "/" in path or not path.lower().endswith(".zip"):
        return None
    year = detect_year(path)
    if not year:
        return None
    base = PurePosixPath(path).name
    for rx, canonical in CANONICAL_RAW_NAMES:
        if rx.search(base):
            return f"raw/{year}/{canonical}"
    return None


def tree_sizes(api: HfApi, repo_id: str) -> dict[str, int | None]:
    sizes: dict[str, int | None] = {}
    try:
        for item in api.list_repo_tree(repo_id=repo_id, repo_type="dataset", recursive=True, expand=True):
            path = getattr(item, "path", None)
            if path and getattr(item, "type", "") != "directory":
                sizes[path] = getattr(item, "size", None)
    except Exception as exc:
        print(f"WARNING: size metadata unavailable: {exc}")
    return sizes


def sniff_delimiter(line: str) -> str:
    candidates = [",", "\t", "|", ";"]
    counts = {d: line.count(d) for d in candidates}
    return max(counts, key=counts.get) if max(counts.values(), default=0) else ","


def inspect_text(fs: HfFileSystem, remote_path: str, ext: str) -> dict:
    out: dict = {}
    try:
        with fs.open(remote_path, "rb") as f:
            raw = f.read(131072)
        text = raw.decode("utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        if lines:
            delimiter = "\t" if ext == ".tsv" else sniff_delimiter(lines[0])
            row = next(csv.reader([lines[0]], delimiter=delimiter))
            out["delimiter"] = delimiter
            out["header"] = row
            out["column_count_preview"] = len(row)
            out["sample_lines"] = lines[1:4]
    except Exception as exc:
        out["inspection_error"] = repr(exc)
    return out


def inspect_zip_like(fs: HfFileSystem, remote_path: str, ext: str, include_headers: bool = False) -> dict:
    out: dict = {}
    try:
        with fs.open(remote_path, "rb") as remote:
            with zipfile.ZipFile(remote) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                out["archive_member_count"] = len(names)
                out["archive_members"] = names
                types = [classify_table(n) for n in names]
                out["archive_table_type_counts"] = dict(Counter(types))
                if include_headers:
                    members: list[dict] = []
                    for name in names:
                        member: dict = {"path": name, "table_type_guess": classify_table(name)}
                        if name.lower().endswith((".csv", ".txt", ".tsv")):
                            try:
                                with zf.open(name) as fh:
                                    first = fh.readline(1024 * 1024)
                                line = first.decode("utf-8-sig", errors="replace").strip("\r\n")
                                delimiter = sniff_delimiter(line)
                                cols = next(csv.reader([line], delimiter=delimiter)) if line else []
                                member.update({
                                    "delimiter": delimiter,
                                    "column_count": len(cols),
                                    "columns": cols,
                                })
                            except Exception as exc:
                                member["header_error"] = repr(exc)
                        members.append(member)
                    out["member_schemas"] = members
                if ext in {".xlsx", ".xlsm"} and "xl/workbook.xml" in names:
                    xml = zf.read("xl/workbook.xml").decode("utf-8", errors="replace")
                    out["excel_sheets"] = re.findall(r'<sheet[^>]+name="([^"]+)"', xml)
    except Exception as exc:
        out["inspection_error"] = repr(exc)
    return out


def inventory(include_headers: bool = False) -> dict:
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
            "detected_year": detect_year(path),
            "detected_table_type": classify_table(path),
            "canonical_raw_destination": canonical_raw_destination(path),
        }
        remote_path = f"datasets/{repo_id}/{path}"
        if ext in TEXT_EXTS:
            record.update(inspect_text(fs, remote_path, ext))
        elif ext in ARCHIVE_EXTS:
            record.update(inspect_zip_like(fs, remote_path, ext, include_headers=include_headers))
        records.append(record)

    year_counts = Counter(r.get("detected_year") or "UNRESOLVED" for r in records)
    collisions: dict[str, list[str]] = defaultdict(list)
    for r in records:
        dest = r.get("canonical_raw_destination")
        if dest:
            collisions[dest].append(r["path"])
    collisions = {k: v for k, v in collisions.items() if len(v) > 1}

    payload = {
        "repo_id": repo_id,
        "file_count": len(records),
        "year_counts": dict(sorted(year_counts.items())),
        "destination_collisions": collisions,
        "records": records,
    }

    out = Path("outputs/hf_dataset_organization")
    out.mkdir(parents=True, exist_ok=True)
    (out / "inventory.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    columns = ["path", "size", "extension", "detected_year", "detected_table_type", "canonical_raw_destination"]
    with (out / "organization_plan.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    print(json.dumps({
        "repo_id": repo_id,
        "file_count": len(records),
        "year_counts": payload["year_counts"],
        "destination_collisions": collisions,
    }, indent=2))
    return payload


def build_readme(years: list[str]) -> str:
    year_text = ", ".join(years)
    return f"""# UDISE+ all-India microdata archive\n\nThis repository stores the original all-India UDISE+ source archives in a stable, year-based layout for reproducible longitudinal analysis.\n\n## Coverage\n\nAcademic years: {year_text}.\n\n## Layout\n\n```text\nraw/\n  2018-19/\n    profile_1.zip\n    profile_2.zip\n    enrolment_1.zip\n    enrolment_2.zip\n    facility.zip\n    teacher.zip\n  ...\n  2025-26/\n    ...\n    safety.zip\nprocessed/2024_25/\n  ...existing derived outputs from the earlier pipeline...\nmanifests/\n  raw_archive_manifest.json\n  raw_file_manifest.csv\n```\n\nThe `raw/` files are byte-for-byte copies of the originally uploaded archives. They are renamed only at the repository-path level. ZIP contents are not rewritten. This preserves the source data while removing inconsistent upload names such as `All State` and `(1)`.\n\nOlder enrolment archives are internally sharded across multiple CSV files, and some contain a separate stream-enrolment table. The archive manifest records every member and its header so analysis code can concatenate only schema-compatible shards.\n\nThe existing `processed/2024_25/` outputs are intentionally left in place so current workflows remain reproducible while the multi-year pipeline is built.\n"""


def organize() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)

    payload = inventory(include_headers=True)
    records = payload["records"]
    if payload["destination_collisions"]:
        raise RuntimeError(f"Refusing to organize because destinations collide: {payload['destination_collisions']}")

    files = set(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    moves: list[tuple[str, str]] = []
    for r in records:
        src = r["path"]
        dest = r.get("canonical_raw_destination")
        if not dest:
            continue
        if dest in files and src != dest:
            raise RuntimeError(f"Destination already exists: {dest}; source={src}")
        if src != dest:
            moves.append((src, dest))

    if not moves:
        print("No raw top-level archives require moving. Repository already organized.")
        return

    manifest_records = []
    record_by_path = {r["path"]: r for r in records}
    for src, dest in moves:
        r = record_by_path[src]
        manifest_records.append({
            "academic_year": r.get("detected_year"),
            "source_path": src,
            "organized_path": dest,
            "size_bytes": r.get("size"),
            "archive_members": r.get("archive_members", []),
            "member_schemas": r.get("member_schemas", []),
        })

    manifest = {
        "repo_id": repo_id,
        "organization_policy": "Original ZIP bytes preserved; only repository paths renamed and grouped by academic year.",
        "raw_archive_count": len(manifest_records),
        "years": sorted({m["academic_year"] for m in manifest_records if m.get("academic_year")}),
        "files": manifest_records,
    }

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["academic_year", "source_path", "organized_path", "size_bytes"])
    writer.writeheader()
    for m in manifest_records:
        writer.writerow({k: m.get(k) for k in writer.fieldnames})

    operations = []
    for src, dest in moves:
        operations.append(CommitOperationCopy(src_path_in_repo=src, path_in_repo=dest))
        operations.append(CommitOperationDelete(path_in_repo=src))
    operations.extend([
        CommitOperationAdd(
            path_in_repo="manifests/raw_archive_manifest.json",
            path_or_fileobj=io.BytesIO(json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")),
        ),
        CommitOperationAdd(
            path_in_repo="manifests/raw_file_manifest.csv",
            path_or_fileobj=io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
        ),
        CommitOperationAdd(
            path_in_repo="README.md",
            path_or_fileobj=io.BytesIO(build_readme(manifest["years"]).encode("utf-8")),
        ),
    ])

    parent = api.repo_info(repo_id=repo_id, repo_type="dataset").sha
    info = api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Organize UDISE+ raw archives by academic year",
        commit_description="Lossless server-side rename of original all-India ZIP archives; adds member/schema manifests. Existing processed/2024_25 outputs are preserved.",
        parent_commit=parent,
    )
    print(f"Created Hugging Face commit: {info.commit_url}")

    after = set(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    missing = [dest for _, dest in moves if dest not in after]
    stale = [src for src, _ in moves if src in after]
    required = {"README.md", "manifests/raw_archive_manifest.json", "manifests/raw_file_manifest.csv"}
    missing_meta = sorted(required - after)
    verification = {
        "moved_archives": len(moves),
        "missing_destinations": missing,
        "stale_source_paths": stale,
        "missing_metadata_files": missing_meta,
        "success": not missing and not stale and not missing_meta,
    }
    out = Path("outputs/hf_dataset_organization")
    out.mkdir(parents=True, exist_ok=True)
    (out / "organization_verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(json.dumps(verification, indent=2))
    if not verification["success"]:
        raise RuntimeError("Post-commit verification failed")


def verify() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    files = sorted(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    raw = [f for f in files if f.startswith("raw/") and f.endswith(".zip")]
    by_year = Counter(PurePosixPath(f).parts[1] for f in raw if len(PurePosixPath(f).parts) >= 3)
    top_level_zips = [f for f in files if "/" not in f and f.lower().endswith(".zip")]
    payload = {
        "raw_archive_count": len(raw),
        "raw_archives_by_year": dict(sorted(by_year.items())),
        "top_level_zip_files_remaining": top_level_zips,
        "has_readme": "README.md" in files,
        "has_schema_manifest": "manifests/raw_archive_manifest.json" in files,
    }
    print(json.dumps(payload, indent=2))
    if top_level_zips or not payload["has_schema_manifest"]:
        raise RuntimeError("Repository is not fully organized")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["inventory", "organize", "verify"], default="inventory")
    args = parser.parse_args()
    if args.mode == "inventory":
        inventory(include_headers=False)
    elif args.mode == "organize":
        organize()
    else:
        verify()


if __name__ == "__main__":
    main()
