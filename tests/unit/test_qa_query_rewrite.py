"""Unit tests for QA / legal query rewrite (follow-up + topic boost)."""

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.labor_red_flags import matching_law_blurbs
from app.infrastructure.retrieval.query_rewrite import (
    augment_qa_retrieval_query,
    expand_legal_topic_query,
)


def test_expand_pregnancy_termination_boosts_blld():
    q = "Điều 4 chấm dứt hợp đồng nếu thông báo mang thai — đúng luật không?"
    out = expand_legal_topic_query(q)
    assert "Bộ luật Lao động" in out
    assert "chấm dứt" in out.lower() or "mang thai" in out.lower()
    assert "cấm" in out.lower()


def test_augment_followup_does_not_keep_nghi_thai_san_conclusion():
    history = [
        HumanMessage(
            content="theo hợp đồng thì khi tôi có thai tôi có được nghỉ thai sản không?"
        ),
        AIMessage(
            content=(
                "Kết luận: Hợp đồng không quy định về việc Người lao động được nghỉ thai sản.\n"
                "Căn cứ:\n"
                "- [Điều 4] quy định NSDLĐ có quyền đơn phương chấm dứt nếu NLĐ thông báo mang thai."
            )
        ),
    ]
    q = "vậy thì có đúng luật không ?"
    out = augment_qa_retrieval_query(q, history)
    # Must not be dominated by "nghỉ thai sản" / BHXH leave framing
    assert "Kết luận" not in out
    assert "đúng luật" in out.lower() or "vậy thì" in out.lower()
    assert "mang thai" in out.lower() or "chấm dứt" in out.lower()
    assert "Bộ luật Lao động" in out
    assert "cấm" in out.lower() or "đơn phương" in out.lower()


def test_matching_blurbs_pregnancy_fire():
    text = (
        "Công ty có quyền đơn phương chấm dứt hợp đồng lao động ngay lập tức "
        "nếu NLĐ thông báo mang thai trong vòng 12 tháng."
    )
    blurbs = matching_law_blurbs(text)
    assert blurbs
    assert any("137" in b or "141" in b or "mang thai" in b.lower() for b in blurbs)
