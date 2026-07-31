from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievedChunk:
    content: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
