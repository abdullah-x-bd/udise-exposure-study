from __future__ import annotations

import re

NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?")


def normalize_financial_year(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2})", str(text))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)[-2:]}"


def extract_csg_totals_from_text(text: str) -> tuple[list[float], str, list[str]]:
    """Extract DoSE&L-recommended 'Total of Composite School Grant' amounts in lakhs.

    PRABANDH costing sheets normally print proposed quantity/amount followed by
    recommended quantity/amount. The final numeric token in the total row/block is
    therefore treated as the recommended amount. Multiple legitimate totals can
    occur for elementary and secondary sections and are returned separately.
    """
    lines = [" ".join(line.split()) for line in str(text).splitlines()]
    amounts: list[float] = []
    evidence: list[str] = []
    used = set()
    exact_hits = 0
    block_hits = 0
    for i, line in enumerate(lines):
        if "total of composite school grant" not in line.lower():
            continue
        candidates = [line]
        if len(NUMBER_RE.findall(line)) < 2:
            candidates.append(" ".join(lines[i:i + 2]))
            candidates.append(" ".join(lines[i:i + 3]))
        chosen = None
        for cand in candidates:
            nums = NUMBER_RE.findall(cand)
            if len(nums) >= 2:
                chosen = cand
                break
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
        if chosen == line:
            exact_hits += 1
        else:
            block_hits += 1
    if amounts and block_hits == 0:
        confidence = "high"
    elif amounts:
        confidence = "medium"
    else:
        confidence = "unresolved"
    return amounts, confidence, evidence


def document_priority(filename: str, link_text: str = "") -> int:
    s = f"{filename} {link_text}".lower()
    score = 0
    if "revised" in s:
        score += 4
    if "pab" in s or "minutes" in s or "mom" in s:
        score += 2
    if "addendum" in s or "corrigendum" in s or "supplement" in s:
        score -= 1
    return score
