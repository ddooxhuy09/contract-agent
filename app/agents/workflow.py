import asyncio
import operator
from typing import Annotated, List, Tuple, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from app.schemas.contract import ContractAnalysis, Clause, RiskItem
from app.core.config import logger
from app.agents.clause_parser import parse_contract
from app.agents.risk_flagger import evaluate_clause
from app.agents.llm_client import DEFAULT_PROVIDER

# Caps concurrent LLM calls per analysis run so a large contract doesn't fan out
# dozens of simultaneous requests and hit provider rate limits.
_MAX_CONCURRENT_CLAUSE_CHECKS = 4


class AnalysisState(TypedDict):
    contract_text: str
    contract_id: str
    provider: str
    analysis: ContractAnalysis
    risks: Annotated[List[RiskItem], operator.add]


class ClauseState(TypedDict):
    clause: Clause
    contract_id: str
    provider: str


async def _extract_node(state: AnalysisState) -> dict:
    try:
        analysis = await asyncio.to_thread(parse_contract, state["contract_text"], state["contract_id"])
    except Exception as e:
        logger.error(f"Rule-based parsing failed: {e}, falling back")
        analysis = ContractAnalysis(contract_id=state["contract_id"])
    return {"analysis": analysis}


def _fan_out_clauses(state: AnalysisState):
    clauses = state["analysis"].clauses
    if not clauses:
        return "aggregate"
    return [
        Send("judge_clause", {"clause": c, "contract_id": state["contract_id"], "provider": state["provider"]})
        for c in clauses
    ]


async def _judge_clause_node(state: ClauseState) -> dict:
    clause = state["clause"]
    try:
        risk = await asyncio.to_thread(evaluate_clause, clause, state["provider"])
        return {"risks": [risk] if risk else []}
    except Exception as e:
        logger.error(f"Risk evaluation failed for clause {clause.clause_number} in {state['contract_id']}: {e}")
        return {"risks": []}


def _aggregate_node(state: AnalysisState) -> dict:
    return {}


_graph = StateGraph(AnalysisState)
_graph.add_node("extract", _extract_node)
_graph.add_node("judge_clause", _judge_clause_node)
_graph.add_node("aggregate", _aggregate_node)
_graph.add_edge(START, "extract")
_graph.add_conditional_edges("extract", _fan_out_clauses, ["judge_clause", "aggregate"])
_graph.add_edge("judge_clause", "aggregate")
_graph.add_edge("aggregate", END)
_compiled_graph = _graph.compile()


async def run_analysis_workflow(contract_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> Tuple[ContractAnalysis, List[RiskItem]]:
    logger.info(f"Starting analysis workflow for contract: {contract_id} (provider={provider})")

    result = await _compiled_graph.ainvoke(
        {"contract_text": contract_text, "contract_id": contract_id, "provider": provider, "risks": []},
        config={"max_concurrency": _MAX_CONCURRENT_CLAUSE_CHECKS},
    )

    analysis: ContractAnalysis = result["analysis"]
    risks: List[RiskItem] = result["risks"]
    logger.info(
        f"Analysis workflow completed for contract: {contract_id} "
        f"({len(risks)} risk item(s) across {len(analysis.clauses)} clause(s))"
    )
    return analysis, risks
