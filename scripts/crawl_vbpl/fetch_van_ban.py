"""Fetch the full-text content ("van ban") of a vbpl.vn document.

Usage:
    python -m scripts.crawl_vbpl.fetch_van_ban <doc_slug> <doc_id>

<doc_slug> is the URL slug including the trailing GUID, e.g.:
    thong-tu-so-100-2026-tt-btc-bai-bo-toan-bo-06-thong-tu-do-bo-truong-bo-tai-chinh-ban-hanh--4fda4da0-80ec-11f1-ac2d-554d7f9461b5
<doc_id> is the trailing GUID from the slug, e.g. 4fda4da0-80ec-11f1-ac2d-554d7f9461b5
"""
import json
import sys
from pathlib import Path

from scripts.crawl_vbpl.common import fetch_document_detail

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "van_ban"


def fetch_van_ban(doc_slug: str, doc_id: str) -> dict:
    """Returns {"html": <raw article HTML>, "attributes": <dict from the same payload>}."""
    return fetch_document_detail(doc_slug, doc_id)


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.crawl_vbpl.fetch_van_ban <doc_slug> <doc_id>")
        sys.exit(1)

    doc_slug, doc_id = sys.argv[1], sys.argv[2]
    result = fetch_van_ban(doc_slug, doc_id)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{doc_id}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
