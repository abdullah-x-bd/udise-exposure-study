from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


RESOURCE_URLS = [
    "https://www.data.gov.in/resource/district-wise-service-ready-gram-panchayat-31-03-2024",
    "https://www.data.gov.in/resource/district-wise-service-ready-gram-panchayat-31-01-2024",
    "https://www.data.gov.in/resource/district-wise-service-ready-gram-panchayat-31-12-2023",
]
PUBLIC_API_KEY = "579b464db66ec23bdd0000017d0wnload"


def api_probe(resource_id: str) -> list[dict[str, object]]:
    attempts = []
    for fmt in ("json", "csv"):
        url = f"https://api.data.gov.in/resource/{resource_id}?api-key={PUBLIC_API_KEY}&format={fmt}&limit=5"
        try:
            response = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            attempts.append({
                "url": url,
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "length": len(response.content),
                "preview": response.text[:1000],
            })
        except Exception as exc:
            attempts.append({"url": url, "error": repr(exc)})
    return attempts


def probe(url: str) -> dict[str, object]:
    response = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    result: dict[str, object] = {
        "url": url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "length": len(response.content),
    }
    text = response.text
    links = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', text, flags=re.I):
        href = urljoin(url, match.group(1))
        low = href.lower()
        if any(token in low for token in ("csv", "download", "api", "resource")):
            links.append(href)
    result["candidate_links"] = sorted(set(links))[:200]
    uuids = sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)))
    result["uuids"] = uuids[:50]
    result["api_attempts"] = {uuid: api_probe(uuid) for uuid in uuids[:10]}
    return result


def main() -> None:
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)
    results = [probe(url) for url in RESOURCE_URLS]
    (out / "bharatnet_ogd_probe.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
