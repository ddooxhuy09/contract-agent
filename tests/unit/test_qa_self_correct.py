"""Tests for the self-correcting RAG loop in app/agents/qa_agent.py.

Builds the QA graph with an in-memory checkpointer and mocked retrieval + LLM so no
DB / network is required. Guards the cycle routing, bounded retries and the
retrieval-weakness rewrite path.
"""

import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver

import app.agents.qa_agent as qa
from app.core.settings import get_settings


@pytest.fixture(autouse=True)
def _isolated_graph(monkeypatch):
    """Compile the QA graph once against an in-memory checkpointer with mocked IO."""
    qa._compiled_graph = None
    monkeypatch.setattr(qa, "get_checkpointer", lambda: MemorySaver())
    monkeypatch.setattr(qa, "retrieve_contract", lambda query, contract_id, k=None: [])
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    monkeypatch.setattr(qa, "chat_completion", lambda prompt, provider="gemini": "truy vấn pháp lý")
    yield
    qa._compiled_graph = None


class _FakeChatModel:
    """Fake ChatGoogleGenerativeAI with a queue of canned .ainvoke responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._last = responses[-1] if responses else ""

    async def ainvoke(self, messages):
        item = self._responses.pop(0) if self._responses else self._last
        return type("Resp", (), {"content": item})


def _install_model(monkeypatch, responses):
    fake = _FakeChatModel(responses)
    monkeypatch.setattr(qa, "get_chat_model", lambda provider="gemini", **kwargs: fake)
    return fake


def test_empty_retrieval_loops_rewrite_then_refusal():
    result = asyncio.run(qa.answer_question("câu hỏi không có dữ liệu", "c-1"))
    assert result.answer == qa._NO_CONTEXT_ANSWER
    assert result.source_clauses == []
    assert result.needs_clarification is False


def test_no_context_uses_two_rewrite_attempts(monkeypatch):
    calls = {"retrieve": 0}

    def counting_contract(query, contract_id, k=None):
        calls["retrieve"] += 1
        return []

    monkeypatch.setattr(qa, "retrieve_contract", counting_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])

    result = asyncio.run(qa.answer_question("hỏi gì đó", "c-2"))
    assert result.answer == qa._NO_CONTEXT_ANSWER
    # 1 initial retrieve + 2 rewrites each re-retrieving, then refusal (bounded).
    assert calls["retrieve"] == 3


def test_weak_context_triggers_rewrite_then_recovers(monkeypatch):
    """Retrieval returns weak-scored docs first, then strong docs after rewrite."""
    sequence = [{"score": 0.3}, {"score": 0.3}, {"score": 0.85}]
    retrieve_calls = {"n": 0}

    def fake_contract(query, contract_id, k=None):
        retrieve_calls["n"] += 1
        doc = sequence[min(retrieve_calls["n"] - 1, len(sequence) - 1)]
        return [
            type(
                "D",
                (),
                {
                    "page_content": "Nội dung điều khoản bồi thường.",
                    "metadata": {"clause_number": "5", "score": doc["score"]},
                },
            )()
        ]

    def fake_legal(query, k=3):
        return []

    monkeypatch.setattr(qa, "retrieve_contract", fake_contract)
    monkeypatch.setattr(qa, "retrieve_legal", fake_legal)
    _install_model(
        monkeypatch,
        ['{"needs_clarification": false, "answer": "Trả lời dựa trên Điều 5.", "cited_clauses": ["5"]}'],
    )

    result = asyncio.run(qa.answer_question("bồi thường thế nào?", "c-3"))
    assert result.answer.startswith("Trả lời dựa trên")
    assert result.source_clauses == ["5"]
    # weak(0.3) -> rewrite -> weak(0.3) -> rewrite -> strong(0.85) -> generate
    assert retrieve_calls["n"] == 3


def test_strong_context_generates_directly(monkeypatch):
    def fake_contract(query, contract_id, k=None):
        return [
            type(
                "D",
                (),
                {
                    "page_content": "Nội dung điều khoản.",
                    "metadata": {"clause_number": "1", "score": 0.9},
                },
            )()
        ]

    monkeypatch.setattr(qa, "retrieve_contract", fake_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    _install_model(
        monkeypatch,
        ['{"needs_clarification": false, "answer": "Kết luận: hợp lệ.", "cited_clauses": ["1"]}'],
    )

    result = asyncio.run(qa.answer_question("hỏi", "c-4"))
    assert result.answer == "Kết luận: hợp lệ."
    assert result.source_clauses == ["1"]


def test_generate_retries_once_on_parse_failure(monkeypatch):
    def fake_contract(query, contract_id, k=None):
        return [
            type(
                "D",
                (),
                {
                    "page_content": "Nội dung.",
                    "metadata": {"clause_number": "2", "score": 0.8},
                },
            )()
        ]

    monkeypatch.setattr(qa, "retrieve_contract", fake_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    _install_model(
        monkeypatch,
        [
            "không phải json",
            '{"needs_clarification": false, "answer": "OK sau khi retry.", "cited_clauses": ["2"]}',
        ],
    )

    result = asyncio.run(qa.answer_question("hỏi", "c-5"))
    assert result.answer == "OK sau khi retry."
    assert result.source_clauses == ["2"]


def test_generate_gives_up_after_budget(monkeypatch):
    def fake_contract(query, contract_id, k=None):
        return [
            type(
                "D",
                (),
                {
                    "page_content": "Nội dung.",
                    "metadata": {"clause_number": "3", "score": 0.8},
                },
            )()
        ]

    monkeypatch.setattr(qa, "retrieve_contract", fake_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    _install_model(monkeypatch, ["không phải json", "cũng không phải json", "vẫn không phải json"])

    result = asyncio.run(qa.answer_question("hỏi", "c-6"))
    assert result.answer == qa._GENERATION_FAILED_ANSWER
    assert result.source_clauses == []


def test_history_excludes_failed_attempts(monkeypatch):
    """A failed generate attempt must not leak into the persisted history."""
    monkeypatch.setattr(
        qa, "retrieve_contract", lambda query, contract_id, k=None: []
    )
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])

    asyncio.run(qa.answer_question("hỏi", "c-7"))
    items = asyncio.run(qa.get_conversation_history("c-7"))
    assert len(items) == 1
    assert items[0].answer == qa._NO_CONTEXT_ANSWER


def test_settings_threshold_used_for_weak_detection():
    assert get_settings().similarity_threshold > 0


def test_state_history_and_rewind(monkeypatch):
    monkeypatch.setattr(qa, "retrieve_contract", lambda query, contract_id, k=None: [])
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])

    asyncio.run(qa.answer_question("hỏi một", "c-8"))
    asyncio.run(qa.answer_question("hỏi hai", "c-8"))

    states = asyncio.run(qa.get_state_history("c-8"))
    assert len(states) >= 1
    first_id = states[0]["checkpoint_id"]
    assert first_id is not None

    snapshot = asyncio.run(qa.rewind_state("c-8", first_id))
    assert snapshot["contract_id"] == "c-8"
    assert snapshot["checkpoint_id"] == first_id

    from app.domain.errors import NotFoundError

    with pytest.raises(NotFoundError):
        asyncio.run(qa.rewind_state("c-8", "không-tồn-tại"))


def test_stream_answer_emits_steps_then_done(monkeypatch):
    import json

    def fake_contract(query, contract_id, k=None):
        return [
            type(
                "D",
                (),
                {
                    "page_content": "Nội dung.",
                    "metadata": {"clause_number": "4", "score": 0.8},
                },
            )()
        ]

    monkeypatch.setattr(qa, "retrieve_contract", fake_contract)
    monkeypatch.setattr(qa, "retrieve_legal", lambda query, k=3: [])
    _install_model(
        monkeypatch,
        ['{"needs_clarification": false, "answer": "Trả lời stream.", "cited_clauses": ["4"]}'],
    )

    async def collect():
        frames = []
        async for frame in qa.stream_answer_events("hỏi", "c-9"):
            frames.append(frame)
        return frames

    frames = asyncio.run(collect())
    joined = "".join(frames)
    # step events for the nodes that ran
    assert "event: step" in joined
    assert "event: done" in joined
    done_data = json.loads(frames[-1].split("data: ", 1)[1].strip())
    assert done_data["answer"] == "Trả lời stream."
    assert done_data["source_clauses"] == ["4"]
