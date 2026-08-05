from app.domain.entities.legal import (
    LegalChunk,
    LegalChunkRelation,
    LegalDocRelation,
    LegalDocument,
)
from app.infrastructure.db.connection import get_db


class PgLegalDocumentRepository:
    def upsert(self, doc: LegalDocument) -> None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO legal_documents (
                        doc_id, doc_num, doc_num_norm, title, doc_type, majors, fields,
                        issue_date, eff_from, eff_to, eff_status, eff_status_code,
                        status_flag, agency, signers, source_url, full_text, crawled_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s::jsonb, %s, %s, COALESCE(%s, NOW())
                    )
                    ON CONFLICT (doc_id) DO UPDATE SET
                        doc_num = EXCLUDED.doc_num,
                        doc_num_norm = EXCLUDED.doc_num_norm,
                        title = EXCLUDED.title,
                        doc_type = EXCLUDED.doc_type,
                        majors = EXCLUDED.majors,
                        fields = EXCLUDED.fields,
                        issue_date = EXCLUDED.issue_date,
                        eff_from = EXCLUDED.eff_from,
                        eff_to = EXCLUDED.eff_to,
                        eff_status = EXCLUDED.eff_status,
                        eff_status_code = EXCLUDED.eff_status_code,
                        status_flag = EXCLUDED.status_flag,
                        agency = EXCLUDED.agency,
                        signers = EXCLUDED.signers,
                        source_url = EXCLUDED.source_url,
                        full_text = EXCLUDED.full_text,
                        updated_at = NOW()
                    """,
                    (
                        doc.doc_id,
                        doc.doc_num,
                        doc.doc_num_norm,
                        doc.title,
                        doc.doc_type,
                        doc.majors or [],
                        doc.fields or [],
                        doc.issue_date,
                        doc.eff_from,
                        doc.eff_to,
                        doc.eff_status,
                        doc.eff_status_code,
                        doc.status_flag,
                        doc.agency,
                        __import__("json").dumps(doc.signers or []),
                        doc.source_url,
                        doc.full_text,
                        doc.crawled_at,
                    ),
                )

    def get(self, doc_id: str) -> LegalDocument | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc_id, doc_num, doc_num_norm, title, doc_type, majors, fields,
                           issue_date, eff_from, eff_to, eff_status, eff_status_code,
                           status_flag, agency, signers, source_url, full_text, crawled_at
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
            doc_num_norm=row[2],
            title=row[3],
            doc_type=row[4],
            majors=list(row[5] or []),
            fields=list(row[6] or []),
            issue_date=row[7],
            eff_from=row[8],
            eff_to=row[9],
            eff_status=row[10],
            eff_status_code=row[11],
            status_flag=row[12] or 0,
            agency=row[13],
            signers=row[14] or [],
            source_url=row[15],
            full_text=row[16],
            crawled_at=row[17],
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
                    cur.execute(
                        """
                        INSERT INTO legal_section_chunks
                            (chunk_ref, doc_id, chunk_type, chunk_text, embedding, is_effective)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_ref) DO UPDATE SET
                            doc_id = EXCLUDED.doc_id,
                            chunk_type = EXCLUDED.chunk_type,
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = COALESCE(EXCLUDED.embedding, legal_section_chunks.embedding),
                            is_effective = EXCLUDED.is_effective
                        """,
                        (
                            ch.chunk_ref,
                            ch.doc_id,
                            ch.chunk_type,
                            ch.chunk_text,
                            ch.embedding,
                            ch.is_effective,
                        ),
                    )

    def upsert_relations(self, relations: list[LegalChunkRelation]) -> None:
        if not relations:
            return
        with get_db() as conn:
            with conn.cursor() as cur:
                for rel in relations:
                    cur.execute(
                        """
                        INSERT INTO legal_chunk_relations
                            (from_chunk_ref, to_chunk_ref, relation_type, note, effective_date)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (from_chunk_ref, to_chunk_ref, relation_type) DO UPDATE SET
                            note = EXCLUDED.note,
                            effective_date = EXCLUDED.effective_date
                        """,
                        (
                            rel.from_chunk_ref,
                            rel.to_chunk_ref,
                            rel.relation_type,
                            rel.note,
                            rel.effective_date,
                        ),
                    )

    def count_for_doc(self, doc_id: str) -> int:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM legal_section_chunks WHERE doc_id = %s",
                    (doc_id,),
                )
                row = cur.fetchone()
                return int(row[0] or 0)

    def get_texts_by_refs(self, chunk_refs: list[str]) -> dict[str, str]:
        if not chunk_refs:
            return {}
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_ref, chunk_text FROM legal_section_chunks
                    WHERE chunk_ref = ANY(%s)
                    """,
                    (chunk_refs,),
                )
                return {r[0]: r[1] for r in cur.fetchall()}

    def get_meta_by_refs(self, chunk_refs: list[str]) -> dict[str, dict]:
        if not chunk_refs:
            return {}
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.chunk_ref, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           d.eff_from, d.eff_to, d.status_flag
                    FROM legal_section_chunks c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE c.chunk_ref = ANY(%s)
                    """,
                    (chunk_refs,),
                )
                return {
                    r[0]: {
                        "doc_id": r[1],
                        "chunk_type": r[2],
                        "doc_number": r[3],
                        "title": r[4],
                        "eff_from": str(r[5]) if r[5] else None,
                        "eff_to": str(r[6]) if r[6] else None,
                        "status_flag": r[7],
                    }
                    for r in cur.fetchall()
                }
