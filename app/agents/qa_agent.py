import asyncio
import json
from datetime import datetime, timezone
from typing import Annotated, AsyncGenerator, List, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, trim_messages
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.agents.checkpointer import get_checkpointer
from app.agents.json_parsing import parse_json_object
from app.agents.llm_client import DEFAULT_PROVIDER, chat_completion, get_chat_model
from app.agents.memory import load_qa_memory, save_qa_memory
from app.core.logging import logger
from app.core.prompts import (
    QA_HUMAN_TEMPLATE,
    QA_QUERY_REWRITE_PROMPT,
    QA_SYSTEM_PROMPT,
)
from app.core.settings import get_settings
from app.domain.errors import NotFoundError
from app.agents.labor_red_flags import matching_law_blurbs
from app.infrastructure.retrieval.query_rewrite import (
    augment_qa_retrieval_query,
    expand_legal_topic_query,
    rewrite_qa_query,
)
from app.schemas.contract import ChatHistoryItem, ChatResponse
from app.vectorstore.retriever import retrieve_contract, retrieve_legal

_NO_CONTEXT_ANSWER = (
    "Không tìm thấy thông tin liên quan trong hợp đồng hoặc kho dữ liệu pháp luật để trả lời câu hỏi này. "
    "Vui lòng đặt câu hỏi cụ thể hơn hoặc liên hệ luật sư để được tư vấn thêm."
)
_GENERATION_FAILED_ANSWER = "Hệ thống gặp lỗi khi xử lý câu trả lời. Vui lòng thử lại câu hỏi."

# How many tokens of prior conversation to feed back as context — the "eviction policy"
# for this agent's memory (analogous to a TokenWindowChatMemory), via LangChain's own
# trim_messages instead of a hand-rolled SQL "last N rows" query.
_MAX_HISTORY_TOKENS = 2000

# Self-correcting retrieval bounds. Up to MAX_RETRIEVAL_ATTEMPTS query rewrites are
# tried (rule-based then, on the last chance, one LLM rewrite) before giving up, so a
# weak first-pass retrieval can recover instead of producing a grounded-sounding guess.
_MAX_RETRIEVAL_ATTEMPTS = 2
# Graph-level retry budget for parsing the LLM answer as JSON (moved out of inline code).
_MAX_GENERATE_RETRIES = 2


class QAState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    contract_id: str
    provider: str
    source_clauses: List[str]
    needs_clarification: bool
    _has_context: bool
    _contract_context: str
    _legal_context: str
    _valid_clause_numbers: List[str]
    # Self-correcting loop bookkeeping (reset each invocation via answer_question).
    query: str
    attempts: int
    generate_attempts: int
    _max_score: float | None
    _parse_ok: bool
    # Cross-thread long-term memory (from app.agents.memory), injected as context.
    _long_term_memory: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_contract_context(docs) -> str:
    if not docs:
        return "Không có dữ liệu hợp đồng liên quan."
    return "\n\n".join(f"[Điều {d.metadata.get('clause_number', '?')}] {d.page_content}" for d in docs)


def _format_legal_context(docs) -> str:
    if not docs:
        return "Không có dữ liệu pháp luật liên quan."
    return "\n\n".join(
        f"[{d.metadata.get('doc_number') or d.metadata.get('title') or 'Nguồn'}] {d.page_content}" for d in docs
    )


def _best_score(docs) -> float | None:
    """Max vector/FTS score across retrieved docs, or None if none carried a score."""
    scores = [
        d.metadata.get("score")
        for d in docs
        if d.metadata and isinstance(d.metadata.get("score"), (int, float))
    ]
    return max(scores) if scores else None


async def _retrieve_node(state: QAState) -> dict:
    question = state.get("query") or state["messages"][-1].content
    history = state["messages"][:-1]
    # Follow-ups like "đúng luật không?" must carry topics (mang thai + chấm dứt),
    # not the prior AI conclusion about "nghỉ thai sản" — that poisoned BHXH retrieval.
    legal_query = augment_qa_retrieval_query(question, history)
    contract_docs = retrieve_contract(question, state["contract_id"])
    legal_docs = retrieve_legal(
        legal_query,
        k=5,
        title=legal_query,
        contract_type="Hợp đồng lao động",
    )
    memory = await load_qa_memory(state["contract_id"])

    contract_ctx = _format_contract_context(contract_docs)[:8000]
    legal_ctx = _format_legal_context(legal_docs)[:6000]
    # Deterministic BLLĐ blurbs when contract/Q match known illegal labor patterns
    # (pregnancy fire, keep CCCD, …) so wrong vector seeds can't blank the answer.
    blurbs = matching_law_blurbs(f"{question}\n{legal_query}\n{contract_ctx}")
    if blurbs:
        legal_ctx = ("\n\n".join(blurbs) + "\n\n" + legal_ctx).strip()[:6000]

    if not contract_docs and not legal_docs and not blurbs:
        # Nothing above the similarity threshold in either source: route straight to
        # the self-correct cycle (rewrite) or refusal, never let the LLM guess.
        return {"_has_context": False, "_max_score": None, "_long_term_memory": memory}

    return {
        "_has_context": True,
        "_max_score": _best_score(contract_docs + legal_docs),
        "_contract_context": contract_ctx,
        "_legal_context": legal_ctx or "Không có dữ liệu pháp luật liên quan.",
        "_valid_clause_numbers": [d.metadata.get("clause_number") for d in contract_docs],
        "_long_term_memory": memory,
    }


def _route_after_retrieve(state: QAState) -> str:
    if state.get("_has_context"):
        max_score = state.get("_max_score")
        # If we couldn't measure a score (e.g. pure GraphRAG hydration) treat it as
        # strong enough and proceed. Otherwise loop on weak hits while attempts remain.
        weak = max_score is not None and max_score < get_settings().similarity_threshold
        if not weak or state.get("attempts", 0) >= _MAX_RETRIEVAL_ATTEMPTS:
            return "generate"
        return "rewrite"
    if state.get("attempts", 0) < _MAX_RETRIEVAL_ATTEMPTS:
        return "rewrite"
    return "refusal"


def _llm_rewrite_query(question: str, provider: str) -> Optional[str]:
    """Bounded LLM query rewrite (plain text, no JSON). None on failure.
    Runs only on the last retrieval attempt, so cost stays capped."""
    prompt = QA_QUERY_REWRITE_PROMPT.format(question=question[:2000])
    try:
        raw = chat_completion(prompt, provider=provider)
        out = (raw or "").strip().strip("`")
        if out and len(out) <= 400:
            return out
    except Exception as e:
        logger.warning("LLM query rewrite failed: %s", e)
    return None


async def _rewrite_query_node(state: QAState) -> dict:
    question = state["messages"][-1].content
    history = state["messages"][:-1]
    attempts = state.get("attempts", 0) + 1

    rewritten = augment_qa_retrieval_query(question, history)
    rewritten = expand_legal_topic_query(rewrite_qa_query(rewritten) or rewritten)
    if attempts >= _MAX_RETRIEVAL_ATTEMPTS:
        llm_q = await asyncio.to_thread(
            _llm_rewrite_query,
            rewritten or question,
            state.get("provider", DEFAULT_PROVIDER),
        )
        if llm_q:
            rewritten = expand_legal_topic_query(llm_q)

    logger.info(
        "QA self-correct rewrite: contract_id=%s attempt=%s query=%r",
        state["contract_id"], attempts, rewritten[:80],
    )
    # Drop any stale context so the next retrieve pass fully recomputes it.
    return {
        "query": rewritten,
        "attempts": attempts,
        "_has_context": False,
        "_contract_context": None,
        "_legal_context": None,
        "_valid_clause_numbers": [],
        "_max_score": None,
    }


def _route_after_generate(state: QAState) -> str:
    if state.get("_parse_ok"):
        return "remember"
    if state.get("generate_attempts", 0) < _MAX_GENERATE_RETRIES:
        return "generate"
    return "finalize"


async def _generate_node(state: QAState) -> dict:
    question = state["messages"][-1].content
    attempts = state.get("generate_attempts", 0) + 1

    # "Memory" fed to the LLM: prior turns trimmed to a token budget, keeping the most
    # recent ones — the current question (last message) is excluded here since it's
    # injected separately below, augmented with this turn's retrieved RAG context.
    history = trim_messages(
        state["messages"][:-1],
        max_tokens=_MAX_HISTORY_TOKENS,
        token_counter="approximate",
        strategy="last",
    )

    human_content = QA_HUMAN_TEMPLATE.format(
        contract_context=state.get("_contract_context", "Không có dữ liệu hợp đồng liên quan."),
        legal_context=state.get("_legal_context", "Không có dữ liệu pháp luật liên quan."),
        long_term_memory=state.get("_long_term_memory") or "Không có ký ức nào từ các phiên trước.",
        question=question,
    )
    prompt_messages = [SystemMessage(content=QA_SYSTEM_PROMPT), *history, HumanMessage(content=human_content)]

    chat_model = get_chat_model(state.get("provider", DEFAULT_PROVIDER), json_mode=True)
    try:
        raw = (await chat_model.ainvoke(prompt_messages)).content
    except Exception as exc:
        logger.error("LLM invoke failed for contract %s, attempt %s: %s", state["contract_id"], attempts, exc)
        return {"generate_attempts": attempts, "_parse_ok": False}
    result = parse_json_object(raw)
    if result is None:
        # Graph-level retry loop handles the retry; do NOT append a message yet so the
        # failed attempt stays out of the persistent history.
        logger.error("QA parse failed for contract %s, attempt %s (graph will retry)", state["contract_id"], attempts)
        return {"generate_attempts": attempts, "_parse_ok": False}

    if result.get("needs_clarification"):
        clarification = (result.get("clarification_question") or "").strip() or _GENERATION_FAILED_ANSWER
        ai_message = AIMessage(
            content=clarification,
            additional_kwargs={"source_clauses": [], "needs_clarification": True, "created_at": _now_iso()},
        )
        return {
            "messages": [ai_message],
            "source_clauses": [],
            "needs_clarification": True,
            "generate_attempts": attempts,
            "_parse_ok": True,
        }

    # Don't trust the model's self-reported citations blindly: only keep clause numbers
    # that actually came back from retrieval, so a hallucinated "Điều 99" can't slip through.
    valid_clause_numbers = set(state.get("_valid_clause_numbers") or [])
    cited_clauses = result.get("cited_clauses") or []
    verified_clauses = [c for c in cited_clauses if c in valid_clause_numbers]
    dropped = set(cited_clauses) - set(verified_clauses)
    if dropped:
        logger.error(f"Contract {state['contract_id']}: dropped unverifiable cited clause(s) {dropped}")

    answer = (result.get("answer") or "").strip() or _GENERATION_FAILED_ANSWER
    ai_message = AIMessage(
        content=answer,
        additional_kwargs={"source_clauses": verified_clauses, "needs_clarification": False, "created_at": _now_iso()},
    )
    return {
        "messages": [ai_message],
        "source_clauses": verified_clauses,
        "needs_clarification": False,
        "generate_attempts": attempts,
        "_parse_ok": True,
    }


async def _refusal_node(state: QAState) -> dict:
    ai_message = AIMessage(
        content=_NO_CONTEXT_ANSWER,
        additional_kwargs={"source_clauses": [], "needs_clarification": False, "created_at": _now_iso()},
    )
    return {"messages": [ai_message], "source_clauses": [], "needs_clarification": False}


async def _remember_node(state: QAState) -> dict:
    """Persist the successful Q&A pair into the cross-thread long-term memory store.

    Only runs after a successfully parsed answer (never after a clarification or a
    failed retry). save_qa_memory is resilient, so a store hiccup cannot break QA.
    """
    if not state.get("_parse_ok"):
        return {}
    messages = state["messages"]
    question = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        "",
    )
    last = messages[-1]
    if isinstance(last, AIMessage) and not last.additional_kwargs.get("needs_clarification"):
        await save_qa_memory(
            state["contract_id"],
            question,
            last.content,
            last.additional_kwargs.get("source_clauses", []),
        )
    return {}


async def _finalize_node(state: QAState) -> dict:
    """Terminal for the generate branch: no-op on success, else emit the
    generation-failed answer once the graph-level retry budget is exhausted."""
    if state.get("_parse_ok"):
        return {}
    ai_message = AIMessage(
        content=_GENERATION_FAILED_ANSWER,
        additional_kwargs={"source_clauses": [], "needs_clarification": False, "created_at": _now_iso()},
    )
    return {"messages": [ai_message], "source_clauses": [], "needs_clarification": False}


_graph_builder = StateGraph(QAState)
_graph_builder.add_node("retrieve", _retrieve_node)
_graph_builder.add_node("rewrite", _rewrite_query_node)
_graph_builder.add_node("generate", _generate_node)
_graph_builder.add_node("refusal", _refusal_node)
_graph_builder.add_node("remember", _remember_node)
_graph_builder.add_node("finalize", _finalize_node)
_graph_builder.add_edge(START, "retrieve")
_graph_builder.add_conditional_edges(
    "retrieve", _route_after_retrieve, {"generate": "generate", "rewrite": "rewrite", "refusal": "refusal"}
)
_graph_builder.add_edge("rewrite", "retrieve")
_graph_builder.add_conditional_edges(
    "generate", _route_after_generate, {"generate": "generate", "remember": "remember", "finalize": "finalize"}
)
_graph_builder.add_edge("refusal", END)
_graph_builder.add_edge("remember", END)
_graph_builder.add_edge("finalize", END)

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        # Deferred: the checkpointer's connection pool is only opened during app startup
        # (needs a running event loop), so the graph can't be compiled at import time.
        _compiled_graph = _graph_builder.compile(checkpointer=get_checkpointer())
    return _compiled_graph


def _qa_input(question: str, contract_id: str, provider: str) -> dict:
    """Fresh per-turn input. Resets transient bookkeeping so a prior turn's attempt
    counters/scores can't leak into this invocation (the thread checkpointer persists
    them between turns)."""
    return {
        "messages": [HumanMessage(content=question)],
        "contract_id": contract_id,
        "provider": provider,
        "query": question,
        "attempts": 0,
        "generate_attempts": 0,
        "source_clauses": [],
        "needs_clarification": False,
        "_has_context": False,
        "_max_score": None,
        "_parse_ok": False,
        "_long_term_memory": "",
    }


def _qa_config(contract_id: str, checkpoint_id: str | None = None) -> dict:
    configurable: dict = {"thread_id": contract_id}
    if checkpoint_id:
        # Time travel: fork the conversation from a past checkpoint so the next
        # question resumes from that exact state instead of the current head.
        configurable["checkpoint_id"] = checkpoint_id
    return {"recursion_limit": 40, "configurable": configurable}


async def answer_question(
    question: str,
    contract_id: str,
    provider: str = DEFAULT_PROVIDER,
    checkpoint_id: str | None = None,
) -> ChatResponse:
    graph = _get_graph()
    result = await graph.ainvoke(
        _qa_input(question, contract_id, provider),
        config=_qa_config(contract_id, checkpoint_id),
    )
    return ChatResponse(
        answer=result["messages"][-1].content,
        source_clauses=result.get("source_clauses", []),
        contract_id=contract_id,
        needs_clarification=result.get("needs_clarification", False),
    )


_STEP_LABELS = {
    "retrieve": "Đang truy hồi dữ liệu hợp đồng & pháp luật",
    "rewrite": "Viết lại truy vấn để tìm chính xác hơn",
    "generate": "Đang tạo câu trả lời",
    "refusal": "Không đủ căn cứ — chuẩn bị câu trả lời",
    "remember": "Ghi nhớ câu hỏi & câu trả lời",
    "finalize": "Hoàn tất",
}


async def stream_answer_events(
    question: str,
    contract_id: str,
    provider: str = DEFAULT_PROVIDER,
    checkpoint_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """SSE frames for the QA graph run.

    Emits a `step` event as each node completes (progressive feedback without a
    second LLM call) and a final `done` event carrying the parsed answer plus
    verified citations. Token-level streaming is intentionally avoided because the
    model's output is a JSON envelope — streaming raw tokens would show the JSON
    structure instead of the prose answer.
    """
    graph = _get_graph()
    async for update in graph.astream(
        _qa_input(question, contract_id, provider),
        config=_qa_config(contract_id, checkpoint_id),
        stream_mode="updates",
    ):
        for node, payload in update.items():
            label = _STEP_LABELS.get(node, f"Đang xử lý ({node})")
            yield f"event: step\ndata: {json.dumps({'node': node, 'label': label}, ensure_ascii=False)}\n\n"

    snapshot = await graph.aget_state({"configurable": {"thread_id": contract_id}})
    messages = snapshot.values.get("messages", []) if snapshot and snapshot.values else []
    final = {"answer": "", "source_clauses": [], "needs_clarification": False}
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            meta = msg.additional_kwargs or {}
            final = {
                "answer": msg.content,
                "source_clauses": meta.get("source_clauses", []),
                "needs_clarification": meta.get("needs_clarification", False),
            }
            break
    yield f"event: done\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"

    if final["answer"] == _GENERATION_FAILED_ANSWER:
        yield f"event: error\ndata: {json.dumps({'message': _GENERATION_FAILED_ANSWER, 'recoverable': True}, ensure_ascii=False)}\n\n"


async def get_state_history(contract_id: str) -> List[dict]:
    """Time-travel debug view: every persisted checkpoint of the chat thread,
    newest-first, with the final message/answer produced at that point."""
    graph = _get_graph()
    config = {"configurable": {"thread_id": contract_id}}
    out: List[dict] = []
    async for state in graph.aget_state_history(config):
        messages = state.values.get("messages", [])
        last = messages[-1] if messages else None
        is_ai = isinstance(last, AIMessage)
        out.append(
            {
                "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
                "next": list(state.next) if state.next else [],
                "message_count": len(messages),
                "answer": last.content if is_ai else "",
                "source_clauses": last.additional_kwargs.get("source_clauses", []) if is_ai else [],
                "needs_clarification": last.additional_kwargs.get("needs_clarification", False) if is_ai else False,
            }
        )
    return out


async def rewind_state(contract_id: str, checkpoint_id: str) -> dict:
    """Validate a checkpoint belongs to this thread and return its snapshot.

    Callers pass the returned checkpoint_id into a subsequent answer_question to
    actually resume from it (LangGraph forks a new branch at that snapshot).
    """
    states = await get_state_history(contract_id)
    for state in states:
        if state["checkpoint_id"] == checkpoint_id:
            return {**state, "contract_id": contract_id}
    raise NotFoundError(f"checkpoint {checkpoint_id} not found for contract {contract_id}")


async def get_conversation_history(contract_id: str) -> List[ChatHistoryItem]:
    """Reconstruct the UI-facing history (question/answer pairs) from the checkpointer's
    persisted message list — the "History" side of the memory-vs-history distinction,
    as opposed to the trimmed "Memory" that _generate_node feeds back to the LLM.
    """
    graph = _get_graph()
    snapshot = await graph.aget_state({"configurable": {"thread_id": contract_id}})
    messages = snapshot.values.get("messages", []) if snapshot and snapshot.values else []

    items: List[ChatHistoryItem] = []
    pending_question: Optional[str] = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            pending_question = msg.content
        elif isinstance(msg, AIMessage) and pending_question is not None:
            meta = msg.additional_kwargs
            items.append(ChatHistoryItem(
                question=pending_question,
                answer=msg.content,
                source_clauses=meta.get("source_clauses", []),
                needs_clarification=meta.get("needs_clarification", False),
                created_at=meta.get("created_at", ""),
            ))
            pending_question = None
    return items