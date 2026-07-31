from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class LegalDocument:
    doc_id: str
    doc_num: str
    title: str
    doc_type: str
    doc_num_norm: str | None = None
    majors: list[str] | None = None
    fields: list[str] | None = None
    issue_date: date | None = None
    eff_from: date | None = None
    eff_to: date | None = None
    eff_status: str | None = None
    eff_status_code: str | None = None
    status_flag: int = 0
    agency: str | None = None
    signers: list[dict[str, Any]] | None = None
    source_url: str | None = None
    full_text: str | None = None
    crawled_at: datetime | None = None


@dataclass(slots=True)
class LegalChunk:
    chunk_ref: str
    doc_id: str
    chunk_text: str
    chunk_type: str = "body"
    embedding: list[float] | None = None
    is_effective: bool = True
    id: int | None = None


@dataclass(slots=True)
class LegalDocRelation:
    from_doc_id: str
    to_doc_id: str
    relation_type: str


@dataclass(slots=True)
class LegalChunkRelation:
    from_chunk_ref: str
    to_chunk_ref: str
    relation_type: str
    note: str | None = None
    effective_date: date | None = None
