"""Effectivity titles + same-doc internal citation extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.legal_corpus.effectivity import is_effectivity_title
from app.infrastructure.legal_corpus.internal_refs import (
    StructuralRef,
    extract_path_relations,
    parse_internal_refs,
    resolve_structural_ref,
)
from app.infrastructure.legal_corpus.muc_luc_paths import MucLucIndex, build_muc_luc_index

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "legal_sample"
BLHS = Path(__file__).resolve().parents[2] / "Bộ luật Hình sự số 100-2015-QH13--96122"


def test_is_effectivity_title_positive():
    assert is_effectivity_title("Điều 53. Hiệu lực thi hành")
    assert is_effectivity_title("Điều 426. Hiệu lực thi hành")
    assert is_effectivity_title("Điều 10. Tổ chức thực hiện")


def test_is_effectivity_title_rejects_near_misses():
    assert not is_effectivity_title(
        "Điều 5. Hiệu lực của Bộ luật hình sự đối với những hành vi phạm tội trên lãnh thổ"
    )
    assert not is_effectivity_title("Điều 7. Hiệu lực của Bộ luật hình sự về thời gian")
    assert not is_effectivity_title("Điều 60. Thời hiệu thi hành bản án")
    assert not is_effectivity_title("Điều 127. Tội làm chết người trong khi thi hành công vụ")
    assert not is_effectivity_title("ĐIỀU KHOẢN THI HÀNH")
    # Body phrase alone is not a title
    assert not is_effectivity_title("có hiệu lực thi hành từ ngày 01 tháng 7 năm 2016")


def test_parse_point_clause_article():
    text = (
        "trừ trường hợp quy định tại Điều 109, điểm a khoản 2 Điều 113 "
        "hoặc điểm a khoản 2 Điều 299 của Bộ luật này."
    )
    refs = parse_internal_refs(text)
    arts = {(r.article, r.clause, r.point) for r in refs if r.article}
    assert (109, None, None) in arts
    assert (113, 2, "a") in arts
    assert (299, 2, "a") in arts


def test_parse_chapter_and_range():
    text = (
        "Không áp dụng thời hiệu thi hành bản án đối với các tội quy định tại "
        "Chương XIII và Chương XXVI của Bộ luật này."
    )
    refs = parse_internal_refs(text)
    chapters = {r.chapter for r in refs if r.chapter}
    assert 13 in chapters
    assert 26 in chapters

    text2 = "được xóa án tích theo quy định tại các điều từ Điều 70 đến Điều 73 của Bộ luật này."
    refs2 = parse_internal_refs(text2)
    arts = sorted(r.article for r in refs2 if r.article is not None)
    assert arts == [70, 71, 72, 73]


def test_parse_dieu_nay():
    text = "theo quy định tại khoản 1 Điều này, trừ trường hợp che giấu."
    refs = parse_internal_refs(text)
    assert any(r.use_source_article and r.clause == 1 for r in refs)


def test_parse_skips_external_doc_number():
    # Citation of another instrument by số hiệu — skip
    text_skip = "theo Điều 5 của Luật Doanh nghiệp số 59/2020/QH14."
    assert parse_internal_refs(text_skip) == []

    # Same sentence mentions another law but cites Bộ luật này — keep
    text_keep = (
        "theo quy định của Luật thi hành án hình sự số 41/2019/QH14 "
        "và Điều 56 của Bộ luật này."
    )
    refs = parse_internal_refs(text_keep)
    arts = [r.article for r in refs if r.article]
    assert 56 in arts


def _mini_index() -> MucLucIndex:
    raw = [
        {
            "id": "c3",
            "title": "Chương III",
            "level": "Chapter",
            "isLeaf": False,
            "children": [
                {
                    "id": "d14",
                    "title": "Điều 14",
                    "level": "Article",
                    "isLeaf": False,
                    "children": [
                        {
                            "id": "k1",
                            "title": "Khoản 1",
                            "level": "Clause",
                            "isLeaf": True,
                        }
                    ],
                },
                {
                    "id": "d109",
                    "title": "Điều 109",
                    "level": "Article",
                    "isLeaf": True,
                },
                {
                    "id": "d113",
                    "title": "Điều 113",
                    "level": "Article",
                    "isLeaf": False,
                    "children": [
                        {
                            "id": "k2",
                            "title": "Khoản 2",
                            "level": "Clause",
                            "isLeaf": False,
                            "children": [
                                {
                                    "id": "pa",
                                    "title": "Điểm a",
                                    "level": "Point",
                                    "isLeaf": True,
                                }
                            ],
                        }
                    ],
                },
            ],
        },
        {
            "id": "c13",
            "title": "Chương XIII",
            "level": "Chapter",
            "isLeaf": True,
        },
    ]
    return build_muc_luc_index(raw)


def test_resolve_and_extract_path_relations():
    index = _mini_index()
    ref = StructuralRef(article=113, clause=2, point="a")
    structural = resolve_structural_ref(
        ref,
        source_path="doc.C3.D14.K1",
        index=index,
    )
    assert structural is not None
    assert structural.endswith("D113.K2.a")

    chunks = [
        {
            "path": "doc.C3.D14.K1",
            "chunk_type": "body",
            "chunk_text": (
                "trừ trường hợp quy định tại Điều 109, điểm a khoản 2 Điều 113 "
                "của Bộ luật này."
            ),
        }
    ]
    rows = extract_path_relations(chunks, index)
    targets = {r["target_path"] for r in rows}
    assert any(t.endswith(".D109") or t.endswith("D109") for t in targets)
    assert any(t.endswith("D113.K2.a") for t in targets)
    assert all(r["ref_type"] == "dan_chieu" for r in rows)
    assert all(r["source_path"] == "doc.C3.D14.K1" for r in rows)


def test_fixture_effectivity_and_path_relations():
    from app.infrastructure.legal_corpus.assemble import load_document_folder

    art = load_document_folder(FIXTURE)
    by_path = {c["path"]: c for c in art["chunks"]}
    eff = by_path["fixture_168.C1.D53.K1"]
    assert eff["chunk_type"] == "effectivity"
    assert "path_relations" in art
    # Fixture has few internal refs; list must exist
    assert isinstance(art["path_relations"], list)


@pytest.mark.skipif(not BLHS.is_dir(), reason="BLHS 96122 corpus folder not present")
def test_blhs_effectivity_only_dieu_426():
    from app.infrastructure.legal_corpus.assemble import load_document_folder

    art = load_document_folder(BLHS)
    eff = [c for c in art["chunks"] if c.get("chunk_type") == "effectivity"]
    assert eff, "expected Điều 426 effectivity chunks"
    assert all(".D426" in (c["path"] or "") for c in eff), {
        c["path"] for c in eff
    }
    # Near-miss titles must stay body
    false_eff = [
        c
        for c in art["chunks"]
        if c.get("chunk_type") == "effectivity"
        and any(x in (c["path"] or "") for x in (".D5", ".D6.", ".D7.", ".D60", ".D127"))
    ]
    assert not false_eff

    path_rels = art["path_relations"]
    assert len(path_rels) > 50
    # Sample: preparing crime cites Điều 109 / 113
    targets = " ".join(r["target_path"] for r in path_rels)
    assert "D109" in targets
    assert "D113" in targets or "C13" in targets
    assert all(r["source_path"] != r["target_path"] for r in path_rels)
