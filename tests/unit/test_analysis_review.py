"""Tests for the human-in-the-loop (review) gate in app/agents/workflow.py.

With review_mode=True the analysis graph pauses at the `review` node via interrupt()
and returns a draft (analysis + risks). A separate resume step feeds the human
decision back through Command(resume=...) so the run completes (or is rejected).
Tests use an InMemorySaver in place of the Postgres checkpointer.
"""

import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver

import app.agents.checkpointer as cp
import app.agents.workflow as wf
from app.schemas.contract import ContractAnalysis, Clause, RiskItem

_CONTRACT_TEXT = "HỢP ĐỒNG LAO ĐỘNG\nĐiều 1. Nội dung A."


@pytest.fixture
def use_inmemory_checkpointer(monkeypatch):
    saver = InMemorySaver()
    monkeypatch.setattr(cp, "get_checkpointer", lambda: saver)
    return saver


def _analysis() -> ContractAnalysis:
    return ContractAnalysis(
        contract_id="c-test",
        contract_type="Hợp đồng lao động",
        clauses=[Clause(clause_number="1", title="Nội dung A", summary="Nội dung A")],
    )


def _risk() -> RiskItem:
    return RiskItem(clause_ref="Điều 1", issue="Vấn đề", severity="warning")


@pytest.mark.usefixtures("use_inmemory_checkpointer")
def test_review_mode_pauses_with_draft(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: _risk())

    draft = asyncio.run(
        wf.run_analysis_workflow_review(_CONTRACT_TEXT, "c-test")
    )
    assert draft["contract_id"] == "c-test"
    assert draft["review_id"]
    assert draft["draft_analysis"]["contract_id"] == "c-test"
    assert len(draft["draft_risks"]) == 1
    assert draft["draft_risks"][0]["severity"] == "warning"


@pytest.mark.usefixtures("use_inmemory_checkpointer")
def test_resume_approved_completes_and_persists(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: _risk())

    draft = asyncio.run(wf.run_analysis_workflow_review(_CONTRACT_TEXT, "c-test"))
    result = asyncio.run(
        wf.resume_analysis_review("c-test", draft["review_id"], approved=True)
    )
    assert result["approved"] is True
    assert len(result["risks"]) == 1
    assert result["analysis"].contract_id == "c-test"


@pytest.mark.usefixtures("use_inmemory_checkpointer")
def test_resume_with_edits_replaces_risks(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: _risk())

    draft = asyncio.run(wf.run_analysis_workflow_review(_CONTRACT_TEXT, "c-test"))
    edits = [
        {"clause_ref": "Điều 1", "issue": "Chỉnh sửa thủ công", "severity": "critical"}
    ]
    result = asyncio.run(
        wf.resume_analysis_review("c-test", draft["review_id"], approved=True, edits=edits)
    )
    assert len(result["risks"]) == 1
    assert result["risks"][0].issue == "Chỉnh sửa thủ công"
    assert result["risks"][0].severity == "critical"


@pytest.mark.usefixtures("use_inmemory_checkpointer")
def test_resume_rejected_returns_draft(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: _risk())

    draft = asyncio.run(wf.run_analysis_workflow_review(_CONTRACT_TEXT, "c-test"))
    result = asyncio.run(
        wf.resume_analysis_review("c-test", draft["review_id"], approved=False)
    )
    assert result["approved"] is False
    # Rejection still returns the AI draft (so the caller can show what was declined);
    # it is the use case layer that decides not to persist it as authoritative.
    assert len(result["risks"]) == 1


def test_non_review_mode_skips_gate(monkeypatch):
    # Without review_mode the review node is a pass-through and no checkpointer is needed.
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: _risk())

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert len(analysis.clauses) == 1
    assert len(risks) == 1


@pytest.mark.usefixtures("use_inmemory_checkpointer")
def test_resume_does_not_duplicate_risks_multicause(monkeypatch):
    """Regression for the Phase D nested-subgraph + reducer pitfall: with several
    clauses, resuming after the interrupt must NOT re-apply the operator.add reducer
    (which would duplicate risks). See workflow.py output_schema notes."""
    multi = ContractAnalysis(
        contract_id="c-test",
        contract_type="Hợp đồng lao động",
        clauses=[
            Clause(clause_number=str(i), title=f"Điều {i}", summary=f"Nội dung {i}")
            for i in range(1, 4)
        ],
    )
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: multi)

    def each_clause_risk(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None):
        return RiskItem(clause_ref=f"Điều {clause.clause_number}", issue=f"Rủi ro {clause.clause_number}", severity="warning")

    monkeypatch.setattr(wf, "evaluate_clause", each_clause_risk)

    draft = asyncio.run(wf.run_analysis_workflow_review(_CONTRACT_TEXT, "c-test"))
    assert len(draft["draft_risks"]) == 3

    result = asyncio.run(
        wf.resume_analysis_review("c-test", draft["review_id"], approved=True)
    )
    assert len(result["risks"]) == 3
    assert {r.clause_ref for r in result["risks"]} == {"Điều 1", "Điều 2", "Điều 3"}
