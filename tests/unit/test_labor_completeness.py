"""Labor contract completeness (Điều 21) + job-context extraction."""

from pathlib import Path

from app.agents.labor_completeness import (
    check_labor_completeness,
    extract_job_context,
    field_is_covered,
    is_labor_contract,
    missing_mandatory_fields,
)
from app.agents.labor_code_resolver import _parse_as_of
from app.schemas.contract import ContractAnalysis

SAMPLE = Path(__file__).resolve().parents[2] / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"


def test_parse_as_of_formats():
    assert _parse_as_of("2026-07-15").isoformat() == "2026-07-15"
    assert _parse_as_of("15/07/2026").isoformat() == "2026-07-15"


def test_sample_is_labor_contract():
    text = SAMPLE.read_text(encoding="utf-8")
    assert is_labor_contract(ContractAnalysis(contract_id="x", contract_type="Hợp đồng lao động"), text)


def test_sample_missing_mandatory_fields():
    text = SAMPLE.read_text(encoding="utf-8")
    missing_keys = {f.key for f in missing_mandatory_fields(text)}
    # Present-ish: employer, employee id core, job, term, hours
    assert "employer_identity" not in missing_keys
    assert "employee_identity" not in missing_keys  # has name + DOB + CCCD
    assert "job_and_workplace" not in missing_keys
    assert "term" not in missing_keys
    # SAI: NLĐ thiếu nơi cư trú / địa chỉ hiện tại
    assert "employee_residence" in missing_keys
    assert "pay_raise" in missing_keys
    assert "ppe" in missing_keys


def test_employee_residence_not_satisfied_by_employer_address():
    """Bare 'Địa chỉ:' của công ty không được tính là nơi cư trú NLĐ."""
    from app.agents.labor_completeness import _MANDATORY

    res = next(f for f in _MANDATORY if f.key == "employee_residence")
    text = (
        "Hợp đồng lao động. Người sử dụng lao động: Công ty A. "
        "Địa chỉ: 1 Nguyễn Huệ, Q1. Người lao động: Nguyễn Văn B. "
        "Ngày sinh: 01/01/1990. Số CCCD: 001."
    )
    assert not field_is_covered(text, res)
    text_ok = text + " Nơi cư trú: 2 Lê Lợi, Q1, TP.HCM."
    assert field_is_covered(text_ok, res)
    text_ok2 = text + " Địa chỉ hiện tại: 3 Hai Bà Trưng, Q1."
    assert field_is_covered(text_ok2, res)


def test_sample_job_context_is_tech_not_oil():
    text = SAMPLE.read_text(encoding="utf-8")
    ctx = extract_job_context(text).lower()
    assert "ai" in ctx or "mlops" in ctx or "công nghệ" in ctx
    assert "dầu khí" not in ctx
    assert "quân đội" not in ctx


def test_completeness_emits_risk_item():
    text = SAMPLE.read_text(encoding="utf-8")
    risks = check_labor_completeness(
        text,
        ContractAnalysis(contract_id="sai", contract_type="Hợp đồng lao động"),
        as_of_date="15/07/2026",
    )
    assert len(risks) == 1
    assert risks[0].severity == "warning"
    assert "Điều 21" in (risks[0].legal_basis or "")
    assert risks[0].reasons
    assert any("cư trú" in r.lower() or "địa chỉ" in r.lower() for r in (risks[0].reasons or []))
    assert "địa chỉ" in (risks[0].title or "").lower() or "cư trú" in (risks[0].title or "").lower()
    assert any("địa chỉ" in t.lower() or "cư trú" in t.lower() for t in (risks[0].summary_topics or []))


def test_wage_requires_payment_form_or_schedule():
    # Salary alone without payment form/schedule → still missing wage bucket's 2nd group
    thin = "Hợp đồng lao động. Mức lương: 10.000.000 đồng."
    from app.agents.labor_completeness import _MANDATORY

    wage = next(f for f in _MANDATORY if f.key == "wage")
    assert not field_is_covered(thin, wage)
