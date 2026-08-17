from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class LegalDocument:
    doc_id: str
    doc_num: str
    title: str
    doc_type: str
    majors: list[str] | None = None
    fields: list[str] | None = None
    issue_date: date | None = None
    eff_from: date | None = None
    eff_to: date | None = None
    eff_flag: str | None = None
    status_flag: int = 0
    agency: str | None = None
    signer_name: str | None = None
    signer_title: str | None = None
    source_url: str | None = None
    full_text: str | None = None
    crawled_at: datetime | None = None


@dataclass(slots=True)
class LegalChunk:
    doc_id: str
    chunk_text: str
    path: str  # ltree text — stable key
    source_element_id: str | None = None  # VBPL prov-article/prov-clause DOM id
    chunk_type: str = "body"
    embedding: list[float] | None = None
    is_effective: bool = True
    root_path: str | None = None  # ltree text to nearest Article
    id: int | None = None


@dataclass(slots=True)
class LegalNode:
    doc_id: str
    level: str
    path: str  # ltree text
    label: str | None = None
    parent_path: str | None = None
    sort_order: int | None = None
    eff_from: date | None = None
    eff_to: date | None = None
    eff_flag: str | None = None
    status_flag: int = 0
    muc_luc_id: str | None = None
    id: int | None = None


@dataclass(slots=True)
class LegalDocRelation:
    from_doc_id: str
    to_doc_id: str
    relation_type: str


@dataclass(slots=True)
class LegalChunkRelation:
    from_path: str  # ltree text
    to_path: str
    relation_type: str
    note: str | None = None
    effective_date: date | None = None
