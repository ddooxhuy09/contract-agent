from datetime import datetime, timezone
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, trim_messages
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.agents.checkpointer import get_checkpointer
from app.agents.json_parsing import parse_json_object
from app.agents.llm_client import DEFAULT_PROVIDER, get_chat_model
from app.core.logging import logger
from app.core.prompts import QA_HUMAN_TEMPLATE, QA_SYSTEM_PROMPT
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


async def _retrieve_node(state: QAState) -> dict:
    question = state["messages"][-1].content
    contract_docs = retrieve_contract(question, state["contract_id"])
    legal_docs = retrieve_legal(question, k=3)

    if not contract_docs and not legal_docs:
        # Nothing above the similarity threshold in either source: route straight to
        # refusal instead of letting the LLM guess an answer with no grounding.
        return {"_has_context": False}

    return {
        "_has_context": True,
        "_contract_context": _format_contract_context(contract_docs)[:8000],
        "_legal_context": _format_legal_context(legal_docs)[:3000],
        "_valid_clause_numbers": [d.metadata.get("clause_number") for d in contract_docs],
    }


def _route_after_retrieve(state: QAState) -> str:
    return "generate" if state.get("_has_context") else "refusal"


async def _refusal_node(state: QAState) -> dict:
    ai_message = AIMessage(
        content=_NO_CONTEXT_ANSWER,
        additional_kwargs={"source_clauses": [], "needs_clarification": False, "created_at": _now_iso()},
    )
    return {"messages": [ai_message], "source_clauses": [], "needs_clarification": False}


async def _generate_node(state: QAState) -> dict:
    question = state["messages"][-1].content

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
        contract_context=state["_contract_context"],
        legal_context=state["_legal_context"],
        question=question,
    )
    prompt_messages = [SystemMessage(content=QA_SYSTEM_PROMPT), *history, HumanMessage(content=human_content)]

    chat_model = get_chat_model(state.get("provider", DEFAULT_PROVIDER))
    raw = (await chat_model.ainvoke(prompt_messages)).content
    result = parse_json_object(raw)
    if result is None:
        logger.error(f"Failed to parse QA output for contract {state['contract_id']}, retrying once")
        raw = (await chat_model.ainvoke(prompt_messages)).content
        result = parse_json_object(raw)

    if result is None:
        logger.error(f"Contract {state['contract_id']}: QA output still unparsable after retry")
        ai_message = AIMessage(
            content=_GENERATION_FAILED_ANSWER,
            additional_kwargs={"source_clauses": [], "needs_clarification": False, "created_at": _now_iso()},
        )
        return {"messages": [ai_message], "source_clauses": [], "needs_clarification": False}

    if result.get("needs_clarification"):
        clarification = (result.get("clarification_question") or "").strip() or _GENERATION_FAILED_ANSWER
        ai_message = AIMessage(
            content=clarification,
            additional_kwargs={"source_clauses": [], "needs_clarification": True, "created_at": _now_iso()},
        )
        return {"messages": [ai_message], "source_clauses": [], "needs_clarification": True}

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
    return {"messages": [ai_message], "source_clauses": verified_clauses, "needs_clarification": False}


_graph_builder = StateGraph(QAState)
_graph_builder.add_node("retrieve", _retrieve_node)
_graph_builder.add_node("generate", _generate_node)
_graph_builder.add_node("refusal", _refusal_node)
_graph_builder.add_edge(START, "retrieve")
_graph_builder.add_conditional_edges("retrieve", _route_after_retrieve, {"generate": "generate", "refusal": "refusal"})
_graph_builder.add_edge("generate", END)
_graph_builder.add_edge("refusal", END)

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        # Deferred: the checkpointer's connection pool is only opened during app startup
        # (needs a running event loop), so the graph can't be compiled at import time.
        _compiled_graph = _graph_builder.compile(checkpointer=get_checkpointer())
    return _compiled_graph


async def answer_question(question: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> ChatResponse:
    graph = _get_graph()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)], "contract_id": contract_id, "provider": provider},
        config={"configurable": {"thread_id": contract_id}},
    )
    return ChatResponse(
        answer=result["messages"][-1].content,
        source_clauses=result.get("source_clauses", []),
        contract_id=contract_id,
        needs_clarification=result.get("needs_clarification", False),
    )


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
