"""Fetch the id/title/docNum/... list of central-level (TRUNG_UONG) legal
documents from vbpl.vn, across the 4 target document types: Luat, Bo luat,
Nghi dinh, Thong tu.

Each list item's `id` (numeric string for older documents, UUID for newer
ones) plus its `title` is everything fetch_van_ban.py / fetch_thuoc_tinh.py /
fetch_luoc_do.py need (they build the detail-page slug themselves).

Usage:
    python -m scripts.crawl_vbpl.fetch_list
"""
import json
import re
import unicodedata
from pathlib import Path

import requests

from scripts.crawl_vbpl.common import base_headers, parse_rsc_stream, router_state_tree_for_list

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "crawl_data" / "list"

LIST_URL = "https://vbpl.vn/van-ban/trung-uong"
NEXT_ACTION = "c529d164f28418e5898a834422629e64c6816af1"
UNDEF = "$undefined"

# GUID for docType filter, captured per-type from the browser devtools request body
# (Network tab -> filter by that type on the UI -> inspect the `docType` field).
# Types left as None fall back to an unfiltered crawl + client-side name filtering,
# which is correct but re-downloads every central-level document once.
DOC_TYPE_IDS = {
    "Luật": "11025e19-2dd6-4165-85ad-ab6241186a1a",
    "Bộ luật": "404b68a7-8e71-4ee5-a6c0-07e59f35f824",
    "Nghị định": "0d08b84c-7de7-4800-8760-2a68265e7890",
    "Thông tư": "178c63a9-73ff-4fd4-9d91-18d690520090",
}


def _build_body(page_number: int, page_size: int, doc_type_ids: list[str] | None) -> str:
    body = {
        "pageNumber": page_number,
        "pageSize": page_size,
        "keyword": UNDEF,
        "sortBy": "issueDate",
        "sortDirection": "desc",
        "groupVbpl": True,
        "documentName": UNDEF,
        "docNum": UNDEF,
        "docType": doc_type_ids if doc_type_ids else UNDEF,
        "majorTypeIds": UNDEF,
        "fieldTypeIds": UNDEF,
        "agencyIds": UNDEF,
        "effStatus": UNDEF,
        "status": UNDEF,
        "issueDateFrom": UNDEF,
        "issueDateTo": UNDEF,
        "effToFrom": UNDEF,
        "effToEnd": UNDEF,
        "effFromBegin": UNDEF,
        "effFromEnd": UNDEF,
        "administrativeUnit": UNDEF,
        "agencyLevel": "TRUNG_UONG",
        "documentType": UNDEF,
        "optionDoc": "title",
        "matchMode": "all_words",
    }
    return json.dumps([body], ensure_ascii=False)


def fetch_page(page_number: int, page_size: int = 50, doc_type_ids: list[str] | None = None) -> tuple[list[dict], int]:
    headers = {
        **base_headers(),
        "accept": "text/x-component",
        "content-type": "text/plain;charset=UTF-8",
        "next-action": NEXT_ACTION,
        "next-router-state-tree": router_state_tree_for_list(),
        "origin": "https://vbpl.vn",
        "referer": LIST_URL,
    }
    body = _build_body(page_number, page_size, doc_type_ids)
    resp = requests.post(LIST_URL, headers=headers, data=body, timeout=30)
    resp.raise_for_status()

    records = parse_rsc_stream(resp.content)
    data = json.loads(records["1"])
    return data["items"], data["total"]


def slugify_title(title: str, doc_id: str) -> str:
    """Best-effort reconstruction of the detail-page slug from a list item's title+id."""
    pre_replaced = title.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", pre_replaced)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    return f"{slug}--{doc_id}"


def crawl_all(page_size: int = 50, target_types: list[str] | None = None) -> dict[str, list[dict]]:
    type_ids = {name: DOC_TYPE_IDS[name] for name in (target_types or DOC_TYPE_IDS)}
    results: dict[str, list[dict]] = {name: [] for name in type_ids}

    known = {name: tid for name, tid in type_ids.items() if tid}
    unknown_names = {name for name, tid in type_ids.items() if not tid}

    for name, tid in known.items():
        page = 1
        while True:
            items, total = fetch_page(page, page_size, doc_type_ids=[tid])
            results[name].extend(items)
            print(f"[{name}] page {page}: {len(items)} item(s), {len(results[name])}/{total} so far")
            if page * page_size >= total:
                break
            page += 1

    if unknown_names:
        print(
            f"No docType GUID for {sorted(unknown_names)}; falling back to an unfiltered "
            f"crawl of all central-level documents + client-side name filtering (slower). "
            f"Capture the missing GUIDs from devtools to speed this up."
        )
        page = 1
        while True:
            items, total = fetch_page(page, page_size, doc_type_ids=None)
            for item in items:
                type_name = (item.get("docType") or {}).get("name")
                if type_name in unknown_names:
                    results[type_name].append(item)
            print(f"[unfiltered] page {page}: scanned {len(items)}, total={total}")
            if page * page_size >= total:
                break
            page += 1

    return results


def main():
    results = crawl_all()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, items in results.items():
        for item in items:
            item["_slug"] = slugify_title(item["title"], item["id"])
        safe_name = name.replace(" ", "_").lower()
        out_path = OUTPUT_DIR / f"{safe_name}.json"
        out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(items)} item(s) to {out_path}")


if __name__ == "__main__":
    main()
