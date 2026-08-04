"""Quick checks: legal corpus size, embedding dims, sample retrieval."""
from __future__ import annotations

from app.infrastructure.container import build_container
from app.infrastructure.db.connection import get_db
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query


def main() -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM legal_documents")
            n_docs = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*),
                       COUNT(embedding),
                       COUNT(*) FILTER (WHERE is_effective),
                       MAX(CASE WHEN embedding IS NOT NULL THEN vector_dims(embedding) END)
                FROM legal_section_chunks
                """
            )
            total, with_emb, effective, dims = cur.fetchone()
    print(f"legal_documents={n_docs}")
    print(f"legal_section_chunks total={total} with_embedding={with_emb} is_effective={effective} dims={dims}")

    if dims is not None and int(dims) != 1024:
        print(
            f"WARNING: embedding dim={dims} but app expects 1024 (BAAI/bge-m3). "
            "Vector search will fail until you re-embed the corpus."
        )

    container = build_container()
    q = rewrite_legal_query("Thời hạn hợp đồng", "Hợp đồng xác định thời hạn 12 tháng", "Hợp đồng lao động")
    print(f"sample_query={q!r}")
    try:
        hits = container.legal_search.search(q, k=5, min_score=0.0)
        print(f"retrieval_hits={len(hits)}")
        for h in hits[:5]:
            print(
                f"  score={h.score} ref={h.metadata.get('chunk_ref')} "
                f"doc={h.metadata.get('doc_number')} text={h.content[:80]!r}"
            )
    except Exception as e:
        print(f"retrieval_error={e}")


if __name__ == "__main__":
    main()
