"""Backfill effective_date, expiry_date, doc_type for docs missing metadata.

Usage:
  docker exec contractlens-api-1 python -m scripts.backfill_doc_dates [--limit N] [--dry-run]
  docker exec contractlens-api-1 python -m scripts.backfill_doc_dates --pre-2010    # mark pre-2010 as expired
  docker exec contractlens-api-1 python -m scripts.backfill_doc_dates --eff-to        # fill eff_to from relations
  docker exec contractlens-api-1 python -m scripts.backfill_doc_dates --sync-neo4j    # sync status to Neo4j
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from app.core.logging import logger
from app.infrastructure.container import build_container
from app.infrastructure.db.connection import get_db
from app.infrastructure.legal_corpus.metadata_extractor import (
    detect_doc_type_from_title,
    extract_doc_metadata,
)


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


def backfill_from_chunks(limit: int | None = None, dry_run: bool = False) -> dict:
    """Extract dates from effectivity chunks for docs with missing eff_from."""
    today = str(date.today())
    rows = []
    noeff_rows = []

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT d.doc_id, d.title, d.issue_date,
                   d.eff_from, d.status_flag, d.doc_type,
                   c.chunk_text
            FROM legal_documents d
            JOIN legal_section_chunks c ON c.doc_id = d.doc_id
            WHERE c.chunk_type = 'effectivity'
              AND d.status_flag = 0
            ORDER BY d.doc_id
            """
            + (f" LIMIT {int(limit)}" if limit else "")
        )
        rows = cur.fetchall()

        cur.execute(
            """
            SELECT DISTINCT d.doc_id, d.title, d.issue_date,
                   d.eff_from, d.status_flag, d.doc_type
            FROM legal_documents d
            JOIN legal_section_chunks c ON c.doc_id = d.doc_id
            WHERE d.status_flag = 0
              AND d.doc_id NOT IN (
                  SELECT DISTINCT doc_id FROM legal_section_chunks WHERE chunk_type = 'effectivity'
              )
            ORDER BY d.doc_id
            """
            + (f" LIMIT {int(limit) if limit else 2500}" if limit else " LIMIT 2500")
        )
        noeff_rows = cur.fetchall()

    _safe_print(f"Found {len(rows)} docs with effectivity chunks (status_flag=0)")
    _safe_print(f"Found {len(noeff_rows)} docs without effectivity chunk (body-only)")

    updated = 0
    updates = []

    # Process docs with effectivity chunks
    for row in rows:
        doc_id, title, issue_date_str, eff_from, status_flag, doc_type, chunk_text = row
        result = extract_doc_metadata(
            title=title or "",
            content=chunk_text or "",
            issued_date=str(issue_date_str) if issue_date_str else None,
            enf_texts=[chunk_text] if chunk_text else None,
        )

        new_eff = result["effective_date"]
        new_expiry = result["expiry_date"]
        new_doc_type = result["doc_type"] or doc_type

        if new_eff or new_doc_type != doc_type:
            updates.append((doc_id, title, new_eff, new_expiry, new_doc_type, status_flag, eff_from))

    # Process docs without effectivity chunk (use body content to find enforcement article)
    for row in noeff_rows:
        doc_id, title, issue_date_str, eff_from, status_flag, doc_type = row
        if isinstance(status_flag, int) and status_flag != 0:
            continue

        body_texts = []
        enf_like = []
        with get_db() as conn:
            cur2 = conn.cursor()
            cur2.execute(
                """SELECT chunk_text FROM legal_section_chunks
                   WHERE doc_id = %s AND chunk_type = 'body'
                   ORDER BY id LIMIT 3""",
                (doc_id,),
            )
            body_texts = [r[0] for r in cur2.fetchall()]

            cur2.execute(
                """SELECT chunk_text FROM legal_section_chunks
                   WHERE doc_id = %s AND chunk_type = 'body'
                     AND (chunk_text ILIKE '%hiệu lực%'
                          OR chunk_text ILIKE '%thi hành%'
                          OR chunk_text ILIKE '%có hiệu lực%')
                   LIMIT 2""",
                (doc_id,),
            )
            enf_like = [r[0] for r in cur2.fetchall()]

        full_text = "\n".join(body_texts) if body_texts else ""

        result = extract_doc_metadata(
            title=title or "",
            content=full_text,
            issued_date=str(issue_date_str) if issue_date_str else None,
            enf_texts=enf_like if enf_like else None,
        )

        new_eff = result["effective_date"]
        new_expiry = result["expiry_date"]
        new_doc_type = result["doc_type"] or doc_type

        if new_eff or new_doc_type != doc_type:
            updates.append((doc_id, title, new_eff, new_expiry, new_doc_type, status_flag, eff_from))

    if dry_run:
        for (doc_id, title, new_eff, new_expiry, new_doc_type, _, old_eff) in updates:
            _safe_print(f"[dry] {doc_id} | {title[:60]} | eff={old_eff}→{new_eff} | type→{new_doc_type}")
        _safe_print(f"\nWould update {len(updates)} docs")
        return {"updated": len(updates), "rows": len(rows) + len(noeff_rows)}

    with get_db() as conn:
        cur = conn.cursor()
        for (doc_id, title, new_eff, new_expiry, new_doc_type, old_status, old_eff) in updates:
            cur.execute(
                """UPDATE legal_documents SET eff_from = COALESCE(%s, eff_from),
                   eff_to = COALESCE(%s, eff_to),
                   doc_type = %s, updated_at = NOW()
                   WHERE doc_id = %s""",
                (new_eff, new_expiry, new_doc_type, doc_id),
            )
            logger.info("backfill doc=%s eff=%s type=%s", doc_id, new_eff, new_doc_type)
            updated += 1

        cur.execute("SELECT refresh_status_flags()")

    _safe_print(f"\nUpdated {updated} docs. Ran refresh_status_flags.")
    return {"updated": updated, "total_rows": len(rows) + len(noeff_rows)}


def mark_pre_2010_expired(dry_run: bool = False) -> int:
    """Mark all docs with issue_date <= 2010-12-31 as expired."""
    with get_db() as conn:
        cur = conn.cursor()
        if dry_run:
            cur.execute(
                "SELECT count(*) FROM legal_documents WHERE issue_date <= '2010-12-31' AND status_flag IN (0, 1)"
            )
            cnt = cur.fetchone()[0]
            _safe_print(f"[dry] Would mark {cnt} docs as expired (issue_date <= 2010)")
            return cnt

        cur.execute(
            """UPDATE legal_documents SET status_flag = 2, updated_at = NOW()
               WHERE issue_date <= '2010-12-31' AND status_flag IN (0, 1)"""
        )
        cnt = cur.rowcount
    _safe_print(f"Marked {cnt} docs as expired (issue_date <= 2010-12-31)")
    return cnt


def fill_eff_to_from_relations(dry_run: bool = False) -> int:
    """Fill eff_to from replacing documents."""
    with get_db() as conn:
        cur = conn.cursor()
        if dry_run:
            cur.execute(
                """
                SELECT count(DISTINCT d.doc_id) FROM legal_documents d
                JOIN legal_document_relations ldr ON ldr.to_doc_id = d.doc_id
                JOIN legal_documents nd ON nd.doc_id = ldr.from_doc_id
                WHERE ldr.relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
                  AND nd.eff_from IS NOT NULL AND nd.status_flag = 1
                  AND d.eff_to IS NULL
                """
            )
            cnt = cur.fetchone()[0]
            _safe_print(f"[dry] Would fill eff_to for {cnt} docs from relations")
            return cnt

        cur.execute(
            """
            UPDATE legal_documents d SET eff_to = (
                SELECT MIN(nd.eff_from) FROM legal_document_relations ldr
                JOIN legal_documents nd ON nd.doc_id = ldr.from_doc_id
                WHERE ldr.to_doc_id = d.doc_id
                  AND ldr.relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
                  AND nd.eff_from IS NOT NULL AND nd.status_flag = 1
            )
            WHERE d.eff_to IS NULL
              AND EXISTS (
                  SELECT 1 FROM legal_document_relations ldr2
                  JOIN legal_documents nd2 ON nd2.doc_id = ldr2.from_doc_id
                  WHERE ldr2.to_doc_id = d.doc_id
                    AND ldr2.relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
                    AND nd2.eff_from IS NOT NULL AND nd2.status_flag = 1
              )
            """
        )
        cnt = cur.rowcount

        # Cascade: mark docs with eff_to <= today as expired
        cur.execute(
            """
            UPDATE legal_documents SET status_flag = 2, updated_at = NOW()
            WHERE eff_to IS NOT NULL AND eff_to <= CURRENT_DATE AND status_flag NOT IN (2, 4)
            """
        )
        cascade_cnt = cur.rowcount

    _safe_print(f"Filled eff_to from relations for {cnt} docs")
    _safe_print(f"Cascade expired {cascade_cnt} docs")
    return cnt


def sync_status_to_neo4j(dry_run: bool = False) -> int:
    """Mirror status_flag from PostgreSQL to Neo4j Document nodes."""
    c = build_container()
    graph = c.graph
    rows = []
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT doc_id, status_flag FROM legal_documents WHERE status_flag != 0"
        )
        rows = cur.fetchall()

    docs = [{"doc_id": r[0], "status_flag": r[1]} for r in rows]
    _safe_print(f"Found {len(docs)} docs with status_flag != 0 to sync")

    if dry_run:
        _safe_print("[dry] Would sync to Neo4j")
        return len(docs)

    batch_size = 500
    total = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        synced = graph.bulk_sync_doc_status(batch)
        total += synced
    _safe_print(f"Synced {total} docs to Neo4j")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill missing document dates")
    parser.add_argument("--limit", type=int, default=None, help="Max docs to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--pre-2010", action="store_true", help="Mark pre-2010 docs as expired")
    parser.add_argument("--eff-to", action="store_true", help="Fill eff_to from relations")
    parser.add_argument("--sync-neo4j", action="store_true", help="Sync status_flag to Neo4j")
    args = parser.parse_args(argv)

    if args.pre_2010:
        mark_pre_2010_expired(dry_run=args.dry_run)
        return 0
    if args.eff_to:
        fill_eff_to_from_relations(dry_run=args.dry_run)
        return 0
    if args.sync_neo4j:
        sync_status_to_neo4j(dry_run=args.dry_run)
        return 0

    backfill_from_chunks(limit=args.limit, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
