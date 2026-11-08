"""LLM helpers — Gemini via LangChain, with respectful 429 backoff."""

from __future__ import annotations

import re
import threading
import time

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.logging import logger
from app.core.settings import get_settings
from app.core.usage import UsageCallback

DEFAULT_PROVIDER = "gemini"

_gemini_chat: ChatGoogleGenerativeAI | None = None
_gemini_chat_json: ChatGoogleGenerativeAI | None = None
_key_index = 0
# Clause checks run on several threads at once; one key failure must move the index only once.
_rotate_lock = threading.Lock()


def active_api_key() -> str:
    """The key currently in use, from GEMINI_API_KEY / GEMINI_API_KEY_1..3."""
    keys = get_settings().gemini_api_keys
    if not keys:
        return ""
    return keys[min(_key_index, len(keys) - 1)]


def _is_daily_quota(exc: BaseException) -> bool:
    text = str(exc)
    if "429" not in text and "RESOURCE_EXHAUSTED" not in text:
        return False
    return bool(re.search(r"per\s*day|perday|daily", text, re.I))


def _is_model_unavailable(exc: BaseException) -> bool:
    """True when this key's project cannot serve the configured model at all.

    Google serves gemini-2.5-flash only to projects that already used it, so a key
    created later answers 404 "no longer available to new users" even though the
    model still shows up in that project's ListModels. Another key may work, so this
    is worth moving on for, exactly like a per-day quota.
    """
    text = str(exc)
    if "404" not in text and "NOT_FOUND" not in text:
        return False
    return "no longer available" in text.lower() or "is not found" in text.lower()


def rotate_api_key_on_key_failure(exc: BaseException, failed_key: str | None = None) -> bool:
    """Switch to the next configured key when this one cannot serve the request.

    Two failures are worth another key: the per-day quota, which lasts hours, and a
    model the key's project has no access to at all. A per-minute limit clears on its
    own and is handled by the sleep in ``chat_completion``.
    ``failed_key`` is the key the failed call used: if another thread already moved on
    from it, that switch is reused instead of skipping a further key.
    Returns True when a different key is now active.
    """
    global _key_index, _gemini_chat, _gemini_chat_json
    reason = "per-day quota exhausted" if _is_daily_quota(exc) else (
        "model unavailable for this key" if _is_model_unavailable(exc) else "")
    if not reason:
        return False
    with _rotate_lock:
        if failed_key is not None and failed_key != active_api_key():
            return True
        keys = get_settings().gemini_api_keys
        if _key_index + 1 >= len(keys):
            return False
        _key_index += 1
        _gemini_chat = None
        _gemini_chat_json = None
        logger.warning("Gemini key %s: %s; switching to key %s of %s", _key_index, reason, _key_index + 1, len(keys))
        return True


def keys_remaining() -> int:
    """Configured keys not yet used in this process (0 = the last key is active)."""
    return max(0, len(get_settings().gemini_api_keys) - 1 - _key_index)


def get_providers() -> dict[str, dict[str, str]]:
    settings = get_settings()
    return {
        "gemini": {
            "public_id": "standard",
            "alias": "Chuẩn",
            "label": "Gemini 2.5 Flash",
            "model": settings.gemini_model,
        },
    }


def resolve_provider(value: str | None) -> str:
    """Map a public analysis-mode id (or legacy internal key) to the internal provider."""
    if not value:
        return DEFAULT_PROVIDER
    providers = get_providers()
    if value in providers:
        return value
    needle = value.strip().lower()
    for key, info in providers.items():
        if info.get("public_id", "").lower() == needle:
            return key
        if info.get("alias", "").lower() == needle:
            return key
    return DEFAULT_PROVIDER


def get_chat_model(provider: str = DEFAULT_PROVIDER, *, json_mode: bool = False) -> ChatGoogleGenerativeAI:
    """Return the underlying LangChain chat model, for callers that need message-list
    invocation (e.g. a LangGraph node building its own SystemMessage/HumanMessage prompt)
    rather than the flattened single-string helper below.

    json_mode=True pins ``response_mime_type=="application/json"`` so the model emits a
    strict JSON envelope (no fences, no prose) for the structured-answer nodes; the
    plain-text instance is kept apart because other callers (query rewrite) need prose.
    """
    global _gemini_chat, _gemini_chat_json
    if json_mode:
        if _gemini_chat_json is None:
            settings = get_settings()
            _gemini_chat_json = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=active_api_key(),
                temperature=0,
                timeout=120,
                max_retries=0,  # we handle 429 sleep ourselves
                response_mime_type="application/json",
                callbacks=[UsageCallback(settings.gemini_model)],
            )
        return _gemini_chat_json
    if _gemini_chat is None:
        settings = get_settings()
        _gemini_chat = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=active_api_key(),
            temperature=0,
            timeout=120,
            max_retries=0,
            callbacks=[UsageCallback(settings.gemini_model)],
        )
    return _gemini_chat


# Not a bare "rate": it would match "generateContent" in any Gemini error.
_RATE_LIMIT_RE = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|rate[\s_-]?limit", re.I)


def _retry_delay_seconds(exc: BaseException, default: float = 30.0) -> float | None:
    """Parse Gemini RESOURCE_EXHAUSTED retryDelay; None if not a rate-limit error."""
    text = str(exc)
    if not _RATE_LIMIT_RE.search(text):
        return None
    m = re.search(r"retry(?:Delay| in)\D+(\d+(?:\.\d+)?)\s*s", text, re.I)
    if m:
        return min(90.0, max(1.0, float(m.group(1))))
    return default


def chat_completion(prompt: str, provider: str = DEFAULT_PROVIDER) -> str:
    """Invoke chat model; on 429 sleep for server-suggested delay then retry (max 2 waits)."""
    model = get_chat_model(provider)
    last_err: BaseException | None = None
    for attempt in range(3):
        key_used = active_api_key()
        try:
            response = model.invoke(prompt)
            return response.content
        except Exception as e:
            last_err = e
            if attempt < 2 and rotate_api_key_on_key_failure(e, key_used):
                model = get_chat_model(provider)
                continue
            delay = _retry_delay_seconds(e)
            # A per-day quota will not clear within a sleep: with no other key to move to, fail now.
            if delay is None or attempt >= 2 or _is_daily_quota(e):
                raise
            logger.warning(
                "LLM rate-limited (attempt %s/3); sleeping %.1fs before retry",
                attempt + 1,
                delay,
            )
            time.sleep(delay)
    assert last_err is not None
    raise last_err
