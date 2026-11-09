from app.core.settings import Settings
from app.infrastructure.vector.rrf import rrf_fuse


def _fuse(weights=None):
    return rrf_fuse([["a", "b"], ["b", "c"]], key_fn=lambda x: x, weights=weights)


def test_default_weights_match_unweighted_rrf():
    assert _fuse() == _fuse([1.0, 1.0])
    assert [k for k, _ in _fuse()][0] == "b"  # in both lists


def test_weights_scale_each_list():
    ordered = _fuse([0.7, 0.3])
    scores = dict(ordered)
    assert scores["a"] == 0.7 / 61
    assert scores["c"] == 0.3 / 62


def test_legal_retrieval_variants_default_to_original_behaviour():
    s = Settings(_env_file=None)
    assert (s.legal_fts_query, s.legal_article_chunks_only) == ("plain", False)
    assert (s.legal_rrf_weight_vector, s.legal_rrf_weight_fts) == (1.0, 1.0)


def test_legal_retrieval_mode_defaults_to_vector():
    assert Settings(_env_file=None).legal_retrieval_mode == "vector"
