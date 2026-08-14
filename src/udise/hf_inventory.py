from __future__ import annotations

import json
import os
import re
from pathlib import Path

from huggingface_hub import HfApi


YEAR_PATTERNS = (
    re.compile(r"(20\d{2})[-_/](\d{2,4})"),
    re.compile(r"(20\d{2})_(\d{2})"),
)


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    files = sorted(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))

    years: set[str] = set()
    for name in files:
        for pattern in YEAR_PATTERNS:
            match = pattern.search(name)
            if match:
                years.add(match.group(0).replace("/", "-").replace("_", "-"))
                break

    payload = {
        "repo_id": repo_id,
        "file_count": len(files),
        "detected_year_tokens": sorted(years),
        "files": files,
    }
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hf_inventory.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("repo_id", "file_count", "detected_year_tokens")}, indent=2))


if __name__ == "__main__":
    main()
