"""Project-specific QA cases for the sample employment contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.agents.labor_completeness import assess_mandatory_fields, check_labor_completeness, missing_mandatory_fields
from app.agents.labor_red_flags import check_labor_red_flags
from app.infrastructure.retrieval.query_rewrite import expand_legal_topic_query
from app.schemas.contract import ContractAnalysis


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "demo_contracts" / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"
CASES = json.loads((ROOT / "tests" / "fixtures" / "contract_qa_cases.json").read_text(encoding="utf-8"))


def _sample_risks():
    text = SAMPLE.read_text(encoding="utf-8")
    analysis = ContractAnalysis(contract_id="qa-sample", contract_type="Hợp đồng lao động")
    with patch("app.agents.labor_red_flags.resolve_labor_code_document", return_value=None):
        with patch("app.agents.labor_red_flags.fetch_provision", return_value=None):
            return text, check_labor_red_flags(text, analysis, as_of_date="15/07/2026")


def test_all_contract_risk_questions_have_deterministic_coverage():
    text, risks = _sample_risks()
    risk_by_clause = {risk.clause_ref: risk for risk in risks}
    expected_markers = {
        "ot_unpaid": "làm thêm",
        "no_bhxh": "bhxh",
        "retain_id_papers": "cccd",
        "forfeit_wage_quit": "lương tháng cuối",
        "fine_deduct_wage": "phạt tiền",
        "terminate_pregnancy": "mang thai",
        "ban_lawsuit": "khởi kiện",
    }
    expected_clauses = {
        "ot_unpaid": "Điều 2",
        "no_bhxh": "Điều 3",
        "retain_id_papers": "Điều 3",
        "forfeit_wage_quit": "Điều 3",
        "fine_deduct_wage": "Điều 4",
        "terminate_pregnancy": "Điều 4",
        "ban_lawsuit": "Điều 5",
    }

    for case in CASES:
        for flag in case["expected_red_flags"]:
            risk = risk_by_clause[expected_clauses[flag]]
            blob = " ".join([risk.title or "", *(risk.reasons or []), risk.issue or ""]).lower()
            assert expected_markers[flag] in blob
            assert risk.revised_clause
        if case["expected_red_flags"]:
            assert case["expected_source_clauses"]
            query = expand_legal_topic_query(case["question"]).lower()
            if case["id"] == "pregnancy_termination":
                assert "mang thai" in query
                assert "bộ luật lao động" in query


def test_completeness_question_exposes_expected_missing_fields():
    text = SAMPLE.read_text(encoding="utf-8")
    expected = next(case for case in CASES if case["id"] == "mandatory_contract_contents")
    fields = {field.key for field in missing_mandatory_fields(text)}
    assert set(expected["expected_missing_fields"]).issubset(fields)
    # «Không áp dụng» is its own status, not a gap.
    statuses = {a.field.key: a.status for a in assess_mandatory_fields(text)}
    for key in expected["expected_not_applicable_fields"]:
        assert statuses[key] == "khong_ap_dung" and key not in fields

    risks = check_labor_completeness(
        text,
        ContractAnalysis(contract_id="qa-sample", contract_type="Hợp đồng lao động"),
        as_of_date="15/07/2026",
    )
    assert len(risks) == 1
    assert risks[0].severity == "warning"
    assert "Điều 21" in (risks[0].legal_basis or "")
