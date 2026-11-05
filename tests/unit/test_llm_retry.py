"""LLM client 429 backoff helper."""

from app.agents.llm_client import _retry_delay_seconds, resolve_provider


def test_retry_delay_parses_seconds():
    err = Exception(
        "429 RESOURCE_EXHAUSTED. Please retry in 28.626842876s. retryDelay: 28s"
    )
    d = _retry_delay_seconds(err)
    assert d is not None
    assert 28 <= d <= 30


def test_retry_delay_none_for_other_errors():
    assert _retry_delay_seconds(Exception("connection reset")) is None


def test_resolve_provider_maps_public_alias():
    assert resolve_provider("standard") == "gemini"
    assert resolve_provider("Chuẩn") == "gemini"
    assert resolve_provider("gemini") == "gemini"
    assert resolve_provider(None) == "gemini"
    assert resolve_provider("unknown") == "gemini"
