from pydantic import BaseModel, Field
from typing import Any


class Party(BaseModel):
    name: str
    role: str
    address: str | None = None
    tax_id: str | None = None  # MST / mã số doanh nghiệp only — never a personal ID number
    id_number: str | None = None  # CCCD / CMND / hộ chiếu of an individual
    representative: str | None = None


class Clause(BaseModel):
    clause_number: str
    title: str | None = None
    summary: str


class LegalCitation(BaseModel):
    """One complete legal reference — title is an atomic doc entity (never split on /)."""

    title: str
    summary: str = ""
    doc_number: str | None = None
    location: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    quote: str | None = None
    source_url: str | None = None
    deep_link: str | None = None
    source_element_id: str | None = None
    evidence_path: str | None = None
    status: str | None = None


class RiskFinding(BaseModel):
    """One independent violation inside a RiskItem (a Điều can hold several)."""

    key: str
    title: str
    severity: str = Field(..., pattern="^(critical|warning|ok)$")
    reason: str
    violated_text: str | None = None  # the contract sentence(s) that trigger it
    legal_citations: list[LegalCitation] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_notes: list[str] | None = None


class RiskItem(BaseModel):
    clause_ref: str
    issue: str
    severity: str = Field(..., pattern="^(critical|warning|ok)$")
    legal_basis: str | None = None
    recommendation: str | None = None
    # Structured fields (optional — older analyses may only have issue/legal_basis/recommendation)
    title: str | None = None
    summary_topics: list[str] | None = None
    reasons: list[str] | None = None
    impact: list[str] | None = None
    legal_citations: list[LegalCitation] | None = None
    actions: list[str] | None = None
    revised_clause: str | None = None
    original_clause: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    # Why the confidence is what it is (evidence checks that raised or lowered it).
    confidence_notes: list[str] | None = None
    # Per-violation breakdown (deterministic engine); the fields above stay the merged view.
    findings: list[RiskFinding] | None = None


class ContractAnalysis(BaseModel):
    contract_id: str
    contract_type: str | None = None
    parties: list[Party] = []
    execution_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    contract_value: str | None = None
    payment_terms: str | None = None
    payment_method: str | None = None
    termination_clause: str | None = None
    penalty_clause: str | None = None
    indemnity: str | None = None
    force_majeure: str | None = None
    governing_law: str | None = None
    dispute_resolution: str | None = None
    confidentiality: str | None = None
    severability: str | None = None
    amendments: str | None = None
    clauses: list[Clause] = []
    # Set by the analysis workflow: how many clauses were actually checked (see workflow._coverage).
    coverage: dict | None = None
    # Set by the analysis workflow: which date the law was checked at and why (signing vs today).
    legal_as_of: dict | None = None
    # Điều 21 BLLĐ checklist: per mandatory item co / chua_day_du / thieu / khong_ap_dung.
    required_content: list[dict] | None = None
    # Set by AnalyzeContract: LLM requests, tokens and duration of the run that produced this result.
    usage: dict | None = None


class UploadResponse(BaseModel):
    contract_id: str
    filename: str
    file_type: str
    status: str
    message: str
    chunk_count: int = 0


class AnalyzeResponse(BaseModel):
    contract_id: str
    analysis: Any
    risks: list[Any]


class AnalyzeReviewResponse(BaseModel):
    contract_id: str
    status: str
    review_id: str
    draft_analysis: Any | None = None
    draft_risks: list[Any] = []


class ResumeAnalysisRequest(BaseModel):
    contract_id: str
    review_id: str
    approved: bool = True
    edits: list[Any] | None = None


class ResumeAnalysisResponse(BaseModel):
    contract_id: str
    status: str
    approved: bool
    analysis: Any
    risks: list[Any]


class ChatResponse(BaseModel):
    answer: str
    source_clauses: list[str]
    contract_id: str
    needs_clarification: bool = False


class ChatHistoryItem(BaseModel):
    question: str
    answer: str
    source_clauses: list[str]
    needs_clarification: bool = False
    created_at: str


class ChatHistoryResponse(BaseModel):
    contract_id: str
    messages: list[ChatHistoryItem]


class ChatStateItem(BaseModel):
    checkpoint_id: str | None = None
    next: list[str] = []
    message_count: int = 0
    answer: str = ""
    source_clauses: list[str] = []
    needs_clarification: bool = False


class ChatStatesResponse(BaseModel):
    contract_id: str
    states: list[ChatStateItem]


class ChatRewindRequest(BaseModel):
    checkpoint_id: str


class ChatRewindResponse(BaseModel):
    contract_id: str
    checkpoint_id: str | None = None
    message_count: int = 0
    answer: str = ""
    source_clauses: list[str] = []
    needs_clarification: bool = False


class ContractSummary(BaseModel):
    contract_id: str
    filename: str
    status: str
    chunk_count: int
    created_at: str


class ContractListResponse(BaseModel):
    contracts: list[ContractSummary]
