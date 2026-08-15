from __future__ import annotations

import csv
import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from huggingface_hub import hf_hub_download

YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]
TABLES = ["profile_1", "profile_2", "facility", "enrolment_1", "enrolment_2", "teacher"]


def norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", x.lower().replace("\ufeff", "")).strip("_")


CONCEPTS = {
    "school_identifier": [r"pseudo.*code", r"^udise.*code$", r"school.*code"],
    "state": [r"^state(_.*)?$"],
    "district": [r"^district(_.*)?$"],
    "block": [r"^block(_.*)?$"],
    "cluster": [r"cluster", r"crc"],
    "gram_panchayat_or_village": [r"panch", r"village", r"habitation"],
    "rural_urban": [r"rural.*urban", r"location"],
    "management": [r"manag"],
    "school_category_or_class_span": [r"school_category", r"lowclass", r"highclass", r"lowest.*class", r"highest.*class"],
    "latitude_longitude": [r"latitude", r"longitude", r"^lat$", r"^long$", r"^lon$"],
    "enrolment_by_class_gender": [r"^c([1-9]|1[0-2])_[bg]$", r"class.*boy", r"class.*girl"],
    "social_category_enrolment": [r"item_group", r"item_desc", r"general", r"scheduled.*caste", r"scheduled.*tribe", r"obc"],
    "religion_enrolment": [r"muslim", r"christian", r"sikh", r"buddh", r"jain", r"parsi", r"relig"],
    "agewise_enrolment": [r"age", r"enrol.*age"],
    "repeater_bpl_ews_cwsn": [r"repeat", r"bpl", r"ews", r"cwsn", r"disab"],
    "teacher_counts": [r"teacher", r"tch", r"regular", r"contract", r"part.?time"],
    "teacher_qualification_training": [r"qualif", r"graduate", r"bed", r"d_el_ed", r"trained", r"training"],
    "classrooms_building_repairs": [r"class.?room", r"building", r"repair", r"boundary"],
    "toilets_wash_water": [r"toilet", r"water", r"handwash", r"rainwater"],
    "electricity": [r"electric"],
    "internet": [r"internet"],
    "ict_devices_labs": [r"ict", r"computer", r"desktop", r"laptop", r"tablet", r"smart", r"digital", r"projector", r"printer"],
    "library_learning_resources": [r"library", r"book", r"reading"],
    "road_access": [r"road"],
    "grant_receipt_expenditure": [r"grant.*receipt", r"grant.*expend", r"grants_receipt", r"grants_expenditure"],
    "inspections_visits": [r"inspection", r"visit", r"crc", r"academic.*inspect"],
    "smc_governance": [r"smc", r"smdc"],
    "free_textbook_uniform": [r"textbook", r"uniform"],
    "special_training_oosc": [r"special.*training", r"out.*school", r"oosc"],
}


def archive_headers(repo: str, token: str, year: str, table: str) -> list[tuple[str, list[str]]]:
    path = hf_hub_download(
        repo_id=repo,
        repo_type="dataset",
        filename=f"raw/{year}/{table}.zip",
        token=token,
    )
    out = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".csv"):
                continue
            with zf.open(info) as fh:
                line = fh.readline().decode("utf-8-sig", errors="replace")
            cols = next(csv.reader([line])) if line else []
            out.append((info.filename, cols))
    return out


def main() -> None:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    outdir = Path("studies/causal_identification/outputs")
    outdir.mkdir(parents=True, exist_ok=True)

    schema_rows = []
    year_table_cols: dict[tuple[str, str], set[str]] = defaultdict(set)
    file_counts: dict[tuple[str, str], int] = defaultdict(int)

    for year in YEARS:
        for table in TABLES:
            headers = archive_headers(repo, token, year, table)
            file_counts[(year, table)] = len(headers)
            for member, cols in headers:
                for c in cols:
                    nc = norm(c)
                    if not nc:
                        continue
                    year_table_cols[(year, table)].add(nc)
                    schema_rows.append({
                        "year": year,
                        "table": table,
                        "member": member,
                        "column_raw": c,
                        "column_norm": nc,
                    })

    with (outdir / "schema_columns.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(schema_rows[0].keys()))
        w.writeheader(); w.writerows(schema_rows)

    coverage_rows = []
    for concept, pats in CONCEPTS.items():
        regexes = [re.compile(p) for p in pats]
        for year in YEARS:
            matched = []
            tables = []
            for table in TABLES:
                cols = year_table_cols[(year, table)]
                m = sorted(c for c in cols if any(r.search(c) for r in regexes))
                if m:
                    tables.append(table)
                    matched.extend(f"{table}:{c}" for c in m[:15])
            coverage_rows.append({
                "concept": concept,
                "year": year,
                "available": int(bool(matched)),
                "tables": "|".join(tables),
                "matched_columns_sample": "|".join(matched[:30]),
            })

    with (outdir / "concept_coverage.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()))
        w.writeheader(); w.writerows(coverage_rows)

    summary = {}
    for concept in CONCEPTS:
        yrs = [r["year"] for r in coverage_rows if r["concept"] == concept and r["available"]]
        summary[concept] = {"years_available": len(yrs), "years": yrs}

    table_summary = {
        year: {
            table: {
                "internal_csv_files": file_counts[(year, table)],
                "distinct_normalized_columns": len(year_table_cols[(year, table)]),
            }
            for table in TABLES
        }
        for year in YEARS
    }

    payload = {"concept_summary": summary, "table_summary": table_summary}
    (outdir / "data_readiness_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    all8 = [k for k, v in summary.items() if v["years_available"] == 8]
    partial = {k: v for k, v in summary.items() if 0 < v["years_available"] < 8}
    missing = [k for k, v in summary.items() if v["years_available"] == 0]
    md = [
        "# Eight-year UDISE causal data-readiness audit",
        "",
        "This is a schema/readiness audit, not an identification claim. A variable being available does not make its relationship causal; causal interpretation still requires an exogenous assignment rule, threshold, rollout or shock.",
        "",
        "## Concepts detected in all eight academic years",
        "",
    ]
    md += [f"- {x}" for x in all8]
    md += ["", "## Partial-year concepts", ""]
    for k, v in partial.items():
        md.append(f"- {k}: {v['years_available']}/8 years ({', '.join(v['years'])})")
    md += ["", "## Concepts not detected by this keyword audit", ""]
    md += [f"- {x}" for x in missing] or ["- none"]
    md += [
        "",
        "## Interpretation",
        "",
        "The UDISE source provides a very large repeated school-level outcome panel. It can support regression discontinuity, instrumental-variable, event-study or difference-in-differences designs only when paired with a defensible treatment-assignment mechanism. School fixed effects or large sample size alone do not make endogenous changes causal.",
    ]
    (outdir / "DATA_READINESS_AUDIT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == "__main__":
    main()
