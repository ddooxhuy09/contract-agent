"""Re-root hierarchy / document / path-relation ltree paths from sanitize(doc_num) to sanitize(doc_id).

Before 2026-11-22 the 7 hierarchy tables and legal_documents.path used the số hiệu as root
while legal_embeddings used doc_id, so `trg_hier_emb_eff` never matched a chunk and documents
sharing a số hiệu overwrote each other's tree. See docs/LEGAL_DB_INGEST_AUDIT.md (B3, B4).

One transaction. Default = dry run (runs everything, prints counts, ROLLBACK).

    python -m scripts.migrate_path_root_doc_id            # dry run
    python -m scripts.migrate_path_root_doc_id --apply    # applies schema.sql first, then COMMIT

Re-rooting fires `trg_hier_emb_eff`, which now syncs legal_embeddings.is_effective from the
hierarchy (status NOT IN (2, 3) = searchable). Documents listed under "need re-ingest" lost
their tree to another document with the same số hiệu: re-run ingest_legal_corpus --force on them.
"""

from __future__ import annotations

import argparse

from app.infrastructure.db.connection import get_connection
from app.infrastructure.db.schema_loader import apply_postgres_schema

_TABLES = (
    "legal_parts", "legal_chapters", "legal_sections", "legal_sub_sections",
    "legal_articles", "legal_clauses", "legal_points",
)
_FKS = (None, "part_id", "chapter_id", "section_id", "sub_section_id", "article_id", "clause_id")

_REROOT_FN = """
CREATE FUNCTION pg_temp.reroot(p ltree, r text) RETURNS ltree LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p IS NULL THEN NULL
                WHEN nlevel(p) = 1 THEN r::ltree
                ELSE r::ltree || subpath(p, 1) END
$$;
"""


def _owner_sql(i: int) -> str:
    """SELECT node id + sanitized doc_id of the owning document, walking the FK chain up to parts."""
    joins = [f"FROM {_TABLES[i]} n{i}"]
    for j in range(i, 0, -1):
        joins.append(f"JOIN {_TABLES[j - 1]} n{j - 1} ON n{j - 1}.id = n{j}.{_FKS[j]}")
    return f"SELECT n{i}.id, sanitize_doc_id_for_ltree(n0.doc_id) AS root " + " ".join(joins)


def migrate(cur) -> dict:
    stats: dict = {}
    cur.execute(_REROOT_FN)
    cur.execute(
        "UPDATE legal_documents SET path = sanitize_doc_id_for_ltree(doc_id)::ltree "
        "WHERE path IS DISTINCT FROM sanitize_doc_id_for_ltree(doc_id)::ltree"
    )
    stats["legal_documents"] = cur.rowcount

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
        stats[table] = cur.rowcount

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
    stats["legal_path_relations"] = cur.rowcount

    cur.execute(
        """
        SELECT count(*) FROM legal_path_relations r
        WHERE NOT EXISTS (SELECT 1 FROM legal_documents d
                          WHERE sanitize_doc_id_for_ltree(d.doc_id) = subpath(r.source_path, 0, 1)::text)
        """
    )
    stats["path_relations_unmapped_root"] = cur.fetchone()[0]

    # Chunks under an Điều that has no hierarchy row: the tree was taken by a same-số-hiệu doc.
    # Every doc sharing a sanitized số hiệu is listed too: the doc that took the tree may now
    # hold stray Điều of the other one, which only a re-ingest (delete_doc_content) removes.
    cur.execute(
        """
        SELECT doc_id, max(missing) FROM (
            SELECT e.doc_id, count(DISTINCT e.root_path) AS missing
            FROM legal_embeddings e
            WHERE e.root_path IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM legal_articles a WHERE a.path = e.root_path)
            GROUP BY 1
            UNION ALL
            SELECT d.doc_id, 0 FROM legal_documents d
            WHERE d.doc_num <> '' AND EXISTS (SELECT 1 FROM legal_parts p WHERE p.doc_id = d.doc_id)
              AND sanitize_doc_id_for_ltree(d.doc_num) IN (
                  SELECT sanitize_doc_id_for_ltree(d2.doc_num) FROM legal_documents d2
                  WHERE d2.doc_num <> ''
                    AND EXISTS (SELECT 1 FROM legal_parts p2 WHERE p2.doc_id = d2.doc_id)
                  GROUP BY 1 HAVING count(*) > 1)
        ) x GROUP BY 1 ORDER BY 2 DESC, 1
        """
    )
    stats["need_reingest"] = cur.fetchall()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="COMMIT (default: dry run + ROLLBACK)")
    args = parser.parse_args(argv)

    if args.apply:
        apply_postgres_schema()  # new trigger rules must be in place before re-rooting fires them
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            stats = migrate(cur)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    need = stats.pop("need_reingest")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(f"need re-ingest (doc_id, missing articles): {len(need)}")
    for doc_id, n in need[:50]:
        print(f"  {doc_id}: {n}")
    print("COMMITTED" if args.apply else "DRY RUN - rolled back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
