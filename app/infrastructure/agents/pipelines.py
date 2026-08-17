import functools
from typing import Any, Awaitable, Callable, TypeVar

import psycopg

from app.agents.llm_client import DEFAULT_PROVIDER
from app.agents.qa_agent import (
    answer_question,
    get_conversation_history,
    get_state_history,
    rewind_state,
    stream_answer_events,
)
from app.agents.workflow import (
    resume_analysis_review,
    run_analysis_workflow,
    run_analysis_workflow_review,
)
from app.core.logging import logger

T = TypeVar("T")

_RETRYABLE = (psycopg.OperationalError, psycopg.InterfaceError)


def _retry_on_dropped_connection(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Retry once if the checkpointer's connection died mid-query.

    The pool validates connections on checkout, which covers the common case of
    a restarted Postgres. This is the second line of defence: a connection that
    dies *while* the query is in flight.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await fn(*args, **kwargs)
        except _RETRYABLE as e:
            logger.warning("Retrying %s after dropped DB connection: %s", fn.__name__, e)
            return await fn(*args, **kwargs)

    return wrapper


class LangGraphAnalyzePipeline:
    async def run(
        self, full_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER
    ) -> tuple[Any, list[Any]]:
        analysis, risks = await run_analysis_workflow(full_text, contract_id=contract_id, provider=provider)
        return analysis, risks

    async def run_review(self, full_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> dict[str, Any]:
        return await run_analysis_workflow_review(full_text, contract_id=contract_id, provider=provider)

    async def resume_review(
        self,
        contract_id: str,
        review_id: str,
        approved: bool,
        edits: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await resume_analysis_review(contract_id, review_id, approved, edits)


class LangGraphQaPipeline:
    @_retry_on_dropped_connection
    async def answer(
        self,
        contract_id: str,
        question: str,
        provider: str = DEFAULT_PROVIDER,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        result = await answer_question(question, contract_id, provider, checkpoint_id=checkpoint_id)
        return {
            "answer": result.answer,
            "source_clauses": result.source_clauses,
            "contract_id": result.contract_id,
            "needs_clarification": result.needs_clarification,
        }

    @_retry_on_dropped_connection
    async def history(self, contract_id: str) -> list[dict[str, Any]]:
        hist = await get_conversation_history(contract_id)
        return [m.model_dump() for m in hist]

    @_retry_on_dropped_connection
    async def state_history(self, contract_id: str) -> list[dict[str, Any]]:
        return await get_state_history(contract_id)

    @_retry_on_dropped_connection
    async def rewind(self, contract_id: str, checkpoint_id: str) -> dict[str, Any]:
        return await rewind_state(contract_id, checkpoint_id)

    def stream(
        self,
        contract_id: str,
        question: str,
        provider: str = DEFAULT_PROVIDER,
        checkpoint_id: str | None = None,
    ):
        return stream_answer_events(question, contract_id, provider, checkpoint_id)
