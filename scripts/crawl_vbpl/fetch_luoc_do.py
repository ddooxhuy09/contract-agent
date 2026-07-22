"""Fetch a vbpl.vn document's "luoc do" (relation scheme) tab.

Note: this tab's 13 relation categories (Van ban bi bai bo, Can cu ban hanh,
Van ban duoc dan chieu, ...) are numerically the SAME data already present in
the `references` list returned by fetch_thuoc_tinh.py (each entry's
`referenceType` maps to one relation category — e.g. referenceType 3 = "Can
cu ban hanh", referenceType 1 = "Van ban bi bai bo", confirmed against a real
document). This script exists for completeness / to expand that referenceType
mapping as more documents are crawled, not because it's the only way to get
relation data.

Usage:
    python -m scripts.crawl_vbpl.fetch_luoc_do <doc_slug> <doc_id>
"""
import json
import sys
from pathlib import Path

import requests

from scripts.crawl_vbpl.common import base_headers, detail_url, router_state_tree

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "luoc_do"

# Next.js build id used in the `_rsc` query param. This is deploy-specific and
# WILL go stale — re-capture from devtools if requests stop returning data
# (see common.py docstring).
RSC_BUILD_ID = "1ok19"


def fetch_luoc_do(doc_slug: str, doc_id: str) -> dict:
    url = f"{detail_url(doc_slug, tabs='luoc-do')}&_rsc={RSC_BUILD_ID}"
    headers = {
        **base_headers(),
        "accept": "*/*",
        "next-router-state-tree": router_state_tree(doc_slug),
        "next-url": f"/van-ban/chi-tiet/{doc_slug}",
        "referer": detail_url(doc_slug, tabs="luoc-do"),
        "rsc": "1",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.encoding = "utf-8"
    resp.raise_for_status()
    return {"raw": resp.text}


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.crawl_vbpl.fetch_luoc_do <doc_slug> <doc_id>")
        sys.exit(1)

    doc_slug, doc_id = sys.argv[1], sys.argv[2]
    result = fetch_luoc_do(doc_slug, doc_id)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{doc_id}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
