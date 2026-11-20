from langchain_core.documents import Document

from app.agents import qa_evidence as evidence
from app.agents.qa_agent import _verified_contract_citations
from app.infrastructure.retrieval.query_rewrite import ground_qa_retrieval_query


def test_topic_index_selects_same_evidence_for_prohibition_and_compliance():
    for body in ("Công ty giữ bản gốc CCCD", "Công ty không giữ bản gốc CCCD"):
        assert evidence.topic_articles(body) == (17,)
    assert evidence.topic_articles("Điều 7. Kỷ luật\nĐi muộn trừ 200.000 đồng") == (127, 102, 124)
    assert evidence.topic_articles("Điều 8. Đào tạo\nNộp chứng chỉ và hoàn phí đào tạo") == (62, 40)
    assert evidence.topic_articles("Điều 40. Tranh chấp\nGiải quyết trong 30 ngày") == (190, 187, 188)
    assert evidence.topic_articles("Điều 2. Thử việc") == (24, 25, 26)
    assert evidence.topic_articles("Giá thuê căn hộ") == ()


def test_article_merge_removes_next_article_and_duplicate_overlap():
    rows = [
        ("Điều 17. Giấy tờ\n2. Bảo đảm bằng tiền.\n## Điều 18. Ký hợp đồng", "x.D17.K2"),
        ("Điều 17. Giấy tờ\n1. Giữ bản chính.\n2. Bảo đảm bằng tiền.", "x.D17.K1"),
    ]
    result = evidence._article_text(rows)
    assert result == "Điều 17. Giấy tờ\n1. Giữ bản chính.\n2. Bảo đảm bằng tiền."
    assert "Điều 18" not in result


def test_exact_statute_evidence_uses_repository_and_actual_paths(monkeypatch):
    lookups = []
    law = {"doc_id": "law", "doc_num": "45/2019/QH14", "status_flag": 1, "eff_from": "2021-01-01"}

    class Repo:
        def find_article_chunks(self, doc_id, regex, limit):
            lookups.append((doc_id, regex, limit))
            return [("Điều 17. Hành vi bị cấm\n1. Giữ bản chính.", "law.C3.D17.K1")]

    monkeypatch.setattr(evidence, "resolve_labor_code_document", lambda date: law)
    monkeypatch.setattr(evidence, "get_legal_chunks", lambda: Repo())
    wrong = Document(page_content="Điều 137. Thai sản", metadata={"path": "law.D137.K3"})
    result = evidence.augment_legal_evidence([wrong], "Giữ bản gốc CCCD của NLĐ", "2026-11-18")
    assert result[0].metadata["path"] == "law.C3.D17.K1"
    assert result[0].metadata["role"] == "topic_anchor"
    assert result[0].metadata["evidence_paths"] == ["law.C3.D17.K1"]
    assert lookups == [("law", r"\.D17(\.|$)", 64)]


def test_earlier_code_and_unavailable_evidence_retain_normal_retrieval(monkeypatch):
    original = [Document(page_content="Luật được truy xuất", metadata={})]
    monkeypatch.setattr(evidence, "resolve_labor_code_document", lambda date: {"doc_num": "10/2012/QH13"})
    assert evidence.augment_legal_evidence(original, "Giấy tờ của NLĐ", "2018-01-01") is original
    monkeypatch.setattr(evidence, "resolve_labor_code_document", lambda date: None)
    assert evidence.augment_legal_evidence(original, "Giấy tờ của NLĐ", None) is original


def test_nonlabor_insurance_question_does_not_inject_labor_code(monkeypatch):
    monkeypatch.setattr(evidence, "resolve_labor_code_document", lambda date: (_ for _ in ()).throw(AssertionError("must not resolve labor code")))
    docs = [Document(page_content="Bảo hiểm ô tô", metadata={})]
    assert evidence.augment_legal_evidence(docs, "Bảo hiểm ô tô có bồi thường không?", None) is docs


def test_renumbering_does_not_change_statute_search_query():
    original = ground_qa_retrieval_query("Điều 4 của hợp đồng có đúng luật không?", [], ["Điều 4. Bảo hiểm\n4.1. Công ty không đóng BHXH."])
    renumbered = ground_qa_retrieval_query("Điều 34 của hợp đồng có đúng luật không?", [], ["Điều 34. Bảo hiểm\n34.1. Công ty không đóng BHXH."])
    assert original == renumbered
    mixed = ground_qa_retrieval_query("Điều 4 hợp đồng và Điều 4 của BLLĐ khác nhau thế nào?", [], ["Điều 4. Bảo hiểm"])
    assert "Điều 4" in mixed


def test_contract_source_types_are_normalized_without_adding_uncited_sources():
    assert _verified_contract_citations([4, "4", "34", "127", None, {}], {"4", "34"}) == ["4", "34"]
    assert _verified_contract_citations([], {"4"}) == []
    assert _verified_contract_citations("4", {"4"}) == []


def test_evidence_review_can_correct_polarity_and_falls_back_on_bad_json():
    import asyncio
    from app.agents.qa_agent import _review_qa_result
    from langchain_core.messages import AIMessage

    draft = {"needs_clarification": False, "answer": "Phải giữ bản chính", "cited_clauses": ["5"]}

    class Model:
        async def ainvoke(self, messages):
            assert "không phải nghĩa vụ" in messages[-1].content
            return AIMessage(content='{"needs_clarification": false, "answer": "Không được giữ bản chính", "cited_clauses": ["5"]}')

    class BrokenModel:
        async def ainvoke(self, messages):
            return AIMessage(content="not json")

    assert "Không được" in asyncio.run(_review_qa_result(draft, "nguồn", Model()))["answer"]
    assert asyncio.run(_review_qa_result(draft, "nguồn", BrokenModel())) is draft
