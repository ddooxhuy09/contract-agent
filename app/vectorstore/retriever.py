from typing import List

from langchain_core.documents import Document

from app.core.settings import get_settings
from app.infrastructure.retrieval.context import get_contract_search, get_graph_rag, get_legal_search


def _as_documents(hits) -> List[Document]:
    """Convert RetrievedChunk -> Document, preserving score in metadata so graph
    nodes can rerank / decide whether retrieval is strong enough."""
    docs = []
    for h in hits:
        meta = dict(h.metadata or {})
        if getattr(h, "score", None) is not None:
            meta["score"] = h.score
        docs.append(Document(page_content=h.content, metadata=meta))
    return docs


def retrieve_contract(query: str, contract_id: str, k: int | None = None) -> List[Document]:
    settings = get_settings()
    hits = get_contract_search().search(query, contract_id, k or settings.top_k_retrieval)
    return _as_documents(hits)


def retrieve_legal(
    query: str,
    k: int = 3,
    *,
    title: str | None = None,
    summary: str | None = None,
    contract_type: str | None = None,
) -> List[Document]:
    """Hybrid PG + optional GraphRAG hydrate. Prefer title/summary for rewrite."""
    rag = get_graph_rag()
    if rag is not None:
        hits = rag.retrieve_for_clause(
            title or query,
            summary,
            contract_type=contract_type,
            k_seed=k,
            max_total=max(k * 2, 8),
        )
        return _as_documents(hits)

    settings = get_settings()
    hits = get_legal_search().search(query, k, min_score=settings.similarity_threshold)
    if not hits:
        hits = get_legal_search().search(query, k, min_score=0.0)
    return _as_documents(hits)


def format_legal_context(docs: List[Document], max_chars: int = 7000) -> str:
    """Structured context when GraphRAG metadata roles are present."""
    from app.domain.entities.search import RetrievedChunk
    from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag

    chunks = [
        RetrievedChunk(content=d.page_content, score=None, metadata=dict(d.metadata or {}))
        for d in docs
    ]
    if any(c.metadata.get("role") for c in chunks):
        return LegalGraphRag.format_context(chunks, max_chars=max_chars)
    return "\n\n".join(d.page_content for d in docs)[:max_chars]
