"""Resolve the Labor Code (Bộ luật Lao động) effective on an analysis date.

Respects ``status_flag`` vocabulary (0..5):
  0 Chưa xác định · 1 Còn hiệu lực · 2 Hết HL toàn bộ · 3 Chưa có HL
  4 Hết HL một phần · 5 Có HL một phần

Prefer 1/5; allow 4/0 as fallback; never 2 or 3.
Must be doc_type Bộ luật — never a Thông tư whose title merely mentions BLLĐ.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.core.logging import logger

_PREFERRED = (1, 5)
_ACCEPTABLE = (1, 5, 4, 0)


def _parse_as_of(as_of: str | date | None) -> date:
    if as_of is None:
        return date.today()
    if isinstance(as_of, date) and not isinstance(as_of, datetime):
        return as_of
    text = str(as_of).strip()[:10]
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y += 2000
                return date(y, m, d)
            except ValueError:
                pass
    try:
        return date.fromisoformat(text)
    except ValueError:
        return date.today()


def resolve_labor_code_document(as_of: str | date | None = None) -> dict[str, Any] | None:
    """Pick Bộ luật Lao động row effective on ``as_of`` (not guiding circulars)."""
    as_of_d = _parse_as_of(as_of)
    try:
        from app.infrastructure.db.connection import get_db
    except Exception as e:
        logger.warning("Labor code resolve: no DB (%s)", e)
        return None

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Strict: instrument level = Bộ luật; title starts with Bộ luật Lao động
                # (avoids TT 10/2020 whose title contains "… Bộ luật Lao động …").
                cur.execute(
                    """
                    SELECT doc_id, doc_num, title, doc_type, status_flag, eff_flag,
                           eff_from, eff_to, issue_date, source_url
                    FROM legal_documents
                    WHERE doc_type ILIKE %s
                      AND (
                        title ILIKE %s
                        OR title ILIKE %s
                        OR doc_num IN ('45/2019/QH14', '10/2012/QH13')
                      )
                      AND status_flag = ANY(%s)
                      AND (eff_from IS NULL OR eff_from <= %s)
                      AND (eff_to IS NULL OR eff_to > %s)
                    ORDER BY
                      CASE status_flag
                        WHEN 1 THEN 0 WHEN 5 THEN 1 WHEN 4 THEN 2 WHEN 0 THEN 3 ELSE 9
                      END,
                      COALESCE(issue_date, eff_from) DESC NULLS LAST,
                      doc_num DESC
                    LIMIT 1
                    """,
                    (
                        "Bộ luật%",
                        "Bộ luật Lao động%",
                        "Bộ Luật lao động%",
                        list(_ACCEPTABLE),
                        as_of_d,
                        as_of_d,
                    ),
                )
                row = cur.fetchone()
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
        from app.infrastructure.db.connection import get_db
    except Exception:
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_text, path::text
                    FROM legal_embeddings
                    WHERE doc_id = %s
                      AND is_effective
                      AND path::text ~ %s
                    ORDER BY nlevel(path) ASC, path
                    LIMIT %s
                    """,
                    (doc_id, alt, limit),
                )
                rows = cur.fetchall()
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
        from app.infrastructure.db.connection import get_db
    except Exception:
        return None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_text, path::text
                    FROM legal_embeddings
                    WHERE doc_id = %s
                      AND is_effective
                      AND path::text ~ %s
                    ORDER BY nlevel(path) ASC, path
                    LIMIT %s
                    """,
                    (doc_id, rf"\.D{article_num}(\.|$)", limit),
                )
                rows = cur.fetchall()
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
