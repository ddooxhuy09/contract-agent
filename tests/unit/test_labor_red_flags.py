"""Deterministic labor red-flags: merge-by-clause + revised_clause."""

from pathlib import Path
from unittest.mock import patch

from app.agents.labor_red_flags import (
    check_labor_red_flags,
    clause_number_from_ref,
    extract_clause_excerpt,
    revise_clause_text,
    skip_llm_clause_numbers,
)
from app.schemas.contract import ContractAnalysis, RiskItem

SAMPLE = Path(__file__).resolve().parents[2] / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"


def _run(text: str):
    with patch("app.agents.labor_red_flags.resolve_labor_code_document", return_value=None):
        with patch("app.agents.labor_red_flags.fetch_article_meta", return_value=None):
            return check_labor_red_flags(
                text,
                ContractAnalysis(contract_id="sai", contract_type="Hợp đồng lao động"),
                as_of_date="15/07/2026",
            )


def test_sai_merges_by_contract_dieu():
    text = SAMPLE.read_text(encoding="utf-8")
    risks = _run(text)
    refs = {r.clause_ref for r in risks}
    assert refs == {"Điều 2", "Điều 3", "Điều 4", "Điều 5"}
    assert all(r.severity == "critical" for r in risks)
    assert all(r.revised_clause for r in risks)

    d3 = next(r for r in risks if r.clause_ref == "Điều 3")
    blob = " ".join(d3.reasons or []).lower()
    assert "bhxh" in (d3.title or "").lower() or "bhxh" in blob
    assert "cccd" in (d3.title or "").lower() or "cccd" in blob or "giấy tờ" in blob
    assert "vấn đề tại" not in (d3.title or "").lower()
    assert d3.summary_topics and len(d3.summary_topics) >= 2


def test_sai_skip_llm_clauses_covers_hard_articles():
    text = SAMPLE.read_text(encoding="utf-8")
    risks = _run(text)
    skip = skip_llm_clause_numbers(risks)
    assert set(skip) >= {"2", "3", "4", "5"}
    assert len(risks) == len({r.clause_ref for r in risks})


def test_hydrate_uses_law_blurb_when_meta_missing():
    text = SAMPLE.read_text(encoding="utf-8")
    risks = _run(text)
    d3 = next(r for r in risks if r.clause_ref == "Điều 3")
    cite = next(
        (c for c in d3.legal_citations if c.article and "17" in (c.article or "")),
        d3.legal_citations[0],
    )
    assert cite.quote and len(cite.quote) > 60
    assert "giấy tờ" in cite.quote.lower() or "bản chính" in cite.quote.lower() or "điều 17" in cite.quote.lower()
    # No duplicate summary when quote is the blurb fallback
    assert not cite.summary or cite.summary != cite.quote
    assert cite.status is None or "đối chiếu" in cite.status.lower() or "còn hiệu lực" in cite.status.lower() or "chưa" in cite.status.lower()


def test_hydrate_sets_quote_when_meta_present():
    text = SAMPLE.read_text(encoding="utf-8")
    labor = {
        "doc_id": "139264",
        "doc_num": "45/2019/QH14",
        "title": "Bộ luật Lao động",
        "status_flag": 4,
        "eff_flag": "Hết hiệu lực một phần",
        "source_url": "https://vbpl.vn/x",
    }
    meta = {
        "quote": "Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động…",
        "path": "45_2019_QH14.C12.D127",
    }
    with patch("app.agents.labor_red_flags.resolve_labor_code_document", return_value=labor):
        with patch("app.agents.labor_red_flags.fetch_article_meta", return_value=meta):
            risks = check_labor_red_flags(
                text,
                ContractAnalysis(contract_id="sai", contract_type="Hợp đồng lao động"),
            )
    d4 = next(r for r in risks if r.clause_ref == "Điều 4")
    assert any("127" in (c.quote or "") for c in d4.legal_citations)
    assert all(
        (c.status or "").startswith("Đã đối chiếu") or "Còn hiệu lực" in (c.status or "")
        for c in d4.legal_citations
    )
    assert d4.original_clause and "phạt tiền" in d4.original_clause.lower()
    assert d4.revised_clause
    assert "500.000" not in d4.revised_clause
    assert "khấu trừ trực tiếp" not in d4.revised_clause.lower()
    assert "mang thai" not in d4.revised_clause.lower() or "không đơn phương" in d4.revised_clause.lower()


def test_revise_clause_text_ot():
    original = (
        "Điều 2: NLĐ có trách nhiệm làm thêm giờ bất cứ khi nào quản lý yêu cầu "
        "và sẽ không được tính thêm tiền lương làm thêm giờ."
    )
    revised = revise_clause_text(original, ["ot_unpaid"])
    assert revised
    assert "không được tính thêm tiền lương làm thêm giờ" not in revised.lower()
    assert "trả lương" in revised.lower() or "hệ số" in revised.lower()


def test_extract_clause_excerpt_dieu_2():
    text = SAMPLE.read_text(encoding="utf-8")
    excerpt = extract_clause_excerpt(text, 2)
    assert excerpt
    assert "làm thêm" in excerpt.lower()


def test_clause_number_from_ref():
    assert clause_number_from_ref("Điều 4") == "4"
    assert clause_number_from_ref("Dieu 12") == "12"


def test_skip_llm_only_critical():
    risks = [
        RiskItem(clause_ref="Điều 1", issue="x", severity="warning", title="a"),
        RiskItem(clause_ref="Điều 2", issue="y", severity="critical", title="b"),
    ]
    assert skip_llm_clause_numbers(risks) == ["2"]
