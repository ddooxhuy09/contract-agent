"""Unit tests for legal crawler folder → ingest artifacts."""

from pathlib import Path

from app.infrastructure.legal_corpus.assemble import load_document_folder
from app.infrastructure.legal_corpus.discover import discover_document_folders, is_document_folder
from app.infrastructure.legal_corpus.luoc_do_flatten import flatten_luoc_do
from app.infrastructure.legal_corpus.muc_luc_paths import build_muc_luc_index
from app.infrastructure.legal_corpus.thuoc_tinh_mapper import map_thuoc_tinh, status_flag_from_thuoc_tinh

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
    mapped = map_thuoc_tinh(
        {
            "doc_id": "1",
            "doc_num": "168/2024/NĐ-CP",
            "title": "t",
            "doc_type": "Nghị định",
            "eff_status_code": "CHL",
        }
    )
    assert mapped["status_flag"] == 1
    assert mapped["doc_num_norm"]


def test_muc_luc_paths_dieu_khoan_diem():
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
    by_ref = {c["chunk_ref"]: c for c in art["chunks"]}
    a = by_ref["fixture-168:C1.D1.K1.a"]
    assert "Điều 1" in a["chunk_text"]
    assert "Phạm vi điều chỉnh" in a["chunk_text"]
    assert "Nghị định này quy định về" in a["chunk_text"]
    assert "a)" in a["chunk_text"]
    assert "trật tự" in a["chunk_text"]

    b = by_ref["fixture-168:C1.D1.K1.b"]
    assert "b)" in b["chunk_text"]
    assert "Điều 1" in b["chunk_text"]

    k2 = by_ref["fixture-168:C1.D1.K2"]
    assert "Điều 1" in k2["chunk_text"]
    assert "chuyên ngành" in k2["chunk_text"]


def test_assemble_preamble_and_effectivity():
    art = load_document_folder(FIXTURE)
    by_ref = {c["chunk_ref"]: c for c in art["chunks"]}
    assert "fixture-168:PREAMBLE" in by_ref
    assert by_ref["fixture-168:PREAMBLE"]["chunk_type"] == "preamble"
    eff = by_ref["fixture-168:C1.D53.K1"]
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
    assert "fixture-168:C1.D1.K1.a" in paths
    assert "fixture-168:PREAMBLE" in paths
