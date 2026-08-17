from pydantic import BaseModel, Field
from typing import Optional, List, Any


class Party(BaseModel):
    name: str
    role: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    representative: Optional[str] = None


class Clause(BaseModel):
    clause_number: str
    title: Optional[str] = None
    summary: str


class LegalCitation(BaseModel):
    """One complete legal reference — title is an atomic doc entity (never split on /)."""

    title: str
    summary: str = ""
    doc_number: Optional[str] = None
    location: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    quote: Optional[str] = None
    source_url: Optional[str] = None
    deep_link: Optional[str] = None
    source_element_id: Optional[str] = None
    evidence_path: Optional[str] = None
    status: Optional[str] = None

    @classmethod
    def from_any(cls, data: dict) -> "LegalCitation | None":
        if not isinstance(data, dict):
            return None
        title = (data.get("title") or data.get("label") or data.get("name") or "").strip()
        if not title:
            return None
        summary = data.get("summary")
        if summary is None:
            points = data.get("points") or data.get("bullets") or []
            if isinstance(points, list):
                summary = " ".join(str(p).strip() for p in points if str(p).strip())
            else:
                summary = ""
        return cls(
            title=title,
            summary=str(summary or "").strip(),
            doc_number=data.get("doc_number"),
            location=data.get("location"),
            article=data.get("article"),
            clause=data.get("clause"),
            point=data.get("point"),
            quote=data.get("quote"),
            source_url=data.get("source_url") or data.get("url"),
            deep_link=data.get("deep_link"),
            source_element_id=data.get("source_element_id"),
            evidence_path=data.get("evidence_path") or data.get("path"),
            status=data.get("status") or data.get("eff_flag"),
        )


class RiskItem(BaseModel):
    clause_ref: str
    issue: str
    severity: str = Field(..., pattern="^(critical|warning|ok)$")
    legal_basis: Optional[str] = None
    recommendation: Optional[str] = None
    # Structured fields (optional — older analyses may only have issue/legal_basis/recommendation)
    title: Optional[str] = None
    summary_topics: Optional[List[str]] = None
    reasons: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    legal_citations: Optional[List[LegalCitation]] = None
    actions: Optional[List[str]] = None
    revised_clause: Optional[str] = None
    original_clause: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ContractAnalysis(BaseModel):
    contract_id: str
    contract_type: Optional[str] = None
    parties: List[Party] = []
    execution_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    contract_value: Optional[str] = None
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    termination_clause: Optional[str] = None
    penalty_clause: Optional[str] = None
    indemnity: Optional[str] = None
    force_majeure: Optional[str] = None
    governing_law: Optional[str] = None
    dispute_resolution: Optional[str] = None
    confidentiality: Optional[str] = None
    severability: Optional[str] = None
    amendments: Optional[str] = None
    clauses: List[Clause] = []


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
    risks: List[Any]


class AnalyzeReviewResponse(BaseModel):
    contract_id: str
    status: str
    review_id: str
    draft_analysis: Optional[Any] = None
    draft_risks: List[Any] = []


class ResumeAnalysisRequest(BaseModel):
    contract_id: str
    review_id: str
    approved: bool = True
    edits: Optional[List[Any]] = None


class ResumeAnalysisResponse(BaseModel):
    contract_id: str
    status: str
    approved: bool
    analysis: Any
    risks: List[Any]


class ChatResponse(BaseModel):
    answer: str
    source_clauses: List[str]
    contract_id: str
    needs_clarification: bool = False


class ChatHistoryItem(BaseModel):
    question: str
    answer: str
    source_clauses: List[str]
    needs_clarification: bool = False
    created_at: str


class ChatHistoryResponse(BaseModel):
    contract_id: str
    messages: List[ChatHistoryItem]


class ChatStateItem(BaseModel):
    checkpoint_id: Optional[str] = None
    next: List[str] = []
    message_count: int = 0
    answer: str = ""
    source_clauses: List[str] = []
    needs_clarification: bool = False


class ChatStatesResponse(BaseModel):
    contract_id: str
    states: List[ChatStateItem]


class ChatRewindRequest(BaseModel):
    checkpoint_id: str


class ChatRewindResponse(BaseModel):
    contract_id: str
    checkpoint_id: Optional[str] = None
    message_count: int = 0
    answer: str = ""
    source_clauses: List[str] = []
    needs_clarification: bool = False


class ContractSummary(BaseModel):
    contract_id: str
    filename: str
    status: str
    chunk_count: int
    created_at: str


class ContractListResponse(BaseModel):
    contracts: List[ContractSummary]
