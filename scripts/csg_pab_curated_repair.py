from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "studies/composite_school_grant/policy_deepening/pab_mechanism.py"
spec = importlib.util.spec_from_file_location("pab_mechanism", MOD_PATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

# These are fixed, manually verified DoSE&L PAB year pages, not a crawl.
# Term IDs are the Ministry's financial-year taxonomy IDs.
SOURCE_PAGES = {
    "2021-22": "https://dsel.education.gov.in/hi/pab-minutes?field_financial_year_target_id=226&field_states_target_id=All",
    "2022-23": "https://dsel.education.gov.in/pab-minutes?field_financial_year_target_id=304&field_states_target_id=All",
    "2023-24": "https://dsel.education.gov.in/hi/pab-minutes?field_financial_year_target_id=329&field_states_target_id=All",
    "2024-25": "https://dsel.education.gov.in/hi/pab-minutes?field_financial_year_target_id=335&field_states_target_id=All",
}

# The current Ministry pages render the State/UT column in Hindi on several
# year-filtered views. Preserve exact aliases here so source rows map explicitly
# rather than by row order or fuzzy matching.
HINDI_STATE = {
    "अंडमान और निकोबार द्वीप समूह": "ANDAMAN & NICOBAR ISLANDS",
    "आंध्र प्रदेश": "ANDHRA PRADESH",
    "अरुणाचल प्रदेश": "ARUNACHAL PRADESH",
    "असम": "ASSAM",
    "बिहार": "BIHAR",
    "चंडीगढ़": "CHANDIGARH",
    "छत्तीसगढ": "CHHATTISGARH",
    "छत्तीसगढ़": "CHHATTISGARH",
    "दादरा और नगर हवेली": "DADRA & NAGAR HAVELI",
    "दमन और दीव": "DAMAN & DIU",
    "दिल्ली": "DELHI",
    "गोवा": "GOA",
    "गुजरात": "GUJARAT",
    "हरियाणा": "HARYANA",
    "हिमाचल प्रदेश": "HIMACHAL PRADESH",
    "जम्मू और कश्मीर": "JAMMU & KASHMIR",
    "झारखंड": "JHARKHAND",
    "कर्नाटक": "KARNATAKA",
    "केरल": "KERALA",
    "लद्दाख": "LADAKH",
    "लक्षद्वीप": "LAKSHADWEEP",
    "मध्य प्रदेश": "MADHYA PRADESH",
    "महाराष्ट्र": "MAHARASHTRA",
    "मणिपुर": "MANIPUR",
    "मेघालय": "MEGHALAYA",
    "मिजोरम": "MIZORAM",
    "नगालैंड": "NAGALAND",
    "नागालैंड": "NAGALAND",
    "ओडिशा": "ODISHA",
    "पुदुचेरी": "PUDUCHERRY",
    "पंजाब": "PUNJAB",
    "राजस्थान": "RAJASTHAN",
    "सिक्किम": "SIKKIM",
    "तमिलनाडु": "TAMIL NADU",
    "तमिल नाडु": "TAMIL NADU",
    "तेलंगाना": "TELANGANA",
    "त्रिपुरा": "TRIPURA",
    "उत्तर प्रदेश": "UTTAR PRADESH",
    "उत्तराखंड": "UTTARAKHAND",
    "पश्चिम बंगाल": "WEST BENGAL",
}


def source_state(raw: str, fy: str) -> tuple[str, str]:
    raw_clean = " ".join(str(raw).split())
    component = HINDI_STATE.get(raw_clean, m.logic.canonical_state(raw_clean) or "")
    canonical = component
    if fy >= "2020-21" and component in {"DADRA & NAGAR HAVELI", "DAMAN & DIU"}:
        canonical = "DADRA & NAGAR HAVELI & DAMAN & DIU"
    return component, canonical


def curated_archive(s, allowed_states: set[str]) -> pd.DataFrame:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for fy, url in SOURCE_PAGES.items():
        r = s.get(url, timeout=90)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        matched = 0
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            row_text = " ".join(tr.stripped_strings)
            row_fy = m.pp.normalize_financial_year(row_text)
            if row_fy != fy:
                continue
            raw_state = " ".join(cells[1].stripped_strings)
            component_state, state = source_state(raw_state, fy)
            if state not in allowed_states:
                continue
            links = []
            for a in tr.find_all("a", href=True):
                href = urljoin(url, a.get("href"))
                label = " ".join(a.stripped_strings)
                if "/sites/default/files/" in href or ".pdf" in href.lower() or "/node/" in href:
                    links.append((href, label))
            if not links:
                key = (state, fy, component_state, "no_document")
                if key not in seen:
                    seen.add(key)
                    rows.append({
                        "state": state,
                        "component_state": component_state,
                        "financial_year": fy,
                        "source_page": url,
                        "archive_page": -1,
                        "node_url": None,
                        "direct_pdf_url": None,
                        "archive_link_text": "",
                        "archive_status": "curated_no_document_link",
                    })
                    matched += 1
                continue
            for href, label in links:
                if "/node/" in href and ".pdf" not in href.lower():
                    node_url, pdf_url = href, None
                else:
                    node_url, pdf_url = None, href
                key = (state, fy, component_state, node_url, pdf_url, label)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "state": state,
                    "component_state": component_state,
                    "financial_year": fy,
                    "source_page": url,
                    "archive_page": -1,
                    "node_url": node_url,
                    "direct_pdf_url": pdf_url,
                    "archive_link_text": label,
                    "archive_status": "curated_fixed_source",
                })
                matched += 1
        print("CURATED SOURCE", fy, "matched rows", matched, "from", url, flush=True)
        if matched == 0:
            raise RuntimeError(f"Curated Ministry source page yielded zero State/UT rows for {fy}: {url}")

    out = pd.DataFrame(rows).drop_duplicates()
    if out.empty:
        raise RuntimeError("Curated Ministry PAB source manifest is empty")

    # Coverage is checked against unique canonical State/UTs, while every source
    # document remains preserved in the inventory.
    counts = out[["state", "financial_year"]].drop_duplicates().groupby("financial_year").state.nunique()
    for fy in SOURCE_PAGES:
        if int(counts.get(fy, 0)) < 25:
            raise RuntimeError(f"Curated Ministry source coverage for {fy} is only {counts.get(fy, 0)} State/UTs")
    return out


def _rank_component(g: pd.DataFrame) -> pd.Series | None:
    parsed = g[g.csg_total_rupees.notna()].copy() if "csg_total_rupees" in g else pd.DataFrame()
    if parsed.empty:
        return None
    parsed["confidence_rank"] = parsed.parse_confidence.map({"high": 2, "medium": 1}).fillna(0)
    parsed["arithmetic_rank"] = parsed.band_arithmetic_ok.fillna(False).astype(int)
    parsed = parsed.sort_values(
        ["arithmetic_rank", "is_revision", "document_priority", "confidence_rank", "contains_prabandh_costing", "pdf_bytes"],
        ascending=[False, False, False, False, False, False],
    )
    return parsed.iloc[0]


def curated_select(docs: pd.DataFrame, keys: pd.DataFrame) -> pd.DataFrame:
    base = m.select_state_year(docs, keys)
    target_state = "DADRA & NAGAR HAVELI & DAMAN & DIU"
    fy = "2021-22"
    g = docs[(docs.state == target_state) & (docs.financial_year == fy)].copy()
    if g.empty or "component_state" not in g:
        return base
    components = []
    for comp in ("DADRA & NAGAR HAVELI", "DAMAN & DIU"):
        top = _rank_component(g[g.component_state == comp])
        if top is None:
            return base
        components.append(top)

    out = {
        "state": target_state,
        "financial_year": fy,
        "selection_status": "selected_combined_components",
        "selected_pdf_url": " | ".join(str(x.pdf_url) for x in components),
        "selected_filename": " | ".join(str(x.filename) for x in components),
        "selected_link_text": "combined pre-merger component PAB documents",
        "pab_csg_lakhs": float(sum(float(x.csg_total_lakhs) for x in components)),
        "pab_csg_rupees": float(sum(float(x.csg_total_rupees) for x in components)),
        "parse_confidence": "high" if all(x.parse_confidence == "high" for x in components) else "medium",
        "n_csg_total_occurrences": int(sum(int(x.n_csg_total_occurrences) for x in components)),
        "n_document_candidates": int(len(g)),
        "candidate_spread_fraction": np.nan,
        "n_amendment_documents": int(g.is_amendment.fillna(False).sum()),
        "n_revision_documents": int(g.is_revision.fillna(False).sum()),
        "band_arithmetic_ok": bool(all(bool(x.band_arithmetic_ok) for x in components)),
        "band_arithmetic_gap_fraction": float(max(abs(float(x.band_arithmetic_gap_fraction)) for x in components if pd.notna(x.band_arithmetic_gap_fraction))) if any(pd.notna(x.band_arithmetic_gap_fraction) for x in components) else np.nan,
        "pab_recommended_school_count": float(sum(float(x.pab_recommended_school_count) for x in components if pd.notna(x.pab_recommended_school_count))),
        "evidence": " || ".join(str(x.evidence) for x in components),
    }
    for band in ("1_30", "31_100", "101_250", "251_1000", "gt1000"):
        qty = f"band_{band}_recommended_qty"
        amt = f"band_{band}_recommended_amount_lakh"
        unit = f"band_{band}_unit_lakh"
        out[qty] = float(sum(float(x.get(qty, 0.0)) for x in components if pd.notna(x.get(qty, np.nan))))
        out[amt] = float(sum(float(x.get(amt, 0.0)) for x in components if pd.notna(x.get(amt, np.nan))))
        units = {round(float(x.get(unit)), 8) for x in components if pd.notna(x.get(unit, np.nan))}
        out[unit] = next(iter(units)) if len(units) == 1 else np.nan

    mask = (base.state == target_state) & (base.financial_year == fy)
    replacement = pd.DataFrame([out])
    return pd.concat([base.loc[~mask], replacement], ignore_index=True)


m.crawl_archive = curated_archive
m.select_state_year = curated_select

if __name__ == "__main__":
    m.main()
