from typing import List, Optional

from app.agents.json_parsing import parse_json_object
from app.agents.llm_client import DEFAULT_PROVIDER, chat_completion
from app.core.config import logger
from app.core.prompts import CLAUSE_RISK_PROMPT
from app.infrastructure.retrieval.context import get_contract_chunks, get_graph_rag
from app.schemas.contract import Clause, RiskItem
from app.vectorstore.retriever import format_legal_context, retrieve_legal


def _resolve_clause_text(
    clause: Clause,
    contract_id: str | None,
) -> str:
    """Prefer stored contract_chunks body for this Điều; fall back to extract summary."""
    if contract_id:
        repo = get_contract_chunks()
        if repo is not None:
            try:
                body = repo.get_text_by_clause(contract_id, clause.clause_number)
                if body and body.strip():
                    return body.strip()
            except Exception as e:
                logger.warning(
                    "Failed to load contract chunk for Điều %s: %s",
                    clause.clause_number,
                    e,
                )
    return (clause.summary or "").strip()


def evaluate_clause(
    clause: Clause,
    provider: str = DEFAULT_PROVIDER,
    *,
    contract_id: str | None = None,
    contract_type: str | None = None,
) -> Optional[RiskItem]:
    """Retrieve law relevant to THIS clause specifically, then judge compliance against it.

    Each clause gets its own targeted retrieval instead of one generic query for the whole
    contract, so a clause about termination isn't judged against law retrieved for confidentiality.
    """
    clause_ref = f"Điều {clause.clause_number}"
    clause_text = _resolve_clause_text(clause, contract_id)
    summary_for_query = clause.summary or clause_text

    rag = get_graph_rag()
    if rag is not None:
        hits = rag.retrieve_for_clause(
            clause.title,
            summary_for_query,
            contract_type=contract_type,
            k_seed=4,
            max_total=10,
        )
        from langchain_core.documents import Document

        legal_docs = [
            Document(page_content=h.content, metadata=h.metadata) for h in hits
        ]
        legal_context = rag.format_context(hits, max_chars=7000)
    else:
        legal_docs = retrieve_legal(
            f"{clause.title or ''} {summary_for_query}".strip(),
            k=4,
            title=clause.title,
            summary=summary_for_query,
            contract_type=contract_type,
        )
        legal_context = format_legal_context(legal_docs, max_chars=7000)

    if not legal_docs:
        # No relevant law found above the similarity threshold: don't let the LLM guess a
        # verdict with no grounding. Surface it as needing manual review instead.
        logger.info(
            "Insufficient legal grounding for clause %s, skipping LLM call",
            clause.clause_number,
        )
        return RiskItem(
            clause_ref=clause_ref,
            issue="Không tìm thấy căn cứ pháp luật đủ liên quan trong kho dữ liệu để đối chiếu điều khoản này.",
            severity="warning",
            legal_basis=None,
            recommendation="Cần luật sư rà soát thủ công do thiếu dữ liệu pháp luật tham chiếu cho điều khoản này.",
        )

    prompt = CLAUSE_RISK_PROMPT.format(
        clause_number=clause.clause_number,
        clause_title_suffix=f" - {clause.title}" if clause.title else "",
        clause_text=clause_text[:4000],
        clause_summary=(clause.summary or "")[:800],
        legal_context=legal_context,
    )

    raw = chat_completion(prompt, provider=provider)
    result = parse_json_object(raw)
    if result is None:
        logger.error(
            "Failed to parse clause risk output for clause %s, retrying once",
            clause.clause_number,
        )
        raw = chat_completion(prompt, provider=provider)
        result = parse_json_object(raw)
        if result is None:
            logger.error(
                "Clause %s: still unparsable after retry, skipping",
                clause.clause_number,
            )
            return None

    severity = result.get("severity", "ok")
    issue = (result.get("issue") or "").strip()
    if severity == "ok" and not issue:
        return None  # clause is fine, don't clutter the report

    return RiskItem(
        clause_ref=clause_ref,
        issue=issue,
        severity=severity,
        legal_basis=result.get("legal_basis"),
        recommendation=result.get("recommendation"),
    )


def flag_risks(
    clauses: List[Clause],
    contract_id: str,
    provider: str = DEFAULT_PROVIDER,
    contract_type: str | None = None,
) -> List[RiskItem]:
    """Sequential fallback used outside the async workflow (e.g. tests, scripts)."""
    logger.info(
        "Flagging risks per-clause for contract %s: %s clause(s)",
        contract_id,
        len(clauses),
    )
    risks: List[RiskItem] = []
    for clause in clauses:
        try:
            risk = evaluate_clause(
                clause,
                provider,
                contract_id=contract_id,
                contract_type=contract_type,
            )
            if risk:
                risks.append(risk)
        except Exception as e:
            logger.error(
                "Risk evaluation failed for clause %s in %s: %s",
                clause.clause_number,
                contract_id,
                e,
            )
    return risks
