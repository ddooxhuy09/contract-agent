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

    def search_in_doc_nums(self, query, doc_nums, k=3):
        return []

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


class _SeqSearch:
    """Returns the queued result lists in call order and records the queries."""

    def __init__(self, *results):
        self._results = list(results)
        self.queries = []

    def search(self, query, k=4, min_score=0.0, **kwargs):
        self.queries.append((query, min_score))
        return self._results.pop(0) if self._results else []

    def search_in_docs(self, query, doc_ids, k=2, **kwargs):
        return []

    def search_in_doc_nums(self, query, doc_nums, k=3, **kwargs):
        return []


def _chunk(path, title, doc_id="D"):
    return RetrievedChunk(
        content=f"body {path}",
        score=0.9,
        metadata={"path": path, "doc_id": doc_id, "doc_number": "1", "title": title},
    )


def test_no_seeds_anywhere_returns_empty_after_all_fallbacks():
    search = _SeqSearch()
    rag = LegalGraphRag(search, _FakeChunks(), None)
    assert rag.retrieve_for_clause("Chấm dứt", "tóm tắt", contract_type="lao động") == []
    # combined query (with floor), same query without floor, then narrow variants
    assert len(search.queries) == 2 + 3
    assert search.queries[0][1] > 0 and search.queries[1][1] == 0.0


def test_sector_mismatch_seed_is_replaced_by_labor_law_recovery():
    oil = _chunk("OIL.1", "Nghị định về hoạt động dầu khí")
    labor = _chunk("BLLD.1", "Bộ luật Lao động")
    search = _SeqSearch([oil], [labor])
    rag = LegalGraphRag(search, _FakeChunks(), None)
    hits = rag.retrieve_for_clause("Làm thêm giờ", "tăng ca", contract_type="lao động")
    assert [h.metadata["path"] for h in hits] == ["BLLD.1"]
    assert hits[0].metadata["role"] == "seed"
    assert search.queries[1][0].startswith("Bộ luật Lao động")


def test_max_total_limits_result_count():
    seeds = [_chunk(f"P.{i}", "Bộ luật Lao động") for i in range(4)]
    rag = LegalGraphRag(_SeqSearch(seeds), _FakeChunks(), None)
    assert len(rag.retrieve_for_clause("t", "s", max_total=2)) == 2


# --- seed diversification and labor-scope pass ---------------------------------------------

import pytest

from app.core.settings import get_settings


class _ScopedSearch(_SeqSearch):
    def __init__(self, *results, scoped=()):
        super().__init__(*results)
        self.scoped_calls = []
        self._scoped = list(scoped)

    def search_in_doc_nums(self, query, doc_nums, k=3, **kwargs):
        self.scoped_calls.append((query, tuple(doc_nums), k))
        return list(self._scoped)


@pytest.fixture
def flags():
    s = get_settings()
    old = s.rag_labor_scope
    yield s
    s.rag_labor_scope = old


def test_labor_scope_pass_adds_labor_code_chunk_after_seeds(flags):
    flags.rag_labor_scope = True
    seed = _chunk("OTHER.1", "Nghị định bảo hiểm", doc_id="X")
    labor = _chunk("139264.D17.K2", "Bộ luật Lao động", doc_id="139264")
    search = _ScopedSearch([seed], scoped=[labor])
    hits = LegalGraphRag(search, _FakeChunks(), None).retrieve_for_clause(
        "Đặt cọc", "người lao động nộp tiền bảo đảm", max_total=10
    )
    assert [h.metadata["path"] for h in hits] == ["OTHER.1", "139264.D17.K2"]
    assert hits[1].metadata["role"] == "labor_scope"
    assert search.scoped_calls and "45/2019/QH14" in search.scoped_calls[0][1]


def test_labor_scope_pass_is_skipped_for_non_labor_queries_and_when_disabled(flags):
    seed = _chunk("OTHER.1", "Luật Dân sự", doc_id="X")
    flags.rag_labor_scope = True
    search = _ScopedSearch([seed], scoped=[_chunk("L.1", "Bộ luật Lao động", doc_id="L")])
    LegalGraphRag(search, _FakeChunks(), None).retrieve_for_clause("Đặt cọc dân sự", "hợp đồng thuê nhà")
    assert search.scoped_calls == []

    flags.rag_labor_scope = False
    search = _ScopedSearch([seed], scoped=[_chunk("L.1", "Bộ luật Lao động", doc_id="L")])
    LegalGraphRag(search, _FakeChunks(), None).retrieve_for_clause("Làm thêm giờ", "người lao động", contract_type="lao động")
    assert search.scoped_calls == []


def test_query_embedding_is_reused_across_searches_of_one_retrieval():
    from app.infrastructure.vector.pg_search import PgLegalVectorSearch

    class CountingEmbedder:
        calls = 0

        def embed_query(self, q):
            CountingEmbedder.calls += 1
            return [0.1, 0.2]

    s = PgLegalVectorSearch(CountingEmbedder())
    assert s._embed_query("q1") == s._embed_query("q1") == [0.1, 0.2]
    assert CountingEmbedder.calls == 1
    s._embed_query("q2")
    assert CountingEmbedder.calls == 2
    for i in range(PgLegalVectorSearch._EMBED_CACHE_SIZE + 5):  # bounded
        s._embed_query(f"x{i}")
    assert len(s._query_vectors) <= PgLegalVectorSearch._EMBED_CACHE_SIZE
