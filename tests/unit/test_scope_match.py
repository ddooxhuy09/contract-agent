"""Sector-scope + normative hierarchy ranking (no fixed số hiệu bias)."""

from app.domain.entities.search import RetrievedChunk
from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag
from app.infrastructure.retrieval.normative_rank import normative_rank
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query
from app.infrastructure.retrieval.scope_match import (
    filter_sector_mismatches,
    is_sector_mismatch,
)


def test_is_sector_mismatch_oil_gas_vs_tech_contract():
    law = (
        "Thông tư số 20/2023/TT-BCT quy định về thời giờ làm việc "
        "trong lĩnh vực thăm dò, khai thác dầu khí trên biển"
    )
    contract = "Hợp đồng lao động Công ty Cổ phần Công nghệ Tương Lai làm thêm giờ"
    assert is_sector_mismatch(law, contract)


def test_sector_mismatch_domestic_helper_gas_mine_abroad():
    tech = "HĐLĐ thực tập sinh MLOps Phòng Nghiên cứu và Phát triển AI"
    assert is_sector_mismatch(
        "Thông tư 19/2014/TT-BLĐTBXH hướng dẫn lao động là người giúp việc gia đình",
        tech,
    )
    assert is_sector_mismatch(
        "Thông tư 12/2022/TT-BCT thời giờ làm việc đường ống phân phối khí",
        tech,
    )
    assert is_sector_mismatch(
        "Thông tư 04/2021/TT-BCT thời giờ làm việc trong hầm lò",
        tech,
    )
    assert is_sector_mismatch(
        "Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng 69/2020/QH14",
        tech,
    )
    assert not is_sector_mismatch(
        "Nghị định 12/2022/NĐ-CP xử phạt vi phạm hành chính trong lĩnh vực lao động",
        tech,
    )
    # Full multi-domain title must NOT be treated as "chỉ NLĐ nước ngoài"
    assert not is_sector_mismatch(
        "Nghị định số 12/2022/NĐ-CP Quy định xử phạt vi phạm hành chính trong lĩnh vực "
        "lao động, bảo hiểm xã hội, người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
        tech,
    )


def test_is_sector_mismatch_military_and_police():
    assert is_sector_mismatch(
        "Thông tư quy định giờ làm việc đối với sĩ quan quân đội",
        "Hợp đồng lao động công ty phần mềm",
    )
    assert not is_sector_mismatch(
        "Thông tư quy định giờ làm việc đối với sĩ quan quân đội",
        "Hợp đồng lao động quân nhân chuyên nghiệp",
    )
    assert is_sector_mismatch(
        "Quy định thời giờ làm việc trong lực lượng công an nhân dân",
        "Hợp đồng lao động văn phòng",
    )
    # CCCD issuer "Cục Cảnh sát…" on a tech contract must not unlock police circulars
    assert is_sector_mismatch(
        "Quy định thời giờ làm việc trong lực lượng công an nhân dân",
        "HĐLĐ công nghệ. Nơi cấp: Cục Cảnh sát QLHC về TTXH",
    )

def test_filter_drops_tt_bct_seed():
    seeds = [
        RetrievedChunk(
            content="… không quá 14 giờ/ngày",
            score=0.9,
            metadata={
                "path": "tt.D6",
                "doc_number": "20/2023/TT-BCT",
                "title": "Thông tư thăm dò khai thác dầu khí trên biển",
                "doc_type": "Thông tư",
            },
        ),
        RetrievedChunk(
            content="làm thêm giờ…",
            score=0.7,
            metadata={
                "path": "bl.D107",
                "doc_number": "45/2019/QH14",
                "title": "Bộ luật Lao động",
                "doc_type": "Bộ luật",
            },
        ),
    ]
    kept, dropped = filter_sector_mismatches(
        seeds, "Hợp đồng lao động công ty công nghệ làm thêm giờ"
    )
    assert [c.metadata["doc_type"] for c in dropped] == ["Thông tư"]
    assert [c.metadata["doc_type"] for c in kept] == ["Bộ luật"]


def test_normative_rank_hierarchy():
    assert normative_rank("Bộ luật") > normative_rank("Luật")
    assert normative_rank("Luật") > normative_rank("Nghị quyết")
    assert normative_rank("Nghị quyết") > normative_rank("Pháp lệnh")
    assert normative_rank("Pháp lệnh") > normative_rank("Nghị định")
    assert normative_rank("Nghị định") > normative_rank("Thông tư")
    assert normative_rank("Thông tư") > normative_rank("Thông tư liên tịch")
    # Title fallback when doc_type missing
    assert normative_rank(None, "Bộ luật Lao động") > normative_rank(None, "Thông tư …")


def test_order_prefers_bo_luat_over_thong_tu_even_if_lower_score():
    chunks = [
        RetrievedChunk(
            content="tt",
            score=0.99,
            metadata={
                "path": "a",
                "doc_type": "Thông tư",
                "title": "Thông tư hướng dẫn",
                "status_flag": 1,
                "role": "seed",
            },
        ),
        RetrievedChunk(
            content="bl",
            score=0.55,
            metadata={
                "path": "b",
                "doc_type": "Bộ luật",
                "title": "Bộ luật Lao động",
                "status_flag": 1,
                "role": "seed",
            },
        ),
    ]
    ordered = LegalGraphRag._order_for_prompt(chunks)
    assert ordered[0].metadata["doc_type"] == "Bộ luật"


def test_order_drops_expired_when_effective_exists_via_validity():
    expired = RetrievedChunk(
        content="x",
        score=0.9,
        metadata={"path": "e", "doc_type": "Bộ luật", "status_flag": 2, "role": "seed"},
    )
    live = RetrievedChunk(
        content="y",
        score=0.5,
        metadata={"path": "l", "doc_type": "Nghị định", "status_flag": 1, "role": "seed"},
    )
    assert LegalGraphRag._validity_key(expired)[0] == 99
    assert LegalGraphRag._validity_key(live)[0] == 0


def test_rewrite_has_no_fixed_doc_number_bias():
    q = rewrite_legal_query(
        "Làm thêm giờ",
        "Người lao động làm thêm không quá 200 giờ/năm",
        contract_type="Hợp đồng lao động",
    )
    assert "145/2020" not in q
    assert "20/2023" not in q
    assert "làm" in q.lower()
