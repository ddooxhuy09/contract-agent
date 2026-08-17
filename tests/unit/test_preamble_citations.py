"""Preamble «Căn cứ …» citation parsing + validation helpers."""

from pathlib import Path
from unittest.mock import patch

from app.agents.preamble_citations import (
    check_preamble_citations,
    parse_can_cu_citations,
)
from app.schemas.contract import RiskItem

SAMPLE = Path(__file__).resolve().parents[2] / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"


def test_parse_can_cu_from_sample():
    text = SAMPLE.read_text(encoding="utf-8")
    cites = parse_can_cu_citations(text)
    nums = {c.doc_num for c in cites}
    assert "45/2019/QH14" in nums
    assert "91/2015/QH13" in nums
    # Boilerplate "nhu cầu và khả năng" skipped
    assert all("nhu cầu" not in c.raw.lower() for c in cites)
    bl = next(c for c in cites if c.doc_num == "45/2019/QH14")
    assert bl.cited_date is not None
    assert bl.cited_date.isoformat() == "2019-11-20"


def test_preamble_flags_expired_doc():
    text = SAMPLE.read_text(encoding="utf-8")

    def fake_lookup(doc_num: str):
        if doc_num.startswith("45/"):
            return {
                "doc_id": "1",
                "doc_num": "45/2019/QH14",
                "title": "Bộ luật Lao động",
                "doc_type": "Bộ luật",
                "status_flag": 1,
                "eff_flag": "Còn hiệu lực",
                "eff_from": "2021-01-01",
                "eff_to": None,
                "issue_date": "2019-11-20",
                "source_url": None,
            }
        return {
            "doc_id": "2",
            "doc_num": "91/2015/QH13",
            "title": "Bộ luật Dân sự",
            "doc_type": "Bộ luật",
            "status_flag": 2,
            "eff_flag": "Hết hiệu lực toàn bộ",
            "eff_from": "2017-01-01",
            "eff_to": "2020-01-01",
            "issue_date": "2015-11-24",
            "source_url": None,
        }

    with patch("app.agents.preamble_citations._lookup_doc", side_effect=fake_lookup):
        risks = check_preamble_citations(text, as_of_date="15/07/2026")
    assert len(risks) == 1
    assert isinstance(risks[0], RiskItem)
    assert risks[0].severity == "critical"
    assert any("91/2015/QH13" in r for r in (risks[0].reasons or []))
    assert any("hết hiệu lực" in r.lower() for r in (risks[0].reasons or []))


def test_preamble_flags_date_mismatch():
    text = (
        "HỢP ĐỒNG LAO ĐỘNG\n"
        "- Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 01/01/2018;\n"
        "Hôm nay ngày 15 tháng 07 năm 2026\n"
        "Điều 1\n"
    )

    def fake_lookup(doc_num: str):
        return {
            "doc_id": "1",
            "doc_num": "45/2019/QH14",
            "title": "Bộ luật Lao động",
            "doc_type": "Bộ luật",
            "status_flag": 1,
            "eff_flag": "Còn hiệu lực",
            "eff_from": "2021-01-01",
            "eff_to": None,
            "issue_date": "2019-11-20",
            "source_url": None,
        }

    with patch("app.agents.preamble_citations._lookup_doc", side_effect=fake_lookup):
        risks = check_preamble_citations(text, as_of_date="2026-07-15")
    assert risks
    assert any("không khớp issue_date" in r for r in (risks[0].reasons or []))


def test_preamble_ok_when_docs_valid():
    text = SAMPLE.read_text(encoding="utf-8")

    def fake_lookup(doc_num: str):
        if doc_num.startswith("45/"):
            title, issue = "Bộ luật Lao động", "2019-11-20"
        else:
            title, issue = "Bộ luật Dân sự", "2015-11-24"
        return {
            "doc_id": doc_num,
            "doc_num": doc_num,
            "title": title,
            "doc_type": "Bộ luật",
            "status_flag": 1,
            "eff_flag": "Còn hiệu lực",
            "eff_from": "2017-01-01",
            "eff_to": None,
            "issue_date": issue,
            "source_url": None,
        }

    with patch("app.agents.preamble_citations._lookup_doc", side_effect=fake_lookup):
        risks = check_preamble_citations(text, as_of_date="2026-07-15")
    assert risks == []
