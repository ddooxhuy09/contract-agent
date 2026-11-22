"""Derive muc_luc nodes from van_ban.md when the crawler gave no muc_luc.json.

scripts/crawl_vbpl writes only van_ban.md / thuoc_tinh.json / luoc_do.json. Its van_ban.md
carries ``## Điều …`` + ``<!-- article_id: X -->`` and ``… <!-- clause_id: Y -->``, which is
enough to rebuild the Phần / Chương / Mục / Điều / Khoản tree the chunker needs.
Points (Điểm) are not marked, so a Khoản becomes the leaf chunk.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

_ARTICLE_ID = re.compile(r"<!--\s*article_id:\s*([0-9a-zA-Z_-]+)\s*-->")
_CLAUSE_ID = re.compile(r"<!--\s*clause_id:\s*([0-9a-zA-Z_-]+)\s*-->")
_HEADING = re.compile(r"^#{1,3}\s*(.+)$")
_CLAUSE_NUM = re.compile(r"^\**\s*(\d+)\s*[.)]")
# Container headings: keyword + number token, e.g. "Chương II", "PHẦN THỨ HAI", "Mục 1".
_CONTAINERS = (
    ("Part", re.compile(r"^\**\s*(?:Phần|PHẦN)\s+(?:thứ\s+)?[IVXLC\d]+\b|^\**\s*(?:Phần|PHẦN)\s+thứ\s+\w+", re.I)),
    ("Chapter", re.compile(r"^\**\s*(?:Chương|CHƯƠNG)\s+[IVXLC\d]+\b", re.I)),
    ("Section", re.compile(r"^\**\s*(?:Mục|MỤC)\s+[IVXLC\d]+\b", re.I)),
)
_DEPTH = {"Part": 0, "Chapter": 1, "Section": 2}


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def muc_luc_from_van_ban(van_ban: str) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    open_containers: list[dict[str, Any]] = []  # Part / Chapter / Section stack
    article: dict[str, Any] | None = None
    lines = van_ban.splitlines()

    def attach(node: dict[str, Any]) -> None:
        (open_containers[-1]["children"] if open_containers else roots).append(node)

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        cm = _CLAUSE_ID.search(s)
        if cm and article is not None:
            num = _CLAUSE_NUM.match(s)
            article["children"].append(
                {"id": cm.group(1), "title": f"Khoản {num.group(1)}" if num else "", "level": "Clause", "children": []}
            )
            continue
        hm = _HEADING.match(s)
        if hm:
            nxt = next((x.strip() for x in lines[i + 1 : i + 3] if x.strip()), "")
            am = _ARTICLE_ID.search(nxt)
            if am:
                article = {"id": am.group(1), "title": _clean(hm.group(1)), "level": "Article", "children": []}
                attach(article)
                continue
        level = next((lv for lv, rx in _CONTAINERS if rx.match(s)), None)
        if level:
            title = _clean(s)
            # Công báo page breaks repeat "Phần thứ hai" / "Mục 3" mid-text: same heading
            # as an already open container → keep the current tree position.
            if any(c["level"] == level and c["title"].upper() == title.upper() for c in open_containers):
                continue
            while open_containers and _DEPTH[open_containers[-1]["level"]] >= _DEPTH[level]:
                open_containers.pop()
            node = {"id": "", "title": title, "level": level, "children": []}
            attach(node)
            open_containers.append(node)
            article = None
    return roots


def read_muc_luc(folder: Path, van_ban: str) -> list[dict[str, Any]]:
    """``muc_luc.json`` if present, else derived from van_ban.md."""
    path = folder / "muc_luc.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = list(data.get("children") or [])
        return data
    return muc_luc_from_van_ban(van_ban)
