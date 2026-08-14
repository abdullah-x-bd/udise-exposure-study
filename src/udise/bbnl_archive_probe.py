from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import requests

ARCHIVE_URL = "https://storage.googleapis.com/bbnl_data/parsed.zip"
TARGETS = ("active_gps.csv", "panchayats.csv", "planned_nofn.csv", "status_active_gps.csv", "GP_locations.csv")


def main() -> None:
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)
    r = requests.get(ARCHIVE_URL, timeout=180)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    payload: dict[str, object] = {
        "archive_url": ARCHIVE_URL,
        "archive_bytes": len(r.content),
        "members": names,
        "tables": {},
    }
    for target in TARGETS:
        matches = [n for n in names if n.endswith(target)]
        if not matches:
            payload["tables"][target] = {"found": False}
            continue
        member = matches[0]
        raw = z.read(member).decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        payload["tables"][target] = {
            "found": True,
            "member": member,
            "row_count_including_header": len(rows),
            "header": rows[0] if rows else [],
            "sample_rows": rows[1:6] if len(rows) > 1 else [],
        }
    (out / "bbnl_archive_probe.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
