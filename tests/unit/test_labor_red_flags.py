"""Deterministic labor red-flags: exact provision citations, per-violation findings, safe rewrites."""

import re
from pathlib import Path
from unittest.mock import patch

import pytest

import app.infrastructure.retrieval.context as ctx
from app.agents.labor_red_flags import (
    _FLAGS,
    check_labor_red_flags,
    clause_number_from_ref,
    extract_clause_excerpt,
    revise_clause_text,
    revised_clause_problems,
    skip_llm_clause_numbers,
)
from app.agents.legal_citations import citation_issues
from app.schemas.contract import ContractAnalysis, RiskItem

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "demo_contracts" / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"
LABOR = {
    "doc_id": "139264", "doc_num": "45/2019/QH14", "title": "Bộ luật Lao động", "status_flag": 4,
    "eff_flag": "Hết hiệu lực một phần", "source_url": "https://vbpl.vn/x",
}

# Same shape as legal_embeddings: a chunk per khoản/điểm; text runs on into the next khoản / Điều.
H = {
    98: "Điều 98. Tiền lương làm thêm giờ, làm việc vào ban đêm",
    107: "Điều 107. Làm thêm giờ",
    168: "Điều 168. Tham gia bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp",
    17: "Điều 17. Hành vi người sử dụng lao động không được làm khi giao kết, thực hiện hợp đồng lao động",
    94: "Điều 94. Nguyên tắc trả lương",
    40: "Điều 40. Nghĩa vụ của người lao động khi đơn phương chấm dứt hợp đồng lao động trái pháp luật",
    62: "Điều 62. Hợp đồng đào tạo nghề giữa người sử dụng lao động, người lao động và chi phí đào tạo nghề",
    127: "Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động",
    102: "Điều 102. Khấu trừ tiền lương",
    137: "Điều 137. Bảo vệ thai sản",
    8: "Điều 8. Các hành vi bị nghiêm cấm trong lĩnh vực lao động",
    179: "Điều 179. Tranh chấp lao động",
    187: "Điều 187. Thẩm quyền giải quyết tranh chấp lao động cá nhân",
}
CORPUS = [
    ("139264.C6.D98.K1.a", f"{H[98]}\n1. Người lao động làm thêm giờ được trả lương như sau:\na) Vào ngày thường, ít nhất bằng 150%;"),
    ("139264.C6.D98.K1.b", f"{H[98]}\n1. Người lao động làm thêm giờ được trả lương như sau:\nb) Vào ngày nghỉ hằng tuần, ít nhất bằng 200%;"),
    ("139264.C6.D98.K2", f"{H[98]}\n2. Người lao động làm việc vào ban đêm thì được trả thêm ít nhất 30%.\n\n## **Điều 99. Tiền lương ngừng việc**"),
    ("139264.C7.M1.D107.K2.a", f"{H[107]}\n2. Người sử dụng lao động được sử dụng người lao động làm thêm giờ khi:\na) Phải được sự đồng ý của người lao động;"),
    ("139264.C12.D168.K1", f"{H[168]}\n1. Người sử dụng lao động, người lao động phải tham gia bảo hiểm xã hội bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp.\n2. Chính phủ quy định chi tiết."),
    ("139264.C3.M1.D17.K1", f"{H[17]}\n1. Giữ bản chính giấy tờ tùy thân, văn bằng, chứng chỉ của người lao động.\n2. Yêu cầu người lao động phải thực hiện biện pháp bảo đảm bằng tiền."),
    ("139264.C6.D94.K1", f"{H[94]}\n1. Người sử dụng lao động phải trả lương trực tiếp, đầy đủ, đúng hạn cho người lao động."),
    ("139264.C3.M3.D40.K2", f"{H[40]}\n2. Phải bồi thường nửa tháng tiền lương theo hợp đồng lao động và tiền lương những ngày không báo trước.\n3. Phải hoàn trả chi phí đào tạo."),
    ("139264.C3.M3.D40.K3", f"{H[40]}\n3. Phải hoàn trả cho người sử dụng lao động chi phí đào tạo quy định tại Điều 62.\n\n## **Điều 41. Nghĩa vụ của người sử dụng lao động**"),
    ("139264.C4.D62.K1", f"{H[62]}\n1. Hai bên phải ký kết hợp đồng đào tạo nghề trong trường hợp người lao động được đào tạo nâng cao trình độ."),
    ("139264.C4.D62.K3", f"{H[62]}\n3. Chi phí đào tạo bao gồm các khoản chi có chứng từ hợp lệ về chi phí trả cho người dạy."),
    ("139264.C8.M1.D127.K1", f"{H[127]}\n1. Xâm phạm sức khỏe, danh dự.\n2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động."),
    ("139264.C8.M1.D127.K2", f"{H[127]}\n2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động.\n3. Xử lý kỷ luật đối với người đang nghỉ."),
    ("139264.C6.D102.K1", f"{H[102]}\n1. Người sử dụng lao động chỉ được khấu trừ tiền lương để bồi thường thiệt hại theo Điều 129.\n2. Người lao động có quyền biết lý do."),
    ("139264.C10.D137.K2", f"{H[137]}\n2. Lao động nữ làm nghề nặng nhọc, độc hại được chuyển công việc.\n3. Không được sa thải."),
    ("139264.C10.D137.K3", f"{H[137]}\n3. Người sử dụng lao động không được sa thải hoặc đơn phương chấm dứt hợp đồng lao động vì lý do kết hôn, mang thai, nghỉ thai sản.\n\n4. Lao động nữ trong thời gian hành kinh được nghỉ 30 phút."),
    ("139264.C1.D8.K1", f"{H[8]}\n1. Phân biệt đối xử trong lao động.\n2. Ngược đãi người lao động."),
    ("139264.C14.M1.D179.K1.a", f"{H[179]}\n1. Tranh chấp lao động là tranh chấp về quyền và nghĩa vụ phát sinh giữa các bên.\n2. Tranh chấp tập thể."),
    ("139264.C14.M2.D187.K3", f"{H[187]}\n3. Tòa án nhân dân.\n\n## **Điều 188. Trình tự**"),
]


class _FakeChunks:
    def find_article_chunks(self, doc_id, path_regex, limit):
        rows = [(text, path) for path, text in CORPUS if re.search(path_regex, path)]
        rows.sort(key=lambda r: (r[1].count("."), r[1]))  # same order as the SQL: nlevel ASC, path
        return rows[:limit]


def _analysis():
    return ContractAnalysis(contract_id="sai", contract_type="Hợp đồng lao động")


@pytest.fixture
def risks():
    """Sample contract checked against a fake corpus shaped like the real one."""
    with patch("app.agents.labor_red_flags.resolve_labor_code_document", return_value=LABOR), patch.object(
        ctx, "get_legal_chunks", lambda: _FakeChunks()
    ):
        return check_labor_red_flags(SAMPLE.read_text(encoding="utf-8"), _analysis(), as_of_date="15/07/2026")


def _by(risks, ref):
    return next(r for r in risks if r.clause_ref == ref)


def _run_without_corpus(text: str):
    with patch("app.agents.labor_red_flags.resolve_labor_code_document", return_value=None):
        return check_labor_red_flags(text, _analysis(), as_of_date="15/07/2026")


# ---- detection & merge ------------------------------------------------------------------------


def test_sai_merges_by_contract_dieu(risks):
    assert {r.clause_ref for r in risks} == {"Điều 2", "Điều 3", "Điều 4", "Điều 5"}
    assert all(r.severity == "critical" and r.revised_clause for r in risks)
    d3 = _by(risks, "Điều 3")
    assert "bhxh" in d3.title.lower() and "cccd" in d3.title.lower()
    assert d3.summary_topics and len(d3.summary_topics) >= 2


def test_sai_skip_llm_clauses_covers_hard_articles(risks):
    assert set(skip_llm_clause_numbers(risks)) >= {"2", "3", "4", "5"}
    assert len(risks) == len({r.clause_ref for r in risks})


def test_each_violation_is_its_own_finding_with_its_own_sentence(risks):
    keys = {f.key: f for f in _by(risks, "Điều 3").findings}
    assert set(keys) == {"no_bhxh", "retain_id_papers", "forfeit_wage_quit", "training_cost_flat"}
    assert "bàn giao bản gốc" in keys["retain_id_papers"].violated_text
    # Compensation for training cost is analysed separately from the last-month wage forfeiture,
    # against its own provisions (Điều 62 / Điều 40 khoản 3), not folded into one generic warning.
    training = keys["training_cost_flat"]
    assert "3 tháng tiền lương" in training.violated_text
    assert {c.article for c in training.legal_citations} == {"Điều 62", "Điều 40"}
    assert {c.article for c in keys["forfeit_wage_quit"].legal_citations} == {"Điều 94", "Điều 40"}


def test_violation_is_located_from_the_text_not_the_hint():
    text = (
        "Hợp đồng lao động\n\nĐiều 1: Công việc\nLập trình.\n\n"
        "Điều 7: Khác\nNLĐ không những không được nhận lương của tháng cuối cùng khi nghỉ."
    )
    assert [r.clause_ref for r in _run_without_corpus(text)] == ["Điều 7"]  # hint says Điều 3


# ---- citations: exact điều / khoản, no noise -------------------------------------------------


@pytest.mark.parametrize(
    "ref, article, clause",
    [
        ("Điều 2", "Điều 98", "Khoản 1"),  # was Khoản 2 (night work)
        ("Điều 4", "Điều 127", "Khoản 2"),  # was Khoản 1
        ("Điều 4", "Điều 137", "Khoản 3"),  # was Khoản 2
    ],
)
def test_citation_points_to_the_right_khoan(risks, ref, article, clause):
    cite = next(c for c in _by(risks, ref).legal_citations if c.article == article)
    assert cite.clause == clause
    assert cite.evidence_path.endswith(f".K{clause.split()[1]}")
    assert cite.location.endswith(f"{article} > {clause}")


def test_every_citation_is_internally_consistent(risks):
    for r in risks:
        for c in r.legal_citations:
            assert citation_issues(c) == [], (c.title, citation_issues(c))


def test_quote_is_the_cited_khoan_only(risks):
    d2 = next(c for c in _by(risks, "Điều 2").legal_citations if c.article == "Điều 98")
    assert "150%" in d2.quote and "200%" in d2.quote  # both điểm of khoản 1, merged once
    assert "ban đêm thì" not in d2.quote  # khoản 2 is another provision
    assert "Điều 99" not in d2.quote  # corpus chunk runs into the next Điều heading
    d4 = next(c for c in _by(risks, "Điều 4").legal_citations if c.article == "Điều 137")
    assert "kết hôn" in d4.quote and "hành kinh" not in d4.quote  # khoản 4 trimmed off
    for r in risks:
        for c in r.legal_citations:
            assert len(re.findall(r"^Điều \d+\.", c.quote, re.M)) == 1  # one heading, never repeated / stitched


def test_cited_text_supports_the_finding(risks):
    d4 = _by(risks, "Điều 4")
    assert "phạt tiền" in next(c for c in d4.legal_citations if c.article == "Điều 127").quote.lower()
    assert not [n for n in (d4.confidence_notes or []) if "không nêu rõ căn cứ" in n]


def test_legal_basis_matches_the_citations(risks):
    d4 = _by(risks, "Điều 4")
    assert "Điều 127 khoản 2" in d4.legal_basis and "Điều 137 khoản 3" in d4.legal_basis
    assert "Điều 141" not in d4.legal_basis  # Điều 141 is child-care allowance, unrelated


def test_unresolved_provision_is_marked_unverified_not_faked():
    d3 = _by(_run_without_corpus(SAMPLE.read_text(encoding="utf-8")), "Điều 3")
    assert all(c.quote is None and not c.evidence_path for c in d3.legal_citations)
    assert all("Chưa đối chiếu kho" in c.status for c in d3.legal_citations)
    assert d3.confidence < 0.8 and d3.confidence_notes


# ---- confidence is evidence-based, not a constant 0.9 ---------------------------------------


def test_confidence_reflects_evidence(risks):
    verified = {r.clause_ref: r.confidence for r in risks}
    assert all(0.3 <= c <= 0.9 for c in verified.values())
    assert verified["Điều 3"] < verified["Điều 2"]  # training-cost legality depends on facts → lower ceiling
    unverified = {r.clause_ref: r.confidence for r in _run_without_corpus(SAMPLE.read_text(encoding="utf-8"))}
    assert all(unverified[k] < verified[k] for k in verified)
    assert len(set(verified.values()) | set(unverified.values())) > 2


# ---- revised clause: rewritten per sentence, then re-validated -------------------------------


def test_revised_clause_has_no_leftover_of_the_violation(risks):
    d3 = _by(risks, "Điều 3").revised_clause
    assert "3 tháng tiền lương" not in d3 and "tháng cuối" not in d3  # was left behind before
    assert "5%" not in d3 and "tối ưu hóa" not in d3
    assert not re.search(r"\.\s+của tháng cuối", d3)  # no grafted sentence fragment
    assert "hợp đồng đào tạo nghề" in d3  # lawful replacement for the flat training fee
    d5 = _by(risks, "Điều 5").revised_clause
    assert "NGƯỜI LAO ĐỘNG" not in d5 and "Ký tên" not in d5  # signature block is not part of Điều 5


def test_revised_clause_keeps_lawful_content_untouched(risks):
    d3 = _by(risks, "Điều 3").revised_clause
    for kept in ("8.500.000 VNĐ/tháng", "Giữ bí mật tuyệt đối các thông tin mô hình học máy."):
        assert kept in d3
    assert "02 bản" in _by(risks, "Điều 5").revised_clause
    assert "Thời giờ làm việc: 8 tiếng/ngày." in _by(risks, "Điều 2").revised_clause


def test_every_shown_revised_clause_passes_revalidation(risks):
    for r in risks:
        assert revised_clause_problems(r.original_clause, r.revised_clause) == [], r.clause_ref


def test_revalidation_catches_a_bad_rewrite():
    original = _by(_run_without_corpus(SAMPLE.read_text(encoding="utf-8")), "Điều 3").original_clause
    assert revised_clause_problems(original, original)  # unchanged / still illegal
    still_illegal = "Điều 3: (iii) NLĐ không những không được nhận lương của tháng cuối cùng làm việc."
    assert any("vi phạm" in p for p in revised_clause_problems(original, still_illegal))
    cut = "Điều 3: Quyền lợi. (i) Công ty trả lương. của tháng cuối cùng làm việc."
    assert any("cắt dở" in p for p in revised_clause_problems(original, cut))
    assert any("Mất nội dung hợp pháp" in p for p in revised_clause_problems(original, "Điều 3: Mức lương 9.000.000."))


def test_negated_mention_is_not_a_violation():
    fixed = (
        "Điều 4: Quyền. (i) Việc xử lý kỷ luật chỉ theo luật; không dùng phạt tiền hay khấu trừ lương. "
        "(ii) Công ty không đơn phương chấm dứt hợp đồng vì lý do kết hôn, mang thai."
    )
    assert revised_clause_problems("Điều 4: x", fixed) == []


def test_revise_clause_text_ot():
    original = (
        "Điều 2: NLĐ có trách nhiệm làm thêm giờ bất cứ khi nào quản lý yêu cầu "
        "và sẽ không được tính thêm tiền lương làm thêm giờ."
    )
    revised = revise_clause_text(original, ["ot_unpaid"])
    assert revised and revised.startswith("Điều 2:")
    assert "không được tính thêm tiền lương làm thêm giờ" not in revised.lower()
    assert "trả lương" in revised.lower() and "đồng ý" in revised.lower()


def test_flag_refs_are_declared_per_khoan():
    for f in _FLAGS:
        assert f.refs and all(r.khoan for r in f.refs), f.key
        assert f.hint.endswith("BLLĐ") and all(f"Điều {r.article} khoản {r.khoan}" in f.hint for r in f.refs)


# ---- helpers ----------------------------------------------------------------------------------


def test_extract_clause_excerpt_dieu_2_and_5():
    text = SAMPLE.read_text(encoding="utf-8")
    assert "làm thêm" in extract_clause_excerpt(text, 2).lower()
    assert "Ký tên" not in extract_clause_excerpt(text, 5)


def test_clause_number_from_ref():
    assert clause_number_from_ref("Điều 4") == "4"
    assert clause_number_from_ref("Dieu 12") == "12"


def test_skip_llm_only_critical():
    items = [
        RiskItem(clause_ref="Điều 1", issue="x", severity="warning", title="a"),
        RiskItem(clause_ref="Điều 2", issue="y", severity="critical", title="b"),
    ]
    assert skip_llm_clause_numbers(items) == ["2"]
