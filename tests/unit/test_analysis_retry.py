"""Tests for graph-level retry loops in app/agents/workflow.py.

The analysis graph loops extract/judge back onto themselves on *exception* (transient
network/rate-limit failures that the inline code does not retry). These tests mock
parse_contract / evaluate_clause (looked up at runtime, so monkeypatching works) and
verify retries are bounded and failures degrade gracefully.
"""

import asyncio

import pytest

import app.agents.workflow as wf
from app.schemas.contract import ContractAnalysis, Clause, RiskItem

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

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    # initial + 2 retries = 3 attempts, then graceful empty analysis.
    assert calls["n"] == 3
    assert len(analysis.clauses) == 0
    assert risks == []


def test_judge_retries_then_recovers(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    calls = {"n": 0}

    def flaky_evaluate(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None):
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


def test_judge_gives_up_and_skips_clause(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())

    def always_fail(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None):
        raise RuntimeError("luôn lỗi")

    monkeypatch.setattr(wf, "evaluate_clause", always_fail)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert risks == []  # clause dropped gracefully, no crash
    assert len(analysis.clauses) == 1


def test_judge_ok_does_not_retry(monkeypatch):
    monkeypatch.setattr(wf, "parse_contract", lambda text, contract_id, provider: _analysis())
    calls = {"n": 0}

    def ok_evaluate(clause, provider, *, contract_id=None, contract_type=None, as_of_date=None):
        calls["n"] += 1
        return None  # no issue -> no risk, no error -> no retry

    monkeypatch.setattr(wf, "evaluate_clause", ok_evaluate)

    analysis, risks = asyncio.run(wf.run_analysis_workflow(_CONTRACT_TEXT, "c-test"))
    assert calls["n"] == 1
    assert risks == []
