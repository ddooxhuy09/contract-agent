from typing import Any, List, Optional
import re

from app.agents.json_parsing import parse_json_object
from app.agents.legal_citations import (
    citations_to_legal_basis_line,
    ground_citations,
    resolve_legal_citations,
)
from app.agents.llm_client import DEFAULT_PROVIDER, chat_completion
from app.core.logging import logger
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


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                # tolerate {text: "..."} shapes
                t = item.get("text") or item.get("point") or item.get("label")
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
        return out
    return []


def _parse_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n > 1:
        n = n / 100.0
    return max(0.0, min(1.0, n))


def _build_recommendation_fallback(actions: list[str], revised: str | None) -> str | None:
    parts = [f"- {a}" for a in actions]
    if revised:
        parts.append(f"«{revised}»")
    return "\n".join(parts) if parts else None


def evaluate_clause(
    clause: Clause,
    provider: str = DEFAULT_PROVIDER,
    *,
    contract_id: str | None = None,
    contract_type: str | None = None,
    as_of_date: str | None = None,
    job_context: str | None = None,
    skip_topics: list[str] | None = None,
) -> Optional[RiskItem]:
    """Retrieve law relevant to THIS clause specifically, then judge compliance against it.

    ``skip_topics``: topic keys already covered by deterministic red-flags (prompt hint
    only — callers that fully skip the clause never invoke this).
    """
    clause_ref = f"Điều {clause.clause_number}"
    clause_text = _resolve_clause_text(clause, contract_id)
    summary_for_query = clause.summary or clause_text
    # Fold job/workplace text so sector filters see "AI / công nghệ" vs "dầu khí".
    scope_summary = " ".join(
        p for p in (summary_for_query, job_context) if p and str(p).strip()
    ).strip() or summary_for_query

    rag = get_graph_rag()
    if rag is not None:
        hits = rag.retrieve_for_clause(
            clause.title,
            scope_summary,
            contract_type=contract_type,
            k_seed=4,
            max_total=10,
            as_of_date=as_of_date,
        )
        from langchain_core.documents import Document

        legal_docs = [
            Document(page_content=h.content, metadata=h.metadata) for h in hits
        ]
        legal_context = rag.format_context(hits, max_chars=7000)
        logger.info(
            "Clause %s: legal=%s superseding=%s expired_seeds=%s assessing",
            clause.clause_number,
            len(hits),
            sum(1 for h in hits if h.metadata.get("role") == "superseding"),
            sum(1 for h in hits if h.metadata.get("note") == "source_doc_may_be_repealed"),
        )
    else:
        legal_docs = retrieve_legal(
            f"{clause.title or ''} {scope_summary}".strip(),
            k=4,
            title=clause.title,
            summary=scope_summary,
            contract_type=contract_type,
        )
        legal_context = format_legal_context(legal_docs, max_chars=7000)

    if not legal_docs:
        logger.info(
            "Insufficient legal grounding for clause %s, skipping LLM call",
            clause.clause_number,
        )
        return RiskItem(
            clause_ref=clause_ref,
            title="Thiếu căn cứ pháp luật để đối chiếu",
            issue="Không tìm thấy căn cứ pháp luật đủ liên quan trong kho dữ liệu để đối chiếu điều khoản này.",
            severity="warning",
            summary_topics=["Thiếu căn cứ"],
            reasons=["Kho luật truy hồi không có đoạn đủ liên quan trên ngưỡng tương đồng."],
            impact=["Cần luật sư rà soát thủ công trước khi ký."],
            actions=["Nhờ luật sư đối chiếu thủ công với Bộ luật / nghị định liên quan."],
            legal_basis=None,
            recommendation="Cần luật sư rà soát thủ công do thiếu dữ liệu pháp luật tham chiếu cho điều khoản này.",
            original_clause=clause_text or None,
            confidence=0.35,
        )

    skip_note = ""
    if skip_topics:
        skip_note = (
            "\n\nĐã có phân tích deterministic cho các chủ đề: "
            + ", ".join(skip_topics)
            + ". Chỉ nêu rủi ro *khác* các chủ đề đó; không lặp lại.\n"
        )

    prompt = CLAUSE_RISK_PROMPT.format(
        clause_number=clause.clause_number,
        clause_title_suffix=f" - {clause.title}" if clause.title else "",
        clause_text=clause_text[:6000],
        clause_summary=(clause.summary or "")[:800],
        legal_context=legal_context + skip_note,
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
        return None

    actions = _as_str_list(result.get("actions"))
    revised = (result.get("revised_clause") or "").strip() or None
    # Also accept draft inside « » from recommendation if revised_clause missing
    if not revised:
        rec = result.get("recommendation") or ""
        m = re.search(r"«([^»]+)»", rec)
        if m and len(m.group(1).strip()) > 40:
            revised = m.group(1).strip()

    recommendation = (result.get("recommendation") or "").strip() or None
    if not recommendation:
        recommendation = _build_recommendation_fallback(actions, revised)

    legal_basis_raw = result.get("legal_basis")
    if isinstance(legal_basis_raw, str):
        legal_basis_raw = legal_basis_raw.strip() or None
    else:
        legal_basis_raw = None

    citations = ground_citations(
        result.get("legal_citations"),
        result.get("evidence_paths"),
        legal_docs,
        contract_text=scope_summary,
        as_of_date=as_of_date,
    )
    if not citations:
        citations = resolve_legal_citations(result.get("legal_citations"), legal_basis_raw)
    legal_basis = citations_to_legal_basis_line(citations) or legal_basis_raw

    # Build legacy issue text if model only returned structured reasons
    reasons = _as_str_list(result.get("reasons"))
    if not issue and reasons:
        issue = "\n".join(["Kết luận: " + (result.get("title") or "Có vấn đề cần xử lý."), "Lý do:"] + [f"- {r}" for r in reasons])

    return RiskItem(
        clause_ref=clause_ref,
        issue=issue,
        severity=severity,
        legal_basis=legal_basis,
        recommendation=recommendation,
        title=(result.get("title") or "").strip() or None,
        summary_topics=_as_str_list(result.get("summary_topics")) or None,
        impact=_as_str_list(result.get("impact")) or None,
        legal_citations=citations or None,
        actions=actions or None,
        revised_clause=revised,
        original_clause=clause_text or None,
        confidence=_parse_confidence(result.get("confidence")),
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
