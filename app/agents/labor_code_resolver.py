"""Resolve the Labor Code (Bộ luật Lao động) effective on an analysis date.

Respects ``status_flag`` vocabulary (0..5):
  0 Chưa xác định · 1 Còn hiệu lực · 2 Hết HL toàn bộ · 3 Chưa có HL
  4 Hết HL một phần · 5 Có HL một phần

Prefer 1/5; allow 4/0 as fallback; never 2 or 3.
Must be doc_type Bộ luật — never a Thông tư whose title merely mentions BLLĐ.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.dates import parse_as_of
from app.core.logging import logger

_PREFERRED = (1, 5)
_ACCEPTABLE = (1, 5, 4, 0)


def resolve_labor_code_document(as_of: str | date | None = None) -> dict[str, Any] | None:
    """Pick Bộ luật Lao động row effective on ``as_of`` (not guiding circulars)."""
    as_of_d = parse_as_of(as_of)
    try:
        from app.infrastructure.retrieval.context import get_legal_docs

        docs = get_legal_docs()
    except Exception as e:
        logger.warning("Labor code resolve: no DB (%s)", e)
        return None

    try:
        row = docs.find_labor_code_row(as_of_d, list(_ACCEPTABLE))
    except Exception as e:
        logger.warning("Labor code resolve query failed: %s", e)
        return None

    if not row:
        return None
    return {
        "doc_id": row[0],
        "doc_num": row[1],
        "title": row[2],
        "doc_type": row[3],
        "status_flag": int(row[4] if row[4] is not None else 0),
        "eff_flag": row[5],
        "eff_from": str(row[6]) if row[6] else None,
        "eff_to": str(row[7]) if row[7] else None,
        "issue_date": str(row[8]) if row[8] else None,
        "source_url": row[9],
    }


def fetch_article_21_snippet(doc_id: str | None) -> str | None:
    return fetch_article_snippet(doc_id, [21])


def fetch_article_snippet(
    doc_id: str | None,
    article_nums: list[int] | tuple[int, ...],
    *,
    limit: int = 3,
) -> str | None:
    """Load embedding chunk text for Điều N (path leaf ``.DN``) — no vector search."""
    if not doc_id or not article_nums:
        return None
    nums = [int(n) for n in article_nums if int(n) > 0]
    if not nums:
        return None
    # Match .D98 or .D98.K1 but not .D980
    alt = "|".join(rf"\.D{n}(\.|$)" for n in nums)
    try:
        from app.infrastructure.retrieval.context import get_legal_chunks

        chunks = get_legal_chunks()
    except Exception:
        return None
    try:
        rows = chunks.find_article_chunks(doc_id, alt, limit)
        if not rows:
            return None
        return "\n".join(r[0] for r in rows if r and r[0])
    except Exception as e:
        logger.warning("fetch_article_snippet failed: %s", e)
        return None


def fetch_article_meta(
    doc_id: str | None,
    article_num: int,
    *,
    limit: int = 4,
) -> dict[str, Any] | None:
    """Return concatenated chunk text + primary path for one Điều (citation hydrate)."""
    if not doc_id or article_num <= 0:
        return None
    try:
        from app.infrastructure.retrieval.context import get_legal_chunks

        chunks = get_legal_chunks()
    except Exception:
        return None
    try:
        rows = chunks.find_article_chunks(doc_id, rf"\.D{article_num}(\.|$)", limit)
        if not rows:
            return None
        quotes = [r[0].strip() for r in rows if r and r[0] and str(r[0]).strip()]
        return {
            "quote": "\n".join(quotes),
            "path": rows[0][1],
        }
    except Exception as e:
        logger.warning("fetch_article_meta failed: %s", e)
        return None
