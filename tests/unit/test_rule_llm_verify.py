"""RED_FLAG_LLM_VERIFY: fixed-rule hits become candidates the judge confirms or rejects."""

import asyncio
from types import SimpleNamespace

import pytest

import app.agents.labor_red_flags as red_flags
import app.agents.workflow as wf
from app.schemas.contract import Clause, ContractAnalysis, RiskFinding, RiskItem

pytestmark = pytest.mark.usefixtures("stub_deterministic_checks")

_TEXT = "HỢP ĐỒNG LAO ĐỘNG\nĐiều 1. Kỷ luật.\nĐiều 2. Lương."
_RULE = "Phạt tiền / khấu trừ lương"


def _analysis() -> ContractAnalysis:
    return ContractAnalysis(
        contract_id="c-v",
        contract_type="Hợp đồng lao động",
        clauses=[Clause(clause_number="1", title="Kỷ luật", summary="Kỷ luật"), Clause(clause_number="2", title="Lương", summary="Lương")],
    )


def _rule_risk() -> RiskItem:
    return RiskItem(
        clause_ref="Điều 1", issue="Phạt tiền", severity="critical", title=_RULE,
        findings=[RiskFinding(key="fine_deduct_wage", title=_RULE, severity="critical", reason="Cấm phạt tiền")],
    )


@pytest.fixture
def run(monkeypatch):
    calls = []
    monkeypatch.setattr(wf, "parse_contract", lambda *a: _analysis())
    monkeypatch.setattr(red_flags, "check_labor_red_flags", lambda *a, **k: [_rule_risk()])

    def setup(verify: bool, judge):
        monkeypatch.setattr(wf, "get_settings", lambda: SimpleNamespace(red_flag_llm_verify=verify))

        def fake_eval(clause, provider, **kw):
            calls.append((clause.clause_number, kw.get("rule_hint")))
            return judge(clause, kw.get("rule_hint"))

        monkeypatch.setattr(wf, "evaluate_clause", fake_eval)
        return asyncio.run(wf.run_analysis_workflow(_TEXT, "c-v"))

    return setup, calls


def _by_clause(risks):
    return {r.clause_ref: r for r in risks}


def test_flag_off_rule_clause_skips_judge(run):
    setup, calls = run
    _, risks = setup(False, lambda c, h: None)
    assert [c for c, _ in calls] == ["2"]
    assert _by_clause(risks)["Điều 1"].severity == "critical"


def test_flag_on_judge_rejects_downgrades_to_info(run):
    setup, calls = run
    ok = RiskItem(clause_ref="Điều 1", issue="Câu phủ định: công ty không phạt tiền.", severity="ok")
    analysis, risks = setup(True, lambda c, h: ok if h else None)
    assert ("1", _RULE) in calls and ("2", None) in calls
    r = _by_clause(risks)["Điều 1"]
    assert r.severity == "info" and all(f.severity == "info" for f in r.findings)
    assert "không xác nhận" in r.confidence_notes[-1] and "Câu phủ định" in r.confidence_notes[-1]
    assert analysis.coverage["chua_kiem"] == 0
    assert analysis.coverage["phat_hien"]["so_dieu_co_rui_ro"] == 0


def test_flag_on_judge_confirms_keeps_single_rule_risk(run):
    setup, _ = run
    confirm = RiskItem(clause_ref="Điều 1", issue="Phạt tiền trái luật", severity="warning")
    _, risks = setup(True, lambda c, h: confirm if h else None)
    on_1 = [r for r in risks if r.clause_ref == "Điều 1"]
    assert len(on_1) == 1 and on_1[0].severity == "critical" and on_1[0].findings


def test_flag_on_judge_failure_keeps_rule_risk_and_not_unchecked(run):
    setup, _ = run

    def judge(c, h):
        if h:
            raise RuntimeError("lỗi mạng")
        return None

    analysis, risks = setup(True, judge)
    assert _by_clause(risks)["Điều 1"].severity == "critical"
    assert analysis.coverage["chua_kiem"] == 0
