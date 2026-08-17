"""End-to-end crawl: list -> per-document detail -> save van_ban.md / thuoc_tinh.json
/ luoc_do.json into a folder named after the document's full title.

Usage:
    python -m scripts.crawl_vbpl.crawl_all
    python -m scripts.crawl_vbpl.crawl_all --doc-type "Bộ luật"   # crawl one type only
    python -m scripts.crawl_vbpl.crawl_all --limit 5              # smoke-test on a few docs
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.crawl_vbpl.common import detail_url, fetch_document_detail
from scripts.crawl_vbpl.convert import build_luoc_do, build_thuoc_tinh, html_to_markdown, safe_folder_name
from scripts.crawl_vbpl.fetch_list import DOC_TYPE_IDS, crawl_all as list_all_types, slugify_title

DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "documents"
LIST_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "list"

SLEEP_MIN_SECONDS = 2
SLEEP_MAX_SECONDS = 4


def crawl_document(doc_type_name: str, item: dict) -> bool:
    doc_id = item["id"]
    title = item["title"]
    slug = item.get("_slug") or slugify_title(title, doc_id)

    folder = DOCS_DIR / doc_type_name.replace(" ", "_").lower() / safe_folder_name(title)
    if (folder / "thuoc_tinh.json").exists():
        print(f"  skip (already crawled): {title}")
        return False

    try:
        detail = fetch_document_detail(slug, doc_id)
        attributes = detail["attributes"]
        if not attributes:
            raise ValueError("empty attributes in response (stale session/action hash?)")
    except Exception as e:
        print(f"  FAILED: {title} ({e})")
        return False

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "van_ban.md").write_text(html_to_markdown(detail["html"]), encoding="utf-8")
    (folder / "thuoc_tinh.json").write_text(
        json.dumps(
            build_thuoc_tinh(attributes, source_url=detail_url(slug, tabs="toan-van")),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (folder / "luoc_do.json").write_text(
        json.dumps(build_luoc_do(attributes), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  saved: {title}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-type", choices=list(DOC_TYPE_IDS), default=None, help="crawl only this document type")
    parser.add_argument("--limit", type=int, default=None, help="crawl at most N documents (per type) - for smoke testing")
    args = parser.parse_args()

    print("Fetching document list...")
    by_type = list_all_types(target_types=[args.doc_type] if args.doc_type else None)

    LIST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, items in by_type.items():
        (LIST_CACHE_DIR / f"{name.replace(' ', '_').lower()}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    target_types = [args.doc_type] if args.doc_type else list(DOC_TYPE_IDS)

    total_saved = 0
    for doc_type_name in target_types:
        items = by_type.get(doc_type_name, [])
        if args.limit:
            items = items[: args.limit]
        print(f"\n=== {doc_type_name}: {len(items)} document(s) ===")

        for i, item in enumerate(items):
            saved = crawl_document(doc_type_name, item)
            total_saved += 1 if saved else 0
            if i < len(items) - 1:
                time.sleep(random.uniform(SLEEP_MIN_SECONDS, SLEEP_MAX_SECONDS))

    print(f"\nDone. {total_saved} document(s) newly saved under {DOCS_DIR}")


if __name__ == "__main__":
    main()
