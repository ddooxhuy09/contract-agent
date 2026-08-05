"""Cross-thread long-term memory backed by langgraph's BaseStore (AsyncPostgresStore).

This is the "Memory" counterpart to the per-thread checkpointer history. Thread
history is scoped to a chat thread and gets trimmed by token budget; these entries
live in a *shared store* namespaced per contract and stay readable from ANY thread
for that contract (including fresh conversations or the analysis review threads).

The QA graph persists a rolling buffer of recent Q&A pairs so a later question —
even in a brand-new thread — can reference conclusions from earlier sessions. A
single rolling document per contract keeps ordering deterministic without relying on
store search ranking.
"""

from datetime import datetime, timezone

from langgraph.store.base import BaseStore
from langgraph.store.postgres import AsyncPostgresStore

from app.core.logging import logger

# Keep at most this many Q&A pairs in the rolling per-contract memory document.
_MAX_MEMORY_PAIRS = 5
# Store keys / namespace segments.
_MEMORY_DOC = "qa_memory"
_MEMORY_KEY = "long_term"

_store: BaseStore | None = None


async def init_memory_store(conn) -> None:
    """Build the cross-thread store on the SAME pool the checkpointer uses.

    Must be called during app startup, after the event loop is running. Idempotent.
    """
    global _store
    if _store is not None:
        return
    store = AsyncPostgresStore(conn=conn)
    await store.setup()
    _store = store
    logger.info("LangGraph long-term memory store initialized")


async def close_memory_store() -> None:
    global _store
    _store = None


def get_memory_store() -> BaseStore:
    if _store is None:
        raise RuntimeError("Memory store not initialized; call init_memory_store() during app startup")
    return _store


def _namespace(contract_id: str) -> tuple[str, str, str]:
    return ("contracts", contract_id, _MEMORY_DOC)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pair_to_text(pair: dict) -> str:
    return f"- Hỏi: {pair.get('question', '')}\n  Đã trả lời: {pair.get('answer', '')}"


def _format_memory(pairs: list[dict]) -> str:
    if not pairs:
        return ""
    return "\n".join(_pair_to_text(p) for p in pairs)


async def save_qa_memory(contract_id: str, question: str, answer: str, source_clauses: list[str]) -> None:
    """Append one Q&A pair to the rolling per-contract memory document.

    Resilient by design: any store failure is logged and swallowed so a QA run never
    breaks because the memory layer is down.
    """
    try:
        store = get_memory_store()
        ns = _namespace(contract_id)
        existing = await store.aget(ns, _MEMORY_KEY)
        pairs = list(existing.value.get("pairs", [])) if existing else []
        pairs.append(
            {
                "question": question,
                "answer": answer,
                "source_clauses": source_clauses,
                "created_at": _now_iso(),
            }
        )
        pairs = pairs[-_MAX_MEMORY_PAIRS:]
        await store.aput(ns, _MEMORY_KEY, {"pairs": pairs, "updated_at": _now_iso()})
    except Exception as e:
        logger.warning("save_qa_memory failed for contract %s: %s", contract_id, e)


async def load_qa_memory(contract_id: str, limit: int = _MAX_MEMORY_PAIRS) -> str:
    """Return the formatted recent memory for a contract ("" if none / unavailable)."""
    try:
        store = get_memory_store()
        item = await store.aget(_namespace(contract_id), _MEMORY_KEY)
        pairs = list(item.value.get("pairs", [])) if item else []
        return _format_memory(pairs[-limit:])
    except Exception as e:
        logger.warning("load_qa_memory failed for contract %s: %s", contract_id, e)
        return ""
