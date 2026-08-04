"""Shared HTTP plumbing for crawling vbpl.vn document-detail tabs.

vbpl.vn is a Next.js app. Its tabs (noi-dung / thuoc-tinh / luoc-do) are served
either as Server Action responses (POST, identified by a `next-action` hash)
or as RSC navigation responses (GET, identified by a `_rsc` build id). Both the
`next-action` hashes and the `_rsc` build id are baked in at deploy time and
WILL go stale when vbpl.vn redeploys — if requests start failing, re-capture a
fresh curl from the browser's Network tab (DevTools) and update the constants
below. The session cookie also expires periodically for the same reason.
"""
import json
import os
import re
from urllib.parse import quote

import requests

BASE_URL = "https://vbpl.vn"

# Refresh from browser devtools when requests start failing (see module docstring).
# Must be provided via the VBPL_COOKIE env var — a hardcoded personal session
# cookie must not live in the repository.
VBPL_COOKIE = os.environ.get("VBPL_COOKIE", "")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
)

_SEC_CH_UA_HEADERS = {
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Microsoft Edge";v="150"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "priority": "u=1, i",
}


def base_headers() -> dict:
    if not VBPL_COOKIE:
        raise RuntimeError(
            "VBPL_COOKIE env var is required. Capture a fresh session cookie from the "
            "browser's Network tab (DevTools) on vbpl.vn and export it as VBPL_COOKIE."
        )
    return {
        "accept-language": "en-US,en;q=0.9",
        "cookie": VBPL_COOKIE,
        "user-agent": USER_AGENT,
        **_SEC_CH_UA_HEADERS,
    }


def detail_url(doc_slug: str, tabs: str | None = None) -> str:
    url = f"{BASE_URL}/van-ban/chi-tiet/{doc_slug}"
    return f"{url}?tabs={tabs}" if tabs else url


def router_state_tree(doc_slug: str) -> str:
    """next-router-state-tree header value for the document-detail route.

    Captured verbatim from real requests: identical for the thuoc-tinh and
    luoc-do tabs (the active tab is selected via the URL/body, not this tree).
    """
    tree = [
        "",
        {
            "children": [
                "van-ban",
                {
                    "children": [
                        ["category", "chi-tiet", "d"],
                        {
                            "children": [
                                ["id", doc_slug, "d"],
                                {"children": ["__PAGE__", {}, None, None]},
                            ]
                        },
                        None,
                        None,
                    ]
                },
                None,
                None,
            ]
        },
        None,
        None,
        True,
    ]
    return quote(json.dumps(tree, separators=(",", ":")))


def router_state_tree_for_list() -> str:
    """next-router-state-tree header value for the /van-ban/trung-uong list route."""
    tree = [
        "",
        {
            "children": [
                "van-ban",
                {"children": [["category", "trung-uong", "d"], {"children": ["__PAGE__", {}, None, None]}, None, None]},
                None,
                None,
            ]
        },
        None,
        None,
        True,
    ]
    return quote(json.dumps(tree, separators=(",", ":")))


_RECORD_START_RE_BYTES = re.compile(rb"(\d+):")


def parse_rsc_stream(raw: bytes) -> dict[str, str]:
    """Parse a Next.js Flight/RSC stream into {index: raw_payload}.

    Operates on raw response BYTES, not a decoded str: the `T<hexlen>,` length
    prefix on text chunks counts UTF-8 bytes, and this payload is full of
    multi-byte Vietnamese characters, so slicing a decoded Python str by that
    same number would overshoot and corrupt/merge adjacent records.

    Two record shapes matter here:
      - `<idx>:T<hexlen>,<data>`  -- a text/HTML chunk; <hexlen> is the exact
        UTF-8 byte length of <data>. The NEXT record can start immediately
        after this chunk with no separating newline (observed:
        `...</html>1:{...}`), so parsing resumes right where the length-based
        slice ends rather than assuming a newline boundary.
      - `<idx>:<json-or-literal>` -- everything else (JSON objects, "null",
        arrays of UI descriptors we don't care about). These end at the next
        newline that's followed by a record start, or at end of data.
    """
    results: dict[str, str] = {}
    i = 0
    n = len(raw)
    while i < n:
        m = _RECORD_START_RE_BYTES.match(raw, i)
        if not m:
            break
        idx = m.group(1).decode("ascii")
        pos = m.end()

        if pos < n and raw[pos : pos + 1] == b"T":
            comma = raw.index(b",", pos)
            hexlen = raw[pos + 1 : comma]
            length = int(hexlen, 16)
            data_start = comma + 1
            data = raw[data_start : data_start + length]
            results[idx] = data.decode("utf-8")
            i = data_start + length
            if i < n and raw[i : i + 1] == b"\n":
                i += 1
        else:
            nl = raw.find(b"\n", pos)
            while nl != -1 and not _RECORD_START_RE_BYTES.match(raw, nl + 1):
                nl = raw.find(b"\n", nl + 1)
            end = nl if nl != -1 else n
            results[idx] = raw[pos:end].decode("utf-8")
            i = end + 1 if nl != -1 else n

    return results


# Server Action hash captured from the browser's "Thuoc tinh" tab request. It
# returns BOTH the article HTML (record "2") and the attributes JSON (record
# "1") in one response — there is no separate action needed for the "Noi
# dung" tab. Refresh from devtools if this starts erroring (see module
# docstring).
DETAIL_NEXT_ACTION = "0fb12b3561faa05adec51a82efb3e4f4f427f07b"


def fetch_document_detail(doc_slug: str, doc_id: str) -> dict:
    """Single request returning {"html": <article HTML>, "attributes": <dict>}."""
    url = detail_url(doc_slug, tabs="thuoc-tinh")
    headers = {
        **base_headers(),
        "accept": "text/x-component",
        "content-type": "text/plain;charset=UTF-8",
        "next-action": DETAIL_NEXT_ACTION,
        "next-router-state-tree": router_state_tree(doc_slug),
        "origin": BASE_URL,
        "referer": url,
    }
    resp = requests.post(url, headers=headers, data=json.dumps([doc_id]), timeout=30)
    resp.raise_for_status()

    records = parse_rsc_stream(resp.content)
    html = records.get("2", "")
    attributes = json.loads(records["1"]) if records.get("1") not in (None, "null") else None
    return {"html": html, "attributes": attributes}
