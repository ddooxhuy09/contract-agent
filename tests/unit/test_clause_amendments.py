"""Unit tests for clause_amendments → legal_path_relations parser."""

from pathlib import Path

from app.infrastructure.legal_corpus.clause_amendments import (
    DocNumResolver,
    doc_num_from_title_document,
    load_clause_amendments_folder,
    parse_clause_amendments,
    ref_type_from_amend_type,
    sanitize_doc_num_for_ltree,
    structural_path_from_provision_title,
    to_doc_num_ltree,
)

FIXTURE_BLHS = (
    Path(__file__).resolve().parents[1].parent
    / "Bộ luật Hình sự số 100-2015-QH13--96122"
)


def test_sanitize_doc_num():
    assert sanitize_doc_num_for_ltree("100/2015/QH13") == "100_2015_QH13"
    assert sanitize_doc_num_for_ltree("59/2024/QH15") == "59_2024_QH15"
    assert to_doc_num_ltree("100/2015/QH13", "P2.C2.D134.K1.g") == (
        "100_2015_QH13.P2.C2.D134.K1.g"
    )


def test_ref_type_map():
    assert ref_type_from_amend_type(1) == "bai_bo"
    assert ref_type_from_amend_type(10) == "sua_doi"
    assert ref_type_from_amend_type(99) == "loai_99"
    assert ref_type_from_amend_type(None) == "sua_doi"


def test_doc_num_from_title_document():
    assert (
        doc_num_from_title_document(
            "Luật Tư pháp người chưa thành niên số 59/2024/QH15"
        )
        == "59/2024/QH15"
    )


def test_structural_from_title():
    assert (
        structural_path_from_provision_title(
            "Điểm b, Khoản 1, Điều 177, Phần Thứ Năm"
        )
        == "P5.D177.K1.b"
    )
    assert structural_path_from_provision_title("Chương XII, Phần Thứ Nhất") == "P1.C12"


def test_parse_blhs_2015_folder():
    if not FIXTURE_BLHS.is_dir():
        return  # optional corpus folder may be absent in CI
    resolver = DocNumResolver(
        by_doc_id={
            "96122": "100/2015/QH13",
            "175425": "59/2024/QH15",
        }
    )
    emb = {
        "175425": [
            "175425.D177.K1.a",
            "175425.D177.K1.b",
        ]
    }
    rows, warnings, meta = load_clause_amendments_folder(
        FIXTURE_BLHS,
        doc_num_resolver=resolver,
        embedding_paths_by_doc=emb,
    )
    assert meta["doc_id"] == "96122"
    assert meta["doc_num"] == "100/2015/QH13"
    assert len(rows) == 2
    by_type = {r.ref_type: r for r in rows}
    assert "sua_doi" in by_type
    assert "bai_bo" in by_type
    assert by_type["sua_doi"].source_path == "59_2024_QH15.D177.K1.b"
    assert by_type["sua_doi"].target_path == "100_2015_QH13.P2.C14.D134.K1.g"
    assert by_type["bai_bo"].target_path == "100_2015_QH13.P1.C12"
    assert by_type["bai_bo"].source_path.endswith("D177.K1.a")


def test_same_doc_uses_shared_doc_num():
    muc = [
        {
            "id": "t1",
            "level": "Article",
            "title": "Điều 1",
            "children": [
                {"id": "s1", "level": "Clause", "title": "Khoản 1", "children": []},
                {"id": "s2", "level": "Clause", "title": "Khoản 2", "children": []},
            ],
        }
    ]
    amendments = {
        "t1": {
            "targetProvision": {"id": "t1", "documentId": "d1"},
            "sourceProvisions": [
                {
                    "id": "s2",
                    "documentId": "d1",
                    "titleDocument": "Luật số 1/2020/QH14",
                    "title": "Khoản 2, Điều 1",
                    "type": 10,
                    "content": "dẫn chiếu nội bộ",
                }
            ],
        }
    }
    resolver = DocNumResolver(by_doc_id={"d1": "1/2020/QH14"})
    rows, warnings = parse_clause_amendments(
        amendments,
        muc_luc=muc,
        target_doc_id="d1",
        target_doc_num="1/2020/QH14",
        doc_num_resolver=resolver,
    )
    assert not warnings
    assert len(rows) == 1
    assert rows[0].source_path.startswith("1_2020_QH14.")
    assert rows[0].target_path.startswith("1_2020_QH14.")
    assert rows[0].ref_type == "sua_doi"
