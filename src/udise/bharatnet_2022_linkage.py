from __future__ import annotations

import csv
import io
import json
import os
import re
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb
import requests
from huggingface_hub import hf_hub_download

REMOTE_DB = "processed/2024_25/database/udise_2024_25.duckdb"
ARCHIVE_URL = "https://storage.googleapis.com/bbnl_data/parsed.zip"


def norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).upper().replace("&", " AND ")
    text = re.sub(r"\bGRAM\s+PANCHAYAT\b", " ", text)
    text = re.sub(r"\bG\.??P\.??\b", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    aliases = {
        "ORISSA": "ODISHA",
        "UTTARANCHAL": "UTTARAKHAND",
        "A AND N": "ANDAMAN AND NICOBAR ISLANDS",
        "ANDAMAN NICOBAR ISLANDS": "ANDAMAN AND NICOBAR ISLANDS",
        "NCT OF DELHI": "DELHI",
    }
    return aliases.get(text, text)


def read_csv_member(z: zipfile.ZipFile, suffix: str) -> list[dict[str, str]]:
    member = next(name for name in z.namelist() if name.endswith(suffix))
    raw = z.read(member).decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(raw)))


def unique_index(rows: list[dict[str, str]], columns: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    buckets: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        key = tuple(norm(row.get(c, "")) for c in columns)
        if all(key):
            buckets[key].append(i)
    return {key: idxs[0] for key, idxs in buckets.items() if len(idxs) == 1}


def active_flags(panchayats: list[dict[str, str]], active: list[dict[str, str]]) -> list[bool]:
    exact = set()
    sdg: dict[tuple[str, str, str], int] = defaultdict(int)
    sbg: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in active:
        s, d, b, g = (norm(row.get(c, "")) for c in ("State", "District", "Block", "GP Name"))
        if all((s, d, b, g)):
            exact.add((s, d, b, g))
        if all((s, d, g)):
            sdg[(s, d, g)] += 1
        if all((s, b, g)):
            sbg[(s, b, g)] += 1
    flags = []
    for row in panchayats:
        s, d, b, g = (norm(row.get(c, "")) for c in ("State", "District", "Block", "Gram Panchayat Name"))
        flag = (s, d, b, g) in exact
        if not flag and sdg.get((s, d, g), 0) == 1:
            flag = True
        if not flag and sbg.get((s, b, g), 0) == 1:
            flag = True
        flags.append(flag)
    return flags


def block_effects(rows: list[dict[str, Any]], outcome: str, weight_col: str = "schools") -> dict[str, Any]:
    blocks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        y = row.get(outcome)
        if y is None:
            continue
        blocks[row["block_key"]].append(row)
    effects = []
    weights = []
    for block_rows in blocks.values():
        treated = [r for r in block_rows if r["active_2022"]]
        control = [r for r in block_rows if not r["active_2022"]]
        if not treated or not control:
            continue
        def wmean(items):
            wsum = sum(float(r.get(weight_col) or 0) for r in items)
            if wsum <= 0:
                return sum(float(r[outcome]) for r in items) / len(items), float(len(items))
            return sum(float(r[outcome]) * float(r.get(weight_col) or 0) for r in items) / wsum, wsum
        mt, wt = wmean(treated)
        mc, wc = wmean(control)
        effects.append(mt - mc)
        weights.append(2 * wt * wc / (wt + wc) if wt + wc > 0 else 1.0)
    if not effects:
        return {"mixed_blocks": 0}
    wsum = sum(weights)
    return {
        "mixed_blocks": len(effects),
        "mean_within_block_difference": sum(e*w for e, w in zip(effects, weights, strict=True))/wsum,
        "median_block_difference": statistics.median(effects),
        "p25_block_difference": sorted(effects)[max(0, int(0.25*(len(effects)-1)))],
        "p75_block_difference": sorted(effects)[max(0, int(0.75*(len(effects)-1)))],
    }


def main() -> None:
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)

    archive = requests.get(ARCHIVE_URL, timeout=180)
    archive.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(archive.content))
    panchayats = read_csv_member(z, "panchayats.csv")
    active = read_csv_member(z, "active_gps.csv")
    flags = active_flags(panchayats, active)

    idx_exact = unique_index(panchayats, ("State", "District", "Block", "Gram Panchayat Name"))
    idx_sdg = unique_index(panchayats, ("State", "District", "Gram Panchayat Name"))
    idx_sbg = unique_index(panchayats, ("State", "Block", "Gram Panchayat Name"))

    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    db_path = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=REMOTE_DB, token=token)
    con = duckdb.connect(db_path, read_only=True)
    cur = con.execute("""
        WITH e AS (
            SELECT pseudocode,
                   SUM(CASE WHEN item_group=1 AND item_id IN (1,2,3,4)
                            THEN COALESCE(c1_b,0)+COALESCE(c1_g,0)+COALESCE(c2_b,0)+COALESCE(c2_g,0)+
                                 COALESCE(c3_b,0)+COALESCE(c3_g,0)+COALESCE(c4_b,0)+COALESCE(c4_g,0)+
                                 COALESCE(c5_b,0)+COALESCE(c5_g,0)+COALESCE(c6_b,0)+COALESCE(c6_g,0)+
                                 COALESCE(c7_b,0)+COALESCE(c7_g,0)+COALESCE(c8_b,0)+COALESCE(c8_g,0)+
                                 COALESCE(c9_b,0)+COALESCE(c9_g,0)+COALESCE(c10_b,0)+COALESCE(c10_g,0)+
                                 COALESCE(c11_b,0)+COALESCE(c11_g,0)+COALESCE(c12_b,0)+COALESCE(c12_g,0)
                            ELSE 0 END) AS students
            FROM raw_enrolment_1 GROUP BY 1
        ), s AS (
            SELECT p.pseudocode, p.state, p.district, p.block, p.lgd_vill_panchayat_name, p.rural_urban,
                   e.students,
                   CASE WHEN f.internet=1 THEN 1.0 WHEN f.internet=2 THEN 0.0 END AS has_internet,
                   CASE WHEN f.electricity_availability=1 THEN 1.0 WHEN f.electricity_availability IN (2,3) THEN 0.0 END AS functional_electricity,
                   CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1.0 ELSE 0.0 END AS any_device,
                   CASE WHEN t.trained_comp>0 THEN 1.0 ELSE 0.0 END AS trained_teacher,
                   CASE WHEN f.comp_ict_lab_yn=1 OR f.ict_lab_yn=1 THEN 1.0 WHEN f.comp_ict_lab_yn=2 AND f.ict_lab_yn=2 THEN 0.0 END AS ict_lab,
                   CASE WHEN f.library_availability=1 THEN 1.0 WHEN f.library_availability=2 THEN 0.0 END AS library,
                   CASE WHEN f.total_girls_func_toilet>0 THEN 1.0 ELSE 0.0 END AS girls_toilet,
                   CASE WHEN p.approachable_road=1 THEN 1.0 WHEN p.approachable_road=2 THEN 0.0 END AS all_weather_road
            FROM raw_profile_1 p
            JOIN raw_facility f USING(pseudocode)
            JOIN raw_teacher t USING(pseudocode)
            LEFT JOIN e USING(pseudocode)
            WHERE p.rural_urban=1 AND p.lgd_vill_panchayat_name IS NOT NULL AND TRIM(p.lgd_vill_panchayat_name)<>''
        )
        SELECT state, district, block, lgd_vill_panchayat_name,
               COUNT(*) AS schools, SUM(students) AS students,
               AVG(has_internet) AS has_internet,
               AVG(functional_electricity) AS functional_electricity,
               AVG(any_device) AS any_device,
               AVG(trained_teacher) AS trained_teacher,
               AVG(ict_lab) AS ict_lab,
               AVG(CASE WHEN functional_electricity=1 AND any_device=1 AND has_internet=1 AND trained_teacher=1 THEN 1.0 ELSE 0.0 END) AS complete_stack,
               AVG(library) AS library, AVG(girls_toilet) AS girls_toilet, AVG(all_weather_road) AS all_weather_road
        FROM s GROUP BY 1,2,3,4
    """)
    cols = [d[0] for d in cur.description]
    udise = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    matched = []
    methods = defaultdict(int)
    for row in udise:
        s, d, b, g = map(norm, (row["state"], row["district"], row["block"], row["lgd_vill_panchayat_name"]))
        idx = idx_exact.get((s,d,b,g))
        method = "exact"
        if idx is None:
            idx = idx_sdg.get((s,d,g))
            method = "state_district_gp_unique"
        if idx is None:
            idx = idx_sbg.get((s,b,g))
            method = "state_block_gp_unique"
        if idx is None:
            methods["unmatched"] += 1
            continue
        methods[method] += 1
        p = panchayats[idx]
        enriched = dict(row)
        enriched["active_2022"] = bool(flags[idx])
        enriched["match_method"] = method
        enriched["block_key"] = "|".join((norm(p.get("State")), norm(p.get("District")), norm(p.get("Block"))))
        matched.append(enriched)

    total_gp = len(udise)
    total_schools = sum(int(r["schools"]) for r in udise)
    total_students = sum(int(r["students"] or 0) for r in udise)
    matched_schools = sum(int(r["schools"]) for r in matched)
    matched_students = sum(int(r["students"] or 0) for r in matched)
    treated = [r for r in matched if r["active_2022"]]
    control = [r for r in matched if not r["active_2022"]]

    outcomes = ("has_internet", "complete_stack", "any_device", "trained_teacher", "ict_lab",
                "functional_electricity", "library", "girls_toilet", "all_weather_road")
    comparisons = {}
    for outcome in outcomes:
        def weighted_mean(items, wcol):
            vals = [(float(r[outcome]), float(r.get(wcol) or 0)) for r in items if r.get(outcome) is not None]
            denom = sum(w for _,w in vals)
            return sum(v*w for v,w in vals)/denom if denom else None
        comparisons[outcome] = {
            "active_school_weighted_mean": weighted_mean(treated, "schools"),
            "inactive_school_weighted_mean": weighted_mean(control, "schools"),
            "active_student_weighted_mean": weighted_mean(treated, "students"),
            "inactive_student_weighted_mean": weighted_mean(control, "students"),
            "within_block_school_weighted": block_effects(matched, outcome, "schools"),
            "within_block_student_weighted": block_effects(matched, outcome, "students"),
        }

    summary = {
        "bbnl_archive_date_note": "archive documented as updated 2 March 2022",
        "bbnl_panchayat_rows": len(panchayats),
        "bbnl_active_rows": len(active),
        "udise_unique_named_gp_units": total_gp,
        "udise_schools_in_named_gp_units": total_schools,
        "udise_students_in_named_gp_units": total_students,
        "matched_gp_units": len(matched),
        "matched_gp_share": len(matched)/total_gp if total_gp else None,
        "matched_schools": matched_schools,
        "matched_school_share": matched_schools/total_schools if total_schools else None,
        "matched_students": matched_students,
        "matched_student_share": matched_students/total_students if total_students else None,
        "match_methods": dict(methods),
        "active_matched_gps": len(treated),
        "inactive_matched_gps": len(control),
        "active_share_of_matched_gps": len(treated)/len(matched) if matched else None,
        "comparisons": comparisons,
        "causal_warning": "2024-25 is the only UDISE microdata year currently available. These 2022-to-2024 comparisons have temporal ordering but are not causal because early BharatNet rollout was not randomized and no pre-treatment school outcome is available."
    }
    (out / "bharatnet_2022_udise_linkage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with (out / "bharatnet_2022_outcome_comparisons.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["outcome", "active_school_weighted_mean", "inactive_school_weighted_mean",
                      "raw_school_weighted_difference", "within_block_difference", "mixed_blocks"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for outcome, comp in comparisons.items():
            a, c = comp["active_school_weighted_mean"], comp["inactive_school_weighted_mean"]
            wb = comp["within_block_school_weighted"]
            w.writerow({
                "outcome": outcome,
                "active_school_weighted_mean": a,
                "inactive_school_weighted_mean": c,
                "raw_school_weighted_difference": (a-c) if a is not None and c is not None else None,
                "within_block_difference": wb.get("mean_within_block_difference"),
                "mixed_blocks": wb.get("mixed_blocks"),
            })

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
