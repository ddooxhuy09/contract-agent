"""Unit tests for RRF, query rewrite, and LegalGraphRag hydrate (fake graph/PG)."""

from app.domain.entities.search import RetrievedChunk
from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query
from app.infrastructure.vector.rrf import rrf_fuse
from app.document.chunker import chunk_by_clause


def test_rrf_fuse_prefers_items_in_both_lists():
    a = [
        RetrievedChunk(content="x", score=0.9, metadata={"chunk_ref": "A"}),
        RetrievedChunk(content="y", score=0.8, metadata={"chunk_ref": "B"}),
    ]
    b = [
        RetrievedChunk(content="y", score=0.5, metadata={"chunk_ref": "B"}),
        RetrievedChunk(content="z", score=0.4, metadata={"chunk_ref": "C"}),
    ]
    fused = rrf_fuse([a, b], key_fn=lambda c: c.metadata["chunk_ref"])
    assert fused[0][0].metadata["chunk_ref"] == "B"
    assert fused[0][1] > fused[1][1]


def test_rewrite_legal_query_keeps_terms_drops_filler():
    q = rewrite_legal_query(
        "Điều khoản chấm dứt",
        "Các bên và hoặc sẽ được chấm dứt hợp đồng khi vi phạm",
        contract_type="Hợp đồng lao động",
    )
    assert "lao động" in q.lower() or "Hợp đồng" in q
    assert "chấm" in q.lower()
    assert " các " not in f" {q.lower()} "


def test_chunker_splits_on_dieu_not_khoan():
    text = (
        "Điều 1. Phạm vi\n"
        "Khoản 1. Bên A.\n"
        "Khoản 2. Bên B.\n"
        "Điều 2. Thời hạn\n"
        "Thời hạn 12 tháng."
    )
    docs = chunk_by_clause(text, "c1")
    numbers = [d.metadata["clause_number"] for d in docs]
    assert "1" in numbers
    assert "2" in numbers
    # Khoản must not become its own clause_number units
    dieu1 = next(d for d in docs if d.metadata["clause_number"] == "1")
    assert "Khoản 1" in dieu1.page_content
    assert "Khoản 2" in dieu1.page_content


class _FakeSearch:
    def __init__(self, seeds):
        self._seeds = seeds

    def search(self, query, k, min_score=None, doc_type_hint=None, doc_ids=None):
        return list(self._seeds)[:k]

    def search_in_docs(self, query, doc_ids, k=2):
        return [
            RetrievedChunk(
                content="related law text",
                score=0.7,
                metadata={
                    "chunk_ref": "OTHER.D1",
                    "doc_id": doc_ids[0],
                    "doc_number": "45/2019/QH14",
                    "title": "Related",
                    "chunk_type": "body",
                },
            )
        ]


class _FakeChunks:
    def get_texts_by_refs(self, refs):
        return {r: f"text of {r}" for r in refs}

    def get_meta_by_refs(self, refs):
        return {
            r: {
                "doc_id": "DOC1",
                "chunk_type": "body",
                "doc_number": "45/2019/QH14",
                "title": "BLLĐ",
            }
            for r in refs
        }


class _FakeGraph:
    def expand(self, chunk_refs, limit=80):
        return {
            "seeds": list(chunk_refs),
            "sibling_paths": ["C1.M1.D5.K1.b"],
            "ancestor_paths": ["C1.M1.D5"],
            "parent_clause_paths": ["C1.M1.D5.K1"],
            "related_docs": ["DOC2"],
            "repealed_by_docs": [],
        }


def test_legal_graph_rag_hydrate_roles():
    seeds = [
        RetrievedChunk(
            content="seed body",
            score=0.85,
            metadata={
                "chunk_ref": "C1.M1.D5.K1.a",
                "doc_id": "DOC1",
                "doc_number": "45/2019/QH14",
                "title": "BLLĐ",
                "chunk_type": "body",
            },
        )
    ]
    rag = LegalGraphRag(_FakeSearch(seeds), _FakeChunks(), _FakeGraph())
    hits = rag.retrieve_for_clause("Chấm dứt HĐLĐ", "đơn phương chấm dứt", contract_type="lao động")
    roles = {h.metadata.get("role") for h in hits}
    assert "seed" in roles
    assert "sibling" in roles or "ancestor" in roles
    assert "related" in roles
    ctx = LegalGraphRag.format_context(hits)
    assert "Điều luật seed" in ctx
    assert "C1.M1.D5.K1.a" in ctx


def test_legal_graph_rag_without_graph_returns_seeds_only():
    seeds = [
        RetrievedChunk(
            content="only seed",
            score=0.9,
            metadata={"chunk_ref": "X.1", "doc_id": "D", "doc_number": "1", "title": "t"},
        )
    ]
    rag = LegalGraphRag(_FakeSearch(seeds), _FakeChunks(), None)
    hits = rag.retrieve_for_clause("title", "summary")
    assert len(hits) == 1
    assert hits[0].metadata["role"] == "seed"
