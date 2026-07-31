"""Reciprocal Rank Fusion helpers."""

from typing import TypeVar

T = TypeVar("T")


def rrf_fuse(
    ranked_lists: list[list[T]],
    *,
    key_fn,
    rrf_k: int = 60,
) -> list[tuple[T, float]]:
    """Fuse multiple ranked lists; returns items sorted by descending RRF score."""
    scores: dict[str, float] = {}
    items: dict[str, T] = {}
    for results in ranked_lists:
        for rank, item in enumerate(results):
            key = key_fn(item)
            items[key] = item
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(items[k], score) for k, score in ordered]
