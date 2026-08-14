from __future__ import annotations

import csv
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path

from huggingface_hub import HfFileSystem

YEARS = [f"{y}-{str(y+1)[-2:]}" for y in range(2018, 2026)]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower().replace("\ufeff", "")).strip("_")


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    fs = HfFileSystem(token=os.environ["HF_TOKEN"])
    results = []
    for year in YEARS:
        remote = f"datasets/{repo_id}/raw/{year}/enrolment_1.zip"
        item_desc = Counter()
        item_pairs = Counter()
        samples = []
        with fs.open(remote, "rb") as fh, zipfile.ZipFile(fh) as zf:
            members = [m for m in zf.infolist() if not m.is_dir() and m.filename.lower().endswith('.csv') and 'stream' not in m.filename.lower()]
            for member in members:
                with zf.open(member) as raw:
                    reader = csv.DictReader((line.decode('utf-8-sig', errors='replace') for line in raw))
                    if not reader.fieldnames:
                        continue
                    fmap = {norm(c): c for c in reader.fieldnames}
                    for i, row in enumerate(reader):
                        if i >= 5000:
                            break
                        d = (row.get(fmap.get('item_desc','')) or '').strip() if 'item_desc' in fmap else ''
                        g = (row.get(fmap.get('item_group','')) or '').strip() if 'item_group' in fmap else ''
                        it = (row.get(fmap.get('item_id','')) or '').strip() if 'item_id' in fmap else ''
                        if d:
                            item_desc[d] += 1
                        if g or it:
                            item_pairs[(g,it)] += 1
                        if len(samples) < 12:
                            samples.append({k: row.get(v) for k,v in fmap.items() if k in {'psuedocode','pseudocode','item_desc','item_group','item_id','cpp_b','cpp_g','c1_b','c1_g'}})
        rec = {
            'year': year,
            'item_desc_values': item_desc.most_common(),
            'item_group_id_values': [[list(k),v] for k,v in item_pairs.most_common()],
            'samples': samples,
        }
        results.append(rec)
        print(year, json.dumps(rec, ensure_ascii=False), flush=True)
    out = Path('studies/composite_school_grant/outputs/enrolment_encodings')
    out.mkdir(parents=True, exist_ok=True)
    (out/'enrolment_encodings.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')

if __name__ == '__main__':
    main()
