"""Labor contract completeness (Điều 21) + job-context extraction."""

from pathlib import Path

from app.agents.labor_completeness import (
    check_labor_completeness,
    extract_job_context,
    field_is_covered,
    is_labor_contract,
    missing_mandatory_fields,
)
from app.core.dates import parse_as_of
from app.schemas.contract import ContractAnalysis

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "demo_contracts" / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"


def test_parse_as_of_formats():
    assert parse_as_of("2026-07-15").isoformat() == "2026-07-15"
    assert parse_as_of("15/07/2026").isoformat() == "2026-07-15"


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


class _Docs:
    def __init__(self, row=None, error=None):
        self.row, self.error, self.calls = row, error, []

    def find_labor_code_row(self, as_of, statuses):
        self.calls.append((as_of, statuses))
        if self.error:
            raise self.error
        return self.row


class _Chunks:
    def __init__(self, rows, error=None):
        self.rows, self.error, self.calls = rows, error, []

    def find_article_chunks(self, doc_id, path_regex, limit):
        self.calls.append((doc_id, path_regex, limit))
        if self.error:
            raise self.error
        return self.rows


def test_resolve_labor_code_document_maps_row_and_passes_acceptable_statuses(monkeypatch):
    from datetime import date

    import app.agents.labor_code_resolver as resolver
    import app.infrastructure.retrieval.context as ctx

    row = ("D1", "45/2019/QH14", "Bộ luật Lao động", "Bộ luật", None, "ok", date(2019, 1, 1), None, None, "http://u")
    docs = _Docs(row)
    monkeypatch.setattr(ctx, "get_legal_docs", lambda: docs)
    out = resolver.resolve_labor_code_document("2024-05-01")
    assert out["doc_id"] == "D1" and out["status_flag"] == 0
    assert out["eff_from"] == "2019-01-01" and out["eff_to"] is None
    assert docs.calls == [(date(2024, 5, 1), [1, 5, 4, 0])]


def test_resolve_labor_code_document_returns_none_on_repository_error(monkeypatch):
    import app.agents.labor_code_resolver as resolver
    import app.infrastructure.retrieval.context as ctx

    monkeypatch.setattr(ctx, "get_legal_docs", lambda: _Docs(error=RuntimeError("db down")))
    assert resolver.resolve_labor_code_document("2024-05-01") is None


def test_fetch_article_helpers_use_chunk_repository(monkeypatch):
    import app.agents.labor_code_resolver as resolver
    import app.infrastructure.retrieval.context as ctx

    chunks = _Chunks([("  Nội dung A ", "D1.P.D21"), (None, "x"), ("B", "D1.P.D21.K1")])
    monkeypatch.setattr(ctx, "get_legal_chunks", lambda: chunks)
    assert resolver.fetch_article_meta("D1", 21, limit=4) == {"quote": "Nội dung A\nB", "path": "D1.P.D21"}
    assert chunks.calls[-1] == ("D1", r"\.D21(\.|$)", 4)
    assert resolver.fetch_article_snippet("D1", [21, 5, 0]) == "  Nội dung A \nB"
    assert chunks.calls[-1] == ("D1", r"\.D21(\.|$)|\.D5(\.|$)", 3)
    assert resolver.fetch_article_meta(None, 21) is None


def test_fetch_article_helpers_return_none_without_rows_or_on_error(monkeypatch):
    import app.agents.labor_code_resolver as resolver
    import app.infrastructure.retrieval.context as ctx

    monkeypatch.setattr(ctx, "get_legal_chunks", lambda: _Chunks([]))
    assert resolver.fetch_article_meta("D1", 21) is None
    assert resolver.fetch_article_snippet("D1", [21]) is None
    monkeypatch.setattr(ctx, "get_legal_chunks", lambda: _Chunks([], error=RuntimeError("db down")))
    assert resolver.fetch_article_meta("D1", 21) is None
    assert resolver.fetch_article_snippet("D1", [21]) is None
