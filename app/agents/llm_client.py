"""LLM helpers — Gemini via LangChain, with respectful 429 backoff."""

from __future__ import annotations

import re
import time

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.logging import logger
from app.core.settings import get_settings

DEFAULT_PROVIDER = "gemini"

_gemini_chat: ChatGoogleGenerativeAI | None = None
_gemini_chat_json: ChatGoogleGenerativeAI | None = None


def get_providers() -> dict[str, dict[str, str]]:
    settings = get_settings()
    return {
        "gemini": {"label": "Gemini 2.5 Flash", "model": settings.gemini_model},
    }


# Kept for routes that iterate providers at import/list time.
PROVIDERS = get_providers()


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
                google_api_key=settings.gemini_api_key,
                temperature=0,
                timeout=120,
                max_retries=0,  # we handle 429 sleep ourselves
                response_mime_type="application/json",
            )
        return _gemini_chat_json
    if _gemini_chat is None:
        settings = get_settings()
        _gemini_chat = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
            timeout=120,
            max_retries=0,
        )
    return _gemini_chat


def _retry_delay_seconds(exc: BaseException, default: float = 30.0) -> float | None:
    """Parse Gemini RESOURCE_EXHAUSTED retryDelay; None if not a rate-limit error."""
    text = str(exc)
    if "429" not in text and "RESOURCE_EXHAUSTED" not in text and "rate" not in text.lower():
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
        try:
            response = model.invoke(prompt)
            return response.content
        except Exception as e:
            last_err = e
            delay = _retry_delay_seconds(e)
            if delay is None or attempt >= 2:
                raise
            logger.warning(
                "LLM rate-limited (attempt %s/3); sleeping %.1fs before retry",
                attempt + 1,
                delay,
            )
            time.sleep(delay)
    assert last_err is not None
    raise last_err
