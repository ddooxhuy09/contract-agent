"""Fetch a vbpl.vn document's "thuoc tinh" (attributes), which also carries
the "luoc do" (relation scheme) data in its `references` field — see
fetch_luoc_do.py's docstring for why a separate luoc-do request is unnecessary.

Usage:
    python -m scripts.crawl_vbpl.fetch_thuoc_tinh <doc_slug> <doc_id>

<doc_id> is the trailing GUID from the slug, e.g. 4fda4da0-80ec-11f1-ac2d-554d7f9461b5
"""
import json
import sys
from pathlib import Path

from scripts.crawl_vbpl.common import fetch_document_detail

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "thuoc_tinh"


def fetch_thuoc_tinh(doc_slug: str, doc_id: str) -> dict:
    return fetch_document_detail(doc_slug, doc_id)["attributes"]


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.crawl_vbpl.fetch_thuoc_tinh <doc_slug> <doc_id>")
        sys.exit(1)

    doc_slug, doc_id = sys.argv[1], sys.argv[2]
    result = fetch_thuoc_tinh(doc_slug, doc_id)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{doc_id}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
