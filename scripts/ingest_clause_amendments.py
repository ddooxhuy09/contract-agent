"""Ingest clause_amendments.json → legal_path_relations (ltree by số hiệu).

Usage:
  python -m scripts.ingest_clause_amendments PATH [--dry-run] [--limit N]

PATH = one document folder or a root of crawler folders (same layout as
``Bộ luật Hình sự số 100-2015-QH13--96122``).

Paths are rooted by sanitized doc_num (e.g. ``100_2015_QH13.P2.C2.D134.K1.g``),
not portal id. Cross-doc and same-doc edges both go to legal_path_relations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.logging import logger
from app.infrastructure.legal_corpus.clause_amendments import (
    DocNumResolver,
    load_clause_amendments_folder,
    load_doc_num_map_from_db,
    load_embedding_paths_for_docs,
    upsert_path_relations,
)
from app.infrastructure.legal_corpus.discover import discover_document_folders


def _safe_print(msg: str, *, file=None) -> None:
    stream = file or sys.stdout
    try:
        print(msg, file=stream)
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), file=stream)


def _collect_source_doc_ids(folder: Path) -> list[str]:
    import json

    path = folder / "clause_amendments.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    if not isinstance(data, dict):
        return []
    for payload in data.values():
        if not payload or not isinstance(payload, dict):
            continue
        for src in payload.get("sourceProvisions") or []:
            if isinstance(src, dict) and src.get("documentId"):
                ids.add(str(src["documentId"]))
    return sorted(ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest clause_amendments.json into legal_path_relations"
    )
    parser.add_argument(
        "path",
        type=str,
        help="Document folder or root containing crawler document folders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print rows only; do not write DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of folders to process",
    )
    args = parser.parse_args(argv)

    root = Path(args.path)
    folders = discover_document_folders(root)
    # Prefer folders that actually have clause_amendments.json
    folders = [f for f in folders if (f / "clause_amendments.json").is_file()]
    if args.limit is not None:
        folders = folders[: max(0, args.limit)]

    if not folders:
        _safe_print(f"No folders with clause_amendments.json under {root}")
        return 1

    resolver = DocNumResolver(by_doc_id={})
    if not args.dry_run:
        try:
            resolver = DocNumResolver(by_doc_id=load_doc_num_map_from_db())
            logger.info("Loaded %s doc_num mappings from legal_documents", len(resolver.by_doc_id))
        except Exception as e:
            logger.warning("DB doc_num map unavailable (%s); using titleDocument fallback", e)

    total_rows = 0
    total_inserted = 0
    for folder in folders:
        source_ids = _collect_source_doc_ids(folder)
        emb_map: dict[str, list[str]] = {}
        if not args.dry_run and source_ids:
            try:
                emb_map = load_embedding_paths_for_docs(source_ids)
            except Exception as e:
                logger.warning("embedding path lookup failed for %s: %s", folder.name, e)

        rows, warnings, meta = load_clause_amendments_folder(
            folder,
            doc_num_resolver=resolver,
            embedding_paths_by_doc=emb_map,
        )
        if meta.get("skipped"):
            _safe_print(f"SKIP {folder.name}: {meta.get('reason')}")
            continue

        _safe_print(
            f"{folder.name}: doc={meta.get('doc_num')} ({meta.get('doc_id')}) "
            f"relations={len(rows)} warnings={len(warnings)}"
        )
        for w in warnings[:8]:
            _safe_print(f"  warn: {w}")
        if len(warnings) > 8:
            _safe_print(f"  warn: … +{len(warnings) - 8} more")

        for r in rows[:10]:
            _safe_print(f"  {r.ref_type}: {r.source_path} → {r.target_path}")
        if len(rows) > 10:
            _safe_print(f"  … +{len(rows) - 10} more rows")

        total_rows += len(rows)
        if not args.dry_run and rows:
            inserted = upsert_path_relations(rows)
            total_inserted += inserted
            _safe_print(f"  inserted={inserted}")

    _safe_print(
        f"Done. folders={len(folders)} relations={total_rows} "
        f"inserted={total_inserted if not args.dry_run else '(dry-run)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
