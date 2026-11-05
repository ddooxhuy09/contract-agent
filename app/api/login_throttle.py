"""In-memory limiter for failed logins (per client address + email).

Single-process only: with several workers each keeps its own counters, so the effective limit is
per worker. Good enough for the local/single-container deployment this project targets.
"""
import time
from collections import deque


class LoginThrottle:
    def __init__(self, max_failures: int = 5, window_seconds: int = 900, clock=time.monotonic, max_keys: int = 10_000):
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        q = self._failures.get(key)
        if q is not None:
            cutoff = self._clock() - self._window
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self._failures[key]
                return deque()
        return q if q is not None else deque()

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed; 0 when not blocked."""
        q = self._recent(key)
        if len(q) < self._max:
            return 0
        return max(1, int(q[0] + self._window - self._clock()) + 1)

    def record_failure(self, key: str) -> None:
        if len(self._failures) >= self._max_keys:  # bound memory under a key-spraying attack
            self._failures.pop(next(iter(self._failures)))
        self._recent(key)
        self._failures.setdefault(key, deque()).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
