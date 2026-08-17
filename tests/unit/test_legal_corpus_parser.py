"""Unit tests for legal crawler folder → ingest artifacts."""

from pathlib import Path

from app.infrastructure.legal_corpus.assemble import load_document_folder
from app.infrastructure.legal_corpus.discover import discover_document_folders, is_document_folder
from app.infrastructure.legal_corpus.luoc_do_flatten import flatten_luoc_do
from app.infrastructure.legal_corpus.muc_luc_paths import build_muc_luc_index
from app.infrastructure.legal_corpus.muc_luc_paths import (
    _segment_token,
    article_root_ltree,
    chunk_ref_to_ltree,
    sanitize_doc_id_for_ltree,
    to_ltree_path,
)
from app.infrastructure.legal_corpus.thuoc_tinh_mapper import (
    map_thuoc_tinh,
    normalize_eff_flag,
    status_flag_from_eff_flag,
    status_flag_from_thuoc_tinh,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "legal_sample"


def test_discover_finds_fixture_folder():
    assert is_document_folder(FIXTURE)
    found = discover_document_folders(FIXTURE.parent)
    assert FIXTURE.resolve() in [p.resolve() for p in found]


def test_discover_single_doc_folder():
    found = discover_document_folders(FIXTURE)
    assert found == [FIXTURE.resolve()]


def test_status_flag_chl():
    assert status_flag_from_thuoc_tinh({"eff_status_code": "CHL"}) == 1
    assert normalize_eff_flag({"eff_status_code": "CHL"}) == "Còn hiệu lực"
    assert status_flag_from_eff_flag("Ngưng hiệu lực") == 2
    assert status_flag_from_eff_flag("Ngưng hiệu lực một phần") == 4
    assert status_flag_from_eff_flag("Có hiệu lực một phần") == 5
    mapped = map_thuoc_tinh(
        {
            "doc_id": "1",
            "doc_num": "168/2024/NĐ-CP",
            "title": "t",
            "doc_type": "Nghị định",
            "eff_status_code": "CHL",
            "signers": [{"name": "A", "title": "B"}],
        }
    )
    assert mapped["status_flag"] == 1
    assert mapped["eff_flag"] == "Còn hiệu lực"
    assert mapped["signer_name"] == "A"
    assert mapped["signer_title"] == "B"
    assert "doc_num_norm" not in mapped
    assert "eff_status_code" not in mapped


def test_segment_token_all_levels():
    assert _segment_token("Part", "Phần Thứ Nhất", 0) == "P1"
    assert _segment_token("Part", "Phần Thứ Hai", 0) == "P2"
    assert _segment_token("Part", "Phần Thứ Ba", 0) == "P3"
    assert _segment_token("Chapter", "Chương I", 0) == "C1"
    assert _segment_token("Chapter", "Chương IX", 0) == "C9"
    assert _segment_token("Chapter", "Chương XIII", 0) == "C13"
    assert _segment_token("Chapter", "Chương XXVI", 0) == "C26"
    assert _segment_token("Section", "Mục 1", 0) == "M1"
    assert _segment_token("Section", "Mục I", 0) == "M1"
    assert _segment_token("SubSection", "Tiểu mục 2", 0) == "TM2"
    assert _segment_token("SubSection", "Tiểu mục II", 0) == "TM2"
    assert _segment_token("Article", "Điều 12", 0) == "D12"
    assert _segment_token("Article", "Điều", 0) is None  # weak — unique id in walk
    assert _segment_token("Clause", "Khoản 3", 0) == "K3"
    assert _segment_token("Clause", "Khoản", 0) is None
    assert _segment_token("Point", "Điểm a", 0) == "a"
    assert _segment_token("Point", "Điểm đ", 0) == "dd"
    assert _segment_token("Point", "Điểm khoan", 0) is None  # junk TOC


def test_blhs_2015_no_path_collisions_and_real_numbers():
    folder = Path(__file__).resolve().parents[1].parent / "Bộ luật Hình sự số 100-2015-QH13--96122"
    if not folder.is_dir():
        return
    import json
    from collections import Counter

    muc = json.loads((folder / "muc_luc.json").read_text(encoding="utf-8"))
    index = build_muc_luc_index(muc)
    counts = Counter(n.path for n in index.nodes)
    assert not [p for p, c in counts.items() if c > 1]

    parts = [n for n in index.nodes if n.level == "Part"]
    assert [n.path for n in parts] == ["P1", "P2", "P3"]
    chapter_paths = {n.path for n in index.nodes if n.level == "Chapter"}
    assert "P1.C1" in chapter_paths and "P1.C12" in chapter_paths
    assert "P2.C13" in chapter_paths and "P2.C26" in chapter_paths
    assert "P2.C1" not in chapter_paths

    # Real Điều 2/3 keep D2/D3; weak "Điều" get id-based tokens
    assert any(n.path == "P1.C1.D2" and n.title == "Điều 2" for n in index.nodes)
    assert any(n.path == "P1.C1.D3" and n.title == "Điều 3" for n in index.nodes)
    weak = [n for n in index.nodes if n.level == "Article" and n.title == "Điều"]
    assert weak
    assert all("_" in n.path.rsplit(".", 1)[-1] for n in weak)

    sections = [n for n in index.nodes if n.level == "Section"]
    assert sections
    assert all(n.path.rsplit(".", 1)[-1].startswith("M") for n in sections)


def test_blhs_2015_parts_and_chapters_from_muc_luc():
    folder = Path(__file__).resolve().parents[1].parent / "Bộ luật Hình sự số 100-2015-QH13--96122"
    if not folder.is_dir():
        return
    art = load_document_folder(folder)
    legal_parts = [n for n in art["legal_nodes"] if n["level"] == "Part"]
    assert len(legal_parts) == 3
    assert {n["path"] for n in legal_parts} == {
        "100_2015_QH13.P1",
        "100_2015_QH13.P2",
        "100_2015_QH13.P3",
    }
    assert all(n["parent_path"] == "100_2015_QH13" for n in legal_parts)
    chapters = [n for n in art["legal_nodes"] if n["level"] == "Chapter"]
    assert len(chapters) == 26
    assert any(n["path"] == "100_2015_QH13.P2.C13" for n in chapters)
    import json

    muc = json.loads((FIXTURE / "muc_luc.json").read_text(encoding="utf-8"))
    index = build_muc_luc_index(muc)
    paths = {n.path for n in index.nodes}
    assert "C1.D1.K1.a" in paths
    assert "C1.D1.K1.b" in paths
    assert "C1.D1.K2" in paths
    cut = {n.path for n in index.cut_leaves}
    assert "C1.D1.K1.a" in cut
    assert "C1.D1.K1.b" in cut
    assert "C1.D1.K2" in cut
    assert "C1.D1.K1" not in cut  # parent of points is not a cut leaf


def test_assemble_body_chunks_have_context():
    art = load_document_folder(FIXTURE)
    by_path = {c["path"]: c for c in art["chunks"]}
    a = by_path["fixture_168.C1.D1.K1.a"]
    assert "Điều 1" in a["chunk_text"]
    assert "Phạm vi điều chỉnh" in a["chunk_text"]
    assert "Nghị định này quy định về" in a["chunk_text"]
    assert "a)" in a["chunk_text"]
    assert "trật tự" in a["chunk_text"]

    b = by_path["fixture_168.C1.D1.K1.b"]
    assert "b)" in b["chunk_text"]
    assert "Điều 1" in b["chunk_text"]

    k2 = by_path["fixture_168.C1.D1.K2"]
    assert "Điều 1" in k2["chunk_text"]
    assert "chuyên ngành" in k2["chunk_text"]


def test_assemble_preamble_and_effectivity():
    art = load_document_folder(FIXTURE)
    by_path = {c["path"]: c for c in art["chunks"]}
    assert "fixture_168.PREAMBLE" in by_path
    assert by_path["fixture_168.PREAMBLE"]["chunk_type"] == "preamble"
    eff = by_path["fixture_168.C1.D53.K1"]
    assert eff["chunk_type"] == "effectivity"
    assert "hiệu lực" in eff["chunk_text"].lower()


def test_appendix_includes_title_and_header_row():
    art = load_document_folder(FIXTURE)
    appendix = [c for c in art["chunks"] if c["chunk_type"] == "appendix"]
    assert appendix
    text = appendix[0]["chunk_text"]
    assert "Phụ lục" in text
    assert "Hành vi" in text  # header
    assert "mũ bảo hiểm" in text or "đèn đỏ" in text


def test_luoc_do_flatten_directions():
    import json

    raw = json.loads((FIXTURE / "luoc_do.json").read_text(encoding="utf-8"))
    rels, stubs = flatten_luoc_do(raw)
    outgoing = [r for r in rels if r["relation_type"] == "can_cu_ban_hanh"]
    assert any(r["from_doc_id"] == "fixture-168" and r["to_doc_id"] == "70821" for r in outgoing)
    incoming = [r for r in rels if r["relation_type"] == "van_ban_bi_bai_bo"]
    assert any(r["from_doc_id"] == "185666" and r["to_doc_id"] == "fixture-168" for r in incoming)
    assert stubs["70821"]["doc_num"] == "76/2015/QH13"
    assert "336/2025" in stubs["185666"]["title"]


def test_assemble_relations_and_graph_nodes():
    art = load_document_folder(FIXTURE)
    assert art["relations"]
    assert art["stub_docs"]["70821"]["title"]
    paths = {n["path"] for n in art["graph_nodes"]}
    assert "168_2024_N__CP.C1.D1.K1.a" in paths
    assert "168_2024_N__CP.PREAMBLE" in paths or "fixture_168.PREAMBLE" in paths
    assert art["legal_nodes"]
    ltree_paths = {n["path"] for n in art["legal_nodes"]}
    assert "168_2024_N__CP.C1.D1.K1.a" in ltree_paths
    assert any(c.get("path") == "fixture_168.C1.D1.K1.a" for c in art["chunks"])


def test_ltree_path_helpers():
    assert sanitize_doc_id_for_ltree("fixture-168") == "fixture_168"
    assert to_ltree_path("fixture-168", "C1.D1.K1.a") == "fixture_168.C1.D1.K1.a"
    assert chunk_ref_to_ltree("fixture-168:C1.D1.K1.a") == "fixture_168.C1.D1.K1.a"
    assert article_root_ltree("fixture_168.C1.D1.K1.a") == "fixture_168.C1.D1"
    assert article_root_ltree("fixture_168.PREAMBLE") is None
