"""Batch-ingest legal crawler folders into Postgres + Neo4j.

Usage:
  python -m scripts.ingest_legal_corpus PATH [--dry-run] [--limit N]
  python -m scripts.ingest_legal_corpus PATH              # resume: skip completed
  python -m scripts.ingest_legal_corpus PATH --force      # re-ingest / overwrite
  python -m scripts.ingest_legal_corpus PATH --reset-checkpoint
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.application.use_cases.legal_ingest import IngestLegalDocument
from app.core.logging import logger
from app.infrastructure.container import build_container
from app.infrastructure.db.schema_loader import apply_postgres_schema
from app.infrastructure.legal_corpus.assemble import load_document_folder
from app.infrastructure.legal_corpus.checkpoint import (
    checkpoint_path_for,
    completed_doc_ids,
    load_checkpoint,
    mark_completed,
    peek_doc_id,
    reset_checkpoint,
)
from app.infrastructure.legal_corpus.discover import discover_document_folders


def _safe_print(msg: str, *, file=None) -> None:
    """Avoid Windows cp1252 crashes on Vietnamese folder names."""
    stream = file or sys.stdout
    try:
        print(msg, file=stream)
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest legal crawler folders (batch)")
    parser.add_argument(
        "path",
        type=str,
        help="Document folder or root containing many document folders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print stats only; do not write DB or checkpoint",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of *new* documents to ingest this run (skips do not count)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even if doc is already in checkpoint / DB (overwrite)",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Delete checkpoint file under PATH then exit (does not delete DB rows)",
    )
    args = parser.parse_args(argv)

    root = Path(args.path)
    ck_path = checkpoint_path_for(root)

    if args.reset_checkpoint:
        reset_checkpoint(ck_path)
        _safe_print(f"Checkpoint reset: {ck_path}")
        return 0

    folders = discover_document_folders(root)
    if not folders:
        _safe_print(f"No document folders found under {root}", file=sys.stderr)
        return 1

    checkpoint = load_checkpoint(ck_path)
    done_ids = completed_doc_ids(checkpoint)
    _safe_print(
        f"Checkpoint {ck_path.name}: {len(done_ids)} completed doc(s)"
        + ("" if not args.force else " (--force: ignore skips)")
    )

    ingest = None
    chunk_repo = None
    if not args.dry_run:
        try:
            apply_postgres_schema()
        except Exception as e:
            logger.warning("Postgres schema apply failed: %s", e)
        c = build_container()
        try:
            c.graph.ensure_schema()
        except Exception as e:
            logger.warning("Neo4j schema ensure failed: %s", e)
        ingest = IngestLegalDocument(c.legal_docs, c.legal_chunks, c.embedder, c.graph)
        chunk_repo = c.legal_chunks

    ok = 0
    skipped = 0
    failed = 0
    ingested_this_run = 0

    for folder in folders:
        try:
            doc_id = peek_doc_id(folder)
        except Exception as e:
            failed += 1
            _safe_print(f"[fail] cannot read thuoc_tinh in folder: {e}", file=sys.stderr)
            continue

        already = doc_id in done_ids
        if not already and chunk_repo is not None and not args.force:
            try:
                if chunk_repo.count_for_doc(doc_id) > 0:
                    already = True
                    # Heal checkpoint so next run skips without DB hit
                    if not args.dry_run:
                        mark_completed(
                            ck_path,
                            doc_id=doc_id,
                            folder=folder,
                            chunk_count=chunk_repo.count_for_doc(doc_id),
                        )
            except Exception as e:
                logger.warning("count_for_doc(%s) failed: %s", doc_id, e)

        if already and not args.force:
            _safe_print(f"[skip] doc_id={doc_id} (already completed)")
            skipped += 1
            continue

        if args.limit is not None and ingested_this_run >= args.limit:
            _safe_print(f"[stop] reached --limit={args.limit}")
            break

        try:
            artifacts = load_document_folder(folder)
            n_chunks = len(artifacts["chunks"])
            n_rels = len(artifacts["relations"])
            n_path = len(artifacts.get("path_relations") or [])
            if args.dry_run:
                body = sum(1 for c in artifacts["chunks"] if c.get("chunk_type") == "body")
                eff = sum(1 for c in artifacts["chunks"] if c.get("chunk_type") == "effectivity")
                _safe_print(
                    f"[dry-run] doc_id={doc_id} chunks={n_chunks} "
                    f"(body={body} effectivity={eff}) relations={n_rels} "
                    f"path_relations={n_path}"
                )
                ok += 1
                ingested_this_run += 1
                continue
            assert ingest is not None
            result = ingest.execute(
                thuoc_tinh=artifacts["thuoc_tinh"],
                chunks=artifacts["chunks"],
                relations=artifacts["relations"],
                graph_nodes=artifacts["graph_nodes"],
                stub_docs=artifacts.get("stub_docs"),
                legal_nodes=artifacts.get("legal_nodes"),
                path_relations=artifacts.get("path_relations"),
            )
            mark_completed(
                ck_path,
                doc_id=result["doc_id"],
                folder=folder,
                chunk_count=result["chunk_count"],
                relation_count=result["relation_count"],
            )
            done_ids.add(result["doc_id"])
            _safe_print(
                f"[ok] doc_id={result['doc_id']} chunks={result['chunk_count']} "
                f"relations={result['relation_count']} "
                f"path_relations={result.get('path_relation_count', 0)}"
            )
            ok += 1
            ingested_this_run += 1
        except Exception as e:
            failed += 1
            logger.exception("Failed ingest for %s: %s", folder, e)
            _safe_print(f"[fail] doc_id={doc_id}: {e}", file=sys.stderr)

    _safe_print(
        f"Done. ok={ok} skipped={skipped} failed={failed} "
        f"total_folders={len(folders)} checkpoint={ck_path}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
