"""LLM usage collection and the shareable contract report."""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.application.use_cases.report import BuildContractReport, render_markdown
from app.core.usage import UsageCallback, track_usage
from app.domain.entities.contract import Contract
from app.domain.errors import NotFoundError

_USER = UUID("00000000-0000-0000-0000-000000000001")


def _result(input_tokens, output_tokens, model="gemini-test"):
    message = AIMessage(
        content="x",
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens},
        response_metadata={"model_name": model},
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_callback_counts_requests_tokens_and_failures():
    cb = UsageCallback("fallback-model")
    with track_usage() as usage:
        cb.on_llm_end(_result(100, 20))
        cb.on_llm_end(_result(50, 5))
        cb.on_llm_error(RuntimeError("429"))
    s = usage.summary()
    assert (s["requests"], s["failed_requests"]) == (3, 1)
    assert (s["input_tokens"], s["output_tokens"], s["total_tokens"]) == (150, 25, 175)
    assert s["by_model"]["gemini-test"]["requests"] == 2
    assert s["by_model"]["fallback-model"]["failed_requests"] == 1


def test_callback_outside_tracking_is_a_noop():
    UsageCallback().on_llm_end(_result(1, 1))  # must not raise


def test_usage_follows_threads_and_concurrent_tasks():
    cb = UsageCallback()

    async def run():
        with track_usage() as usage:
            await asyncio.gather(*(asyncio.to_thread(cb.on_llm_end, _result(10, 2)) for _ in range(20)))
        return usage.summary()

    s = asyncio.run(run())
    assert (s["requests"], s["total_tokens"]) == (20, 240)


class _Repo:
    def __init__(self, contract):
        self._contract = contract

    def get_owned(self, contract_id, user_id):
        return self._contract


def _contract(analysis, risks):
    return Contract(contract_id="abcd1234-0000", user_id=_USER, filename="hd.docx", file_type=".docx",
                    storage_key="k", analysis=analysis, risks=risks, created_at=datetime(2026, 11, 8, 9, 0))


_USAGE = {"requests": 7, "failed_requests": 1, "input_tokens": 9000, "output_tokens": 1200,
          "total_tokens": 10200, "duration_seconds": 31.4, "by_model": {}}
_RISK = {"clause_ref": "Điều 3", "issue": "Thử việc quá dài", "severity": "critical", "title": "Thử việc vượt mức",
         "legal_basis": "Điều 25 BLLĐ", "actions": ["Giảm xuống 60 ngày"]}


def test_report_collects_findings_and_usage_apart_from_the_analysis():
    analysis = {"clauses": [{"clause_number": "3", "summary": "s"}], "usage": _USAGE,
                "coverage": {"da_kiem": 1, "chua_kiem": 0}}
    report = BuildContractReport(_Repo(_contract(analysis, [_RISK]))).execute("abcd1234-0000", _USER)
    assert report["usage"] == _USAGE
    assert "usage" not in report["analysis"]
    assert report["summary"]["findings_by_severity"] == {"critical": 1, "warning": 0, "ok": 0}
    assert report["contract"]["uploaded_at"].startswith("2026-11-08")


def test_report_requires_an_analysis():
    with pytest.raises(NotFoundError):
        BuildContractReport(_Repo(_contract(None, None))).execute("abcd1234-0000", _USER)
    with pytest.raises(NotFoundError):
        BuildContractReport(_Repo(None)).execute("abcd1234-0000", _USER)


def test_markdown_shows_usage_and_findings():
    analysis = {"clauses": [], "usage": _USAGE}
    md = render_markdown(BuildContractReport(_Repo(_contract(analysis, [_RISK]))).execute("abcd1234-0000", _USER))
    assert "Tổng token | 10,200" in md
    assert "Số lượt request | 7 (lỗi: 1)" in md
    assert "Điều 3 — Thử việc vượt mức" in md
    assert "Giảm xuống 60 ngày" in md


def test_markdown_for_analysis_without_usage_says_so():
    md = render_markdown(BuildContractReport(_Repo(_contract({"clauses": []}, []))).execute("abcd1234-0000", _USER))
    assert "Không có số liệu" in md


def test_usage_reaches_the_use_case_through_langgraph_fan_out():
    """The real mechanism: LangGraph Send fan-out whose nodes call the model from worker threads."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send
    from typing_extensions import TypedDict
    from typing import Annotated
    import operator

    cb = UsageCallback()

    class State(TypedDict):
        done: Annotated[list, operator.add]

    async def work(state):
        await asyncio.to_thread(cb.on_llm_end, _result(10, 3))
        return {"done": [1]}

    g = StateGraph(State)
    g.add_node("work", work)
    g.add_conditional_edges(START, lambda s: [Send("work", {}) for _ in range(5)], ["work"])
    g.add_edge("work", END)
    graph = g.compile()

    async def run():
        with track_usage() as usage:
            await graph.ainvoke({"done": []})
        return usage.summary()

    s = asyncio.run(run())
    assert (s["requests"], s["output_tokens"], s["total_tokens"]) == (5, 15, 65)
