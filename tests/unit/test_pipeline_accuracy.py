"""Regression tests for the accuracy review of contractlens-f87af2fa (hợp đồng «_SAI»).

One section per finding: Điều 21 checklist, structured extraction, legal-date basis,
coverage vs detection, provision lookup. Red-flag / citation / rewrite tests live in
test_labor_red_flags.py and test_risk_flagger.py.
"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

import app.agents.clause_parser as cp
import app.agents.labor_code_resolver as resolver
import app.agents.workflow as wf
import app.infrastructure.retrieval.context as ctx
from app.agents.clause_text import sentences_matching, split_segments, strip_signature_block
from app.agents.effectivity import legal_timeline, stamp_legal_basis
from app.agents.labor_completeness import (
    CHUA_DAY_DU,
    CO,
    KHONG_AP_DUNG,
    THIEU,
    assess_mandatory_fields,
    check_labor_completeness,
    required_content_table,
)
from app.agents.legal_citations import (
    build_provision,
    citation_issues,
    evidence_confidence,
    trim_to_provision,
)
from app.core.dates import parse_as_of, parse_vn_date
from app.schemas.contract import Clause, ContractAnalysis, LegalCitation, RiskFinding, RiskItem

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "demo_contracts" / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"
TEXT = SAMPLE.read_text(encoding="utf-8")


# ---- 5. Điều 21 checklist: có / chưa đầy đủ / thiếu / không áp dụng ------------------------------


def _status(text=TEXT):
    return {a.field.key: a for a in assess_mandatory_fields(text)}


def test_checklist_distinguishes_present_partial_missing_and_not_applicable():
    s = _status()
    assert s["employer_identity"].status == CO and s["term"].status == CO
    assert s["employee_residence"].status == THIEU and s["pay_raise"].status == THIEU
    assert s["employee_identity"].status == CHUA_DAY_DU and s["employee_identity"].missing == ("Giới tính",)
    assert s["job_and_workplace"].status == CHUA_DAY_DU
    assert s["job_and_workplace"].missing == ("Địa điểm làm việc cụ thể",)  # «Đơn vị làm việc: Phòng …» ≠ địa điểm
    assert s["ppe"].status == KHONG_AP_DUNG  # AI research job, no hazard wording


def test_salary_that_is_present_is_not_reported_as_missing():
    wage = _status()["wage"]
    assert wage.status == CHUA_DAY_DU  # not THIEU: the amount 8.500.000 VNĐ/tháng is there
    assert wage.found == ("Mức lương",)
    assert "Hình thức trả lương" in wage.missing and "Thời hạn trả lương" in wage.missing
    assert _status("Hợp đồng lao động. Trả lương bằng chuyển khoản vào ngày 5 hàng tháng.")["wage"].found != ()


def test_rest_time_is_not_satisfied_by_the_overtime_sentence():
    # «ngày nghỉ cuối tuần» only appears while forcing overtime — not a rest-time regime.
    hours = _status()["working_hours_rest"]
    assert hours.status == CHUA_DAY_DU and hours.missing == ("Thời giờ nghỉ ngơi",)
    assert _status(TEXT + " NLĐ được nghỉ hằng tuần 01 ngày và nghỉ phép năm.")["working_hours_rest"].status == CO


def test_training_cost_clause_is_not_a_training_regime():
    assert _status()["training"].status == THIEU  # text only talks about «chi phí đào tạo» as a penalty


def test_insurance_mentioned_only_to_exclude_it_is_not_present():
    ins = _status()["social_insurance"]
    assert ins.status == THIEU and "không tham gia" in ins.missing[0]


def test_ppe_is_required_for_hazardous_work():
    hazard = TEXT + " Công việc vận hành máy trong xưởng, môi trường độc hại."
    assert _status(hazard)["ppe"].status == THIEU


def test_checklist_table_and_risk_item_carry_the_statuses():
    table = {r["key"]: r for r in required_content_table(assess_mandatory_fields(TEXT))}
    assert table["wage"]["trang_thai"] == CHUA_DAY_DU and table["wage"]["can_cu"] == "Điều 21 khoản 1 điểm đ"
    assert table["ppe"]["trang_thai"] == KHONG_AP_DUNG and table["ppe"]["ghi_chu"]
    with patch("app.agents.labor_completeness.resolve_labor_code_document", return_value=None):
        item = check_labor_completeness(TEXT, ContractAnalysis(contract_id="x", contract_type="Hợp đồng lao động"))[0]
    joined = " ".join(item.reasons)
    assert "[Chưa đầy đủ] Mức lương" in joined and "Giới tính" in joined and "Địa điểm làm việc cụ thể" in joined
    assert "[Thiếu hoàn toàn] Nơi cư trú" in joined
    assert "Trang bị bảo hộ" not in joined  # not applicable → not a gap
    assert "[Không áp dụng" in item.recommendation
    assert item.confidence <= 0.55  # corpus unreachable → unverified


# ---- 7. structured extraction ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def parsed():
    with patch.object(cp, "_extract_with_llm", return_value=None):
        return cp.parse_contract(TEXT, "x")


def test_dates_and_duration_are_extracted(parsed):
    assert (parsed.execution_date, parsed.start_date, parsed.end_date) == ("15 tháng 07 năm 2026", "01/08/2026", "31/01/2027")
    assert parsed.duration == "6 tháng"  # was null although both dates exist
    assert parsed.contract_type == "Hợp đồng LAO ĐỘNG"


def test_text_fields_hold_only_their_own_sentence(parsed):
    assert parsed.confidentiality == "(i) Giữ bí mật tuyệt đối các thông tin mô hình học máy."
    assert parsed.indemnity.startswith("(iii) Trường hợp NLĐ đơn phương chấm dứt") and "Căn cước" not in parsed.indemnity
    assert "kết hôn" in parsed.termination_clause and "phạt tiền" not in parsed.termination_clause
    assert parsed.penalty_clause.startswith("Nếu NLĐ đi làm muộn") and "kết hôn" not in parsed.penalty_clause
    assert parsed.payment_terms is None  # the contract has none; insurance support is not one


def test_personal_id_is_never_a_tax_id():
    parties = cp._fix_party_ids([
        {"name": "Ông Trần Minh Nhật", "role": "Người lao động", "tax_id": "079099123456"},
        {"name": "CÔNG TY CỔ PHẦN X", "role": "Người sử dụng lao động", "tax_id": "0312345678"},
    ])
    assert (parties[0]["tax_id"], parties[0]["id_number"]) == (None, "079099123456")
    assert (parties[1]["tax_id"], parties[1].get("id_number")) == ("0312345678", None)
    employee = cp._extract_parties("BÊN B: Người lao động\nHọ và tên: Trần B | Sinh ngày: 01/01/2000\nCCCD số: 079099123456\n")
    assert employee and employee[0].tax_id is None and employee[0].id_number == "079099123456"


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("payment_terms", "Công ty sẽ hỗ trợ 5% mức lương cơ bản, cộng vào tiền lương hàng tháng của NLĐ.", None),
        ("payment_terms", "Trả lương vào ngày 5 hàng tháng. Công ty hỗ trợ bảo hiểm 5%.", "Trả lương vào ngày 5 hàng tháng."),
        ("confidentiality", "Điều 3. (ii) Bảo hiểm 5%. (i) Giữ bí mật mô hình. (iii) Bồi thường 3 tháng lương.", "(i) Giữ bí mật mô hình."),
        ("indemnity", "Không có nội dung liên quan.", None),
    ],
)
def test_llm_filled_fields_are_cut_back_to_their_topic(field, value, expected):
    assert cp._clean_llm_field(field, value, TEXT) == expected


def test_segments_split_on_sentences_and_list_markers_but_not_numbers():
    segs = [s for s, _ in split_segments("3.1. Quyền lợi (i) Mức lương: 8.500.000 VNĐ/tháng. Thay vào đó, hỗ trợ 5%. (ii) Khác.")]
    assert segs == ["3.1. Quyền lợi", "(i) Mức lương: 8.500.000 VNĐ/tháng.", "Thay vào đó, hỗ trợ 5%.", "(ii) Khác."]
    assert sentences_matching("A bí mật. B khác.", r"bí\s*mật") == ["A bí mật."]
    assert strip_signature_block("5.2. Có hiệu lực. **NGƯỜI LAO ĐỘNG** _(Ký tên)_") == "5.2. Có hiệu lực."


# ---- 9. legal date basis --------------------------------------------------------------------------


def test_vietnamese_written_dates_are_read_not_replaced_by_today():
    assert parse_vn_date("15 tháng 07 năm 2026") == date(2026, 7, 15)
    assert parse_as_of("15 tháng 07 năm 2026") == date(2026, 7, 15)  # used to fall back to date.today()
    assert parse_as_of("2026-07-15T10:00:00") == date(2026, 7, 15)
    assert parse_vn_date("không có ngày") is None


def test_timeline_states_signing_date_vs_report_date():
    with patch("app.agents.labor_code_resolver.resolve_labor_code_document", return_value=None):
        t = legal_timeline("15 tháng 07 năm 2026", "01/08/2026", "31/01/2027", today=date(2026, 11, 8))
    assert (t["co_so"], t["ngay_doi_chieu"], t["ngay_phan_tich"]) == ("ngay_ky", "2026-07-15", "2026-11-08")
    assert "ngày ký" in t["ghi_chu"] and "2026-11-08" in t["ghi_chu"]
    with patch("app.agents.labor_code_resolver.resolve_labor_code_document", return_value=None):
        assert legal_timeline(None, "01/08/2026", today=date(2026, 11, 8))["co_so"] == "ngay_bat_dau"
        assert legal_timeline(None, None, today=date(2026, 11, 8))["co_so"] == "hom_nay"


def test_timeline_reports_when_the_law_changed_after_signing():
    def fake(as_of):
        return {"doc_id": "A" if as_of < date(2026, 9, 1) else "B", "doc_num": "45/2019/QH14", "status_flag": 4}

    with patch("app.agents.labor_code_resolver.resolve_labor_code_document", side_effect=fake):
        t = legal_timeline("15/07/2026", None, today=date(2026, 11, 8))
        same = legal_timeline("15/07/2026", None, today=date(2026, 8, 1))
    assert "đã thay đổi" in t["thay_doi_sau_ky"] and "rà soát lại" in t["thay_doi_sau_ky"]
    assert "giữ nguyên" in same["thay_doi_sau_ky"]


def test_citation_status_names_the_date_it_was_checked_at():
    cite = LegalCitation(title="Điều 98", status="Đã đối chiếu · Còn hiệu lực (có sửa đổi) · 2026-07-15")
    item = RiskItem(
        clause_ref="Điều 2", issue="x", severity="critical", legal_basis="BLLĐ — Đã đối chiếu · 2026-07-15",
        legal_citations=[cite],
        findings=[RiskFinding(key="k", title="t", severity="critical", reason="r", legal_citations=[cite])],
    )
    t = {"ngay_doi_chieu": "2026-07-15", "co_so": "ngay_ky"}
    out = stamp_legal_basis([item], t)[0]
    assert out.legal_citations[0].status.endswith("· tại ngày ký 2026-07-15")
    assert out.findings[0].legal_citations[0].status.endswith("· tại ngày ký 2026-07-15")
    assert "tại ngày ký" in out.legal_basis
    assert stamp_legal_basis([out], t)[0].legal_basis == out.legal_basis  # idempotent


# ---- 8. coverage ≠ detection quality --------------------------------------------------------------


def test_coverage_reports_detection_separately_from_clause_scan():
    analysis = ContractAnalysis(
        contract_id="c", contract_type="Hợp đồng lao động",
        clauses=[Clause(clause_number=str(i), summary="s") for i in range(1, 6)],
    )
    risks = [
        RiskItem(clause_ref="Điều 3", issue="x", severity="critical", confidence=0.9),
        RiskItem(clause_ref="Điều 4", issue="y", severity="warning", confidence=0.45),
        RiskItem(clause_ref="Hợp đồng (toàn văn)", issue="z", severity="warning", confidence=0.8),
    ]
    cov = wf._with_coverage(analysis, [], risks, ["3"]).coverage
    assert cov["ty_le_da_kiem"] == 1.0  # every Điều was scanned …
    assert "không đo" in cov["pham_vi"]  # … which says nothing about what was found
    d = cov["phat_hien"]
    assert (d["so_rui_ro"], d["so_dieu_co_rui_ro"]) == (3, 2)
    assert d["dieu_chua_phat_hien_rui_ro"] == ["1", "2", "5"] and d["dieu_chi_kiem_bang_quy_tac"] == ["3"]
    assert d["so_rui_ro_do_tin_cay_thap"] == 1 and d["do_tin_cay_trung_binh"] == 0.72
    assert "không phải đã chứng minh hợp lệ" in d["luu_y"]


def test_finalize_adds_timeline_and_checklist_and_stamps_statuses():
    analysis = ContractAnalysis(
        contract_id="c", contract_type="Hợp đồng lao động", execution_date="15 tháng 07 năm 2026",
        clauses=[Clause(clause_number="1", summary="s")],
    )
    cite = LegalCitation(title="t", status="Còn hiệu lực · 2026-07-15")
    risk = RiskItem(clause_ref="Điều 1", issue="x", severity="warning", legal_citations=[cite])
    with patch("app.agents.labor_code_resolver.resolve_labor_code_document", return_value=None):
        out, risks = wf._finalize(analysis, [], [risk], TEXT, [])
    assert out.legal_as_of["ngay_doi_chieu"] == "2026-07-15" and out.legal_as_of["co_so"] == "ngay_ky"
    assert {r["key"] for r in out.required_content} >= {"wage", "ppe"}
    assert risks[0].legal_citations[0].status.endswith("tại ngày ký 2026-07-15")
    assert wf._as_of_date(analysis) == "2026-07-15"


# ---- 2/3. provision lookup ------------------------------------------------------------------------


class _Chunks:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def find_article_chunks(self, doc_id, path_regex, limit):
        self.calls.append((doc_id, path_regex, limit))
        return self.rows


def test_fetch_provision_asks_for_the_exact_khoan_and_trims_the_chunk(monkeypatch):
    chunk = "Điều 137. Bảo vệ thai sản\n3. Không được sa thải vì mang thai.\n\n4. Lao động nữ hành kinh nghỉ 30 phút.\n\n## **Điều 138. Khác**"
    chunks = _Chunks([(chunk, "139264.C10.D137.K3")])
    monkeypatch.setattr(ctx, "get_legal_chunks", lambda: chunks)
    got = resolver.fetch_provision("139264", 137, 3)
    assert chunks.calls[-1] == ("139264", r"\.D137\.K3(\.|$)", 12)
    assert got == {"quote": "Điều 137. Bảo vệ thai sản\n3. Không được sa thải vì mang thai.", "path": "139264.C10.D137.K3"}
    resolver.fetch_provision("139264", 21, 1, "dd")
    assert chunks.calls[-1][1] == r"\.D21\.K1\.dd$"
    assert resolver.fetch_provision(None, 21, 1) is None


def test_provision_merges_diem_chunks_once_and_cites_the_khoan_level():
    rows = [
        ("Điều 98. Tiền lương\n1. Làm thêm giờ được trả lương:\na) Ngày thường 150%;\n2. Ban đêm 30%.", "1.C6.D98.K1.a"),
        ("Điều 98. Tiền lương\n1. Làm thêm giờ được trả lương:\nb) Ngày nghỉ 200%;\n2. Ban đêm 30%.", "1.C6.D98.K1.b"),
    ]
    got = build_provision(rows, 1)
    assert got["path"] == "1.C6.D98.K1"
    assert got["quote"].count("Điều 98.") == 1 and got["quote"].count("1. Làm thêm giờ") == 1
    assert "150%" in got["quote"] and "200%" in got["quote"] and "Ban đêm" not in got["quote"]
    assert trim_to_provision("x" * 5000, None, max_chars=100).endswith("…")


def test_citation_consistency_checks():
    ok = LegalCitation(
        title="t", article="Điều 98", clause="Khoản 1", location="Chương 6 > Điều 98 > Khoản 1",
        evidence_path="139264.C6.D98.K1", quote="Điều 98. Tiền lương\n1. Làm thêm giờ",
    )
    assert citation_issues(ok) == []
    assert any("khoản" in i.lower() for i in citation_issues(ok.model_copy(update={"clause": "Khoản 2"})))
    assert any("khác" in i for i in citation_issues(ok.model_copy(update={"quote": "Điều 99. Khác\n1. x"})))
    assert any("khoản 1" in i.lower() for i in citation_issues(ok.model_copy(update={"quote": "Điều 98. T\n2. Ban đêm"})))
    stitched = ok.model_copy(update={"quote": "Điều 98. A\n1. x\nĐiều 98. A\n1. x"})
    assert any("ghép" in i for i in citation_issues(stitched))
    assert any("evidence_path" in i for i in citation_issues(LegalCitation(title="t")))


def test_evidence_confidence_caps_and_explains():
    ok = LegalCitation(title="t", article="Điều 98", clause="Khoản 1", evidence_path="1.C6.D98.K1", quote="Điều 98. T\n1. x")
    assert evidence_confidence([ok], 0.9) == (0.9, [])
    assert evidence_confidence([], 0.9)[0] == 0.45
    conf, notes = evidence_confidence([ok.model_copy(update={"clause": "Khoản 2"}), LegalCitation(title="u")], 0.9)
    assert conf == pytest.approx(0.7) and len(notes) == 2


# ---- report shows the basis, the scope of coverage and the checklist ---------------------------------


def test_markdown_report_explains_basis_coverage_and_checklist():
    from app.application.use_cases.report import render_markdown

    analysis = ContractAnalysis(
        contract_id="c", contract_type="Hợp đồng lao động", execution_date="15/07/2026",
        clauses=[Clause(clause_number="1", summary="s")],
    )
    with patch("app.agents.labor_code_resolver.resolve_labor_code_document", return_value=None):
        analysis, risks = wf._finalize(analysis, [], [RiskItem(clause_ref="Điều 1", issue="x", severity="warning", confidence=0.6)], TEXT, [])
    report = {
        "contract": {"filename": "f", "contract_id": "c", "uploaded_at": None},
        "summary": {"clause_count": 1, "clauses_checked": 1, "clauses_unchecked": 0,
                    "findings_by_severity": {"critical": 0, "warning": 1, "ok": 0}},
        "generated_at": "2026-11-08T00:00:00+00:00", "analysis": analysis.model_dump(),
        "risks": [r.model_dump() for r in risks], "usage": None, "disclaimer": "d",
    }
    md = render_markdown(report)
    assert "Cơ sở đối chiếu pháp luật" in md and "ngày ký (2026-07-15)" in md
    assert "không đo độ đầy đủ" in md and "Nội dung bắt buộc (Điều 21 BLLĐ)" in md
    assert "| Chưa đầy đủ |" in md and "| Không áp dụng |" in md
    assert "Độ tin cậy:** 0.60" in md
