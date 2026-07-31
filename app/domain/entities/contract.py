from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class Contract:
    contract_id: str
    user_id: UUID
    filename: str
    file_type: str
    storage_key: str
    full_text: str | None = None
    status: str = "pending"
    message: str | None = None
    chunk_count: int = 0
    analysis: dict[str, Any] | None = None
    risks: list[Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ContractChunk:
    contract_id: str
    chunk_index: int
    clause_number: str
    content: str
    embedding: list[float] | None = None
    id: int | None = None
