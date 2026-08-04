from typing import Any

from app.agents.llm_client import DEFAULT_PROVIDER
from app.agents.qa_agent import answer_question, get_conversation_history
from app.agents.workflow import run_analysis_workflow


class LangGraphAnalyzePipeline:
    async def run(
        self, full_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER
    ) -> tuple[Any, list[Any]]:
        analysis, risks = await run_analysis_workflow(full_text, contract_id=contract_id, provider=provider)
        return analysis, risks


class LangGraphQaPipeline:
    async def answer(self, contract_id: str, question: str, provider: str = DEFAULT_PROVIDER) -> dict[str, Any]:
        result = await answer_question(question, contract_id, provider)
        return {
            "answer": result.answer,
            "source_clauses": result.source_clauses,
            "contract_id": result.contract_id,
            "needs_clarification": result.needs_clarification,
        }

    async def history(self, contract_id: str) -> list[dict[str, Any]]:
        hist = await get_conversation_history(contract_id)
        return [m.model_dump() for m in hist]
