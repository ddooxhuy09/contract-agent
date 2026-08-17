"""Unit tests for RRF, query rewrite, and LegalGraphRag hydrate (fake graph/PG)."""

from app.domain.entities.search import RetrievedChunk
from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query
from app.infrastructure.vector.rrf import rrf_fuse
from app.document.chunker import chunk_by_clause


def test_rrf_fuse_prefers_items_in_both_lists():
    a = [
        RetrievedChunk(content="x", score=0.9, metadata={"path": "A"}),
        RetrievedChunk(content="y", score=0.8, metadata={"path": "B"}),
    ]
    b = [
        RetrievedChunk(content="y", score=0.5, metadata={"path": "B"}),
        RetrievedChunk(content="z", score=0.4, metadata={"path": "C"}),
    ]
    fused = rrf_fuse([a, b], key_fn=lambda c: c.metadata["path"])
    assert fused[0][0].metadata["path"] == "B"
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
                    "path": "OTHER.D1",
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

    def get_texts_by_paths(self, paths):
        return {p: f"text of {p}" for p in paths}

    def get_meta_by_paths(self, paths):
        return {
            p: {
                "path": p,
                "doc_id": "DOC1",
                "chunk_type": "body",
                "doc_number": "45/2019/QH14",
                "title": "BLLĐ",
            }
            for p in paths
        }

    def expand_paths(self, seed_keys, limit=80):
        return {
            "sibling_paths": [],
            "ancestor_paths": [],
            "parent_clause_paths": [],
            "related_docs": [],
            "repealed_by_docs": [],
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
                "path": "C1.M1.D5.K1.a",
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
            metadata={"path": "X.1", "doc_id": "D", "doc_number": "1", "title": "t"},
        )
    ]
    rag = LegalGraphRag(_FakeSearch(seeds), _FakeChunks(), None)
    hits = rag.retrieve_for_clause("title", "summary")
    assert len(hits) == 1
    assert hits[0].metadata["role"] == "seed"


class _FakeGraphSuperseding:
    def expand(self, chunk_refs, limit=80):
        return {
            "seeds": list(chunk_refs),
            "sibling_paths": [],
            "ancestor_paths": [],
            "parent_clause_paths": [],
            "related_docs": [],
            "repealed_by_docs": ["DOC_SUPERSEDING"],
        }


def test_repealed_seeds_yield_superseding_context():
    """When the graph reports repealed_by_docs, the replacement doc's text is
    fetched (via search_in_docs) and appears with role=superseding + section."""
    seeds = [
        RetrievedChunk(
            content="old law text",
            score=0.85,
            metadata={
                "path": "C1.M1.D5.K1.a",
                "doc_id": "DOC1",
                "doc_number": "45/2019/QH14",
                "title": "Bộ luật Lao động",
                "chunk_type": "body",
            },
        )
    ]
    rag = LegalGraphRag(_FakeSearch(seeds), _FakeChunks(), _FakeGraphSuperseding())
    hits = rag.retrieve_for_clause("Chấm dứt HĐLĐ", "đơn phương chấm dứt")
    roles = {h.metadata.get("role") for h in hits}
    assert "superseding" in roles
    ctx = LegalGraphRag.format_context(hits)
    assert "Văn bản thay thế" in ctx


def test_validity_key_as_of_date_not_yet_effective_and_expired():
    """_validity_key with a future as_of_date: a doc effective 2025 is
    not yet active for a contract dated 2024, so it ranks after an in-effect doc.
    Likewise, a doc expired in 2023 is dead for 2024."""
    from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag as LG

    future_eff = RetrievedChunk(content="", score=0.9, metadata={
        "path": "A", "doc_number": "L1", "status_flag": 1,
        "eff_from": "2025-01-01", "eff_to": None,
    })
    expired = RetrievedChunk(content="", score=0.9, metadata={
        "path": "B", "doc_number": "L2", "status_flag": 1,
        "eff_from": "2020-01-01", "eff_to": "2023-12-31",
    })
    in_effect = RetrievedChunk(content="", score=0.9, metadata={
        "path": "C", "doc_number": "L3", "status_flag": 1,
        "eff_from": "2022-01-01", "eff_to": None,
    })

    # as_of 2024-06-15: future_eff not yet effective (eff_from > as_of), expired dead,
    # in_effect is the only valid one.
    ordered = LG._order_for_prompt([future_eff, expired, in_effect], as_of="2024-06-15")
    assert ordered[0].metadata["path"] == "C"
    # expired + future_eff should sort after in_effect.
    refs_after = {c.metadata["path"] for c in ordered[1:]}
    assert refs_after == {"A", "B"}

    # as_of 2025-06-15: future_eff now in effect, expired still dead.
    ordered2 = LG._order_for_prompt([future_eff, expired, in_effect], as_of="2025-06-15")
    first_two = {c.metadata["path"] for c in ordered2[:2]}
    assert first_two == {"A", "C"}  # both in-effect, order by role/score
    assert ordered2[-1].metadata["path"] == "B"  # expired last


def test_validity_key_parses_dd_mm_yyyy_as_of_against_iso_eff_to():
    """Regression: contract date 15/07/2026 must expire TT with eff_to=2025-02-15."""
    from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag as LG

    stale = RetrievedChunk(
        content="",
        score=0.9,
        metadata={
            "path": "tt19",
            "doc_number": "19/2014/TT-BLĐTBXH",
            "status_flag": 1,
            "eff_flag": "Còn hiệu lực",  # stale cache
            "eff_from": "2014-10-05",
            "eff_to": "2025-02-15",
        },
    )
    assert LG._validity_key(stale, as_of="15/07/2026")[0] == 99
    assert LG._validity_key(stale, as_of="2024-01-01")[0] == 0
