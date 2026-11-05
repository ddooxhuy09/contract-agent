"""Re-enable retrieval of the labor-law chunks that carry only the vbpl "status 4" flag.

Status 4 ("hết hiệu lực một phần") is a document-level metadata flag. The trigger-style rule
`is_effective = status_flag IN (1, 5)` therefore hid every chunk of the Labor Code (45/2019/QH14),
Decree 145/2020 and the OSH Law (84/2015/QH13) from vector search, although these texts are in
force and their hierarchy nodes carry no `eff_to`. See docs/kiem_tra_hieu_luc.md.

This script sets `is_effective = TRUE` for chunks of the allowed documents, except chunks under a
hierarchy node that is expired (status 2/3 or `eff_to` <= today). Changed ids are saved in
`legal_eff_fix_backup` so the change can be reverted. It is idempotent and dry-run by default.

    python -m scripts.fix_labor_effectivity                 # dry run: counts only
    python -m scripts.fix_labor_effectivity --apply         # write + backup
    python -m scripts.fix_labor_effectivity --revert TAG    # undo one run
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

# Documents whose status-4 flag was verified against the official text (see docs/kiem_tra_hieu_luc.md).
ALLOWED_DOC_NUMS = ("45/2019/QH14", "145/2020/NĐ-CP", "84/2015/QH13")

_NODE_TABLES = (
    "legal_parts", "legal_chapters", "legal_sections", "legal_sub_sections",
    "legal_articles", "legal_clauses", "legal_points",
)

# Chunk paths are rooted at the numeric doc_id while hierarchy paths are rooted at the doc's
# own label, so an expired node is mapped onto chunk space by swapping the first label.
_SELECT_SQL = f"""
WITH docs AS (
    SELECT doc_id, path FROM legal_documents WHERE doc_num = ANY(%(nums)s) AND status_flag = 4
), nodes AS (
    {" UNION ALL ".join(f"SELECT path, status_flag, eff_to FROM {t}" for t in _NODE_TABLES)}
), expired AS (
    SELECT d.doc_id,
           (sanitize_doc_id_for_ltree(d.doc_id)
            || CASE WHEN nlevel(n.path) > 1 THEN '.' || subpath(n.path, 1)::text ELSE '' END)::ltree AS mapped
    FROM docs d JOIN nodes n ON n.path <@ d.path
    WHERE n.status_flag IN (2, 3) OR n.eff_to <= CURRENT_DATE
)
SELECT e.id, e.doc_id FROM legal_embeddings e JOIN docs d ON d.doc_id = e.doc_id
WHERE NOT e.is_effective
  AND NOT EXISTS (SELECT 1 FROM expired x WHERE x.doc_id = e.doc_id AND e.path <@ x.mapped)
"""

_BACKUP_DDL = """
CREATE TABLE IF NOT EXISTS legal_eff_fix_backup (
    id BIGINT NOT NULL, doc_id TEXT NOT NULL, run_tag TEXT NOT NULL,
    fixed_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (run_tag, id)
)"""


def run(database_url: str, doc_nums: tuple[str, ...], apply: bool, revert: str | None) -> None:
    import psycopg2

    conn = psycopg2.connect(database_url, connect_timeout=10)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='300s'")
            if revert:
                cur.execute(
                    "UPDATE legal_embeddings e SET is_effective = FALSE FROM legal_eff_fix_backup b "
                    "WHERE b.run_tag = %s AND b.id = e.id AND e.is_effective",
                    (revert,),
                )
                print(f"reverted {cur.rowcount} chunks of run {revert}")
                return
            cur.execute(_SELECT_SQL, {"nums": list(doc_nums)})
            rows = cur.fetchall()
            per_doc: dict[str, int] = {}
            for _, doc_id in rows:
                per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
            print(f"chunks to re-enable: {len(rows)} {per_doc}")
            if not apply or not rows:
                print("dry run: nothing written" if not apply else "nothing to do")
                return
            tag = datetime.now(timezone.utc).strftime("labor_eff_%Y%m%d_%H%M%S")
            cur.execute(_BACKUP_DDL)
            cur.executemany(
                "INSERT INTO legal_eff_fix_backup (id, doc_id, run_tag) VALUES (%s, %s, %s)",
                [(i, d, tag) for i, d in rows],
            )
            cur.execute(
                "UPDATE legal_embeddings e SET is_effective = TRUE FROM legal_eff_fix_backup b "
                "WHERE b.run_tag = %s AND b.id = e.id",
                (tag,),
            )
            print(f"updated {cur.rowcount} chunks; backup run_tag={tag}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--revert", metavar="RUN_TAG", help="undo a previous run")
    parser.add_argument("--doc-num", action="append", choices=ALLOWED_DOC_NUMS,
                        help="repeatable; defaults to all allowed documents")
    args = parser.parse_args()

    from app.core.settings import get_settings

    run(get_settings().database_url, tuple(args.doc_num or ALLOWED_DOC_NUMS), args.apply, args.revert)
