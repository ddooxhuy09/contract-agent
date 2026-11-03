from app.document.chunker import chunk_by_clause


def test_chunk_by_clause_with_pattern():
    text = "Điều 1. Nội dung hợp đồng\nĐây là nội dung.\nĐiều 2. Nghĩa vụ\nNghĩa vụ các bên."
    docs = chunk_by_clause(text, "test-1")
    assert len(docs) >= 2
    assert all(d.metadata["contract_id"] == "test-1" for d in docs)


def test_chunk_by_clause_fallback():
    text = "A" * 2000
    docs = chunk_by_clause(text, "test-2")
    assert len(docs) >= 1
    assert docs[0].metadata["contract_id"] == "test-2"


def _clause_numbers(text):
    return [d.metadata["clause_number"] for d in chunk_by_clause(text, "t")]


def test_chunk_by_clause_heading_alone_on_line():
    text = "HỢP ĐỒNG\nĐiều 1\nNội dung một.\nĐiều 2\nNội dung hai.\n"
    assert _clause_numbers(text) == ["Preamble", "1", "2"]


def test_chunk_by_clause_uppercase_heading_with_colon():
    text = "ĐIỀU 1: Phạm vi\nA.\nĐIỀU 2: Giá\nB."
    assert _clause_numbers(text) == ["1", "2"]


def test_chunk_by_clause_muc_headings_when_no_dieu():
    text = "HỢP ĐỒNG DÂN SỰ\nMục A\nNội dung A.\nMục B\nNội dung B."
    assert _clause_numbers(text) == ["Preamble", "A", "B"]


def test_chunk_by_clause_khoan_headings_when_no_dieu_or_muc():
    text = "ĐIỀU KHOẢN NGƯỜI TIÊU DÙNG\nKhoản A\nMột.\nKhoản B\nHai."
    assert _clause_numbers(text) == ["Preamble", "A", "B"]


def test_chunk_by_clause_dieu_wins_over_muc_and_khoan():
    text = "Điều 1\nMục A\nx\nKhoản B\ny\nĐiều 2\nz"
    assert _clause_numbers(text) == ["1", "2"]


def test_chunk_by_clause_inline_reference_does_not_split():
    text = "Điều 1\nCác bên thực hiện theo Điều 5. của Luật Thương mại.\nĐiều 2\nHết."
    assert _clause_numbers(text) == ["1", "2"]


def test_chunk_by_clause_legacy_inline_heading_still_splits():
    text = "Mở đầu. Điều 1. Một\nnội dung Điều 2. Hai\nnội dung"
    assert _clause_numbers(text) == ["Preamble", "1", "2"]
