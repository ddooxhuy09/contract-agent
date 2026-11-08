"""Characterization tests for app/agents/risk_flagger.evaluate_clause.

All collaborators (RAG, retrieval, LLM, citation grounding) are faked, so the tests
pin the retrieve -> prompt -> parse -> RiskItem behaviour without any DB or network.
"""

import json
from types import SimpleNamespace

import pytest

import app.agents.risk_flagger as rf
from app.schemas.contract import Clause, LegalCitation

CLAUSE = Clause(clause_number="3", title="Chấm dứt", summary="Tóm tắt điều 3")
CLAUSE_BODY = "Nội dung đầy đủ của điều 3."


class _Repo:
    def get_text_by_clause(self, contract_id, clause_number):
        return f"  {CLAUSE_BODY}  "


class _Rag:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def retrieve_for_clause(self, title, summary, **kwargs):
        self.calls.append((title, summary, kwargs))
        return self.hits

    def format_context(self, hits, max_chars):
        return f"RAG-CTX({len(hits)},{max_chars})"


def _hit(role="seed", note=None):
    meta = {"role": role}
    if note:
        meta["note"] = note
    return SimpleNamespace(content="Điều luật", metadata=meta)


@pytest.fixture
def env(monkeypatch):
    """Faked collaborators; tests tweak the returned namespace."""
    state = SimpleNamespace(llm_outputs=[], prompts=[], legal_calls=[], rag=None)

    monkeypatch.setattr(rf, "get_contract_chunks", lambda: _Repo())
    monkeypatch.setattr(rf, "get_graph_rag", lambda: state.rag)

    def fake_retrieve_legal(query, **kwargs):
        state.legal_calls.append((query, kwargs))
        return [SimpleNamespace(page_content="Luật", metadata={})]

    monkeypatch.setattr(rf, "retrieve_legal", fake_retrieve_legal)
    monkeypatch.setattr(rf, "format_legal_context", lambda docs, max_chars: f"LEGAL-CTX({len(docs)})")

    def fake_chat(prompt, provider=None):
        state.prompts.append(prompt)
        return state.llm_outputs.pop(0)

    monkeypatch.setattr(rf, "chat_completion", fake_chat)
    monkeypatch.setattr(rf, "ground_citations", lambda *a, **k: [])
    monkeypatch.setattr(rf, "resolve_legal_citations", lambda *a, **k: [])
    return state


def _llm(**fields):
    return json.dumps({"severity": "warning", "issue": "Vấn đề", **fields})


def test_no_legal_docs_returns_insufficient_grounding_item(env, monkeypatch):
    monkeypatch.setattr(rf, "retrieve_legal", lambda *a, **k: [])
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.clause_ref == "Điều 3"
    assert risk.severity == "warning"
    assert risk.title == "Thiếu căn cứ pháp luật để đối chiếu"
    assert risk.confidence == 0.35
    assert risk.original_clause == CLAUSE_BODY
    assert risk.legal_basis is None
    assert env.prompts == []  # LLM never called


def test_fallback_retrieval_arguments(env):
    env.llm_outputs.append(_llm())
    rf.evaluate_clause(CLAUSE, contract_id="c1", contract_type="HĐLĐ", job_context="công nghệ")
    query, kwargs = env.legal_calls[0]
    scope = "Tóm tắt điều 3 công nghệ"
    assert query == f"Chấm dứt {scope}"
    assert kwargs == {"k": 4, "title": "Chấm dứt", "summary": scope, "contract_type": "HĐLĐ"}
    assert "LEGAL-CTX(1)" in env.prompts[0]


def test_graph_rag_path_uses_rag_context_and_arguments(env):
    env.rag = _Rag([_hit(), _hit("superseding")])
    env.llm_outputs.append(_llm())
    rf.evaluate_clause(CLAUSE, contract_id="c1", contract_type="HĐLĐ", as_of_date="2024-01-01")
    title, summary, kwargs = env.rag.calls[0]
    assert (title, summary) == ("Chấm dứt", "Tóm tắt điều 3")
    assert kwargs == {"contract_type": "HĐLĐ", "k_seed": 4, "max_total": 10, "as_of_date": "2024-01-01"}
    assert "RAG-CTX(2,7000)" in env.prompts[0]
    assert env.legal_calls == []  # fallback retrieval unused


def test_empty_rag_hits_returns_insufficient_grounding_item(env):
    env.rag = _Rag([])
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.title == "Thiếu căn cứ pháp luật để đối chiếu"
    assert env.prompts == []


def test_prompt_carries_clause_title(env):
    env.llm_outputs.append(_llm())
    rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert "Điều 3 - Chấm dứt" in env.prompts[0]


def test_unparsable_once_then_ok_retries(env):
    env.llm_outputs.extend(["không phải json", _llm()])
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert len(env.prompts) == 2
    assert risk.issue == "Vấn đề"


def test_unparsable_twice_raises_not_clean(env):
    env.llm_outputs.extend(["x", "y"])
    with pytest.raises(rf.JudgeUnparsable):
        rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert len(env.prompts) == 2


@pytest.mark.parametrize("verdict", ['{"issue": "x"}', '{"severity": "high", "issue": "x"}', "[]"])
def test_verdict_without_valid_severity_is_unusable(env, verdict):
    env.llm_outputs.extend([verdict, verdict])
    with pytest.raises(rf.JudgeUnparsable):
        rf.evaluate_clause(CLAUSE, contract_id="c1")


def test_ok_without_issue_returns_none(env):
    env.llm_outputs.append(json.dumps({"severity": "ok", "issue": ""}))
    assert rf.evaluate_clause(CLAUSE, contract_id="c1") is None


def test_full_risk_item_fields(env):
    env.llm_outputs.append(
        _llm(
            title=" Tiêu đề ",
            severity="critical",
            recommendation=" Nên sửa ",
            revised_clause="Điều khoản mới",
            actions=["Làm A", " "],
            summary_topics=["t1"],
            impact=["i1"],
            confidence=80,
            legal_basis=" BLLĐ Điều 36 ",
        )
    )
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.model_dump() == {
        "clause_ref": "Điều 3",
        "issue": "Vấn đề",
        "severity": "critical",
        "legal_basis": "BLLĐ Điều 36",
        "recommendation": "Nên sửa",
        "title": "Tiêu đề",
        "summary_topics": ["t1"],
        "reasons": None,
        "impact": ["i1"],
        "legal_citations": None,
        "actions": ["Làm A"],
        "revised_clause": "Điều khoản mới",
        "original_clause": CLAUSE_BODY,
        # The model said 80 but nothing was grounded in the corpus → capped, with the reason kept.
        "confidence": 0.45,
        "confidence_notes": ["Không có căn cứ pháp lý đã xác minh trong kho."],
        "findings": None,
    }


def test_confidence_keeps_model_value_when_citation_is_consistent(env, monkeypatch):
    cite = LegalCitation(
        title="Điều 36 — BLLĐ", article="Điều 36", clause="Khoản 1", location="Chương 3 > Mục 3 > Điều 36 > Khoản 1",
        evidence_path="139264.C3.M3.D36.K1", quote="Điều 36. Quyền đơn phương\n1. Người sử dụng lao động có quyền",
    )
    monkeypatch.setattr(rf, "ground_citations", lambda *a, **k: [cite])
    env.llm_outputs.append(_llm(confidence=0.9))
    assert rf.evaluate_clause(CLAUSE, contract_id="c1").confidence == 0.9


def test_confidence_drops_when_citation_is_inconsistent(env, monkeypatch):
    bad = LegalCitation(  # article/clause disagree with the evidence path
        title="Điều 98 — BLLĐ", article="Điều 98", clause="Khoản 2", evidence_path="139264.C6.D98.K1",
        quote="Điều 98. Tiền lương\n1. Người lao động làm thêm giờ",
    )
    monkeypatch.setattr(rf, "ground_citations", lambda *a, **k: [bad])
    env.llm_outputs.append(_llm(confidence=0.9))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.confidence < 0.9
    assert any("khoản" in n.lower() for n in risk.confidence_notes)


def test_llm_revised_clause_still_containing_illegal_term_is_dropped(env):
    env.llm_outputs.append(_llm(
        recommendation="Sửa thành «Công ty có quyền áp dụng hình thức kỷ luật phạt tiền 500.000 VNĐ mỗi lần.»",
        revised_clause="Công ty có quyền áp dụng hình thức kỷ luật phạt tiền 500.000 VNĐ mỗi lần.",
    ))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.revised_clause is None
    assert "phạt tiền" not in (risk.recommendation or "")
    assert any("không qua kiểm tra" in n for n in risk.confidence_notes)


def test_revised_clause_taken_from_recommendation_guillemets(env):
    draft = "Bên A chỉ được chấm dứt hợp đồng khi có thông báo trước ít nhất 45 ngày."
    env.llm_outputs.append(_llm(recommendation=f"Sửa thành «{draft}»"))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.revised_clause == draft


def test_short_guillemets_not_used_as_revised_clause(env):
    env.llm_outputs.append(_llm(recommendation="Sửa «ngắn»"))
    assert rf.evaluate_clause(CLAUSE, contract_id="c1").revised_clause is None


def test_recommendation_fallback_built_from_actions_and_revised(env):
    env.llm_outputs.append(_llm(actions=["Làm A", "Làm B"], revised_clause="Bản sửa"))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.recommendation == "- Làm A\n- Làm B\n«Bản sửa»"


def test_issue_built_from_reasons_when_missing(env):
    env.llm_outputs.append(json.dumps({"severity": "warning", "reasons": ["R1", "R2"], "title": "TT"}))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.issue == "Kết luận: TT\nLý do:\n- R1\n- R2"
    assert risk.reasons is None  # reasons are not copied onto the item


def test_grounded_citations_set_legal_basis_and_citations(env, monkeypatch):
    cite = LegalCitation(title="Bộ luật Lao động 2019", doc_number="45/2019/QH14")
    monkeypatch.setattr(rf, "ground_citations", lambda *a, **k: [cite])
    monkeypatch.setattr(rf, "citations_to_legal_basis_line", lambda cites: "DÒNG-CĂN-CỨ")
    env.llm_outputs.append(_llm(legal_basis="bỏ qua"))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert risk.legal_citations == [cite]
    assert risk.legal_basis == "DÒNG-CĂN-CỨ"


def test_resolve_citations_fallback_when_not_grounded(env, monkeypatch):
    cite = LegalCitation(title="Từ legal_basis")
    resolved = {}

    def fake_resolve(raw_citations, legal_basis):
        resolved["args"] = (raw_citations, legal_basis)
        return [cite]

    monkeypatch.setattr(rf, "resolve_legal_citations", fake_resolve)
    monkeypatch.setattr(rf, "citations_to_legal_basis_line", lambda cites: None)
    env.llm_outputs.append(_llm(legal_basis="  BLLĐ  ", legal_citations=["x"]))
    risk = rf.evaluate_clause(CLAUSE, contract_id="c1")
    assert resolved["args"] == (["x"], "BLLĐ")
    assert risk.legal_citations == [cite]
    assert risk.legal_basis == "BLLĐ"  # falls back to the raw text
