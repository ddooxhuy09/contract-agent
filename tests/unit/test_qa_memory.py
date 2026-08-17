"""Tests for Phase E: cross-thread long-term memory (app/agents/memory.py + QA graph).

Verifies the store round-trip and the rolling buffer, plus the QA graph persisting a
successful Q&A pair and injecting it back as context on a later turn. Uses an
InMemoryStore so no DB is needed.
"""

import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

import app.agents.memory as mem
import app.agents.qa_agent as qa


def _strong_contract(query, contract_id, k=None):
    return [
        type(
            "D",
            (),
            {
                "page_content": "Nội dung điều khoản bồi thường.",
                "metadata": {"clause_number": "5", "score": 0.9},
            },
        )()
    ]


class _RecordingModel:
    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    async def ainvoke(self, messages):
        self.prompts.append([m.content for m in messages])
        item = self._responses.pop(0) if self._responses else self._responses[-1:]
        return type("Resp", (), {"content": item})()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    qa._compiled_graph = None
    monkeypatch.setattr(qa, "get_checkpointer", lambda: MemorySaver())
    monkeypatch.setattr(qa, "retrieve_contract", _strong_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    monkeypatch.setattr(qa, "chat_completion", lambda prompt, provider="gemini": "truy vấn pháp lý")
    store = InMemoryStore()
    monkeypatch.setattr(mem, "get_memory_store", lambda: store)
    yield store
    qa._compiled_graph = None


def test_memory_roundtrip_and_rolling(monkeypatch):
    monkeypatch.setattr(mem, "_MAX_MEMORY_PAIRS", 3)
    for i in range(5):
        asyncio.run(mem.save_qa_memory("c-m", f"Hỏi {i}", f"Trả lời {i}", [str(i)]))

    text = asyncio.run(mem.load_qa_memory("c-m"))
    # Rolling buffer keeps only the most recent 3.
    assert "Trả lời 4" in text and "Trả lời 2" in text
    assert "Trả lời 0" not in text
    assert text.index("Trả lời 2") < text.index("Trả lời 3") < text.index("Trả lời 4")
    # Different contract -> no memory.
    assert asyncio.run(mem.load_qa_memory("c-other")) == ""


def test_qa_persists_pair_then_injects_it_next_turn(monkeypatch):
    fake = _RecordingModel(
        [
            '{"needs_clarification": false, "answer": "Điều 5 quy định bồi thường.", "cited_clauses": ["5"]}',
            '{"needs_clarification": false, "answer": "Trả lời lượt 2.", "cited_clauses": ["5"]}',
        ]
    )
    monkeypatch.setattr(qa, "get_chat_model", lambda provider="gemini", **kwargs: fake)

    asyncio.run(qa.answer_question("bồi thường thế nào?", "c-x"))
    stored = asyncio.run(mem.load_qa_memory("c-x"))
    assert "Điều 5 quy định bồi thường." in stored

    asyncio.run(qa.answer_question("giải thích thêm", "c-x"))
    second_prompt = "".join(fake.prompts[1])
    # Cross-turn: the second question's context includes the first pair's memory.
    assert "Điều 5 quy định bồi thường." in second_prompt
    assert "## Ký ức dài hạn" in second_prompt


def test_no_memory_saved_on_clarification(monkeypatch):
    fake = _RecordingModel(
        ['{"needs_clarification": true, "clarification_question": "Bạn hỏi khoản nào?", "answer": "", "cited_clauses": []}']
    )
    monkeypatch.setattr(qa, "get_chat_model", lambda provider="gemini", **kwargs: fake)

    result = asyncio.run(qa.answer_question("hỏi mơ hồ", "c-y"))
    assert result.needs_clarification is True
    assert asyncio.run(mem.load_qa_memory("c-y")) == ""


def test_no_memory_saved_on_refusal(monkeypatch):
    monkeypatch.setattr(qa, "retrieve_contract", lambda query, contract_id, k=None: [])
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])

    result = asyncio.run(qa.answer_question("không có dữ liệu", "c-z"))
    assert result.answer == qa._NO_CONTEXT_ANSWER
    assert asyncio.run(mem.load_qa_memory("c-z")) == ""
