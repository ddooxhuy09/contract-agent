"""Tests: legal citation structuring must never split VN doc numbers on '/'."""

from app.agents.legal_citations import (
    citations_from_legal_basis_text,
    citations_from_llm,
    resolve_legal_citations,
    strip_internal_refs,
)


def test_strip_chunk_ref_keeps_doc_number():
    raw = "[20/2023/TT-BCT | 163444:C2.M1.D6.K2]: Làm thêm phải có đồng ý."
    assert "163444" not in strip_internal_refs(raw)
    assert "20/2023/TT-BCT" in strip_internal_refs(raw)


def test_does_not_split_inside_doc_number():
    raw = (
        "20/2023/TT-BCT: Phải có sự đồng ý của NLĐ. "
        "12/2022/TT-BCT: Quy định khác. "
        "145/2020/NĐ-CP: Giới hạn thời giờ làm thêm."
    )
    cites = citations_from_legal_basis_text(raw)
    titles = [c.title for c in cites]
    assert titles == ["20/2023/TT-BCT", "12/2022/TT-BCT", "145/2020/NĐ-CP"]
    assert "2" not in titles
    assert "0/2023/TT-BCT" not in titles
    assert "1" not in titles
    assert cites[0].summary.startswith("Phải có sự đồng ý")


def test_prefix_thong_tu_kept_intact():
    raw = "Thông tư 20/2023/TT-BCT: Đồng ý làm thêm giờ. Nghị định 145/2020/NĐ-CP: Giới hạn OT."
    cites = citations_from_legal_basis_text(raw)
    assert cites[0].title == "Thông tư 20/2023/TT-BCT"
    assert cites[1].title == "Nghị định 145/2020/NĐ-CP"


def test_llm_structured_title_summary():
    cites = citations_from_llm(
        [
            {
                "title": "Thông tư 20/2023/TT-BCT",
                "summary": "Tổ chức làm thêm phải có sự đồng ý của NLĐ.",
            },
            {
                "label": "Nghị định 145/2020/NĐ-CP",
                "points": ["Giới hạn thời giờ làm thêm."],
            },
        ]
    )
    assert len(cites) == 2
    assert cites[0].title == "Thông tư 20/2023/TT-BCT"
    assert "đồng ý" in cites[0].summary
    assert cites[1].title == "Nghị định 145/2020/NĐ-CP"


def test_resolve_prefers_llm_over_basis_text():
    cites = resolve_legal_citations(
        [{"title": "45/2019/QH14", "summary": "Bộ luật Lao động."}],
        "20/2023/TT-BCT: should be ignored when structured present",
    )
    assert len(cites) == 1
    assert cites[0].title == "45/2019/QH14"


def test_resolve_falls_back_to_basis_without_splitting():
    cites = resolve_legal_citations(
        None,
        "[20/2023/TT-BCT | 163444:C2.D1]: Đồng ý OT. [12/2022/TT-BCT | 1:C1]: Khác.",
    )
    titles = [c.title for c in cites]
    assert "20/2023/TT-BCT" in titles
    assert "12/2022/TT-BCT" in titles
    assert "2" not in titles
    assert "0/2023/TT-BCT" not in titles
