from typing import List, Optional
from app.schemas.contract import Clause, RiskItem
from app.core.prompts import CLAUSE_RISK_PROMPT
from app.core.config import logger
from app.agents.llm_client import chat_completion, DEFAULT_PROVIDER
from app.agents.json_parsing import parse_json_object
from app.vectorstore.retriever import retrieve_legal


def evaluate_clause(clause: Clause, provider: str = DEFAULT_PROVIDER) -> Optional[RiskItem]:
    """Retrieve law relevant to THIS clause specifically, then judge compliance against it.

    Each clause gets its own targeted retrieval instead of one generic query for the whole
    contract, so a clause about termination isn't judged against law retrieved for confidentiality.
    """
    clause_ref = f"Điều {clause.clause_number}"
    query = f"{clause.title or ''} {clause.summary}".strip()
    legal_docs = retrieve_legal(query, k=3)

    if not legal_docs:
        # No relevant law found above the similarity threshold: don't let the LLM guess a
        # verdict with no grounding. Surface it as needing manual review instead.
        return RiskItem(
            clause_ref=clause_ref,
            issue="Không tìm thấy căn cứ pháp luật đủ liên quan trong kho dữ liệu để đối chiếu điều khoản này.",
            severity="warning",
            legal_basis=None,
            recommendation="Cần luật sư rà soát thủ công do thiếu dữ liệu pháp luật tham chiếu cho điều khoản này.",
        )

    legal_context = "\n\n".join(d.page_content for d in legal_docs)
    prompt = CLAUSE_RISK_PROMPT.format(
        clause_number=clause.clause_number,
        clause_title_suffix=f" - {clause.title}" if clause.title else "",
        clause_text=clause.summary[:3000],
        legal_context=legal_context[:4000],
    )

    raw = chat_completion(prompt, provider=provider)
    result = parse_json_object(raw)
    if result is None:
        logger.error(f"Failed to parse clause risk output for clause {clause.clause_number}, retrying once")
        raw = chat_completion(prompt, provider=provider)
        result = parse_json_object(raw)
        if result is None:
            logger.error(f"Clause {clause.clause_number}: still unparsable after retry, skipping")
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


def flag_risks(clauses: List[Clause], contract_id: str, provider: str = DEFAULT_PROVIDER) -> List[RiskItem]:
    """Sequential fallback used outside the async workflow (e.g. tests, scripts)."""
    logger.info(f"Flagging risks per-clause for contract {contract_id}: {len(clauses)} clause(s)")
    risks: List[RiskItem] = []
    for clause in clauses:
        try:
            risk = evaluate_clause(clause, provider)
            if risk:
                risks.append(risk)
        except Exception as e:
            logger.error(f"Risk evaluation failed for clause {clause.clause_number} in {contract_id}: {e}")
    return risks
