"""Detect enforcement (effectivity) titles — Chương/Điều headings only."""

from __future__ import annotations

import re
import unicodedata

_ARTICLE_PREFIX = re.compile(
    r"^(?:Điều|ĐIỀU)\s+\d+\s*[\.\:\-–—]?\s*",
    re.IGNORECASE,
)
_CHAPTER_PREFIX = re.compile(
    r"^(?:Chương|CHƯƠNG)\s+[IVXLCDM\d]+\s*[\.\:\-–—]?\s*",
    re.IGNORECASE,
)

# Strict: remaining title must START with these phrases (not "Hiệu lực của…",
# "Thời hiệu thi hành…", "thi hành công vụ", body "có hiệu lực thi hành").
_EFF_TITLE = re.compile(
    r"^Hiệu\s+lực\s+thi\s+hành\b",
    re.IGNORECASE,
)
_ORG_TITLE = re.compile(
    r"^Tổ\s+chức\s+thực\s+hiện\b",
    re.IGNORECASE,
)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").replace("\u00a0", " ")


def title_after_level_prefix(title: str) -> str:
    """Strip leading 'Điều N.' / 'Chương XIII.' → remaining rubric."""
    text = re.sub(r"\s+", " ", _nfc(title)).strip().strip("*").strip()
    text = _ARTICLE_PREFIX.sub("", text, count=1)
    text = _CHAPTER_PREFIX.sub("", text, count=1)
    return text.strip().strip("*").strip()


def is_effectivity_title(title: str) -> bool:
    """True only for headings like ``Điều 53. Hiệu lực thi hành``.

    Does **not** match body phrases or near-miss titles
    (``Hiệu lực của…``, ``Thời hiệu thi hành…``, ``thi hành công vụ``).
    """
    rest = title_after_level_prefix(title)
    if not rest:
        return False
    return bool(_EFF_TITLE.match(rest) or _ORG_TITLE.match(rest))
