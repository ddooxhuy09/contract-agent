"""LLM gap-fill must never discard a successful rule-based extraction."""

import app.agents.clause_parser as cp
from app.schemas.contract import Clause, ContractAnalysis


def _analysis():
    return ContractAnalysis(
        contract_id="c1",
        parties=[],
        clauses=[Clause(clause_number="1", title="Công việc", summary="Nhân viên kinh doanh")],
    )


def _fill(monkeypatch, llm_result):
    monkeypatch.setattr(cp, "_extract_with_llm", lambda *a, **k: llm_result)
    return cp._fill_gaps_with_llm(_analysis(), "văn bản hợp đồng", "c1", "gemini")


def test_nameless_party_is_dropped_not_fatal(monkeypatch):
    # Anonymised contracts make the model answer null for the name it cannot find.
    out = _fill(monkeypatch, {"parties": [
        {"name": None, "role": "Người sử dụng lao động"},
        {"name": "Trần Văn B", "role": "Người lao động"},
    ], "duration": "12 tháng"})
    assert [p.name for p in out.parties] == ["Trần Văn B"]
    assert out.duration == "12 tháng"
    assert len(out.clauses) == 1


def test_all_parties_nameless_keeps_other_gapfill(monkeypatch):
    out = _fill(monkeypatch, {"parties": [{"name": None, "role": None}], "duration": "6 tháng"})
    assert out.parties == []
    assert out.duration == "6 tháng"
    assert len(out.clauses) == 1


def test_schema_rejection_keeps_rule_based_analysis(monkeypatch):
    out = _fill(monkeypatch, {"duration": {"not": "a string"}})
    assert len(out.clauses) == 1
    assert out.duration is None


def test_valid_parties_still_fill(monkeypatch):
    out = _fill(monkeypatch, {"parties": [{"name": "Công ty A", "role": "Bên A"}]})
    assert [p.name for p in out.parties] == ["Công ty A"]
