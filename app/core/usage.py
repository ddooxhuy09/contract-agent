"""LLM usage per analysis run: request and token counts.

``track_usage()`` opens a collector in a context variable; ``UsageCallback`` (attached to every
chat model in ``agents/llm_client``) adds one entry per API call, successful or failed, so a
retry counts as the request it really was. The context variable follows ``asyncio.to_thread``
and LangGraph tasks, which is how calls made deep inside the workflow reach the collector.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

_TOKEN_KEYS = ("input_tokens", "output_tokens", "total_tokens")


class UsageCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: dict[str, dict[str, int]] = defaultdict(
            lambda: {"requests": 0, "failed_requests": 0, **dict.fromkeys(_TOKEN_KEYS, 0)}
        )

    def record(self, model: str, tokens: dict[str, int] | None = None, failed: bool = False) -> None:
        with self._lock:
            entry = self._by_model[model or "unknown"]
            entry["requests"] += 1
            if failed:
                entry["failed_requests"] += 1
            for key in _TOKEN_KEYS:
                entry[key] += int((tokens or {}).get(key) or 0)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            by_model = {name: dict(entry) for name, entry in self._by_model.items()}
        total = {"requests": 0, "failed_requests": 0, **dict.fromkeys(_TOKEN_KEYS, 0)}
        for entry in by_model.values():
            for key in total:
                total[key] += entry[key]
        return {**total, "by_model": by_model}


_current: ContextVar[UsageCollector | None] = ContextVar("llm_usage", default=None)


@contextmanager
def track_usage() -> Iterator[UsageCollector]:
    collector = UsageCollector()
    token = _current.set(collector)
    try:
        yield collector
    finally:
        _current.reset(token)


def _tokens_from(response: Any) -> tuple[str, dict[str, int]]:
    """(model name, token counts) from the first generation of a LangChain result."""
    try:
        message = response.generations[0][0].message
    except (AttributeError, IndexError):
        return "", {}
    meta = getattr(message, "usage_metadata", None) or {}
    tokens = {key: int(meta.get(key) or 0) for key in _TOKEN_KEYS}
    if not tokens["total_tokens"]:
        tokens["total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
    model = (getattr(message, "response_metadata", None) or {}).get("model_name", "")
    return model, tokens


class UsageCallback(BaseCallbackHandler):
    """Feeds the active ``UsageCollector``; a no-op outside ``track_usage()``."""

    # Cheap and thread-safe: run in the calling thread so the context variable is the caller's.
    run_inline = True
    raise_error = False

    def __init__(self, default_model: str = "") -> None:
        self._default_model = default_model

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        collector = _current.get()
        if collector is not None:
            model, tokens = _tokens_from(response)
            collector.record(model or self._default_model, tokens)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        collector = _current.get()
        if collector is not None:
            collector.record(self._default_model, failed=True)
