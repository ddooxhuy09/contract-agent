"""Document effectivity checks for citable legal bases."""

from app.agents.effectivity import evaluate_document_effectivity


def test_fully_effective_ok_to_cite():
    row = {
        "doc_num": "45/2019/QH14",
        "status_flag": 1,
        "eff_flag": "Còn hiệu lực",
        "eff_from": "2021-01-01",
        "eff_to": None,
    }
    eff = evaluate_document_effectivity(row, "2026-07-15")
    assert eff.ok_to_cite is True
    assert eff.verified is True
    assert "Đã đối chiếu" in eff.status_label
    assert "Còn hiệu lực" in eff.status_label


def test_expired_not_ok_to_cite():
    row = {
        "doc_num": "10/2012/QH13",
        "status_flag": 2,
        "eff_flag": "Hết hiệu lực toàn bộ",
        "eff_from": "2013-01-01",
        "eff_to": "2021-01-01",
    }
    eff = evaluate_document_effectivity(row, "2026-07-15")
    assert eff.ok_to_cite is False
    assert "Hết hiệu lực" in eff.status_label


def test_eff_to_passed_not_ok():
    row = {
        "doc_num": "19/2014/TT-BLĐTBXH",
        "status_flag": 1,
        "eff_flag": "Còn hiệu lực",
        "eff_from": "2014-01-01",
        "eff_to": "2025-02-15",
    }
    eff = evaluate_document_effectivity(row, "2026-07-15")
    assert eff.ok_to_cite is False
    assert "Hết hiệu lực" in eff.status_label


def test_partial_effect_ok_but_flagged():
    row = {
        "doc_num": "45/2019/QH14",
        "status_flag": 4,
        "eff_flag": "Hết hiệu lực một phần",
        "eff_from": "2021-01-01",
        "eff_to": None,
    }
    eff = evaluate_document_effectivity(row, "15/07/2026")
    assert eff.ok_to_cite is True
    assert "sửa đổi" in eff.status_label.lower() or "một phần" in eff.detail.lower()


def test_missing_row_unverified():
    eff = evaluate_document_effectivity(None, "2026-07-15")
    assert eff.ok_to_cite is False
    assert eff.verified is False
    assert "Chưa đối chiếu" in eff.status_label
