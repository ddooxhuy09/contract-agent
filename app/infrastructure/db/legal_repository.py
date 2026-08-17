from __future__ import annotations

from app.domain.entities.legal import (
    LegalChunk,
    LegalChunkRelation,
    LegalDocRelation,
    LegalDocument,
    LegalNode,
)
from app.infrastructure.db.connection import get_db
from app.infrastructure.db.hierarchy_chain import (
    KHONG_CO,
    ensure_chain_for_article,
    ensure_doc_root_path,
    ensure_part,
)
from app.infrastructure.legal_corpus.muc_luc_paths import (
    article_root_ltree,
    chunk_ref_to_ltree,
    sanitize_doc_id_for_ltree,
)

_HIERARCHY_LEVELS = frozenset(
    {"Part", "Chapter", "Section", "SubSection", "Article", "Clause", "Point"}
)


def _path_leaf(path: str) -> str:
    return (path or "").rsplit(".", 1)[-1]


def _node_title(n: LegalNode) -> str:
    """Prefer muc_luc label; else path leaf / sort_order; else Không có."""
    if n.label and str(n.label).strip():
        return str(n.label).strip()
    leaf = _path_leaf(n.path)
    if leaf:
        return leaf
    if n.sort_order is not None:
        return str(n.sort_order)
    return KHONG_CO


def _lookup_id_by_path(cur, table: str, path: str | None) -> int | None:
    if not path:
        return None
    cur.execute(f"SELECT id FROM {table} WHERE path = %s::ltree", (path,))
    row = cur.fetchone()
    return int(row[0]) if row else None


_EFF_COLS = "eff_from, eff_to, eff_flag, status_flag"
_EFF_UPSERT = """
    eff_from = COALESCE(EXCLUDED.eff_from, {t}.eff_from),
    eff_to = COALESCE(EXCLUDED.eff_to, {t}.eff_to),
    eff_flag = COALESCE(EXCLUDED.eff_flag, {t}.eff_flag),
    status_flag = CASE
        WHEN EXCLUDED.status_flag IS DISTINCT FROM 0 THEN EXCLUDED.status_flag
        ELSE {t}.status_flag
    END
"""


def _eff_params(n: LegalNode) -> tuple:
    return (n.eff_from, n.eff_to, n.eff_flag, int(n.status_flag or 0))


class PgLegalDocumentRepository:
    def upsert(self, doc: LegalDocument) -> None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO legal_documents (
                        doc_id, doc_num, title, doc_type, majors, fields,
                        issue_date, eff_from, eff_to, eff_flag,
                        status_flag, agency, signer_name, signer_title,
                        source_url, full_text, path, crawled_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s::ltree, COALESCE(%s, NOW())
                    )
                    ON CONFLICT (doc_id) DO UPDATE SET
                        doc_num = EXCLUDED.doc_num,
                        title = EXCLUDED.title,
                        doc_type = EXCLUDED.doc_type,
                        majors = EXCLUDED.majors,
                        fields = EXCLUDED.fields,
                        issue_date = EXCLUDED.issue_date,
                        eff_from = EXCLUDED.eff_from,
                        eff_to = EXCLUDED.eff_to,
                        eff_flag = EXCLUDED.eff_flag,
                        status_flag = EXCLUDED.status_flag,
                        agency = EXCLUDED.agency,
                        signer_name = EXCLUDED.signer_name,
                        signer_title = EXCLUDED.signer_title,
                        source_url = EXCLUDED.source_url,
                        full_text = EXCLUDED.full_text,
                        path = COALESCE(EXCLUDED.path, legal_documents.path),
                        updated_at = NOW()
                    """,
                    (
                        doc.doc_id,
                        doc.doc_num,
                        doc.title,
                        doc.doc_type,
                        doc.majors or [],
                        doc.fields or [],
                        doc.issue_date,
                        doc.eff_from,
                        doc.eff_to,
                        doc.eff_flag,
                        doc.status_flag,
                        doc.agency,
                        doc.signer_name,
                        doc.signer_title,
                        doc.source_url,
                        doc.full_text,
                        sanitize_doc_id_for_ltree(doc.doc_num or doc.doc_id),
                        doc.crawled_at,
                    ),
                )

    def get(self, doc_id: str) -> LegalDocument | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc_id, doc_num, title, doc_type, majors, fields,
                           issue_date, eff_from, eff_to, eff_flag,
                           status_flag, agency, signer_name, signer_title,
                           source_url, full_text, crawled_at
                    FROM legal_documents WHERE doc_id = %s
                    """,
                    (doc_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return LegalDocument(
            doc_id=row[0],
            doc_num=row[1],
            title=row[2],
            doc_type=row[3],
            majors=list(row[4] or []),
            fields=list(row[5] or []),
            issue_date=row[6],
            eff_from=row[7],
            eff_to=row[8],
            eff_flag=row[9],
            status_flag=row[10] or 0,
            agency=row[11],
            signer_name=row[12],
            signer_title=row[13],
            source_url=row[14],
            full_text=row[15],
            crawled_at=row[16],
        )

    def upsert_relations(self, relations: list[LegalDocRelation]) -> None:
        if not relations:
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                for rel in relations:
                    cur.execute(
                        """
                        INSERT INTO legal_document_relations (from_doc_id, to_doc_id, relation_type)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (from_doc_id, to_doc_id, relation_type) DO NOTHING
                        """,
                        (rel.from_doc_id, rel.to_doc_id, rel.relation_type),
                    )


class PgLegalChunkRepository:
    def upsert_many(self, chunks: list[LegalChunk]) -> None:
        if not chunks:
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                for ch in chunks:
                    if not ch.path:
                        continue
                    root = ch.root_path or article_root_ltree(ch.path)
                    cur.execute(
                        """
                        INSERT INTO legal_embeddings
                            (doc_id, chunk_type, chunk_text, embedding,
                             is_effective, path, root_path, source_element_id)
                        VALUES (%s, %s, %s, %s, %s, %s::ltree, %s::ltree, %s)
                        ON CONFLICT (path) DO UPDATE SET
                            doc_id = EXCLUDED.doc_id,
                            chunk_type = EXCLUDED.chunk_type,
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = COALESCE(EXCLUDED.embedding, legal_embeddings.embedding),
                            is_effective = EXCLUDED.is_effective,
                            root_path = COALESCE(EXCLUDED.root_path, legal_embeddings.root_path),
                            source_element_id = COALESCE(
                                EXCLUDED.source_element_id, legal_embeddings.source_element_id
                            )
                        """,
                        (
                            ch.doc_id,
                            ch.chunk_type,
                            ch.chunk_text,
                            ch.embedding,
                            ch.is_effective,
                            ch.path,
                            root,
                            ch.source_element_id,
                        ),
                    )

    def upsert_nodes(self, nodes: list[LegalNode]) -> None:
        """Upsert hierarchy into 7 level tables with full FK chain + Không có scaffolds."""
        if not nodes:
            return
        ranked = sorted(
            (n for n in nodes if n.level in _HIERARCHY_LEVELS and n.path),
            key=lambda n: (n.path.count("."), n.sort_order if n.sort_order is not None else 0),
        )
        with get_db() as conn:
            with conn.cursor() as cur:
                for n in ranked:
                    title = _node_title(n)
                    content = KHONG_CO
                    eff = _eff_params(n)

                    if n.level == "Part":
                        cur.execute(
                            f"""
                            INSERT INTO legal_parts
                                (doc_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (doc_id, path) DO UPDATE SET
                                title = COALESCE(EXCLUDED.title, legal_parts.title),
                                content = COALESCE(EXCLUDED.content, legal_parts.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_parts")}
                            """,
                            (n.doc_id, title, content, n.path, n.parent_path, *eff),
                        )
                    elif n.level == "Chapter":
                        part_id = _lookup_id_by_path(cur, "legal_parts", n.parent_path)
                        if not part_id:
                            root = ensure_doc_root_path(cur, n.doc_id, n.path)
                            part_id = ensure_part(cur, n.doc_id, root, None)
                        cur.execute(
                            f"""
                            INSERT INTO legal_chapters
                                (part_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                part_id = COALESCE(EXCLUDED.part_id, legal_chapters.part_id),
                                title = COALESCE(EXCLUDED.title, legal_chapters.title),
                                content = COALESCE(EXCLUDED.content, legal_chapters.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_chapters")}
                            """,
                            (part_id, title, content, n.path, n.parent_path, *eff),
                        )
                    elif n.level == "Section":
                        chapter_id = _lookup_id_by_path(
                            cur, "legal_chapters", n.parent_path
                        )
                        if not chapter_id:
                            ensure_chain_for_article(cur, n.doc_id, f"{n.path}.D0")
                            chapter_id = _lookup_id_by_path(
                                cur, "legal_chapters", n.parent_path
                            )
                        if not chapter_id:
                            ssid = ensure_chain_for_article(cur, n.doc_id, n.path + ".D0")
                            cur.execute(
                                """
                                SELECT c.id FROM legal_sub_sections ss
                                JOIN legal_sections s ON s.id = ss.section_id
                                JOIN legal_chapters c ON c.id = s.chapter_id
                                WHERE ss.id = %s
                                """,
                                (ssid,),
                            )
                            chapter_id = int(cur.fetchone()[0])
                        cur.execute(
                            f"""
                            INSERT INTO legal_sections
                                (chapter_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                chapter_id = COALESCE(
                                    EXCLUDED.chapter_id, legal_sections.chapter_id
                                ),
                                title = COALESCE(EXCLUDED.title, legal_sections.title),
                                content = COALESCE(EXCLUDED.content, legal_sections.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_sections")}
                            """,
                            (chapter_id, title, content, n.path, n.parent_path, *eff),
                        )
                    elif n.level == "SubSection":
                        section_id = _lookup_id_by_path(
                            cur, "legal_sections", n.parent_path
                        )
                        if not section_id:
                            ensure_chain_for_article(cur, n.doc_id, f"{n.path}.D0")
                            section_id = _lookup_id_by_path(
                                cur, "legal_sections", n.parent_path
                            )
                        if not section_id:
                            ssid = ensure_chain_for_article(cur, n.doc_id, n.path + ".D0")
                            cur.execute(
                                "SELECT section_id FROM legal_sub_sections WHERE id = %s",
                                (ssid,),
                            )
                            section_id = int(cur.fetchone()[0])
                        cur.execute(
                            f"""
                            INSERT INTO legal_sub_sections
                                (section_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                section_id = COALESCE(
                                    EXCLUDED.section_id, legal_sub_sections.section_id
                                ),
                                title = COALESCE(EXCLUDED.title, legal_sub_sections.title),
                                content = COALESCE(
                                    EXCLUDED.content, legal_sub_sections.content
                                ),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_sub_sections")}
                            """,
                            (section_id, title, content, n.path, n.parent_path, *eff),
                        )
                    elif n.level == "Article":
                        sub_section_id = ensure_chain_for_article(cur, n.doc_id, n.path)
                        cur.execute(
                            f"""
                            INSERT INTO legal_articles
                                (sub_section_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                sub_section_id = EXCLUDED.sub_section_id,
                                title = EXCLUDED.title,
                                content = COALESCE(EXCLUDED.content, legal_articles.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_articles")}
                            """,
                            (
                                sub_section_id,
                                title,
                                content,
                                n.path,
                                n.parent_path,
                                *eff,
                            ),
                        )
                    elif n.level == "Clause":
                        article_id = _lookup_id_by_path(
                            cur, "legal_articles", n.parent_path
                        )
                        if not article_id:
                            continue
                        cur.execute(
                            f"""
                            INSERT INTO legal_clauses
                                (article_id, title, content, path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                article_id = COALESCE(
                                    EXCLUDED.article_id, legal_clauses.article_id
                                ),
                                title = EXCLUDED.title,
                                content = COALESCE(EXCLUDED.content, legal_clauses.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_clauses")}
                            """,
                            (
                                article_id,
                                title,
                                content,
                                n.path,
                                n.parent_path,
                                *eff,
                            ),
                        )
                    elif n.level == "Point":
                        clause_id = _lookup_id_by_path(
                            cur, "legal_clauses", n.parent_path
                        )
                        if not clause_id:
                            continue
                        symbol = _path_leaf(n.path)[:10] or "x"
                        cur.execute(
                            f"""
                            INSERT INTO legal_points
                                (clause_id, symbol, title, content,
                                 path, parent_path, {_EFF_COLS})
                            VALUES (%s, %s, %s, %s, %s::ltree, %s::ltree, %s, %s, %s, %s)
                            ON CONFLICT (path) DO UPDATE SET
                                clause_id = COALESCE(
                                    EXCLUDED.clause_id, legal_points.clause_id
                                ),
                                symbol = EXCLUDED.symbol,
                                title = COALESCE(EXCLUDED.title, legal_points.title),
                                content = COALESCE(EXCLUDED.content, legal_points.content),
                                parent_path = EXCLUDED.parent_path,
                                {_EFF_UPSERT.format(t="legal_points")}
                            """,
                            (
                                clause_id,
                                symbol,
                                title,
                                content,
                                n.path,
                                n.parent_path,
                                *eff,
                            ),
                        )

    def upsert_relations(self, relations: list[LegalChunkRelation]) -> None:
        """Store path cross-refs as legal_path_relations (ltree dan_chieu)."""
        if not relations:
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                for rel in relations:
                    src = rel.from_path
                    tgt = rel.to_path
                    if not src or not tgt:
                        continue
                    if ":" in src:
                        src = chunk_ref_to_ltree(src) or src
                    if ":" in tgt:
                        tgt = chunk_ref_to_ltree(tgt) or tgt
                    cur.execute(
                        """
                        INSERT INTO legal_path_relations (source_path, target_path, ref_type)
                        VALUES (%s::ltree, %s::ltree, %s)
                        ON CONFLICT (source_path, target_path, ref_type) DO NOTHING
                        """,
                        (src, tgt, rel.relation_type or "dan_chieu"),
                    )

    def count_for_doc(self, doc_id: str) -> int:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM legal_embeddings WHERE doc_id = %s",
                    (doc_id,),
                )
                row = cur.fetchone()
                return int(row[0] or 0)

    def get_texts_by_refs(self, chunk_refs: list[str]) -> dict[str, str]:
        """Compat: accept legacy colon refs or ltree; return keyed by input."""
        if not chunk_refs:
            return {}
        paths = []
        key_by_path: dict[str, str] = {}
        for k in chunk_refs:
            lt = chunk_ref_to_ltree(k) if ":" in k else k
            if lt:
                paths.append(lt)
                key_by_path[lt] = k
        by_path = self.get_texts_by_paths(paths)
        return {key_by_path.get(p, p): t for p, t in by_path.items()}

    def get_meta_by_refs(self, chunk_refs: list[str]) -> dict[str, dict]:
        """Compat: accept legacy colon refs or ltree; return keyed by input."""
        if not chunk_refs:
            return {}
        paths = []
        key_by_path: dict[str, str] = {}
        for k in chunk_refs:
            lt = chunk_ref_to_ltree(k) if ":" in k else k
            if lt:
                paths.append(lt)
                key_by_path[lt] = k
        by_path = self.get_meta_by_paths(paths)
        return {key_by_path.get(p, p): meta for p, meta in by_path.items()}

    def get_texts_by_paths(self, paths: list[str]) -> dict[str, str]:
        if not paths:
            return {}
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT path::text, chunk_text FROM legal_embeddings
                    WHERE path = ANY(%s::ltree[])
                    """,
                    (paths,),
                )
                return {r[0]: r[1] for r in cur.fetchall()}

    def get_meta_by_paths(self, paths: list[str]) -> dict[str, dict]:
        if not paths:
            return {}
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.path::text, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           d.eff_from, d.eff_to, d.status_flag, d.eff_flag, c.root_path::text,
                            d.doc_type, d.issue_date, c.source_element_id, d.source_url
                    FROM legal_embeddings c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE c.path = ANY(%s::ltree[])
                    """,
                    (paths,),
                )
                return {
                    r[0]: {
                        "path": r[0],
                        "doc_id": r[1],
                        "chunk_type": r[2],
                        "doc_number": r[3],
                        "title": r[4],
                        "eff_from": str(r[5]) if r[5] else None,
                        "eff_to": str(r[6]) if r[6] else None,
                        "status_flag": r[7],
                        "eff_flag": r[8],
                        "root_path": r[9],
                        "doc_type": r[10],
                        "issue_date": str(r[11]) if r[11] else None,
                        "source_element_id": r[12],
                        "source_url": r[13],
                    }
                    for r in cur.fetchall()
                }

    def expand_paths(self, seed_keys: list[str], limit: int = 80) -> dict:
        """Postgres ltree expand. Seeds are ltree path strings."""
        empty: dict = {
            "sibling_paths": [],
            "ancestor_paths": [],
            "parent_clause_paths": [],
            "related_docs": [],
            "repealed_by_docs": [],
        }
        if not seed_keys:
            return empty

        path_candidates = []
        for k in seed_keys:
            if ":" in k:
                lt = chunk_ref_to_ltree(k)
                if lt:
                    path_candidates.append(lt)
            else:
                path_candidates.append(k)

        with get_db() as conn:
            with conn.cursor() as cur:
                if not path_candidates:
                    return empty
                cur.execute(
                    """
                    SELECT path::text, doc_id FROM legal_embeddings
                    WHERE path = ANY(%s::ltree[])
                    """,
                    (path_candidates,),
                )
                rows = cur.fetchall()
                if not rows:
                    return empty
                seeds = [r[0] for r in rows]
                doc_ids = list({r[1] for r in rows})

                # siblings under same parent_path of seed leaf nodes
                cur.execute(
                    """
                    WITH seeds AS (
                        SELECT path, subpath(path, 0, nlevel(path) - 1) AS parent
                        FROM unnest(%s::ltree[]) AS path
                        WHERE nlevel(path) > 1
                    )
                    SELECT DISTINCT e.path::text
                    FROM legal_embeddings e
                    JOIN seeds s ON e.path <@ s.parent AND nlevel(e.path) = nlevel(s.path)
                    WHERE e.path <> ALL(%s::ltree[])
                    LIMIT %s
                    """,
                    (seeds, seeds, min(limit, 24)),
                )
                siblings = [r[0] for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT subpath(path, 0, n)::text
                    FROM unnest(%s::ltree[]) AS path
                    CROSS JOIN generate_series(1, nlevel(path) - 1) AS n
                    LIMIT %s
                    """,
                    (seeds, min(limit, 16)),
                )
                ancestors = [r[0] for r in cur.fetchall() if r[0]]

                # parent clause = nearest ancestor ending in K*
                parent_clauses = []
                for s in seeds:
                    parts = s.split(".")
                    for i in range(len(parts) - 1, -1, -1):
                        if parts[i].startswith("K") and parts[i][1:].isdigit():
                            parent_clauses.append(".".join(parts[: i + 1]))
                            break

                cur.execute(
                    """
                    SELECT DISTINCT ldr.to_doc_id
                    FROM legal_document_relations ldr
                    WHERE ldr.from_doc_id = ANY(%s)
                      AND ldr.relation_type IN (
                          'can_cu_ban_hanh', 'dan_chieu', 'sua_doi_bo_sung',
                          'BASED_ON', 'CITES', 'AMENDS'
                      )
                    LIMIT 8
                    """,
                    (doc_ids,),
                )
                related = [r[0] for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT DISTINCT ldr.from_doc_id
                    FROM legal_document_relations ldr
                    WHERE ldr.to_doc_id = ANY(%s)
                      AND ldr.relation_type IN (
                          'van_ban_bi_bai_bo', 'thay_the', 'REPEALS', 'SUPERSEDES'
                      )
                    LIMIT 8
                    """,
                    (doc_ids,),
                )
                repealed = [r[0] for r in cur.fetchall()]

                return {
                    "sibling_paths": siblings,
                    "ancestor_paths": ancestors,
                    "parent_clause_paths": list(dict.fromkeys(parent_clauses)),
                    "related_docs": related,
                    "repealed_by_docs": repealed,
                }
