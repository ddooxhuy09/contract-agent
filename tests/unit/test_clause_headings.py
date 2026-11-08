"""Clause extraction heading styles (shared with the chunker's heading detection)."""

from app.agents.clause_parser import _extract_clauses

TITLE_ON_NEXT_LINE = """HỢP ĐỒNG LAO ĐỘNG
Điều 1
Vị trí nhân viên kho, lương 12.000.000 đồng/tháng.
Điều 2
Người lao động giao bản chính căn cước công dân cho công ty giữ.
"""

TITLE_SAME_LINE = """HỢP ĐỒNG LAO ĐỘNG
Điều 1. CÔNG VIỆC
Vị trí nhân viên kho.
ĐIỀU 2: TIỀN LƯƠNG
Lương 12.000.000 đồng/tháng.
"""

SECTION_HEADINGS = """HỢP ĐỒNG DỊCH VỤ DÂN SỰ
Mục A
Hai bên thỏa thuận dịch vụ thiết kế.
Mục B
Bên thuê đặt cọc 3.000.000 đồng.
"""

INLINE_REFERENCE = """HỢP ĐỒNG LAO ĐỘNG
Điều 1
Hai bên thực hiện theo Điều 5. Bộ luật Lao động 2019 và theo Điều 17 của luật này.
"""


def test_heading_with_title_on_next_line():
    # This form yielded zero clauses before, which failed the whole analysis.
    clauses = _extract_clauses(TITLE_ON_NEXT_LINE)
    assert [c.clause_number for c in clauses] == ["1", "2"]
    assert "căn cước công dân" in clauses[1].summary


def test_heading_with_title_on_same_line_still_works():
    clauses = _extract_clauses(TITLE_SAME_LINE)
    assert [c.clause_number for c in clauses] == ["1", "2"]
    assert clauses[0].title == "CÔNG VIỆC"


def test_falls_back_to_muc_when_no_dieu():
    clauses = _extract_clauses(SECTION_HEADINGS)
    assert [c.clause_number for c in clauses] == ["A", "B"]
    assert "đặt cọc" in clauses[1].summary


def test_inline_reference_does_not_split():
    clauses = _extract_clauses(INLINE_REFERENCE)
    assert [c.clause_number for c in clauses] == ["1"]
    assert "Điều 17" in clauses[0].summary


def test_no_heading_gives_no_clauses():
    assert _extract_clauses("Văn bản không có tiêu đề điều khoản nào.") == []
