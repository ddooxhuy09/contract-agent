from app.core.settings import get_settings
from app.domain.entities.search import RetrievedChunk
from app.domain.ports.services import Embedder
from app.infrastructure.db.connection import get_db
from app.infrastructure.vector.rrf import rrf_fuse

_EXCLUDE_TYPES = ("signature",)


def _row_to_chunk(r, score: float | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        content=r[0],
        score=score if score is not None else (float(r[6]) if r[6] is not None else None),
        metadata={
            "chunk_ref": r[1],
            "doc_id": r[2],
            "chunk_type": r[3],
            "doc_number": r[4],
            "title": r[5],
        },
    )


class PgContractVectorSearch:
    def __init__(self, embedder: Embedder):
        self._embedder = embedder

    def search(self, query: str, contract_id: str, k: int) -> list[RetrievedChunk]:
        vector = self._embedder.embed_query(query)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, clause_number, chunk_index,
                           1 - (embedding <=> %s::vector) AS score
                    FROM contract_chunks
                    WHERE contract_id = %s AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector, contract_id, vector, k),
                )
                rows = cur.fetchall()
        return [
            RetrievedChunk(
                content=r[0],
                score=float(r[3]) if r[3] is not None else None,
                metadata={
                    "contract_id": contract_id,
                    "clause_number": r[1],
                    "chunk_index": r[2],
                },
            )
            for r in rows
        ]


class PgLegalVectorSearch:
    def __init__(self, embedder: Embedder):
        self._embedder = embedder

    def search(
        self,
        query: str,
        k: int,
        min_score: float | None = None,
        doc_type_hint: str | None = None,
        doc_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        threshold = settings.similarity_threshold if min_score is None else min_score
        fetch_n = max(k * 4, 12)
        vector_hits = self._vector_search(query, fetch_n, doc_type_hint, doc_ids)
        fts_hits = self._fts_search(query, fetch_n, doc_type_hint, doc_ids)

        fused = rrf_fuse(
            [vector_hits, fts_hits],
            key_fn=lambda c: c.metadata.get("chunk_ref") or c.content[:80],
        )
        results: list[RetrievedChunk] = []
        for chunk, rrf_score in fused:
            vec_score = chunk.score
            # Keep if strong vector score OR appeared in FTS (rrf from fts-only)
            if vec_score is not None and vec_score < threshold:
                # allow if also in FTS list (lexical match)
                in_fts = any(
                    h.metadata.get("chunk_ref") == chunk.metadata.get("chunk_ref") for h in fts_hits
                )
                if not in_fts:
                    continue
            chunk.score = rrf_score if vec_score is None else max(vec_score, rrf_score)
            chunk.metadata["rrf_score"] = rrf_score
            chunk.metadata.setdefault("role", "seed")
            results.append(chunk)
            if len(results) >= k:
                break
        return results

    def search_in_docs(self, query: str, doc_ids: list[str], k: int = 2) -> list[RetrievedChunk]:
        if not doc_ids:
            return []
        return self.search(query, k=k, min_score=0.0, doc_ids=doc_ids)

    def _base_where(self, doc_type_hint: str | None, doc_ids: list[str] | None) -> tuple[str, list]:
        clauses = [
            "c.is_effective",
            "c.embedding IS NOT NULL",
            "c.chunk_type <> ALL(%s)",
        ]
        params: list = [list(_EXCLUDE_TYPES)]
        if doc_ids:
            clauses.append("c.doc_id = ANY(%s)")
            params.append(doc_ids)
        if doc_type_hint:
            clauses.append("(d.doc_type ILIKE %s OR d.title ILIKE %s OR d.doc_num ILIKE %s)")
            hint = f"%{doc_type_hint}%"
            params.extend([hint, hint, hint])
        return " AND ".join(clauses), params

    def _vector_search(
        self,
        query: str,
        n: int,
        doc_type_hint: str | None,
        doc_ids: list[str] | None,
    ) -> list[RetrievedChunk]:
        vector = self._embedder.embed_query(query)
        where_sql, params = self._base_where(doc_type_hint, doc_ids)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.chunk_text, c.chunk_ref, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           1 - (c.embedding <=> %s::vector) AS score
                    FROM legal_section_chunks c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE {where_sql}
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    [vector, *params, vector, n],
                )
                rows = cur.fetchall()
        return [_row_to_chunk(r) for r in rows]

    def _fts_search(
        self,
        query: str,
        n: int,
        doc_type_hint: str | None,
        doc_ids: list[str] | None,
    ) -> list[RetrievedChunk]:
        q = (query or "").strip()
        if not q:
            return []
        where_sql, params = self._base_where(doc_type_hint, doc_ids)
        # FTS does not require embedding but we keep same filters for consistency
        where_sql = where_sql.replace("c.embedding IS NOT NULL", "c.tsv IS NOT NULL")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.chunk_text, c.chunk_ref, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           ts_rank_cd(c.tsv, plainto_tsquery('simple', %s)) AS score
                    FROM legal_section_chunks c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE {where_sql}
                      AND c.tsv @@ plainto_tsquery('simple', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    [q, *params, q, n],
                )
                rows = cur.fetchall()
        return [_row_to_chunk(r) for r in rows]
