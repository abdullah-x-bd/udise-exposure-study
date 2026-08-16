from __future__ import annotations

import re

NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?")


def normalize_financial_year(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2})", str(text))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)[-2:]}"


def _clean_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in str(text).splitlines()]


def extract_csg_totals_from_text(text: str) -> tuple[list[float], str, list[str]]:
    """Extract DoSE&L-recommended `Total of Composite School Grant` amounts in lakhs."""
    lines = _clean_lines(text)
    amounts: list[float] = []
    evidence: list[str] = []
    used = set()
    block_hits = 0
    for i, line in enumerate(lines):
        if "total of composite school grant" not in line.lower():
            continue
        candidates = [line]
        if len(NUMBER_RE.findall(line)) < 2:
            candidates.append(" ".join(lines[i:i + 2]))
            candidates.append(" ".join(lines[i:i + 3]))
        chosen = next((c for c in candidates if len(NUMBER_RE.findall(c)) >= 2), None)
        if chosen is None:
            continue
        key = chosen.lower()
        if key in used:
            continue
        used.add(key)
        nums = [float(x.replace(",", "")) for x in NUMBER_RE.findall(chosen)]
        amount = nums[-1]
        if not (0 < amount < 10_000_000):
            continue
        amounts.append(amount)
        evidence.append(chosen)
        if chosen != line:
            block_hits += 1
    if amounts and block_hits == 0:
        confidence = "high"
    elif amounts:
        confidence = "medium"
    else:
        confidence = "unresolved"
    return amounts, confidence, evidence


def classify_csg_band(label: str) -> str | None:
    s = " ".join(str(label).lower().replace("=", " = ").split())
    if ("> = 1" in s or ">= 1" in s) and ("< = 30" in s or "<= 30" in s):
        return "1_30"
    if "> 30" in s and ("< = 100" in s or "<= 100" in s):
        return "31_100"
    if "> 100" in s and ("< = 250" in s or "<= 250" in s):
        return "101_250"
    if "> 250" in s and ("< = 1000" in s or "<= 1000" in s):
        return "251_1000"
    if "> 1000" in s:
        return "gt1000"
    return None


def extract_csg_band_rows_from_text(text: str) -> list[dict]:
    """Parse band-level recommended quantities/amounts inside each CSG costing block.

    Each block starts after the preceding `Total of Composite School Grant` row and
    ends at the current total. This prevents elementary rows from being re-read as
    secondary rows. Each label stops before the next School Grant label or the numeric
    `R ...` record, preventing adjacent threshold labels from contaminating one another.
    """
    lines = _clean_lines(text)
    total_idx = [i for i, line in enumerate(lines) if "total of composite school grant" in line.lower()]
    out: list[dict] = []
    for block_no, ti in enumerate(total_idx):
        prior_total = total_idx[block_no - 1] if block_no > 0 else -1
        lo = max(prior_total + 1, ti - 80)
        used: set[tuple] = set()
        i = lo
        while i < ti:
            line = lines[i]
            if "school grant" not in line.lower() or "total of" in line.lower():
                i += 1
                continue
            label_parts = [line]
            numeric_row = None
            nums: list[float] = []
            for j in range(i + 1, min(ti, i + 8)):
                candidate = lines[j]
                if "school grant" in candidate.lower() and "total of" not in candidate.lower():
                    break
                if re.match(r"^R(?:\s|$)", candidate, flags=re.I):
                    vals = [float(x.replace(",", "")) for x in NUMBER_RE.findall(candidate)]
                    if len(vals) >= 6:
                        numeric_row = candidate
                        nums = vals
                    break
                label_parts.append(candidate)
            # Some pdftotext layouts keep the numeric R row on the label line.
            if numeric_row is None and re.search(r"(?:^|\s)R\s+\d", line):
                tail = re.split(r"(?:^|\s)R\s+", line, maxsplit=1)[-1]
                vals = [float(x.replace(",", "")) for x in NUMBER_RE.findall(tail)]
                if len(vals) >= 6:
                    numeric_row = "R " + tail
                    nums = vals
            label = " ".join(label_parts)
            band = classify_csg_band(label)
            if band is None or numeric_row is None:
                i += 1
                continue
            proposed_qty, proposed_unit, proposed_amount, rec_qty, rec_unit, rec_amount = nums[:6]
            key = (band, rec_qty, rec_unit, rec_amount)
            if key not in used:
                used.add(key)
                out.append({
                    "total_block": block_no,
                    "band": band,
                    "proposed_qty": proposed_qty,
                    "proposed_unit_lakh": proposed_unit,
                    "proposed_amount_lakh": proposed_amount,
                    "recommended_qty": rec_qty,
                    "recommended_unit_lakh": rec_unit,
                    "recommended_amount_lakh": rec_amount,
                    "evidence": f"{label} || {numeric_row}",
                })
            i += 1
    return out


def reconcile_band_rows_to_totals(text: str) -> dict:
    totals, confidence, evidence = extract_csg_totals_from_text(text)
    rows = extract_csg_band_rows_from_text(text)
    band_sum = sum(float(r["recommended_amount_lakh"]) for r in rows)
    total_sum = sum(totals)
    rel_gap = abs(band_sum - total_sum) / total_sum if total_sum > 0 and rows else None
    return {
        "total_amounts_lakh": totals,
        "total_sum_lakh": total_sum,
        "band_rows": rows,
        "band_sum_lakh": band_sum,
        "relative_arithmetic_gap": rel_gap,
        "total_confidence": confidence,
        "total_evidence": evidence,
        "band_arithmetic_ok": bool(rel_gap is not None and rel_gap <= 0.005),
    }


def document_priority(filename: str, link_text: str = "") -> int:
    s = f"{filename} {link_text}".lower()
    score = 0
    if "revised" in s or "revision" in s:
        score += 4
    if "pab" in s or "minutes" in s or "mom" in s:
        score += 2
    if "addendum" in s or "corrigendum" in s or "supplement" in s:
        score -= 1
    return score
