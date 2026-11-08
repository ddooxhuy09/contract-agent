"""LLM client 429 backoff helper."""

import app.agents.llm_client as llm
from app.agents.llm_client import _retry_delay_seconds, resolve_provider
from app.core.settings import Settings


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


class _Keys:
    def __init__(self, keys):
        self.gemini_api_keys = keys


def test_daily_quota_detected_and_per_minute_not():
    per_day = Exception(
        "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, "
        "limit: 20 ... Generate content requests per day limit exceeded on Free Tier. "
        "Please retry in 4h46m51s."
    )
    per_minute = Exception(
        "429 RESOURCE_EXHAUSTED. Generate content requests per minute limit exceeded on Free Tier. "
        "Please retry in 50.9s."
    )
    assert llm._is_daily_quota(per_day) is True
    assert llm._is_daily_quota(per_minute) is False
    assert llm._is_daily_quota(Exception("connection reset")) is False


def test_rotates_to_next_key_on_daily_quota(monkeypatch):
    per_day = Exception("429 RESOURCE_EXHAUSTED: requests per day limit exceeded on Free Tier")
    monkeypatch.setattr(llm, "get_settings", lambda: _Keys(["k1", "k2", "k3"]))
    monkeypatch.setattr(llm, "_key_index", 0)
    monkeypatch.setattr(llm, "_gemini_chat", object())
    assert llm.active_api_key() == "k1"
    assert llm.rotate_api_key_on_key_failure(per_day) is True
    assert llm.active_api_key() == "k2"
    assert llm._gemini_chat is None  # cached client dropped so the new key is used
    assert llm.rotate_api_key_on_key_failure(per_day) is True
    assert llm.active_api_key() == "k3"
    # Last key: nothing left to switch to.
    assert llm.rotate_api_key_on_key_failure(per_day) is False


def test_no_rotation_for_per_minute_limit(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: _Keys(["k1", "k2"]))
    monkeypatch.setattr(llm, "_key_index", 0)
    assert llm.rotate_api_key_on_key_failure(Exception("429 requests per minute limit exceeded")) is False
    assert llm.active_api_key() == "k1"


def test_active_api_key_empty_without_configuration(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: _Keys([]))
    assert llm.active_api_key() == ""


def test_settings_collects_numbered_keys(monkeypatch):
    for name, value in (("GEMINI_API_KEY", ""), ("GEMINI_API_KEY_1", "a"),
                        ("GEMINI_API_KEY_2", "b"), ("GEMINI_API_KEY_3", "a")):
        monkeypatch.setenv(name, value)
    assert Settings(_env_file=None).gemini_api_keys == ["a", "b"]


def test_rotates_when_key_has_no_access_to_the_model(monkeypatch):
    # A key from a project created after the model was closed to new users.
    not_found = Exception(
        "404 models/gemini-2.5-flash is no longer available to new users. "
        "Please update your code to use models/gemini-3.8-flash"
    )
    monkeypatch.setattr(llm, "get_settings", lambda: _Keys(["k1", "k2"]))
    monkeypatch.setattr(llm, "_key_index", 0)
    assert llm._is_model_unavailable(not_found) is True
    assert llm._is_model_unavailable(Exception("404 contract not found")) is False
    assert llm.rotate_api_key_on_key_failure(not_found) is True
    assert llm.active_api_key() == "k2"
