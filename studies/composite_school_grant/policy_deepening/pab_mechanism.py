from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
spec_logic = importlib.util.spec_from_file_location("logic", ROOT / "logic.py")
logic = importlib.util.module_from_spec(spec_logic)
assert spec_logic.loader is not None
spec_logic.loader.exec_module(logic)

spec_parser = importlib.util.spec_from_file_location("pab_parser", ROOT / "pab_parser.py")
pp = importlib.util.module_from_spec(spec_parser)
assert spec_parser.loader is not None
spec_parser.loader.exec_module(pp)

OUT = Path("studies/composite_school_grant/outputs/policy_deepening/pab_mechanism")
BASE_DIR = Path(os.environ.get(
    "MECHANISM_BASE_DIR",
    "studies/composite_school_grant/outputs/policy_deepening/mechanism_base",
))
BASE_URL = "https://dsel.education.gov.in"
ARCHIVE_URL = BASE_URL + "/en/pab-minutes?field_financial_year_target_id=All&field_states_target_id=All&page={page}"
TARGET_FYS = ("2021-22", "2022-23", "2023-24", "2024-25")
UA = "Mozilla/5.0 (compatible; CSGPolicyAudit/1.0; research use)"
AMENDMENT_WORDS = ("addendum", "corrigendum", "supplement")
REVISION_WORDS = ("revised", "revision")


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, connect=4, read=4, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": UA})
    return s


def canon_pab_state(state: str, fy: str) -> str:
    x = logic.canonical_state(state) or ""
    if fy >= "2020-21" and x in {"DADRA & NAGAR HAVELI", "DAMAN & DIU"}:
        return "DADRA & NAGAR HAVELI & DAMAN & DIU"
    return x


def crawl_archive(s: requests.Session, allowed_states: set[str]) -> pd.DataFrame:
    rows = []
    seen = set()
    empty_streak = 0
    for page in range(0, 15):
        url = ARCHIVE_URL.format(page=page)
        r = s.get(url, timeout=60)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        page_rows = 0
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            state_raw = " ".join(tds[1].stripped_strings)
            fy = pp.normalize_financial_year(" ".join(tds[2].stripped_strings))
            if fy not in TARGET_FYS:
                continue
            state = canon_pab_state(state_raw, fy)
            if not state or state not in allowed_states:
                continue
            link_entries = [
                (urljoin(BASE_URL, a.get("href")), " ".join(a.stripped_strings))
                for a in tr.find_all("a", href=True)
            ]
            node_links = [(u, t) for u, t in link_entries if "/node/" in u]
            direct_pdfs = [(u, t) for u, t in link_entries if ".pdf" in u.lower()]
            if not node_links and not direct_pdfs:
                key = (state, fy, "no_document_link")
                if key not in seen:
                    seen.add(key)
                    rows.append({
                        "state": state, "financial_year": fy, "archive_page": page,
                        "node_url": None, "direct_pdf_url": None,
                        "archive_link_text": "", "archive_status": "no_document_link",
                    })
                    page_rows += 1
                continue
            for u, t in node_links:
                key = (state, fy, "node", u)
                if key not in seen:
                    seen.add(key)
                    rows.append({
                        "state": state, "financial_year": fy, "archive_page": page,
                        "node_url": u, "direct_pdf_url": None,
                        "archive_link_text": t, "archive_status": "node",
                    })
                    page_rows += 1
            for u, t in direct_pdfs:
                key = (state, fy, "pdf", u)
                if key not in seen:
                    seen.add(key)
                    rows.append({
                        "state": state, "financial_year": fy, "archive_page": page,
                        "node_url": None, "direct_pdf_url": u,
                        "archive_link_text": t, "archive_status": "direct_pdf",
                    })
                    page_rows += 1
        if page_rows == 0:
            empty_streak += 1
        else:
            empty_streak = 0
        if page >= 8 and empty_streak >= 3:
            break
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("PAB archive crawler found no target-year State/UT rows")
    return out.drop_duplicates()


def node_documents(s: requests.Session, row: pd.Series) -> list[dict]:
    if pd.notna(row.get("direct_pdf_url")):
        u = str(row.direct_pdf_url)
        return [{
            "pdf_url": u,
            "filename": u.split("?")[0].rsplit("/", 1)[-1],
            "link_text": str(row.get("archive_link_text") or ""),
            "node_url": None,
        }]
    if pd.isna(row.get("node_url")):
        return []
    node = str(row.node_url)
    r = s.get(node, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    docs = []
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a.get("href"))
        if ".pdf" not in href.lower():
            continue
        docs.append({
            "pdf_url": href,
            "filename": href.split("?")[0].rsplit("/", 1)[-1],
            "link_text": " ".join(a.stripped_strings),
            "node_url": node,
        })
    return docs


def pdf_to_text(s: requests.Session, url: str) -> tuple[str, int]:
    with tempfile.TemporaryDirectory(prefix="csg_pab_") as td:
        pdf = Path(td) / "doc.pdf"
        with s.get(url, timeout=120, stream=True) as r:
            r.raise_for_status()
            total = 0
            with pdf.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        if total > 150 * 1024 * 1024:
                            raise RuntimeError("pdf_exceeds_150mb_safety_limit")
        if shutil.which("pdftotext"):
            p = subprocess.run(
                ["pdftotext", "-layout", str(pdf), "-"],
                check=True, capture_output=True, text=True, errors="replace",
                timeout=180,
            )
            return p.stdout, total
        from pypdf import PdfReader
        reader = PdfReader(str(pdf))
        return "\n".join((page.extract_text() or "") for page in reader.pages), total


def band_summary(rec: dict, rows: list[dict]) -> None:
    for band in ("1_30", "31_100", "101_250", "251_1000", "gt1000"):
        br = [r for r in rows if r["band"] == band]
        rec[f"band_{band}_recommended_qty"] = sum(float(r["recommended_qty"]) for r in br) if br else np.nan
        rec[f"band_{band}_recommended_amount_lakh"] = sum(float(r["recommended_amount_lakh"]) for r in br) if br else np.nan
        units = sorted({round(float(r["recommended_unit_lakh"]), 8) for r in br})
        rec[f"band_{band}_unit_lakh"] = units[0] if len(units) == 1 else np.nan
    rec["pab_recommended_school_count"] = sum(float(r["recommended_qty"]) for r in rows) if rows else np.nan


def extract_documents(s: requests.Session, archive: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seen_pdf = set()
    for _, ar in archive.iterrows():
        try:
            docs = node_documents(s, ar)
        except Exception as e:
            rows.append({**ar.to_dict(), "parse_status": "node_error", "error": repr(e)})
            continue
        if not docs:
            rows.append({**ar.to_dict(), "parse_status": "no_pdf", "error": None})
            continue
        for doc in docs:
            pdf_key = (ar.state, ar.financial_year, doc["pdf_url"])
            if pdf_key in seen_pdf:
                continue
            seen_pdf.add(pdf_key)
            rec = {**ar.to_dict(), **doc}
            rec["document_priority"] = pp.document_priority(doc["filename"], doc["link_text"])
            label = f"{doc['filename']} {doc['link_text']}".lower()
            rec["is_revision"] = any(w in label for w in REVISION_WORDS)
            rec["is_amendment"] = any(w in label for w in AMENDMENT_WORDS)
            try:
                text, size = pdf_to_text(s, doc["pdf_url"])
                reconciled = pp.reconcile_band_rows_to_totals(text)
                amounts = reconciled["total_amounts_lakh"]
                rec.update({
                    "pdf_bytes": size,
                    "parse_status": "parsed" if amounts else "no_csg_total",
                    "parse_confidence": reconciled["total_confidence"],
                    "n_csg_total_occurrences": len(amounts),
                    "csg_total_lakhs": float(reconciled["total_sum_lakh"]) if amounts else np.nan,
                    "csg_total_rupees": float(reconciled["total_sum_lakh"] * 100_000) if amounts else np.nan,
                    "evidence": " || ".join(reconciled["total_evidence"][:8]),
                    "band_rows_json": json.dumps(reconciled["band_rows"], ensure_ascii=False),
                    "n_band_rows": len(reconciled["band_rows"]),
                    "band_sum_lakh": reconciled["band_sum_lakh"],
                    "band_arithmetic_gap_fraction": reconciled["relative_arithmetic_gap"],
                    "band_arithmetic_ok": reconciled["band_arithmetic_ok"],
                    "contains_prabandh_costing": "prabandh.education.gov.in" in text.lower(),
                    "error": None,
                })
                band_summary(rec, reconciled["band_rows"])
            except Exception as e:
                rec.update({
                    "parse_status": "pdf_error", "parse_confidence": "unresolved",
                    "n_csg_total_occurrences": 0, "csg_total_lakhs": np.nan,
                    "csg_total_rupees": np.nan, "evidence": "", "band_rows_json": "[]",
                    "n_band_rows": 0, "band_sum_lakh": np.nan,
                    "band_arithmetic_gap_fraction": np.nan, "band_arithmetic_ok": False,
                    "contains_prabandh_costing": False, "error": repr(e),
                })
            rows.append(rec)
            print(rec["state"], rec["financial_year"], rec.get("link_text"), rec["parse_status"], rec.get("csg_total_lakhs"), flush=True)
    return pd.DataFrame(rows)


def select_state_year(docs: pd.DataFrame, keys: pd.DataFrame) -> pd.DataFrame:
    chosen = []
    for _, key in keys[["state", "financial_year"]].drop_duplicates().iterrows():
        g = docs[(docs.state == key.state) & (docs.financial_year == key.financial_year)].copy()
        parsed = g[g.csg_total_rupees.notna()].copy() if "csg_total_rupees" in g else pd.DataFrame()
        amendment_count = int(g.is_amendment.fillna(False).sum()) if "is_amendment" in g else 0
        revision_count = int(g.is_revision.fillna(False).sum()) if "is_revision" in g else 0
        if parsed.empty:
            chosen.append({
                "state": key.state, "financial_year": key.financial_year,
                "selection_status": "unresolved", "selected_pdf_url": None,
                "selected_filename": None, "selected_link_text": None,
                "pab_csg_lakhs": np.nan, "pab_csg_rupees": np.nan,
                "parse_confidence": "unresolved", "n_document_candidates": len(g),
                "n_amendment_documents": amendment_count, "n_revision_documents": revision_count,
            })
            continue
        parsed["confidence_rank"] = parsed.parse_confidence.map({"high": 2, "medium": 1}).fillna(0)
        parsed["arithmetic_rank"] = parsed.band_arithmetic_ok.fillna(False).astype(int)
        parsed = parsed.sort_values(
            ["arithmetic_rank", "is_revision", "document_priority", "confidence_rank", "contains_prabandh_costing", "pdf_bytes"],
            ascending=[False, False, False, False, False, False],
        )
        top = parsed.iloc[0]
        spread = (
            (parsed.csg_total_rupees.max() - parsed.csg_total_rupees.min()) / top.csg_total_rupees
            if len(parsed) > 1 and top.csg_total_rupees > 0 else 0.0
        )
        if spread > 0.05 and not bool(top.is_revision):
            selection_status = "ambiguous_conflicting_documents"
        elif bool(top.is_revision):
            selection_status = "selected_revised"
        else:
            selection_status = "selected"
        out = {
            "state": key.state, "financial_year": key.financial_year,
            "selection_status": selection_status,
            "selected_pdf_url": top.pdf_url, "selected_filename": top.filename,
            "selected_link_text": top.link_text,
            "pab_csg_lakhs": top.csg_total_lakhs, "pab_csg_rupees": top.csg_total_rupees,
            "parse_confidence": top.parse_confidence,
            "n_csg_total_occurrences": top.n_csg_total_occurrences,
            "n_document_candidates": len(g), "candidate_spread_fraction": spread,
            "n_amendment_documents": amendment_count, "n_revision_documents": revision_count,
            "band_arithmetic_ok": bool(top.band_arithmetic_ok),
            "band_arithmetic_gap_fraction": top.band_arithmetic_gap_fraction,
            "pab_recommended_school_count": top.get("pab_recommended_school_count", np.nan),
            "evidence": top.evidence,
        }
        for band in ("1_30", "31_100", "101_250", "251_1000", "gt1000"):
            for suffix in ("recommended_qty", "recommended_amount_lakh", "unit_lakh"):
                col = f"band_{band}_{suffix}"
                out[col] = top.get(col, np.nan)
        chosen.append(out)
    return pd.DataFrame(chosen)


def fy_start(fy: str) -> int:
    return int(str(fy).split("-")[0])


def academic_start(ay: str) -> int:
    return int(str(ay).split("-")[0])


def next_academic_year(fy: str) -> str:
    y = fy_start(fy) + 1
    return f"{y}-{str(y+1)[-2:]}"


def alignment(selected: pd.DataFrame, formula: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    use = selected[(selected.pab_csg_rupees.notna()) & (selected.selection_status.str.startswith("selected", na=False))]
    for _, p in use.iterrows():
        for _, r in formula[formula.state == p.state].iterrows():
            lag = fy_start(p.financial_year) - academic_start(r.academic_year)
            if lag < 0 or lag > 4:
                continue
            for schedule, col in [("small10", "formula_total_small10_rupees"), ("small25", "formula_total_small25_rupees")]:
                val = float(r[col])
                gap = val - float(p.pab_csg_rupees)
                rows.append({
                    "state": p.state, "financial_year": p.financial_year,
                    "academic_year": r.academic_year,
                    "lag_from_enrolment_to_pab_fy": lag, "schedule": schedule,
                    "pab_csg_rupees": float(p.pab_csg_rupees), "formula_rupees": val,
                    "formula_minus_pab_rupees": gap,
                    "abs_pct_gap": abs(gap) / float(p.pab_csg_rupees) if p.pab_csg_rupees else np.nan,
                    "n_schools_formula": r.n_schools,
                    "pab_recommended_school_count": p.pab_recommended_school_count,
                    "school_count_gap_fraction": (
                        (float(r.n_schools)-float(p.pab_recommended_school_count))/float(p.pab_recommended_school_count)
                        if pd.notna(p.pab_recommended_school_count) and p.pab_recommended_school_count > 0 else np.nan
                    ),
                    "n_1_30": r.n_1_30,
                    "formula_total_31plus_rupees": r.formula_total_31plus_rupees,
                    "implied_small_school_amount_rupees": (
                        (float(p.pab_csg_rupees)-float(r.formula_total_31plus_rupees))/float(r.n_1_30)
                        if r.n_1_30 > 0 else np.nan
                    ),
                })
    cand = pd.DataFrame(rows)
    nat_rows = []
    if not cand.empty:
        for (fy, lag, schedule), g in cand.groupby(["financial_year", "lag_from_enrolment_to_pab_fy", "schedule"]):
            p = g.pab_csg_rupees.to_numpy(float)
            f = g.formula_rupees.to_numpy(float)
            nat_rows.append({
                "financial_year": fy, "lag_from_enrolment_to_pab_fy": int(lag),
                "schedule": schedule, "n_states": len(g),
                "pab_total_rupees": float(p.sum()), "formula_total_rupees": float(f.sum()),
                "aggregate_abs_pct_gap": float(abs(f.sum()-p.sum())/p.sum()) if p.sum() else np.nan,
                "median_state_abs_pct_gap": float(g.abs_pct_gap.median()),
                "mean_state_abs_pct_gap": float(g.abs_pct_gap.mean()),
                "median_abs_school_count_gap_fraction": float(g.school_count_gap_fraction.abs().median()) if g.school_count_gap_fraction.notna().any() else np.nan,
                "pearson_state_totals": float(pd.Series(p).corr(pd.Series(f))) if len(g) >= 3 else np.nan,
            })
    return cand, pd.DataFrame(nat_rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    formula_path = BASE_DIR / "formula_totals_state_year.csv"
    recorded_path = BASE_DIR / "recorded_totals_state_year.csv"
    if not formula_path.exists() or not recorded_path.exists():
        raise FileNotFoundError(f"Mechanism-base inputs missing under {BASE_DIR}")
    formula = pd.read_csv(formula_path)
    recorded = pd.read_csv(recorded_path)
    allowed_states = set(formula.state.dropna().astype(str).map(logic.canonical_state))

    s = session()
    archive = crawl_archive(s, allowed_states)
    archive.to_csv(OUT / "pab_archive_inventory.csv", index=False)
    keys = archive[["state", "financial_year"]].drop_duplicates()
    inventory_counts = keys.groupby("financial_year").state.nunique()
    for fy in TARGET_FYS:
        if int(inventory_counts.get(fy, 0)) < 25:
            raise RuntimeError(f"PAB archive inventory for {fy} has only {inventory_counts.get(fy,0)} State/UT labels")

    docs = extract_documents(s, archive)
    docs.to_csv(OUT / "pab_document_candidates.csv", index=False)
    selected = select_state_year(docs, keys)
    selected.to_csv(OUT / "pab_state_year_selected.csv", index=False)

    parsed_rate = selected.groupby("financial_year").pab_csg_rupees.apply(lambda x: x.notna().mean())
    if (parsed_rate < 0.50).any():
        raise RuntimeError(f"PAB CSG parser resolved fewer than half of State/UTs in a target year: {parsed_rate.to_dict()}")

    cand, nat = alignment(selected, formula)
    if nat.empty:
        raise RuntimeError("No formula-to-PAB alignment candidates were constructed")
    cand.to_csv(OUT / "formula_pab_alignment_candidates.csv", index=False)
    nat.to_csv(OUT / "formula_pab_alignment_national.csv", index=False)

    eligible_nat = nat[nat.n_states >= 15].copy()
    if eligible_nat.empty:
        raise RuntimeError("No PAB year has at least 15 selected State/UTs for national alignment")
    best_map = (
        eligible_nat.sort_values(["financial_year", "median_state_abs_pct_gap", "aggregate_abs_pct_gap", "median_abs_school_count_gap_fraction"])
        .groupby("financial_year", as_index=False).first()
    )
    best_map.to_csv(OUT / "best_global_alignment_by_pab_year.csv", index=False)

    reconciled_rows = []
    for _, p in selected.iterrows():
        b = best_map[best_map.financial_year == p.financial_year]
        rec = p.to_dict()
        rec["report_year"] = next_academic_year(p.financial_year)
        if b.empty or pd.isna(p.pab_csg_rupees) or not str(p.selection_status).startswith("selected"):
            rec["mechanism_status"] = "unresolved"
            reconciled_rows.append(rec)
            continue
        m = b.iloc[0]
        candidate_year = fy_start(p.financial_year) - int(m.lag_from_enrolment_to_pab_fy)
        ay = f"{candidate_year}-{str(candidate_year+1)[-2:]}"
        f = formula[(formula.state == p.state) & (formula.academic_year == ay)]
        rr = recorded[(recorded.state == p.state) & (recorded.academic_year == rec["report_year"])]
        rec.update({"selected_formula_academic_year": ay, "selected_formula_schedule": m.schedule, "selected_lag": int(m.lag_from_enrolment_to_pab_fy)})
        if not f.empty:
            col = "formula_total_small10_rupees" if m.schedule == "small10" else "formula_total_small25_rupees"
            rec["formula_rupees"] = float(f.iloc[0][col])
            rec["formula_pab_gap_fraction"] = ((rec["formula_rupees"]-float(p.pab_csg_rupees))/float(p.pab_csg_rupees)) if p.pab_csg_rupees else np.nan
            if pd.notna(p.pab_recommended_school_count) and p.pab_recommended_school_count > 0:
                rec["formula_pab_school_count_gap_fraction"] = ((float(f.iloc[0].n_schools)-float(p.pab_recommended_school_count))/float(p.pab_recommended_school_count))
        if not rr.empty:
            rec["recorded_receipt_total_rupees"] = rr.iloc[0].recorded_receipt_total_rupees
            rec["recorded_expenditure_total_rupees"] = rr.iloc[0].recorded_expenditure_total_rupees
            rec["receipt_reporting_rate"] = rr.iloc[0].receipt_reporting_rate
            rec["pab_recorded_receipt_gap_fraction"] = ((float(rr.iloc[0].recorded_receipt_total_rupees)-float(p.pab_csg_rupees))/float(p.pab_csg_rupees)) if pd.notna(rr.iloc[0].recorded_receipt_total_rupees) and p.pab_csg_rupees else np.nan
        fg = abs(rec.get("formula_pab_gap_fraction", np.nan))
        rg = abs(rec.get("pab_recorded_receipt_gap_fraction", np.nan))
        if np.isfinite(fg) and np.isfinite(rg):
            if fg <= 0.10 and rg > 0.20:
                status = "divergence_after_PAB_or_reporting"
            elif fg > 0.20:
                status = "formula_to_PAB_difference"
            elif fg <= 0.10 and rg <= 0.20:
                status = "broadly_reconciled"
            else:
                status = "mixed"
        else:
            status = "unresolved"
        rec["mechanism_status"] = status
        reconciled_rows.append(rec)
    reconciled = pd.DataFrame(reconciled_rows)
    reconciled.to_csv(OUT / "all_state_mechanism_reconciliation.csv", index=False)
    summary = reconciled.groupby(["financial_year", "mechanism_status"], dropna=False).size().rename("n_state_uts").reset_index()
    summary.to_csv(OUT / "mechanism_status_summary.csv", index=False)

    band_validation = selected[[c for c in selected.columns if c in {"state", "financial_year", "selection_status", "band_arithmetic_ok", "band_arithmetic_gap_fraction", "pab_recommended_school_count"} or c.startswith("band_")]].copy()
    band_validation.to_csv(OUT / "pab_band_validation.csv", index=False)

    validation = {
        "target_financial_years": list(TARGET_FYS),
        "archive_state_year_rows": int(len(keys)),
        "selected_state_year_rows": int(len(selected)),
        "resolved_state_year_rows": int(selected.pab_csg_rupees.notna().sum()),
        "resolved_rate_by_year": {k: float(v) for k, v in parsed_rate.to_dict().items()},
        "band_arithmetic_ok_rows": int(selected.band_arithmetic_ok.fillna(False).sum()) if "band_arithmetic_ok" in selected else 0,
        "ambiguous_conflicting_document_rows": int((selected.selection_status == "ambiguous_conflicting_documents").sum()),
        "selected_revised_rows": int((selected.selection_status == "selected_revised").sum()),
        "selection_preserves_unresolved_rows": True,
        "global_alignment_prevents_state_specific_overfit": True,
        "alignment_primary_objective": "median State/UT absolute percentage PAB-formula gap",
        "source": "Department of School Education & Literacy official PAB archive / PRABANDH costing sheets",
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    lines = [
        "# All-State PAB mechanism audit", "",
        f"Target PAB years: {', '.join(TARGET_FYS)}.",
        f"State/UT-year rows inventoried: {validation['archive_state_year_rows']}.",
        f"State/UT-year rows with a parsed CSG recommended total: {validation['resolved_state_year_rows']}.",
        f"Selected rows with band arithmetic internally reconciled: {validation['band_arithmetic_ok_rows']}.",
        f"Conflicting-document rows left ambiguous: {validation['ambiguous_conflicting_document_rows']}.",
        "", "## Best national enrolment-to-PAB alignment",
    ]
    for _, r in best_map.iterrows():
        lines.append(f"- {r.financial_year}: lag {int(r.lag_from_enrolment_to_pab_fy)}, {r.schedule}; median State/UT absolute gap {100*r.median_state_abs_pct_gap:.1f}%, aggregate gap {100*r.aggregate_abs_pct_gap:.1f}% across {int(r.n_states)} State/UTs.")
    lines += ["", "## Diagnostic mechanism status counts"]
    for _, r in summary.iterrows():
        lines.append(f"- {r.financial_year} / {r.mechanism_status}: {int(r.n_state_uts)}.")
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
