"""Tests: legal citation structuring must never split VN doc numbers on '/'."""

from app.agents.legal_citations import (
    build_text_fragment_url,
    build_source_deep_link,
    citations_from_legal_basis_text,
    citations_from_llm,
    extract_article_title,
    format_path_location,
    ground_citations,
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


def test_format_path_location_includes_chapter_section_article_clause_point():
    location = format_path_location("100_2015_QH13.C3.M2.D35.K1.a")
    assert location["location"] == "Chương 3 > Mục 2 > Điều 35 > Khoản 1 > Điểm a"
    assert location["article"] == "Điều 35"
    assert location["clause"] == "Khoản 1"
    assert location["point"] == "Điểm a"


def test_ground_citations_uses_retrieved_quote_and_path():
    docs = [
        {
            "page_content": "Điều 35.\n1. Người sử dụng lao động phải báo trước.",
            "metadata": {
                "path": "45_2019_QH14.C3.D35.K1",
                "doc_number": "45/2019/QH14",
                "title": "Bộ luật Lao động",
                "source_url": "https://vbpl.vn/van-ban/chi-tiet/bo-luat-lao-dong--45",
                "source_element_id": "article-35-id",
                "eff_flag": "Còn hiệu lực",
            },
        }
    ]
    citations = ground_citations(
        [{"title": "45/2019/QH14", "summary": "Báo trước"}],
        ["45_2019_QH14.C3.D35.K1"],
        docs,
    )
    assert len(citations) == 1
    assert citations[0].quote.startswith("Điều 35.")
    assert citations[0].location == "Chương 3 > Điều 35 > Khoản 1"
    assert citations[0].source_url.startswith("https://vbpl.vn/")
    assert citations[0].deep_link.endswith("#article-35-id")
    assert citations[0].source_element_id == "article-35-id"


def test_ground_citations_dedupes_sibling_points_and_drops_sector():
    docs = [
        {
            "page_content": "a) Phạt 1-2 triệu",
            "metadata": {
                "path": "nd12.D12.K2.a",
                "doc_number": "12/2022/NĐ-CP",
                "title": "Nghị định xử phạt lao động",
                "status_flag": 1,
                "eff_flag": "Còn hiệu lực",
            },
        },
        {
            "page_content": "b) Phạt 2-5 triệu",
            "metadata": {
                "path": "nd12.D12.K2.b",
                "doc_number": "12/2022/NĐ-CP",
                "title": "Nghị định xử phạt lao động",
                "status_flag": 1,
                "eff_flag": "Còn hiệu lực",
            },
        },
        {
            "page_content": "giúp việc gia đình",
            "metadata": {
                "path": "tt19.D10.K1.a",
                "doc_number": "19/2014/TT-BLĐTBXH",
                "title": "Thông tư hướng dẫn lao động là người giúp việc gia đình",
                "status_flag": 1,
                "eff_flag": "Còn hiệu lực",
                "eff_to": "2025-02-15",
            },
        },
    ]
    citations = ground_citations(
        None,
        ["nd12.D12.K2.a", "nd12.D12.K2.b", "tt19.D10.K1.a"],
        docs,
        contract_text="Thực tập sinh MLOps công ty công nghệ AI",
        as_of_date="15/07/2026",
    )
    assert len(citations) == 1
    assert citations[0].doc_number == "12/2022/NĐ-CP"
    assert citations[0].status == "Còn hiệu lực"


def test_extract_article_title_uses_heading_only():
    assert (
        extract_article_title("Điều 6. Làm thêm giờ\n2. Nội dung khoản rất dài.")
        == "Điều 6. Làm thêm giờ"
    )


def test_source_deep_link_falls_back_to_article_title_text():
    link = build_source_deep_link(
        "https://vbpl.vn/doc?tabs=toan-van", None, "Điều 6. Làm thêm giờ"
    )
    assert link == (
        "https://vbpl.vn/doc?tabs=toan-van"
        "#:~:text=%C4%90i%E1%BB%81u%206.%20L%C3%A0m%20th%C3%AAm%20gi%E1%BB%9D"
    )


def test_text_fragment_url_rejects_invalid_source():
    assert build_text_fragment_url("not-a-url", "Điều 1") is None


def test_source_deep_link_prefers_native_element_id():
    assert (
        build_source_deep_link("https://vbpl.vn/doc?tabs=toan-van", "abc-123", "Điều 1")
        == "https://vbpl.vn/doc?tabs=toan-van#abc-123"
    )


def test_source_deep_link_forces_full_text_tab():
    assert (
        build_source_deep_link("https://vbpl.vn/doc", "abc-123", "Điều 1")
        == "https://vbpl.vn/doc?tabs=toan-van#abc-123"
    )
