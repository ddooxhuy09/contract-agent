"""The red-flag scan skips negated matches («không giữ bản gốc…») but keeps real violations."""

import pytest

from app.agents.labor_red_flags import _FLAGS, _violates, check_labor_red_flags, revise_clause_text

BY_KEY = {f.key: f for f in _FLAGS}


def _contract(clause: str) -> str:
    return ("HỢP ĐỒNG LAO ĐỘNG\n\nĐiều 1. Công việc\n1.1. Chuyên viên kinh doanh, làm việc tại Hà Nội.\n\n"
            f"Điều 2. Nội dung kiểm tra\n{clause}\n\nĐiều 3. Chung\n3.1. Lập thành 02 bản.\n")


def _keys(text: str) -> set[str]:
    return {f.key for item in check_labor_red_flags(text, None) for f in (item.findings or [])}


@pytest.mark.parametrize("key, text", [
    ("retain_id_papers", "Công ty không giữ bản gốc CCCD của NLĐ."),
    ("no_bhxh", "Công ty không được thỏa thuận không đóng BHXH với NLĐ."),
    ("fine_deduct_wage", "Công ty không áp dụng hình thức kỷ luật phạt tiền."),
    ("ot_unpaid", "Công ty nghiêm cấm mọi hành vi không trả lương làm thêm giờ."),
    ("terminate_pregnancy", "Công ty không được đơn phương chấm dứt hợp đồng vì NLĐ mang thai."),
])
def test_negated_match_is_not_a_violation(key, text):
    assert not _violates(BY_KEY[key], text)
    assert key not in _keys(_contract(f"2.1. {text}"))


@pytest.mark.parametrize("key, text", [
    ("retain_id_papers", "NLĐ bàn giao bản gốc Căn cước công dân cho Công ty giữ."),
    ("no_bhxh", "Công ty không đóng BHXH cho NLĐ."),
    ("fine_deduct_wage", "Hình thức kỷ luật phạt tiền, khấu trừ trực tiếp vào tiền lương."),
    ("ban_lawsuit", "NLĐ không được khởi kiện ra Tòa án."),
])
def test_real_violation_still_fires(key, text):
    assert _violates(BY_KEY[key], text)
    assert key in _keys(_contract(f"2.1. {text}"))


def test_negation_in_an_earlier_sentence_does_not_hide_a_violation():
    text = "Công ty không thu tiền cọc.\nCông ty giữ bản gốc CCCD của NLĐ."
    assert "retain_id_papers" in _keys(_contract(f"2.1. {text}"))


def test_only_the_violating_sentence_is_reported_and_rewritten():
    clause = "2.1. Công ty không giữ bản gốc bằng cấp của NLĐ. 2.2. Công ty không đóng BHXH cho NLĐ."
    items = [i for i in check_labor_red_flags(_contract(clause), None)]
    assert {f.key for i in items for f in i.findings} == {"no_bhxh"}
    violated = " ".join(v for i in items for f in i.findings for v in [f.violated_text or ""])
    assert "không đóng BHXH" in violated and "bản gốc" not in violated
    revised = revise_clause_text(clause, ["no_bhxh", "retain_id_papers"])
    assert revised is not None and "Công ty không giữ bản gốc bằng cấp của NLĐ" in revised and "không đóng BHXH" not in revised
