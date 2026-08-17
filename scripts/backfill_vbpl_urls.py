"""Populate missing VBPL detail URLs for already-ingested legal documents.

Only documents with stored full text are backfilled. Those are the documents
that came through the VBPL corpus ingest and can be linked back to a detail
page using the same slug rule as the crawler.
"""

from __future__ import annotations

import argparse
import os

import psycopg2

from scripts.crawl_vbpl.fetch_list import slugify_title


DEFAULT_DATABASE_URL = "postgresql://contractlens:contractlens@localhost:5433/contractlens"


def backfill(database_url: str, apply: bool) -> int:
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id, title, eff_from, eff_to
                FROM legal_documents
                WHERE (source_url IS NULL OR btrim(source_url) = '')
                  AND full_text IS NOT NULL
                  AND btrim(full_text) <> ''
                  AND (eff_from IS NULL OR eff_to IS NULL OR eff_from < eff_to)
                ORDER BY doc_id
                """
            )
            rows = cur.fetchall()
            updates = [
                (
                    f"https://vbpl.vn/van-ban/chi-tiet/{slugify_title(title, str(doc_id))}?tabs=toan-van",
                    str(doc_id),
                )
                for doc_id, title, _eff_from, _eff_to in rows
            ]
            if apply and updates:
                cur.executemany(
                    """
                    UPDATE legal_documents
                    SET source_url = %s, updated_at = NOW()
                    WHERE doc_id = %s
                      AND (source_url IS NULL OR btrim(source_url) = '')
                    """,
                    updates,
                )
        if not apply:
            conn.rollback()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write URLs; default is dry-run")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args()
    count = backfill(args.database_url, apply=args.apply)
    mode = "updated" if args.apply else "would update"
    print(f"{mode} {count} legal document URL(s)")


if __name__ == "__main__":
    main()
