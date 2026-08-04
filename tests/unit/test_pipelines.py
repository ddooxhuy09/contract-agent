"""Regression tests for LangGraphAnalyzePipeline / LangGraphQaPipeline adapters.

These guard against W-001 (swapped argument order) and W-002 (accessing
``.messages`` on the list returned by ``get_conversation_history``) by mocking
the underlying qa_agent functions — no DB, checkpointer or LLM required.
"""

import asyncio

from app.agents.llm_client import DEFAULT_PROVIDER
from app.infrastructure.agents.pipelines import LangGraphQaPipeline
from app.schemas.contract import ChatHistoryItem, ChatResponse


def test_answer_passes_arguments_in_signature_order(monkeypatch):
    captured = {}

    async def fake_answer_question(question: str, contract_id: str, provider: str = DEFAULT_PROVIDER):
        captured["question"] = question
        captured["contract_id"] = contract_id
        captured["provider"] = provider
        return ChatResponse(
            answer="Câu trả lời",
            source_clauses=["Điều 5"],
            contract_id=contract_id,
            needs_clarification=False,
        )

    monkeypatch.setattr("app.infrastructure.agents.pipelines.answer_question", fake_answer_question)

    result = asyncio.run(LangGraphQaPipeline().answer("contract-uuid", "Bồi thường thế nào?"))

    assert captured == {
        "question": "Bồi thường thế nào?",
        "contract_id": "contract-uuid",
        "provider": DEFAULT_PROVIDER,
    }
    assert result == {
        "answer": "Câu trả lời",
        "source_clauses": ["Điều 5"],
        "contract_id": "contract-uuid",
        "needs_clarification": False,
    }


def test_history_iterates_returned_list(monkeypatch):
    item = ChatHistoryItem(
        question="Q1",
        answer="A1",
        source_clauses=["Điều 1"],
        needs_clarification=False,
        created_at="2026-08-02T00:00:00+00:00",
    )

    async def fake_get_conversation_history(contract_id: str):
        assert contract_id == "contract-uuid"
        return [item]

    monkeypatch.setattr(
        "app.infrastructure.agents.pipelines.get_conversation_history",
        fake_get_conversation_history,
    )

    result = asyncio.run(LangGraphQaPipeline().history("contract-uuid"))

    assert result == [
        {
            "question": "Q1",
            "answer": "A1",
            "source_clauses": ["Điều 1"],
            "needs_clarification": False,
            "created_at": "2026-08-02T00:00:00+00:00",
        }
    ]
