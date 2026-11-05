"""Tests for graph-level retry loops in app/agents/workflow.py.

The analysis graph loops extract/judge back onto themselves on *exception* (transient
network/rate-limit failures that the inline code does not retry). These tests mock
parse_contract / evaluate_clause (looked up at runtime, so monkeypatching works) and
verify retries are bounded and failures degrade gracefully.
"""

import asyncio

import pytest

import app.agents.workflow as wf
from app.agents.risk_flagger import JudgeUnparsable
from app.domain.errors import AnalysisFailedError
from app.schemas.contract import ContractAnalysis, Clause, RiskItem

pytestmark = pytest.mark.usefixtures("stub_deterministic_checks")

_CONTRACT_TEXT = "HỢP ĐỒNG LAO ĐỘNG\nĐiều 1. Nội dung A."


def _analysis() -> ContractAnalysis:
    return ContractAnalysis(
        contract_id="c-test",
        contract_type="Hợp đồng lao động",
        clauses=[Clause(clause_number="1", title="Nội dung A", summary="Nội dung A")],
    )


def _risk() -> RiskItem:
    return RiskItem(clause_ref="Điều 1", issue="Vấn đề", severity="warning")


def test_extract_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky_parse(text, contract_id, provider):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("tạm thời lỗi mạng")
        return _analysis()

    monkeypatch.setattr(wf, "parse_contract", flaky_parse)
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: None)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert calls["n"] == 3
    assert len(analysis.clauses) == 1
    assert risks == []


def test_extract_gives_up_after_budget(monkeypatch):
    calls = {"n": 0}

    def always_fail(text, contract_id, provider):
        calls["n"] += 1
        raise RuntimeError("lỗi dai dẳng")

    monkeypatch.setattr(wf, "parse_contract", always_fail)

    # initial + 2 retries = 3 attempts, then a clear failure (never an empty "clean" analysis).
    with pytest.raises(AnalysisFailedError):
        asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert calls["n"] == 3


def test_judge_retries_then_recovers(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    calls = {"n": 0}

    def flaky_evaluate(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None, job_context=None, skip_topics=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("rate limit")
        return _risk()

    monkeypatch.setattr(wf, "evaluate_clause", flaky_evaluate)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    # 1 clause; initial judge + 2 retries, then success.
    assert calls["n"] == 3
    assert len(risks) == 1
    assert risks[0].severity == "warning"
    assert len(analysis.clauses) == 1


def test_judge_gives_up_marks_clause_unchecked(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())

    def always_fail(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None, job_context=None, skip_topics=None):
        raise RuntimeError("luôn lỗi")

    monkeypatch.setattr(wf, "evaluate_clause", always_fail)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert risks == []
    assert len(analysis.clauses) == 1
    # The clause is reported as NOT checked, never as clean.
    cov = analysis.coverage
    assert (cov["tong_so_dieu"], cov["da_kiem"], cov["chua_kiem"], cov["ty_le_da_kiem"]) == (1, 0, 1, 0.0)
    assert cov["chua_kiem_chi_tiet"] == [{"clause_ref": "Điều 1", "status": "unchecked_error"}]


def test_judge_unparsable_marks_clause_unparsable_without_retry(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    calls = {"n": 0}

    def unparsable(clause, provider, **kwargs):
        calls["n"] += 1
        raise JudgeUnparsable("không có JSON")

    monkeypatch.setattr(wf, "evaluate_clause", unparsable)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert calls["n"] == 1  # the judge already retried its own output
    assert risks == []
    assert analysis.coverage["chua_kiem_chi_tiet"] == [{"clause_ref": "Điều 1", "status": "unparsable"}]


def test_coverage_counts_only_failed_clauses(monkeypatch):
    two = ContractAnalysis(
        contract_id="c-test",
        clauses=[Clause(clause_number=n, title=f"T{n}", summary=f"S{n}") for n in ("1", "2", "3", "4")],
    )
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: two)

    def one_fails(clause, provider, **kwargs):
        if clause.clause_number == "3":
            raise JudgeUnparsable("hỏng")
        return None

    monkeypatch.setattr(wf, "evaluate_clause", one_fails)

    analysis, _ = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert (analysis.coverage["da_kiem"], analysis.coverage["chua_kiem"], analysis.coverage["ty_le_da_kiem"]) == (3, 1, 0.75)


def test_all_clauses_checked_gives_full_coverage(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    monkeypatch.setattr(wf, "evaluate_clause", lambda *a, **k: None)

    analysis, _ = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert analysis.coverage == {
        "tong_so_dieu": 1, "da_kiem": 1, "chua_kiem": 0, "ty_le_da_kiem": 1.0, "chua_kiem_chi_tiet": [],
    }


def test_judge_ok_does_not_retry(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    calls = {"n": 0}

    def ok_evaluate(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None, job_context=None, skip_topics=None):
        calls["n"] += 1
        return None  # no issue -> no risk, no error -> no retry

    monkeypatch.setattr(wf, "evaluate_clause", ok_evaluate)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert calls["n"] == 1
    assert risks == []
