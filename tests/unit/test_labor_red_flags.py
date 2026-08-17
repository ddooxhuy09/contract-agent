"""Deterministic labor red-flags on the crafted SAI sample contract."""

from pathlib import Path

from app.agents.labor_red_flags import check_labor_red_flags
from app.schemas.contract import ContractAnalysis

SAMPLE = Path(__file__).resolve().parents[2] / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"


def test_sai_sample_hits_core_red_flags():
    text = SAMPLE.read_text(encoding="utf-8")
    risks = check_labor_red_flags(
        text,
        ContractAnalysis(contract_id="sai", contract_type="Hợp đồng lao động"),
        as_of_date="15/07/2026",
    )
    keys = {r.title for r in risks}
    assert any("làm thêm" in t.lower() or "ot" in t.lower() for t in keys)
    assert any("bhxh" in t.lower() or "bảo hiểm" in t.lower() for t in keys)
    assert any("cccd" in t.lower() or "giấy tờ" in t.lower() for t in keys)
    assert any("phạt tiền" in t.lower() or "khấu trừ" in t.lower() for t in keys)
    assert any("mang thai" in t.lower() or "kết hôn" in t.lower() for t in keys)
    assert any("khởi kiện" in t.lower() or "tòa" in t.lower() for t in keys)
    assert all(r.severity == "critical" for r in risks)
    assert len(risks) >= 6
