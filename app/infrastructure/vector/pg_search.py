import re
import threading

from app.core.logging import logger
from app.core.settings import get_settings
from app.domain.entities.search import RetrievedChunk
from app.domain.ports.services import Embedder
from app.infrastructure.db.connection import get_db
from app.infrastructure.vector.rrf import rrf_fuse

_EXCLUDE_TYPES = ("signature",)


def _chunk_key(meta: dict) -> str:
    """Stable retrieval key: ltree path."""
    return meta.get("path") or ""


def _row_to_chunk(r, score: float | None = None) -> RetrievedChunk:
    # row: text, path, doc_id, chunk_type, doc_num, title, score,
    #      eff_from, eff_to, status_flag, eff_flag, root_path, doc_type, issue_date,
    #      source_element_id, source_url
    meta = {
        "path": r[1],
        "doc_id": r[2],
        "chunk_type": r[3],
        "doc_number": r[4],
        "title": r[5],
    }
    if len(r) > 7:
        meta["eff_from"] = str(r[7]) if r[7] else None
    if len(r) > 8:
        meta["eff_to"] = str(r[8]) if r[8] else None
    if len(r) > 9:
        meta["status_flag"] = r[9]
    if len(r) > 10:
        meta["eff_flag"] = r[10]
    if len(r) > 11 and r[11]:
        meta["root_path"] = str(r[11])
    if len(r) > 12:
        meta["doc_type"] = r[12]
    if len(r) > 13:
        meta["issue_date"] = str(r[13]) if r[13] else None
    if len(r) > 14:
        meta["source_element_id"] = r[14]
    if len(r) > 15:
        meta["source_url"] = r[15]
    return RetrievedChunk(
        content=r[0],
        score=score if score is not None else (float(r[6]) if r[6] is not None else None),
        metadata=meta,
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
    _EMBED_CACHE_SIZE = 64

    def __init__(self, embedder: Embedder):
        self._embedder = embedder
        self._query_vectors: dict[str, list[float]] = {}
        # Clause checks call this from several threads; eviction mutates the dict while iterating it.
        self._query_lock = threading.Lock()

    def _embed_query(self, query: str):
        """One retrieval searches the same query several times (seeds, related documents, labor scope)."""
        vec = self._query_vectors.get(query)
        if vec is None:
            vec = self._embedder.embed_query(query)  # outside the lock: slow, and threads should not queue on it
            with self._query_lock:
                if query not in self._query_vectors and len(self._query_vectors) >= self._EMBED_CACHE_SIZE:
                    self._query_vectors.pop(next(iter(self._query_vectors)))
                self._query_vectors[query] = vec
        return vec

    def search(
        self,
        query: str,
        k: int,
        min_score: float | None = None,
        doc_type_hint: str | None = None,
        doc_ids: list[str] | None = None,
        doc_nums: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        threshold = settings.similarity_threshold if min_score is None else min_score
        fetch_n = max(k * 4, 12)
        try:
            vector_hits = self._vector_search(query, fetch_n, doc_type_hint, doc_ids, doc_nums)
        except Exception as e:
            # Typical: dump embeddings dim ≠ query dim (768 vs 1024) or embedder not ready.
            logger.error("Legal vector search failed (falling back to FTS): %s", e)
            vector_hits = []
        try:
            fts_hits = self._fts_search(query, fetch_n, doc_type_hint, doc_ids, doc_nums)
        except Exception as e:
            logger.error("Legal FTS search failed: %s", e)
            fts_hits = []
        if not vector_hits and not fts_hits:
            logger.warning(
                "Legal search empty: query=%r hint=%r doc_ids=%s",
                (query or "")[:80],
                doc_type_hint,
                len(doc_ids or []),
            )

        fused = rrf_fuse(
            [vector_hits, fts_hits],
            key_fn=lambda c: _chunk_key(c.metadata) or c.content[:80],
            weights=[settings.legal_rrf_weight_vector, settings.legal_rrf_weight_fts],
        )
        results: list[RetrievedChunk] = []
        for chunk, rrf_score in fused:
            vec_score = chunk.score
            # Keep if strong vector score OR appeared in FTS (rrf from fts-only)
            if vec_score is not None and vec_score < threshold:
                key = _chunk_key(chunk.metadata)
                in_fts = any(_chunk_key(h.metadata) == key for h in fts_hits)
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

    def search_in_doc_nums(self, query: str, doc_nums: list[str], k: int = 3) -> list[RetrievedChunk]:
        """Search only inside the instruments with these document numbers (e.g. '45/2019/QH14')."""
        if not doc_nums:
            return []
        return self.search(query, k=k, min_score=0.0, doc_nums=doc_nums)

    def _base_where(
        self, doc_type_hint: str | None, doc_ids: list[str] | None, doc_nums: list[str] | None = None
    ) -> tuple[str, list]:
        # Chunk still effective (hierarchy cache) + document not fully expired.
        clauses = [
            "c.is_effective",
            "c.embedding IS NOT NULL",
            "c.chunk_type <> ALL(%s)",
            "(d.status_flag IS NULL OR d.status_flag IS DISTINCT FROM 2)",
        ]
        params: list = [list(_EXCLUDE_TYPES)]
        if get_settings().legal_article_chunks_only:
            clauses.append("c.path::text ~ '(^|[.])[Dd][0-9]+([.]|$)'")
        if doc_ids:
            clauses.append("c.doc_id = ANY(%s)")
            params.append(doc_ids)
        if doc_nums:
            clauses.append("d.doc_num = ANY(%s)")
            params.append(doc_nums)
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
        doc_nums: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        vector = self._embed_query(query)
        where_sql, params = self._base_where(doc_type_hint, doc_ids, doc_nums)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.chunk_text, c.path::text, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           1 - (c.embedding <=> %s::vector) AS score,
                           d.eff_from, d.eff_to, d.status_flag, d.eff_flag,
                            c.root_path::text,
                            d.doc_type, d.issue_date, c.source_element_id, d.source_url
                    FROM legal_embeddings c
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
        doc_nums: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        q = (query or "").strip()
        if not q:
            return []
        tsquery_fn, q_text = "plainto_tsquery", q
        if get_settings().legal_fts_query == "or":
            words = list(dict.fromkeys(re.findall(r"\w+", q.lower())))
            if not words:
                return []
            tsquery_fn, q_text = "to_tsquery", " | ".join(words)
        where_sql, params = self._base_where(doc_type_hint, doc_ids, doc_nums)
        # FTS does not require embedding but we keep same filters for consistency
        where_sql = where_sql.replace("c.embedding IS NOT NULL", "c.tsv IS NOT NULL")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.chunk_text, c.path::text, c.doc_id, c.chunk_type, d.doc_num, d.title,
                           ts_rank_cd(c.tsv, {tsquery_fn}('simple', %s)) AS score,
                           d.eff_from, d.eff_to, d.status_flag, d.eff_flag,
                            c.root_path::text,
                            d.doc_type, d.issue_date, c.source_element_id, d.source_url
                    FROM legal_embeddings c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE {where_sql}
                      AND c.tsv @@ {tsquery_fn}('simple', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    [q_text, *params, q_text, n],
                )
                rows = cur.fetchall()
        return [_row_to_chunk(r) for r in rows]
