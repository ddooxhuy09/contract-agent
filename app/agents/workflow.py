import asyncio
import operator
import uuid
from typing import Annotated, List, Tuple, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Send, interrupt

from app.schemas.contract import ContractAnalysis, Clause, RiskItem
from app.core.logging import logger
from app.agents.clause_parser import parse_contract
from app.agents.risk_flagger import evaluate_clause
from app.agents.llm_client import DEFAULT_PROVIDER

# Caps concurrent LLM calls per analysis run so a large contract doesn't fan out
# dozens of simultaneous requests and hit provider rate limits.
_MAX_CONCURRENT_CLAUSE_CHECKS = 4
# Graph-level retry budgets. `extract` loops back onto itself on *exception*
# (transient network / rate-limit errors the inline code does not retry), then gives
# up gracefully. judge_clause retries internally because Send-spawned branches lose
# their payload on a graph-edge cycle.
_MAX_EXTRACT_RETRIES = 2
_MAX_JUDGE_RETRIES = 2


class AnalysisState(TypedDict):
    contract_text: str
    contract_id: str
    provider: str
    analysis: ContractAnalysis | None
    risks: Annotated[List[RiskItem], operator.add]
    attempts: int
    _extract_failed: bool
    # Human-in-the-loop (review) bookkeeping.
    review_mode: bool
    _approved: bool
    _edited_risks: list[dict]
    # Supervisor bookkeeping: which subgraph to run next.
    _plan: str
    _extract_started: bool
    _evaluated: bool


class ClauseState(TypedDict):
    clause: Clause
    contract_id: str
    provider: str
    contract_type: str | None
    as_of_date: str | None
    job_context: str | None


# Output schemas for the nested subgraphs. Limiting what each subgraph writes back
# to the parent state is REQUIRED: without it, a subgraph echoes every channel it
# received as output, and channels with a reducer (e.g. `risks` uses operator.add)
# get re-applied on the resume path after an interrupt -> duplicated risks.
class _ExtractOutput(TypedDict):
    analysis: ContractAnalysis | None
    attempts: int
    _extract_failed: bool


class _EvaluateOutput(TypedDict):
    risks: List[RiskItem]


class _ReviewOutput(TypedDict):
    _approved: bool
    _edited_risks: list[dict] | None


async def _extract_node(state: AnalysisState) -> dict:
    attempts = state.get("attempts", 0) + 1
    try:
        analysis = await asyncio.to_thread(parse_contract, state["contract_text"], state["contract_id"], state["provider"])
        logger.info(f"Extract done: contract_id={state['contract_id']} clause_count={len(analysis.clauses)}")
        return {"analysis": analysis, "attempts": attempts, "_extract_failed": False}
    except Exception as e:
        logger.error(f"Extract failed: contract_id={state['contract_id']} error={e} (attempt {attempts})")
        return {"analysis": None, "attempts": attempts, "_extract_failed": True}


async def _judge_clause_node(state: ClauseState) -> dict:
    clause = state["clause"]
    logger.info(f"Judging clause: contract_id={state['contract_id']} clause_number={clause.clause_number}")
    # Judge branches are spawned via Send, so a graph-edge retry loop would lose the
    # per-clause payload. Retry on exception inside the node instead (initial attempt
    # + up to _MAX_JUDGE_RETRIES), so transient network/rate-limit errors don't
    # silently drop the clause.
    for attempt in range(1, _MAX_JUDGE_RETRIES + 2):
        try:
            risk = await asyncio.to_thread(
                evaluate_clause,
                clause,
                state["provider"],
                contract_id=state["contract_id"],
                contract_type=state.get("contract_type"),
                as_of_date=state.get("as_of_date"),
                job_context=state.get("job_context"),
            )
            if risk:
                logger.info("Judge result: contract_id=%s clause=%s severity=%s issue=%s",
                    state["contract_id"], clause.clause_number, risk.severity,
                    (risk.issue or "")[:100])
            else:
                logger.info("Judge result: contract_id=%s clause=%s severity=ok (no issue)",
                    state["contract_id"], clause.clause_number)
            return {"risks": [risk] if risk else []}
        except Exception as e:
            logger.error(
                f"Judge failed: contract_id={state['contract_id']} clause_number={clause.clause_number} error={e} (attempt {attempt}/{_MAX_JUDGE_RETRIES + 1})"
            )
    return {"risks": []}


def _aggregate_node(state: AnalysisState) -> dict:
    """After per-clause judging: HĐLĐ red-flags + completeness + preamble «Căn cứ»."""
    from app.agents.labor_completeness import check_labor_completeness
    from app.agents.labor_red_flags import check_labor_red_flags
    from app.agents.preamble_citations import check_preamble_citations

    analysis = state.get("analysis")
    text = state.get("contract_text") or ""
    if analysis is None and not text:
        return {}
    eff = None
    if analysis is not None:
        eff = analysis.execution_date or analysis.start_date
    as_of = str(eff) if eff else None
    extra: list = []
    extra.extend(check_labor_red_flags(text, analysis, as_of_date=as_of))
    extra.extend(check_labor_completeness(text, analysis, as_of_date=as_of))
    extra.extend(check_preamble_citations(text, as_of_date=as_of))
    return {"risks": extra} if extra else {}


async def _review_node(state: AnalysisState) -> dict:
    """Human-in-the-loop gate: pauses after aggregation so a person can inspect /
    edit the flagged risks before they are persisted. No-op unless review_mode."""
    if not state.get("review_mode"):
        return {}
    analysis = state.get("analysis")
    payload = {
        "contract_id": state["contract_id"],
        "draft_analysis": analysis.model_dump() if analysis is not None else None,
        "draft_risks": [r.model_dump() if hasattr(r, "model_dump") else r for r in state.get("risks", [])],
    }
    decision = interrupt(payload)
    edits = decision.get("edits")
    return {
        "_approved": bool(decision.get("approved", False)),
        # Only a non-empty list replaces the AI draft; None keeps it untouched.
        "_edited_risks": edits if isinstance(edits, list) and edits else None,
    }


# ---------------------------------------------------------------------------
# Phase D — supervisor + subgraphs.
#
# The analysis pipeline is split into three reusable subgraphs (extract /
# evaluate / review), orchestrated by a single `supervisor` node that decides,
# from the current state, which subgraph to run next:
#
#   START -> supervisor -> extract  (retry on transient failure while budget left)
#   extract -> supervisor -> evaluate  (per-clause fan-out via Send)
#   evaluate -> supervisor -> review   (HITL gate, only when review_mode=True)
#   review -> END
#
# Each subgraph is compiled standalone (no checkpointer) and, when nested under
# the supervisor graph, inherits the parent's checkpointer. LangGraph nests
# compiled graphs as nodes: the parent state must expose every input AND output
# channel of each subgraph (AnalysisState is the union), which is why `_plan`
# and `_extract_started` live there too.
# ---------------------------------------------------------------------------

def _supervisor_node(state: AnalysisState) -> dict:
    """Central router: picks the next subgraph from the current state."""
    if not state.get("_extract_started"):
        return {"_plan": "extract", "_extract_started": True}
    # Extract failed transiently and we still have retry budget -> retry.
    if state.get("_extract_failed") and state.get("attempts", 0) <= _MAX_EXTRACT_RETRIES:
        return {"_plan": "extract"}
    analysis = state.get("analysis")
    clauses = (analysis.clauses if analysis is not None else []) or []
    # Clauses to judge that have not been evaluated yet -> fan out once.
    if clauses and not state.get("_evaluated"):
        logger.info(f"Judge fan-out: contract_id={state['contract_id']} clause_count={len(clauses)} max_concurrency={_MAX_CONCURRENT_CLAUSE_CHECKS}")
        return {"_plan": "evaluate", "_evaluated": True}
    if not clauses:
        logger.info(f"No clauses to judge: contract_id={state['contract_id']}")
    # Everything evaluated (or nothing to judge): pause for review if requested.
    if state.get("review_mode"):
        return {"_plan": "review"}
    return {"_plan": "end"}


def _build_extract_subgraph():
    """Subgraph: clause extraction with graceful failure (retry is supervised)."""
    g = StateGraph(AnalysisState, output_schema=_ExtractOutput)
    g.add_node("extract", _extract_node)
    g.add_edge(START, "extract")
    g.add_edge("extract", END)
    return g.compile()


def _build_evaluate_subgraph():
    """Subgraph: per-clause risk evaluation (map-reduce via Send)."""
    def _fan_out(state: AnalysisState):
        from app.agents.labor_completeness import extract_job_context

        clauses = (state.get("analysis").clauses if state.get("analysis") is not None else []) or []
        contract_type = state.get("analysis").contract_type if state.get("analysis") is not None else None
        analysis = state.get("analysis")
        eff_date = analysis.execution_date or analysis.start_date if analysis is not None else None
        as_of = str(eff_date) if eff_date else None
        job_ctx = extract_job_context(state.get("contract_text") or "", analysis)
        return [
            Send(
                "judge_clause",
                {
                    "clause": c,
                    "contract_id": state["contract_id"],
                    "provider": state["provider"],
                    "contract_type": contract_type,
                    "as_of_date": as_of,
                    "job_context": job_ctx,
                },
            )
            for c in clauses
        ]

    g = StateGraph(AnalysisState, output_schema=_EvaluateOutput)
    g.add_node("judge_clause", _judge_clause_node)
    g.add_node("aggregate", _aggregate_node)
    g.add_conditional_edges(START, _fan_out, ["judge_clause"])
    g.add_edge("judge_clause", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()


def _build_review_subgraph():
    """Subgraph: human-in-the-loop gate (interrupt + resume)."""
    g = StateGraph(AnalysisState, output_schema=_ReviewOutput)
    g.add_node("review", _review_node)
    g.add_edge(START, "review")
    g.add_edge("review", END)
    return g.compile()


_extract_subgraph = _build_extract_subgraph()
_evaluate_subgraph = _build_evaluate_subgraph()
_review_subgraph = _build_review_subgraph()


def _route_by_plan(state: AnalysisState) -> str:
    return state.get("_plan", "end")


_supervisor_graph = StateGraph(AnalysisState)
_supervisor_graph.add_node("supervisor", _supervisor_node)
_supervisor_graph.add_node("extract", _extract_subgraph)
_supervisor_graph.add_node("evaluate", _evaluate_subgraph)
_supervisor_graph.add_node("review", _review_subgraph)
_supervisor_graph.add_edge(START, "supervisor")
_supervisor_graph.add_conditional_edges(
    "supervisor", _route_by_plan,
    {"extract": "extract", "evaluate": "evaluate", "review": "review", "end": END},
)
_supervisor_graph.add_edge("extract", "supervisor")
_supervisor_graph.add_edge("evaluate", "supervisor")
_supervisor_graph.add_edge("review", END)

_compiled_graph = _supervisor_graph.compile()
_review_graph = None


def _get_review_graph():
    """Compiled WITH a checkpointer so interrupt()/resume work. Deferred because the
    checkpointer's connection pool opens during app startup, not at import time."""
    global _review_graph
    if _review_graph is None:
        from app.agents.checkpointer import get_checkpointer

        _review_graph = _supervisor_graph.compile(checkpointer=get_checkpointer())
    return _review_graph


def _analysis_input(contract_text: str, contract_id: str, provider: str, review_mode: bool = False) -> dict:
    return {
        "contract_text": contract_text,
        "contract_id": contract_id,
        "provider": provider,
        "risks": [],
        "attempts": 0,
        "_extract_failed": False,
        "review_mode": review_mode,
        "_approved": False,
        "_edited_risks": None,
        "_plan": "extract",
        "_extract_started": False,
        "_evaluated": False,
    }


def _run_config(thread_id: str | None = None) -> dict:
    config = {
        "max_concurrency": _MAX_CONCURRENT_CLAUSE_CHECKS,
        # Fan-out of judge_clause + retry loops easily exceeds the default 25.
        "recursion_limit": 300,
    }
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}
    return config


async def run_analysis_workflow(contract_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> Tuple[ContractAnalysis, List[RiskItem]]:
    logger.info(f"Starting analysis workflow for contract: {contract_id} (provider={provider})")

    result = await _compiled_graph.ainvoke(
        _analysis_input(contract_text, contract_id, provider),
        config=_run_config(),
    )

    analysis: ContractAnalysis = result.get("analysis") or ContractAnalysis(contract_id=contract_id)
    risks: List[RiskItem] = result["risks"]
    logger.info(
        f"Analysis workflow completed for contract: {contract_id} "
        f"({len(risks)} risk item(s) across {len(analysis.clauses)} clause(s))"
    )
    return analysis, risks


async def run_analysis_workflow_review(
    contract_text: str,
    contract_id: str,
    provider: str = DEFAULT_PROVIDER,
) -> dict:
    """Run analysis in review mode: pauses at the review gate and returns the draft
    (analysis + risks) plus a review_id used to resume. Nothing is persisted yet."""
    review_id = str(uuid.uuid4())
    thread_id = f"analysis:{review_id}"
    graph = _get_review_graph()
    result = await graph.ainvoke(
        _analysis_input(contract_text, contract_id, provider, review_mode=True),
        config=_run_config(thread_id),
    )
    interrupts = result.get("__interrupt__")
    if not interrupts:
        raise RuntimeError(f"analysis did not pause for review: contract_id={contract_id}")
    payload = interrupts[0].value
    logger.info(f"Analysis paused for review: contract_id={contract_id} review_id={review_id} risks={len(payload.get('draft_risks', []))}")
    return {
        "review_id": review_id,
        "contract_id": contract_id,
        "draft_analysis": payload.get("draft_analysis"),
        "draft_risks": payload.get("draft_risks"),
    }


async def resume_analysis_review(
    contract_id: str,
    review_id: str,
    approved: bool,
    edits: list[dict] | None = None,
) -> dict:
    """Resume a paused analysis. `approved=False` marks it rejected; `edits` may carry
    a human-corrected risk list that replaces the AI draft."""
    thread_id = f"analysis:{review_id}"
    graph = _get_review_graph()
    result = await graph.ainvoke(
        Command(resume={"approved": approved, "edits": edits or []}),
        config=_run_config(thread_id),
    )
    if result.get("contract_id") != contract_id:
        raise RuntimeError(f"review {review_id} belongs to a different contract")
    analysis = result.get("analysis") or ContractAnalysis(contract_id=contract_id)
    risks = result["risks"]
    if result.get("_edited_risks") is not None:
        risks = [RiskItem(**r) for r in result["_edited_risks"]]
    approved_flag = bool(result.get("_approved"))
    logger.info(f"Analysis review resumed: contract_id={contract_id} review_id={review_id} approved={approved_flag} risks={len(risks)}")
    return {
        "contract_id": contract_id,
        "analysis": analysis,
        "risks": risks,
        "approved": approved_flag,
    }
