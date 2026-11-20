import asyncio

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from app.agents import qa_agent as qa
from app.infrastructure.retrieval.query_rewrite import (
    augment_qa_retrieval_query,
    contract_clause_references,
    ground_qa_retrieval_query,
)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Điều 4 của hợp đồng có trái pháp luật lao động không?", ["4"]),
        ("điều 24 có đúng luật không?", ["24"]),
        ("Đối chiếu Điều 4 và Điều 7 của hợp đồng", ["4", "7"]),
        ("Điều 98 Bộ luật Lao động quy định gì?", []),
        ("Điều 98 của BLLĐ và Điều 4 hợp đồng có mâu thuẫn không?", ["4"]),
        ("Điều 2 Luật BHXH và Điều 7 Nghị định 145", []),
        ("Hợp đồng có rủi ro không?", []),
    ],
)
def test_contract_reference_is_not_statute_reference(question, expected):
    assert contract_clause_references(question) == expected


def test_legal_query_preserves_clause_evidence_and_bounds_length():
    content = "Điều 24. Bảo hiểm. Công ty không đóng bảo hiểm xã hội bắt buộc."
    query = ground_qa_retrieval_query("Điều 24 có trái luật không?", [], [content * 100])
    assert "không đóng bảo hiểm xã hội" in query
    assert len(query) <= 1600


def test_topic_question_without_clause_keeps_original_query():
    question = "Công ty có được giữ bản gốc CCCD không?"
    assert ground_qa_retrieval_query(question, [], []) == augment_qa_retrieval_query(question, [])


def test_referenced_clause_is_retrieved_for_this_contract_and_used_for_legal_search(monkeypatch):
    lookups, legal_calls = [], []

    class Repo:
        def get_text_by_clause(self, contract_id, number):
            lookups.append((contract_id, number))
            if number == "1":
                return None
            return "Điều 24. Bảo hiểm. Công ty không đóng bảo hiểm xã hội bắt buộc."

    async def no_memory(_):
        return ""

    def legal_search(query, **kwargs):
        legal_calls.append((query, kwargs))
        return []

    monkeypatch.setattr(qa, "get_contract_chunks", lambda: Repo())
    monkeypatch.setattr(qa, "retrieve_contract", lambda *a: [
        Document(page_content="Điều 1. Thông tin các bên", metadata={"clause_number": "1", "score": 0.9}),
    ])
    monkeypatch.setattr(qa, "retrieve_legal", legal_search)
    monkeypatch.setattr(qa, "load_qa_memory", no_memory)
    question = "Điều 24 của hợp đồng có trái luật không?"
    result = asyncio.run(qa._retrieve_node({
        "messages": [HumanMessage(content=question)], "contract_id": "owned-contract",
        "as_of_date": "2026-11-18",
    }))
    assert lookups == [("owned-contract", "24"), ("owned-contract", "1")]
    assert "24" in result["_valid_clause_numbers"]
    assert "không đóng bảo hiểm xã hội" in legal_calls[0][0]
    assert legal_calls[0][1]["as_of_date"] == "2026-11-18"
    assert "Thông tin các bên" not in legal_calls[0][0]


def test_missing_reference_does_not_invent_contract_evidence(monkeypatch):
    class Repo:
        def get_text_by_clause(self, contract_id, number):
            return None

    doc = Document(page_content="Điều 1. Thông tin các bên", metadata={"clause_number": "1"})
    monkeypatch.setattr(qa, "get_contract_chunks", lambda: Repo())
    monkeypatch.setattr(qa, "retrieve_contract", lambda *a: [doc])
    assert qa._retrieve_contract_docs("Điều 99 hợp đồng có trái luật không?", "c") == [doc]


def test_statute_question_does_not_lookup_same_number_in_contract(monkeypatch):
    monkeypatch.setattr(qa, "get_contract_chunks", lambda: pytest.fail("statute reference is not contract lookup"))
    monkeypatch.setattr(qa, "retrieve_contract", lambda *a: [])
    assert qa._retrieve_contract_docs("Điều 98 Bộ luật Lao động quy định gì?", "c") == []
