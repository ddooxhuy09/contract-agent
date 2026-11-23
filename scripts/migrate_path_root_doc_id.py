"""Bring an existing legal DB to schema.sql: every hierarchy / document / path-relation ltree
rooted at sanitize(doc_id), hierarchy shaped as schema.sql (FK chain, "Không có" scaffolds).

Two layouts are handled (detected from the DB):

* legacy (DBs created before the doc_id-less hierarchy): every hierarchy table has its own
  ``doc_id`` column, UNIQUE (doc_id, path), nullable SET NULL parent FKs (some pointing into
  another document's tree), paths rooted at the số hiệu. The current code cannot write into it
  (``ON CONFLICT (path)`` has no matching constraint). The 7 tables are moved to schema
  ``legacy_hierarchy``, recreated from schema.sql, and refilled per document through
  PgLegalChunkRepository.upsert_nodes (same structure as a fresh ingest), keyed by each row's
  own doc_id + path. content / created_at are copied back. Khoản / Điểm with no Điều parent
  cannot exist in schema.sql (a fresh ingest drops them too) and are reported as dropped.
* schema.sql layout with số-hiệu roots: paths re-rooted through the FK chain.

Then legal_path_relations roots are mapped, and legal_embeddings.is_effective is recomputed
from the deepest matching hierarchy node (document status for chunks outside a Điều):
searchable = status NOT IN (2, 3).

One transaction (schema.sql included). Stop the API first: the legal tables stay locked.
Default = dry run (everything runs, counts printed, ROLLBACK).

    python -m scripts.migrate_path_root_doc_id            # dry run
    python -m scripts.migrate_path_root_doc_id --apply    # COMMIT

After --apply on a legacy DB the old rows stay in schema legacy_hierarchy for checking;
drop it when satisfied:  DROP SCHEMA legacy_hierarchy CASCADE;
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.core.settings import get_settings
from app.domain.entities.legal import LegalNode
from app.infrastructure.db.connection import transaction
from app.infrastructure.db.legal_repository import PgLegalChunkRepository

_TABLES = (
    "legal_parts", "legal_chapters", "legal_sections", "legal_sub_sections",
    "legal_articles", "legal_clauses", "legal_points",
)
_FKS = (None, "part_id", "chapter_id", "section_id", "sub_section_id", "article_id", "clause_id")
_LEVELS = ("Part", "Chapter", "Section", "SubSection", "Article", "Clause", "Point")
LEGACY = "legacy_hierarchy"

_REROOT_FN = """
CREATE FUNCTION pg_temp.reroot(p ltree, r text) RETURNS ltree LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p IS NULL THEN NULL
                WHEN nlevel(p) = 1 THEN r::ltree
                ELSE r::ltree || subpath(p, 1) END
$$;
"""


def _schema_sql() -> str:
    path = Path(get_settings().schema_sql_path)
    if not path.is_file():
        path = Path(__file__).resolve().parents[1] / "schema.sql"
    return path.read_text(encoding="utf-8")


def _is_legacy(cur) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = 'legal_chapters' AND column_name = 'doc_id'"
    )
    return cur.fetchone() is not None


def _count(cur, sql: str) -> int:
    cur.execute(sql)
    return int(cur.fetchone()[0])


def _owner_sql(i: int) -> str:
    """SELECT node id + sanitized doc_id of the owning document, walking the FK chain up to parts."""
    joins = [f"FROM {_TABLES[i]} n{i}"]
    for j in range(i, 0, -1):
        joins.append(f"JOIN {_TABLES[j - 1]} n{j - 1} ON n{j - 1}.id = n{j}.{_FKS[j]}")
    return f"SELECT n{i}.id, sanitize_doc_id_for_ltree(n0.doc_id) AS root " + " ".join(joins)


def _reroot_new_layout(cur, stats: dict) -> None:
    for i, table in enumerate(_TABLES):
        cur.execute(
            f"""
            UPDATE {table} t
            SET path = pg_temp.reroot(t.path, o.root),
                parent_path = pg_temp.reroot(t.parent_path, o.root)
            FROM ({_owner_sql(i)}) o
            WHERE o.id = t.id AND subpath(t.path, 0, 1)::text <> o.root
            """
        )
        stats[f"rerooted {table}"] = cur.rowcount


def _rebuild_legacy(cur, stats: dict) -> None:
    legacy_counts = {t: _count(cur, f"SELECT count(*) FROM {t}") for t in _TABLES}
    cur.execute(f"CREATE SCHEMA {LEGACY}")
    for t in _TABLES:
        cur.execute(f"ALTER TABLE public.{t} SET SCHEMA {LEGACY}")
        cur.execute(f"ALTER TABLE {LEGACY}.{t} DISABLE TRIGGER USER")
    cur.execute(_schema_sql())  # recreates the 7 tables (+ triggers, indexes) in public
    cur.execute(
        "UPDATE legal_documents SET path = sanitize_doc_id_for_ltree(doc_id)::ltree "
        "WHERE path IS DISTINCT FROM sanitize_doc_id_for_ltree(doc_id)::ltree"
    )
    stats["legal_documents path"] = cur.rowcount
    # Triggers off while refilling: statuses are copied as they are (refresh functions run
    # after the migration), and is_effective is recomputed once at the end.
    for t in _TABLES:
        cur.execute(f"ALTER TABLE public.{t} DISABLE TRIGGER USER")

    cur.execute(
        " UNION ".join(f"SELECT doc_id FROM {LEGACY}.{t}" for t in _TABLES) + " ORDER BY 1"
    )
    doc_ids = [r[0] for r in cur.fetchall()]
    repo = PgLegalChunkRepository()
    started = time.monotonic()
    for i, doc_id in enumerate(doc_ids, 1):
        nodes: list[LegalNode] = []
        for level, t in zip(_LEVELS, _TABLES):
            cur.execute(
                f"""
                SELECT pg_temp.reroot(path, r)::text, pg_temp.reroot(parent_path, r)::text,
                       title, eff_from, eff_to, eff_flag, status_flag
                FROM {LEGACY}.{t}, (SELECT sanitize_doc_id_for_ltree(%s) AS r) x
                WHERE doc_id = %s ORDER BY id
                """,
                (doc_id, doc_id),
            )
            nodes += [
                LegalNode(doc_id=doc_id, level=level, path=p, parent_path=pp, label=title,
                          eff_from=ef, eff_to=et, eff_flag=fl, status_flag=int(sf or 0))
                for p, pp, title, ef, et, fl, sf in cur.fetchall()
            ]
        repo.upsert_nodes(nodes)  # shares this transaction (transaction() context)
        if i % 2000 == 0:
            print(f"  rebuilt {i}/{len(doc_ids)} docs ({time.monotonic() - started:.0f}s)", flush=True)
    stats["docs rebuilt"] = len(doc_ids)

    for t in _TABLES:
        cur.execute(
            f"""
            UPDATE public.{t} n
            SET content = COALESCE(NULLIF(l.content, ''), n.content), created_at = l.created_at
            FROM {LEGACY}.{t} l
            WHERE n.path = pg_temp.reroot(l.path, sanitize_doc_id_for_ltree(l.doc_id))
            """
        )
        copied = cur.rowcount
        # What the INSERT trigger does for a row without a label (scaffolds, unlabeled rows).
        cur.execute(
            f"UPDATE public.{t} SET eff_flag = eff_flag_for_status(status_flag) "
            "WHERE TRIM(COALESCE(eff_flag, '')) = ''"
        )
        new = _count(cur, f"SELECT count(*) FROM public.{t}")
        stats[t] = (
            f"legacy {legacy_counts[t]} -> new {new} "
            f"(kept {copied}, scaffolds {new - copied}, dropped {legacy_counts[t] - copied})"
        )
        cur.execute(f"ALTER TABLE public.{t} ENABLE TRIGGER USER")

    # schema.sql has no slot for a Khoản without a Điều or an Điểm without a Khoản (a fresh ingest
    # drops them too), so only rows whose required parent survived count as lost.
    for t, parent in (("legal_clauses", "legal_articles"), ("legal_points", "legal_clauses")):
        stats[f"CHECK {t} legacy rows lost although their parent exists"] = _count(
            cur,
            f"""
            SELECT count(*) FROM (
                SELECT pg_temp.reroot(path, sanitize_doc_id_for_ltree(doc_id)) p,
                       pg_temp.reroot(parent_path, sanitize_doc_id_for_ltree(doc_id)) pp
                FROM {LEGACY}.{t}
            ) l
            WHERE NOT EXISTS (SELECT 1 FROM public.{t} n WHERE n.path = l.p)
              AND EXISTS (SELECT 1 FROM public.{parent} a WHERE a.path = l.pp)
            """,
        )
    for t in _TABLES[:5]:
        stats[f"CHECK {t} legacy rows lost"] = _count(
            cur,
            f"""
            SELECT count(*) FROM {LEGACY}.{t} l WHERE NOT EXISTS (
                SELECT 1 FROM public.{t} n
                WHERE n.path = pg_temp.reroot(l.path, sanitize_doc_id_for_ltree(l.doc_id)))
            """,
        )


def _map_path_relations(cur, stats: dict) -> None:
    # clause_amendments rows were rooted at số hiệu: map only roots that belong to exactly one doc.
    cur.execute(
        """
        CREATE TEMP TABLE root_map ON COMMIT DROP AS
        SELECT sanitize_doc_id_for_ltree(doc_num) AS old_root,
               min(sanitize_doc_id_for_ltree(doc_id)) AS new_root
        FROM legal_documents
        WHERE doc_num <> ''
        GROUP BY 1
        HAVING count(*) = 1
           AND sanitize_doc_id_for_ltree(doc_num) NOT IN (
               SELECT sanitize_doc_id_for_ltree(doc_id) FROM legal_documents)
        """
    )
    cur.execute(
        """
        CREATE TEMP TABLE moved ON COMMIT DROP AS
        SELECT r.id,
               pg_temp.reroot(r.source_path, COALESCE(s.new_root, subpath(r.source_path, 0, 1)::text)) AS source_path,
               pg_temp.reroot(r.target_path, COALESCE(t.new_root, subpath(r.target_path, 0, 1)::text)) AS target_path,
               r.ref_type, r.created_at
        FROM legal_path_relations r
        LEFT JOIN root_map s ON s.old_root = subpath(r.source_path, 0, 1)::text
        LEFT JOIN root_map t ON t.old_root = subpath(r.target_path, 0, 1)::text
        WHERE s.old_root IS NOT NULL OR t.old_root IS NOT NULL
        """
    )
    cur.execute("DELETE FROM legal_path_relations WHERE id IN (SELECT id FROM moved)")
    cur.execute(
        """
        INSERT INTO legal_path_relations (source_path, target_path, ref_type, created_at)
        SELECT source_path, target_path, ref_type, created_at FROM moved
        ON CONFLICT (source_path, target_path, ref_type) DO NOTHING
        """
    )
    stats["legal_path_relations re-rooted"] = cur.rowcount
    stats["CHECK path_relations with unknown root"] = _count(
        cur,
        """
        SELECT count(*) FROM legal_path_relations r
        WHERE NOT EXISTS (SELECT 1 FROM legal_documents d
                          WHERE sanitize_doc_id_for_ltree(d.doc_id) = subpath(r.source_path, 0, 1)::text)
        """,
    )


def _recompute_is_effective(cur, stats: dict) -> None:
    before = _count(cur, "SELECT count(*) FROM legal_embeddings WHERE is_effective")
    cur.execute(
        """
        UPDATE legal_embeddings e
        SET is_effective = s.st NOT IN (2, 3)
        FROM (
            SELECT e2.id, COALESCE(
                (SELECT p.status_flag FROM legal_points p WHERE p.path = e2.path),
                (SELECT c.status_flag FROM legal_clauses c WHERE c.path = e2.path),
                (SELECT c.status_flag FROM legal_clauses c
                 WHERE nlevel(e2.path) > 1 AND c.path = subpath(e2.path, 0, nlevel(e2.path) - 1)),
                (SELECT a.status_flag FROM legal_articles a WHERE a.path = e2.root_path),
                d.status_flag) AS st
            FROM legal_embeddings e2 JOIN legal_documents d ON d.doc_id = e2.doc_id
        ) s
        WHERE s.id = e.id AND e.is_effective IS DISTINCT FROM (s.st NOT IN (2, 3))
        """
    )
    stats["is_effective changed"] = cur.rowcount
    after = _count(cur, "SELECT count(*) FROM legal_embeddings WHERE is_effective")
    stats["is_effective true"] = f"{before} -> {after}"


def migrate(cur) -> dict:
    stats: dict = {}
    cur.execute(_REROOT_FN)
    legacy = _is_legacy(cur)
    stats["layout"] = "legacy (doc_id on every hierarchy table)" if legacy else "schema.sql"
    if legacy:
        _rebuild_legacy(cur, stats)
    else:
        cur.execute(_schema_sql())
        cur.execute(
            "UPDATE legal_documents SET path = sanitize_doc_id_for_ltree(doc_id)::ltree "
            "WHERE path IS DISTINCT FROM sanitize_doc_id_for_ltree(doc_id)::ltree"
        )
        stats["legal_documents path"] = cur.rowcount
        _reroot_new_layout(cur, stats)
    _map_path_relations(cur, stats)
    _recompute_is_effective(cur, stats)

    for t in _TABLES:
        stats[f"CHECK {t} rows not rooted at doc_id"] = _count(
            cur,
            f"""
            SELECT count(*) FROM {t} n WHERE NOT EXISTS (
                SELECT 1 FROM legal_documents d
                WHERE sanitize_doc_id_for_ltree(d.doc_id) = subpath(n.path, 0, 1)::text)
            """,
        )
    stats["CHECK chunks not rooted at their doc_id"] = _count(
        cur,
        "SELECT count(*) FROM legal_embeddings "
        "WHERE subpath(path, 0, 1)::text <> sanitize_doc_id_for_ltree(doc_id)",
    )

    # Chunks under a Điều that has no hierarchy row: the document needs a re-ingest.
    # In the schema.sql layout every doc sharing a sanitized số hiệu is listed too: the doc that
    # took the shared tree may hold stray Điều of the other one.
    dup_docs = "" if legacy else """
            UNION ALL
            SELECT d.doc_id, 0 FROM legal_documents d
            WHERE d.doc_num <> '' AND EXISTS (SELECT 1 FROM legal_parts p WHERE p.doc_id = d.doc_id)
              AND sanitize_doc_id_for_ltree(d.doc_num) IN (
                  SELECT sanitize_doc_id_for_ltree(d2.doc_num) FROM legal_documents d2
                  WHERE d2.doc_num <> ''
                    AND EXISTS (SELECT 1 FROM legal_parts p2 WHERE p2.doc_id = d2.doc_id)
                  GROUP BY 1 HAVING count(*) > 1)"""
    cur.execute(
        f"""
        SELECT doc_id, max(missing) FROM (
            SELECT e.doc_id, count(DISTINCT e.root_path) AS missing
            FROM legal_embeddings e
            WHERE e.root_path IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM legal_articles a WHERE a.path = e.root_path)
            GROUP BY 1{dup_docs}
        ) x GROUP BY 1 ORDER BY 2 DESC, 1
        """
    )
    stats["need_reingest"] = cur.fetchall()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="COMMIT (default: dry run + ROLLBACK)")
    args = parser.parse_args(argv)

    started = time.monotonic()
    with transaction() as conn:
        with conn.cursor() as cur:
            stats = migrate(cur)
        if not args.apply:
            conn.rollback()  # transaction() then commits an empty transaction

    need = stats.pop("need_reingest")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(f"need re-ingest (doc_id, missing articles): {len(need)}")
    for doc_id, n in need:
        print(f"  {doc_id}: {n}")
    print(f"{'COMMITTED' if args.apply else 'DRY RUN - rolled back'} in {time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
