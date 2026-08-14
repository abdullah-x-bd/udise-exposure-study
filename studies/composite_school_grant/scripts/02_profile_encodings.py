from __future__ import annotations

import csv
import json
import math
import os
import random
import re
import zipfile
from collections import Counter
from pathlib import Path

from huggingface_hub import HfFileSystem


YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]
PROFILE2_FIELDS = [
    "grants_receipt",
    "grants_expenditure",
    "acad_inspections",
    "smc_exists",
    "smc_smdc_meetings",
]
PROFILE1_FIELDS = [
    "managment",
    "management",
    "school_category",
    "school_type",
    "rural_urban",
    "lowclass",
    "highclass",
]
FACILITY_FIELDS = [
    "building_status",
    "classrooms_needs_minor_repair",
    "classrooms_needs_major_repair",
    "total_boys_toilet",
    "total_boys_func_toilet",
    "total_girls_toilet",
    "total_girls_func_toilet",
    "drinking_water_available",
    "drinking_water_functional",
    "electricity_availability",
    "library_availability",
    "handwash_near_toilet",
    "handwash_facility_for_meal",
    "internet",
]


def normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower().replace("\ufeff", "")).strip("_")


def iter_csv_rows(zf: zipfile.ZipFile):
    members = [m for m in zf.infolist() if not m.is_dir() and m.filename.lower().endswith(".csv")]
    if not members:
        return
    # Profile/facility archives have one CSV. Keep this generic in case a vintage changes.
    for member in members:
        with zf.open(member) as raw:
            text = (line.decode("utf-8-sig", errors="replace") for line in raw)
            reader = csv.DictReader(text)
            if reader.fieldnames is None:
                continue
            field_map = {normalise(c): c for c in reader.fieldnames}
            yield member.filename, field_map, reader


def profile_archive(fs: HfFileSystem, repo_id: str, year: str, name: str, requested: list[str]) -> dict:
    remote = f"datasets/{repo_id}/raw/{year}/{name}.zip"
    result: dict = {"year": year, "archive": name, "members": []}
    with fs.open(remote, "rb") as fh, zipfile.ZipFile(fh) as zf:
        for member_name, field_map, reader in iter_csv_rows(zf):
            fields = [f for f in requested if f in field_map]
            counters = {f: Counter() for f in fields}
            numeric = {f: {"n": 0, "min": math.inf, "max": -math.inf, "sample": []} for f in fields}
            rng = random.Random(73017)
            row_count = 0
            for row in reader:
                row_count += 1
                for f in fields:
                    raw = (row.get(field_map[f]) or "").strip()
                    counters[f][raw] += 1
                    try:
                        val = float(raw)
                    except Exception:
                        continue
                    stat = numeric[f]
                    stat["n"] += 1
                    stat["min"] = min(stat["min"], val)
                    stat["max"] = max(stat["max"], val)
                    sample = stat["sample"]
                    if len(sample) < 50000:
                        sample.append(val)
                    else:
                        j = rng.randrange(stat["n"])
                        if j < len(sample):
                            sample[j] = val
            summaries = {}
            for f in fields:
                stat = numeric[f]
                samp = sorted(stat["sample"])
                def q(p: float):
                    if not samp:
                        return None
                    return samp[min(len(samp)-1, max(0, round(p*(len(samp)-1))))]
                summaries[f] = {
                    "top_values": counters[f].most_common(30),
                    "distinct_values_seen": len(counters[f]),
                    "numeric_n": stat["n"],
                    "numeric_min": None if stat["n"] == 0 else stat["min"],
                    "numeric_max": None if stat["n"] == 0 else stat["max"],
                    "numeric_q01": q(0.01),
                    "numeric_q25": q(0.25),
                    "numeric_q50": q(0.50),
                    "numeric_q75": q(0.75),
                    "numeric_q99": q(0.99),
                }
            result["members"].append({
                "member": member_name,
                "row_count": row_count,
                "available_requested_fields": fields,
                "summaries": summaries,
            })
    return result


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    fs = HfFileSystem(token=token)
    payload = []
    for year in YEARS:
        print(f"Profiling {year} profile_2", flush=True)
        payload.append(profile_archive(fs, repo_id, year, "profile_2", PROFILE2_FIELDS))
        print(f"Profiling {year} profile_1", flush=True)
        payload.append(profile_archive(fs, repo_id, year, "profile_1", PROFILE1_FIELDS))
        print(f"Profiling {year} facility", flush=True)
        payload.append(profile_archive(fs, repo_id, year, "facility", FACILITY_FIELDS))

    out = Path("studies/composite_school_grant/outputs/encoding_profile")
    out.mkdir(parents=True, exist_ok=True)
    (out / "encoding_profile.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== GRANT DISTRIBUTIONS ===")
    for rec in payload:
        if rec["archive"] != "profile_2":
            continue
        for member in rec["members"]:
            print(f"\n{rec['year']} rows={member['row_count']}")
            for field in ("grants_receipt", "grants_expenditure"):
                if field in member["summaries"]:
                    s = member["summaries"][field]
                    print(field, json.dumps(s, ensure_ascii=False))

    print("\n=== MANAGEMENT CODES ===")
    for rec in payload:
        if rec["archive"] != "profile_1":
            continue
        for member in rec["members"]:
            for field in ("managment", "management"):
                if field in member["summaries"]:
                    print(rec["year"], field, member["summaries"][field]["top_values"])

    print("\n=== FACILITY ENCODING CHECKS ===")
    for rec in payload:
        if rec["archive"] != "facility":
            continue
        for member in rec["members"]:
            subset = {}
            for field in ("building_status", "electricity_availability", "library_availability", "internet", "drinking_water_available", "drinking_water_functional"):
                if field in member["summaries"]:
                    subset[field] = member["summaries"][field]["top_values"][:12]
            print(rec["year"], json.dumps(subset, ensure_ascii=False))


if __name__ == "__main__":
    main()
