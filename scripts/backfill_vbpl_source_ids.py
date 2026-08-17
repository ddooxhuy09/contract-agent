"""Backfill VBPL article/clause DOM ids into legal_embeddings.

The crawler preserves ``article_id`` and ``clause_id`` comments in full_text.
This script maps those comments back to the persisted D/K path so native
``#<id>`` links work for documents already in PostgreSQL.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
import os
import re

import psycopg2
from psycopg2.extras import execute_values


DEFAULT_DATABASE_URL = "postgresql://contractlens:contractlens@localhost:5433/contractlens"
_ARTICLE = re.compile(r"<!--\s*article_id:\s*([0-9A-Za-z_-]+)\s*-->")
_CLAUSE = re.compile(r"<!--\s*clause_id:\s*([0-9A-Za-z_-]+)\s*-->")
_ARTICLE_HEADING = re.compile(r"(?im)^\s*#{1,3}\s*\**\s*Điều\s+(\d+)\b")
_CLAUSE_NUMBER = re.compile(r"(?m)^\s*(?:Khoản\s+)?(\d+)[.)]\s+")
_ARTICLE_PATH = re.compile(r"(?:^|\.)D(\d+)(?:\.|$)")
_CLAUSE_PATH = re.compile(r"(?:^|\.)K(\d+)(?:\.|$)")


def _source_ids(full_text: str) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    article_ids: dict[str, str] = {}
    clause_ids: dict[tuple[str, str], str] = {}
    headings = list(_ARTICLE_HEADING.finditer(full_text))
    heading_positions = [m.start() for m in headings]

    def article_number_at(position: int) -> str | None:
        index = bisect_right(heading_positions, position) - 1
        return headings[index].group(1) if index >= 0 else None

    article_markers = list(_ARTICLE.finditer(full_text))
    for marker in article_markers:
        number = article_number_at(marker.start())
        if number and number not in article_ids:
            article_ids[number] = marker.group(1)

    all_markers = sorted([*article_markers, *_CLAUSE.finditer(full_text)], key=lambda m: m.start())
    previous_article_end = 0
    previous_clause_end = 0
    current_article = None
    for marker in all_markers:
        if marker.re is _ARTICLE:
            current_article = article_number_at(marker.start())
            previous_article_end = marker.end()
            previous_clause_end = marker.end()
            continue
        if current_article is None:
            continue
        start = previous_clause_end or previous_article_end
        segment = full_text[start : marker.start()]
        number_match = _CLAUSE_NUMBER.search(segment)
        if number_match:
            clause_ids.setdefault((current_article, number_match.group(1)), marker.group(1))
        previous_clause_end = marker.end()
    return article_ids, clause_ids


def backfill(database_url: str, apply: bool, doc_id_filter: str | None = None) -> tuple[int, int]:
    updated = 0
    documents = 0
    with psycopg2.connect(database_url) as conn:
        last_doc_id = ""
        while True:
            with conn.cursor() as cur:
                if doc_id_filter:
                    cur.execute(
                        """
                        SELECT doc_id, full_text
                        FROM legal_documents
                        WHERE doc_id = %s AND full_text IS NOT NULL AND btrim(full_text) <> ''
                        """,
                        (doc_id_filter,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT doc_id, full_text
                        FROM legal_documents
                        WHERE doc_id > %s
                          AND full_text IS NOT NULL AND btrim(full_text) <> ''
                        ORDER BY doc_id
                        LIMIT 250
                        """,
                        (last_doc_id,),
                    )
                document_rows = cur.fetchall()
            if not document_rows:
                break

            doc_ids = [doc_id for doc_id, _ in document_rows]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc_id, path::text
                    FROM legal_embeddings
                    WHERE doc_id = ANY(%s) AND source_element_id IS NULL AND path IS NOT NULL
                    """,
                    (doc_ids,),
                )
                paths_by_doc: dict[str, list[str]] = {}
                for chunk_doc_id, path in cur.fetchall():
                    paths_by_doc.setdefault(chunk_doc_id, []).append(path)

            changes = []
            for doc_id, full_text in document_rows:
                documents += 1
                article_ids, clause_ids = _source_ids(full_text)
                for path in paths_by_doc.get(doc_id, []):
                    article_match = _ARTICLE_PATH.search(path)
                    if not article_match:
                        continue
                    article = article_match.group(1)
                    clause_match = _CLAUSE_PATH.search(path)
                    source_id = None
                    if clause_match:
                        source_id = clause_ids.get((article, clause_match.group(1)))
                    if not source_id:
                        source_id = article_ids.get(article)
                    if source_id:
                        changes.append((source_id, path))
            if apply and changes:
                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        """
                        UPDATE legal_embeddings AS e
                        SET source_element_id = v.source_element_id
                        FROM (VALUES %s) AS v(source_element_id, path)
                        WHERE e.path = v.path::ltree
                        """,
                        changes,
                    )
                # Commit each page so a large corpus backfill can resume safely.
                conn.commit()
            updated += len(changes)
            if doc_id_filter:
                break
            last_doc_id = doc_ids[-1]
        if not apply:
            conn.rollback()
    return documents, updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write source ids; default is dry-run")
    parser.add_argument("--doc-id", help="Process one document only")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args()
    documents, updated = backfill(args.database_url, args.apply, args.doc_id)
    mode = "updated" if args.apply else "would update"
    print(f"scanned {documents} document(s); {mode} {updated} chunk source id(s)")


if __name__ == "__main__":
    main()
