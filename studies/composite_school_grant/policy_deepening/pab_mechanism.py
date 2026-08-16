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
TARGET_FYS = ("2023-24", "2024-25")
NON_STATE = {
    "TECHNICAL SUPPORT GROUP", "NCERT", "NCPCR", "PM SHRI", "EDCIL",
}
UA = "Mozilla/5.0 (compatible; CSGPolicyAudit/1.0; research use)"


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


def crawl_archive(s: requests.Session) -> pd.DataFrame:
    rows = []
    seen_nodes = set()
    empty_streak = 0
    for page in range(0, 12):
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
            if not state or state in NON_STATE:
                continue
            links = [urljoin(BASE_URL, a.get("href")) for a in tr.find_all("a", href=True)]
            node_links = [u for u in links if "/node/" in u]
            direct_pdfs = [u for u in links if ".pdf" in u.lower()]
            if not node_links and not direct_pdfs:
                rows.append({
                    "state": state, "financial_year": fy, "archive_page": page,
                    "node_url": None, "direct_pdf_url": None, "archive_status": "no_document_link",
                })
                page_rows += 1
                continue
            if node_links:
                for node in node_links:
                    key = (state, fy, node)
                    if key in seen_nodes:
                        continue
                    seen_nodes.add(key)
                    rows.append({
                        "state": state, "financial_year": fy, "archive_page": page,
                        "node_url": node, "direct_pdf_url": None, "archive_status": "node",
                    })
                    page_rows += 1
            else:
                for pdf in direct_pdfs:
                    key = (state, fy, pdf)
                    if key in seen_nodes:
                        continue
                    seen_nodes.add(key)
                    rows.append({
                        "state": state, "financial_year": fy, "archive_page": page,
                        "node_url": None, "direct_pdf_url": pdf, "archive_status": "direct_pdf",
                    })
                    page_rows += 1
        if page_rows == 0:
            empty_streak += 1
        else:
            empty_streak = 0
        if page >= 4 and empty_streak >= 3:
            break
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("PAB archive crawler found no target-year State/UT rows")
    return out.drop_duplicates()


def node_documents(s: requests.Session, row: pd.Series) -> list[dict]:
    if pd.notna(row.get("direct_pdf_url")):
        u = str(row.direct_pdf_url)
        return [{"pdf_url": u, "filename": u.rsplit("/", 1)[-1], "link_text": "", "node_url": None}]
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
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text, total


def extract_documents(s: requests.Session, archive: pd.DataFrame) -> pd.DataFrame:
    rows = []
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
            rec = {**ar.to_dict(), **doc}
            rec["document_priority"] = pp.document_priority(doc["filename"], doc["link_text"])
            try:
                text, size = pdf_to_text(s, doc["pdf_url"])
                amounts, confidence, evidence = pp.extract_csg_totals_from_text(text)
                rec.update({
                    "pdf_bytes": size,
                    "parse_status": "parsed" if amounts else "no_csg_total",
                    "parse_confidence": confidence,
                    "n_csg_total_occurrences": len(amounts),
                    "csg_total_lakhs": float(sum(amounts)) if amounts else np.nan,
                    "csg_total_rupees": float(sum(amounts) * 100_000) if amounts else np.nan,
                    "evidence": " || ".join(evidence[:8]),
                    "contains_prabandh_costing": "prabandh.education.gov.in" in text.lower(),
                    "error": None,
                })
            except Exception as e:
                rec.update({
                    "parse_status": "pdf_error",
                    "parse_confidence": "unresolved",
                    "n_csg_total_occurrences": 0,
                    "csg_total_lakhs": np.nan,
                    "csg_total_rupees": np.nan,
                    "evidence": "",
                    "contains_prabandh_costing": False,
                    "error": repr(e),
                })
            rows.append(rec)
            print(rec["state"], rec["financial_year"], rec.get("filename"), rec["parse_status"], rec.get("csg_total_lakhs"), flush=True)
    return pd.DataFrame(rows)


def select_state_year(docs: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame:
    keys = archive[["state", "financial_year"]].drop_duplicates()
    chosen = []
    for _, key in keys.iterrows():
        g = docs[(docs.state == key.state) & (docs.financial_year == key.financial_year)].copy()
        parsed = g[g.csg_total_rupees.notna()].copy() if "csg_total_rupees" in g else pd.DataFrame()
        if parsed.empty:
            chosen.append({
                "state": key.state, "financial_year": key.financial_year,
                "selection_status": "unresolved",
                "selected_pdf_url": None, "selected_filename": None,
                "pab_csg_lakhs": np.nan, "pab_csg_rupees": np.nan,
                "parse_confidence": "unresolved",
                "n_document_candidates": len(g),
            })
            continue
        parsed["confidence_rank"] = parsed.parse_confidence.map({"high": 2, "medium": 1}).fillna(0)
        parsed = parsed.sort_values(
            ["document_priority", "confidence_rank", "contains_prabandh_costing", "pdf_bytes"],
            ascending=[False, False, False, False],
        )
        top = parsed.iloc[0]
        competing = parsed[np.isclose(parsed.document_priority, top.document_priority)]
        spread = (
            (competing.csg_total_rupees.max() - competing.csg_total_rupees.min()) / top.csg_total_rupees
            if len(competing) > 1 and top.csg_total_rupees > 0 else 0.0
        )
        chosen.append({
            "state": key.state, "financial_year": key.financial_year,
            "selection_status": "ambiguous" if spread > 0.05 else "selected",
            "selected_pdf_url": top.pdf_url,
            "selected_filename": top.filename,
            "pab_csg_lakhs": top.csg_total_lakhs,
            "pab_csg_rupees": top.csg_total_rupees,
            "parse_confidence": top.parse_confidence,
            "n_csg_total_occurrences": top.n_csg_total_occurrences,
            "n_document_candidates": len(g),
            "candidate_spread_fraction": spread,
            "evidence": top.evidence,
        })
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
    for _, p in selected[selected.pab_csg_rupees.notna()].iterrows():
        f = formula[formula.state == p.state]
        for _, r in f.iterrows():
            lag = fy_start(p.financial_year) - academic_start(r.academic_year)
            if lag < 0 or lag > 4:
                continue
            for schedule, col in [
                ("small10", "formula_total_small10_rupees"),
                ("small25", "formula_total_small25_rupees"),
            ]:
                val = float(r[col])
                gap = val - float(p.pab_csg_rupees)
                rows.append({
                    "state": p.state,
                    "financial_year": p.financial_year,
                    "academic_year": r.academic_year,
                    "lag_from_enrolment_to_pab_fy": lag,
                    "schedule": schedule,
                    "pab_csg_rupees": float(p.pab_csg_rupees),
                    "formula_rupees": val,
                    "formula_minus_pab_rupees": gap,
                    "abs_pct_gap": abs(gap) / float(p.pab_csg_rupees) if p.pab_csg_rupees else np.nan,
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
                "financial_year": fy,
                "lag_from_enrolment_to_pab_fy": int(lag),
                "schedule": schedule,
                "n_states": len(g),
                "pab_total_rupees": float(p.sum()),
                "formula_total_rupees": float(f.sum()),
                "aggregate_abs_pct_gap": float(abs(f.sum()-p.sum())/p.sum()) if p.sum() else np.nan,
                "median_state_abs_pct_gap": float(g.abs_pct_gap.median()),
                "pearson_state_totals": float(pd.Series(p).corr(pd.Series(f))) if len(g) >= 3 else np.nan,
            })
    nat = pd.DataFrame(nat_rows)
    return cand, nat


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    formula_path = BASE_DIR / "formula_totals_state_year.csv"
    recorded_path = BASE_DIR / "recorded_totals_state_year.csv"
    if not formula_path.exists() or not recorded_path.exists():
        raise FileNotFoundError(f"Mechanism-base inputs missing under {BASE_DIR}")
    formula = pd.read_csv(formula_path)
    recorded = pd.read_csv(recorded_path)

    s = session()
    archive = crawl_archive(s)
    archive.to_csv(OUT / "pab_archive_inventory.csv", index=False)
    inventory_counts = archive.groupby("financial_year").state.nunique()
    for fy in TARGET_FYS:
        if int(inventory_counts.get(fy, 0)) < 25:
            raise RuntimeError(f"PAB archive inventory for {fy} has only {inventory_counts.get(fy,0)} State/UT labels")

    docs = extract_documents(s, archive)
    docs.to_csv(OUT / "pab_document_candidates.csv", index=False)
    selected = select_state_year(docs, archive)
    selected.to_csv(OUT / "pab_state_year_selected.csv", index=False)

    parsed_rate = selected.groupby("financial_year").pab_csg_rupees.apply(lambda x: x.notna().mean())
    if (parsed_rate < 0.50).any():
        raise RuntimeError(f"PAB CSG parser resolved fewer than half of State/UTs in a target year: {parsed_rate.to_dict()}")

    cand, nat = alignment(selected, formula)
    cand.to_csv(OUT / "formula_pab_alignment_candidates.csv", index=False)
    nat.to_csv(OUT / "formula_pab_alignment_national.csv", index=False)

    best_map = (
        nat.sort_values(["financial_year", "aggregate_abs_pct_gap", "median_state_abs_pct_gap"])
           .groupby("financial_year", as_index=False)
           .first()
    )
    best_map.to_csv(OUT / "best_global_alignment_by_pab_year.csv", index=False)

    reconciled_rows = []
    for _, p in selected.iterrows():
        b = best_map[best_map.financial_year == p.financial_year]
        rec = p.to_dict()
        rec["report_year"] = next_academic_year(p.financial_year)
        if b.empty or pd.isna(p.pab_csg_rupees):
            rec["mechanism_status"] = "unresolved"
            reconciled_rows.append(rec)
            continue
        m = b.iloc[0]
        candidate_year = fy_start(p.financial_year) - int(m.lag_from_enrolment_to_pab_fy)
        ay = f"{candidate_year}-{str(candidate_year+1)[-2:]}"
        f = formula[(formula.state == p.state) & (formula.academic_year == ay)]
        rr = recorded[(recorded.state == p.state) & (recorded.academic_year == rec["report_year"])]
        rec.update({
            "selected_formula_academic_year": ay,
            "selected_formula_schedule": m.schedule,
            "selected_lag": int(m.lag_from_enrolment_to_pab_fy),
        })
        if not f.empty:
            col = "formula_total_small10_rupees" if m.schedule == "small10" else "formula_total_small25_rupees"
            rec["formula_rupees"] = float(f.iloc[0][col])
            rec["formula_pab_gap_fraction"] = (
                (rec["formula_rupees"] - float(p.pab_csg_rupees)) / float(p.pab_csg_rupees)
                if p.pab_csg_rupees else np.nan
            )
        if not rr.empty:
            rec["recorded_receipt_total_rupees"] = rr.iloc[0].recorded_receipt_total_rupees
            rec["recorded_expenditure_total_rupees"] = rr.iloc[0].recorded_expenditure_total_rupees
            rec["receipt_reporting_rate"] = rr.iloc[0].receipt_reporting_rate
            rec["pab_recorded_receipt_gap_fraction"] = (
                (float(rr.iloc[0].recorded_receipt_total_rupees) - float(p.pab_csg_rupees)) / float(p.pab_csg_rupees)
                if pd.notna(rr.iloc[0].recorded_receipt_total_rupees) and p.pab_csg_rupees else np.nan
            )
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

    summary = (
        reconciled.groupby(["financial_year", "mechanism_status"], dropna=False)
        .size().rename("n_state_uts").reset_index()
    )
    summary.to_csv(OUT / "mechanism_status_summary.csv", index=False)

    validation = {
        "target_financial_years": list(TARGET_FYS),
        "archive_state_year_rows": int(len(archive[["state","financial_year"]].drop_duplicates())),
        "selected_state_year_rows": int(len(selected)),
        "resolved_state_year_rows": int(selected.pab_csg_rupees.notna().sum()),
        "resolved_rate_by_year": {k: float(v) for k, v in parsed_rate.to_dict().items()},
        "selection_preserves_unresolved_rows": True,
        "global_alignment_prevents_state_specific_overfit": True,
        "source": "Department of School Education & Literacy official PAB archive / PRABANDH costing sheets",
    }
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    lines = [
        "# All-State PAB mechanism audit",
        "",
        f"Target PAB years: {', '.join(TARGET_FYS)}.",
        f"State/UT-year rows inventoried: {validation['archive_state_year_rows']}.",
        f"State/UT-year rows with a parsed CSG recommended total: {validation['resolved_state_year_rows']}.",
        "",
        "## Best national enrolment-to-PAB alignment",
    ]
    for _, r in best_map.iterrows():
        lines.append(
            f"- {r.financial_year}: lag {int(r.lag_from_enrolment_to_pab_fy)}, "
            f"{r.schedule}, aggregate absolute gap {100*r.aggregate_abs_pct_gap:.1f}% "
            f"across {int(r.n_states)} parsed State/UTs."
        )
    lines += ["", "## Mechanism status counts"]
    for _, r in summary.iterrows():
        lines.append(f"- {r.financial_year} / {r.mechanism_status}: {int(r.n_state_uts)}.")
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
