from __future__ import annotations

import csv
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "studies/composite_school_grant/data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = DATA_DIR / "pab_csg_source_manifest.csv"
DATA_PATH = DATA_DIR / "pab_csg_state_year.csv"
AUDIT_PATH = DATA_DIR / "pab_csg_static_build_audit.json"

spec = importlib.util.spec_from_file_location(
    "pab_parser",
    ROOT / "studies/composite_school_grant/policy_deepening/pab_parser.py",
)
pp = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pp)

# Fixed Ministry pages used only for one-time dataset construction.
# 2021-22 spans two archive pages because the old year-filtered view is unreliable.
SOURCE_PAGES = {
    "2021-22": [
        "https://dsel.education.gov.in/en/pab-minutes?field_financial_year_target_id=All&field_states_target_id=All&page=3",
        "https://dsel.education.gov.in/en/pab-minutes?field_financial_year_target_id=All&field_states_target_id=All&page=4",
    ],
    "2022-23": [
        "https://dsel.education.gov.in/pab-minutes?field_financial_year_target_id=304&field_states_target_id=All",
    ],
    "2023-24": [
        "https://dsel.education.gov.in/hi/pab-minutes?field_financial_year_target_id=329&field_states_target_id=All",
    ],
    "2024-25": [
        "https://dsel.education.gov.in/hi/pab-minutes?field_financial_year_target_id=335&field_states_target_id=All",
    ],
}

STATE_ALIASES = {
    "ANDAMAN AND NICOBAR ISLANDS": "ANDAMAN & NICOBAR ISLANDS",
    "DADRA AND NAGAR HAVELI": "DADRA & NAGAR HAVELI & DAMAN & DIU",
    "DAMAN AND DIU": "DADRA & NAGAR HAVELI & DAMAN & DIU",
    "JAMMU AND KASHMIR": "JAMMU & KASHMIR",
    "ORISSA": "ODISHA",
    "TAMILNADU": "TAMIL NADU",
    "KERLA": "KERALA",
    "अंडमान और निकोबार द्वीप समूह": "ANDAMAN & NICOBAR ISLANDS",
    "आंध्र प्रदेश": "ANDHRA PRADESH",
    "अरुणाचल प्रदेश": "ARUNACHAL PRADESH",
    "असम": "ASSAM",
    "बिहार": "BIHAR",
    "चंडीगढ़": "CHANDIGARH",
    "छत्तीसगढ": "CHHATTISGARH",
    "छत्तीसगढ़": "CHHATTISGARH",
    "दादरा और नगर हवेली": "DADRA & NAGAR HAVELI & DAMAN & DIU",
    "दमन और दीव": "DADRA & NAGAR HAVELI & DAMAN & DIU",
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

NON_STATE = {
    "NCERT", "NCPCR", "NIEPA", "TECHNICAL SUPPORT GROUP",
    "NATIONAL ACHIEVEMENT SURVEY", "NATIONAL INFORMATICS CENTRE",
    "PM SHRI", "PM JANMAN, DAJGUA", "EDCIL",
    "एनसीईआरटी", "एनसीपीसीआर", "नीपा", "तकनीकी सहायता समूह",
    "राष्ट्रीय उपलब्धि सर्वेक्षण", "राष्ट्रीय सूचना विज्ञान केंद्र", "पीएम श्री स्कूल",
}

REVISION_WORDS = ("revised", "revision", "revised mom", "revised minutes")
AMENDMENT_WORDS = ("addendum", "corrigendum", "supplement")


def canon_state(raw: str) -> str | None:
    s = " ".join(str(raw).strip().split())
    if s in NON_STATE:
        return None
    if s in STATE_ALIASES:
        return STATE_ALIASES[s]
    u = s.upper().replace(" AND ", " & ")
    if u in NON_STATE:
        return None
    return STATE_ALIASES.get(u, u)


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, connect=5, read=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "Mozilla/5.0 (PAB-CSG-static-dataset-build; research)"})
    return s


def norm_fy(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2})", str(text))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)[-2:]}"


def inventory(s: requests.Session) -> pd.DataFrame:
    rows = []
    seen = set()
    for target_fy, pages in SOURCE_PAGES.items():
        for page in pages:
            r = s.get(page, timeout=90)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for tr in soup.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 3:
                    continue
                fy = norm_fy(" ".join(tr.stripped_strings))
                if fy != target_fy:
                    continue
                state_raw = " ".join(cells[1].stripped_strings)
                state = canon_state(state_raw)
                if not state:
                    continue
                for a in tr.find_all("a", href=True):
                    href = urljoin(page, a.get("href"))
                    label = " ".join(a.stripped_strings).strip() or "Minutes"
                    if not (".pdf" in href.lower() or "/sites/default/files/" in href or "/node/" in href):
                        continue
                    label_l = label.lower()
                    doc_type = (
                        "revision" if any(w in label_l for w in REVISION_WORDS)
                        else "amendment" if any(w in label_l for w in AMENDMENT_WORDS)
                        else "minutes"
                    )
                    key = (state, target_fy, href, doc_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "state": state,
                        "source_state_label": state_raw,
                        "financial_year": target_fy,
                        "document_type": doc_type,
                        "document_label": label,
                        "document_url": href,
                        "source_page_url": page,
                    })
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("No PAB source documents were inventoried")
    out = out.sort_values(["financial_year", "state", "document_type", "document_url"]).reset_index(drop=True)
    out.to_csv(MANIFEST_PATH, index=False, quoting=csv.QUOTE_MINIMAL)
    return out


def pdf_text(s: requests.Session, url: str) -> tuple[str, int]:
    with tempfile.TemporaryDirectory(prefix="pab_static_") as td:
        p = Path(td) / "doc.pdf"
        with s.get(url, stream=True, timeout=180, allow_redirects=True) as r:
            r.raise_for_status()
            n = 0
            with p.open("wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    n += len(chunk)
                    if n > 160 * 1024 * 1024:
                        raise RuntimeError("document_exceeds_160mb")
                    f.write(chunk)
        if shutil.which("pdftotext"):
            q = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, errors="replace", timeout=240)
            if q.returncode == 0 and q.stdout.strip():
                return q.stdout, n
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages), n


def parse_document(s: requests.Session, row: pd.Series) -> dict:
    rec = row.to_dict()
    try:
        text, nbytes = pdf_text(s, row.document_url)
        z = pp.reconcile_band_rows_to_totals(text)
        totals = z.get("total_amounts_lakh", [])
        rec.update({
            "download_status": "ok",
            "pdf_bytes": nbytes,
            "parse_status": "parsed" if totals else "no_csg_total",
            "parse_confidence": z.get("total_confidence", "unresolved"),
            "csg_total_lakh": float(z.get("total_sum_lakh")) if totals else None,
            "csg_total_rupees": float(z.get("total_sum_lakh") * 100000) if totals else None,
            "band_arithmetic_ok": bool(z.get("band_arithmetic_ok", False)),
            "band_arithmetic_gap_fraction": z.get("relative_arithmetic_gap"),
            "n_band_rows": len(z.get("band_rows", [])),
            "evidence": " || ".join(z.get("total_evidence", [])[:6]),
            "error": "",
        })
        bands = z.get("band_rows", [])
        for band in ("1_30", "31_100", "101_250", "251_1000", "gt1000"):
            br = [x for x in bands if x.get("band") == band]
            rec[f"{band}_recommended_qty"] = sum(float(x["recommended_qty"]) for x in br) if br else None
            rec[f"{band}_recommended_amount_lakh"] = sum(float(x["recommended_amount_lakh"]) for x in br) if br else None
    except Exception as e:
        rec.update({
            "download_status": "error",
            "parse_status": "error",
            "parse_confidence": "unresolved",
            "csg_total_lakh": None,
            "csg_total_rupees": None,
            "band_arithmetic_ok": False,
            "band_arithmetic_gap_fraction": None,
            "n_band_rows": 0,
            "evidence": "",
            "error": repr(e),
        })
    return rec


def select_state_year(docs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (state, fy), g in docs.groupby(["state", "financial_year"], dropna=False):
        parsed = g[g["csg_total_rupees"].notna()].copy()
        base = {"state": state, "financial_year": fy}
        if parsed.empty:
            rows.append({**base, "selection_status": "unresolved", "csg_recommended_total_lakh": None,
                         "csg_recommended_total_rupees": None, "selected_document_url": None,
                         "selected_document_type": None, "parse_confidence": "unresolved",
                         "band_arithmetic_ok": False, "source_document_count": len(g)})
            continue
        parsed["type_rank"] = parsed.document_type.map({"revision": 3, "minutes": 2, "amendment": 1}).fillna(0)
        parsed["arith_rank"] = parsed.band_arithmetic_ok.fillna(False).astype(int)
        parsed["conf_rank"] = parsed.parse_confidence.map({"high": 2, "medium": 1}).fillna(0)
        parsed = parsed.sort_values(["type_rank", "arith_rank", "conf_rank", "pdf_bytes"], ascending=False)
        top = parsed.iloc[0]
        status = "selected_revision" if top.document_type == "revision" else "selected_minutes" if top.document_type == "minutes" else "selected_amendment_only"
        out = {
            **base,
            "selection_status": status,
            "csg_recommended_total_lakh": top.csg_total_lakh,
            "csg_recommended_total_rupees": top.csg_total_rupees,
            "selected_document_url": top.document_url,
            "selected_document_type": top.document_type,
            "parse_confidence": top.parse_confidence,
            "band_arithmetic_ok": bool(top.band_arithmetic_ok),
            "band_arithmetic_gap_fraction": top.band_arithmetic_gap_fraction,
            "source_document_count": len(g),
            "all_source_urls": " | ".join(sorted(set(g.document_url.astype(str)))),
            "evidence": top.evidence,
        }
        for band in ("1_30", "31_100", "101_250", "251_1000", "gt1000"):
            out[f"{band}_recommended_qty"] = top.get(f"{band}_recommended_qty")
            out[f"{band}_recommended_amount_lakh"] = top.get(f"{band}_recommended_amount_lakh")
        rows.append(out)
    return pd.DataFrame(rows).sort_values(["financial_year", "state"]).reset_index(drop=True)


def main() -> None:
    s = session()
    manifest = inventory(s)
    print("MANIFEST", len(manifest), "documents", manifest.groupby("financial_year").state.nunique().to_dict(), flush=True)
    parsed_rows = []
    for i, row in manifest.iterrows():
        rec = parse_document(s, row)
        parsed_rows.append(rec)
        print(i + 1, "/", len(manifest), rec["financial_year"], rec["state"], rec["document_type"], rec["parse_status"], rec.get("csg_total_lakh"), flush=True)
    docs = pd.DataFrame(parsed_rows)
    docs.to_csv(DATA_DIR / "pab_csg_document_extracts.csv", index=False)
    state_year = select_state_year(docs)
    state_year.to_csv(DATA_PATH, index=False)
    audit = {
        "source_pages": SOURCE_PAGES,
        "manifest_documents": int(len(manifest)),
        "state_year_rows": int(len(state_year)),
        "state_year_rows_by_fy": {str(k): int(v) for k, v in state_year.groupby("financial_year").size().to_dict().items()},
        "resolved_state_year_rows": int(state_year.csg_recommended_total_rupees.notna().sum()),
        "resolved_by_fy": {str(k): int(v) for k, v in state_year.groupby("financial_year").csg_recommended_total_rupees.apply(lambda x: x.notna().sum()).to_dict().items()},
        "band_arithmetic_ok_rows": int(state_year.band_arithmetic_ok.fillna(False).sum()),
        "note": "Frozen research input built once from official DoSE&L PAB documents. Analysis must consume the committed CSV, not scrape Ministry pages at runtime.",
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    main()
