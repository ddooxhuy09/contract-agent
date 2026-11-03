"""Adapters and observation hooks around the existing ContractLens pipeline."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "evaluation" / "benchmark" / "v04"
RESULTS = ROOT / "evaluation_results"
RUNS = RESULTS / "runs"
BASELINE_RUN = RUNS / "baseline_20261019"


def dumpable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): dumpable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [dumpable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def settings_summary():
    from app.core.settings import get_settings
    s = get_settings()
    u = urlsplit(s.database_url)
    names = ("gemini_model", "embedding_model", "embedding_dim", "embedding_device", "embedding_normalize",
             "embedding_max_seq_length", "top_k_retrieval", "similarity_threshold", "legal_expand_backend")
    return {**{n: getattr(s, n) for n in names}, "provider": "gemini", "temperature": 0,
            "gemini_key_configured": bool(s.gemini_api_key), "database_host": u.hostname,
            "database_name": u.path.lstrip("/"), "llm_timeout_seconds": 120,
            "llm_sdk_max_retries": 0, "application_chat_completion_max_attempts": 3}


def error_info(exc):
    from app.core.settings import get_settings
    s = get_settings()
    message = str(exc)
    for secret in (s.gemini_api_key, s.neo4j_password, urlsplit(s.database_url).password):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return {"type": type(exc).__name__, "message": message[:4000]}


def chunk_json(c):
    return copy.deepcopy({"text": getattr(c, "content", getattr(c, "page_content", "")),
                          "score": getattr(c, "score", None), "metadata": dumpable(c.metadata)})


class Observer:
    def __init__(self):
        self.lock = threading.Lock()
        self.local = threading.local()
        self.restores = []
        self.events = []

    def reset(self):
        with self.lock:
            self.events = []

    def add(self, kind, **data):
        with self.lock:
            self.events.append({"kind": kind, "scope": getattr(self.local, "scope", None),
                                "rag_call_id": getattr(self.local, "rag_id", None), **dumpable(data)})

    def patch(self, obj, name, fn):
        original = getattr(obj, name)
        self.restores.append((obj, name, original))
        setattr(obj, name, fn)
        return original

    def install(self, rag):
        import app.agents.llm_client as llm
        import app.agents.qa_agent as qa
        import app.agents.risk_flagger as rf
        import app.agents.workflow as wf
        original_get_model = llm.get_chat_model
        observer = self

        class ModelProxy:
            def __init__(self, model):
                self.model = model

            def __getattr__(self, name):
                return getattr(self.model, name)

            def invoke(self, messages, *args, **kwargs):
                started = time.perf_counter()
                try:
                    response = self.model.invoke(messages, *args, **kwargs)
                    observer.add("llm", prompt=messages, raw_response=response.content,
                                 response_metadata=response.response_metadata, usage_metadata=getattr(response, "usage_metadata", None),
                                 start=started, end=time.perf_counter(), error=None)
                    return response
                except Exception as exc:
                    observer.add("llm", prompt=messages, raw_response=None, start=started,
                                 end=time.perf_counter(), error=error_info(exc))
                    raise

            async def ainvoke(self, messages, *args, **kwargs):
                started = time.perf_counter()
                try:
                    response = await self.model.ainvoke(messages, *args, **kwargs)
                    observer.add("llm", prompt=messages, raw_response=response.content,
                                 response_metadata=response.response_metadata, usage_metadata=getattr(response, "usage_metadata", None),
                                 start=started, end=time.perf_counter(), error=None)
                    return response
                except Exception as exc:
                    observer.add("llm", prompt=messages, raw_response=None, start=started,
                                 end=time.perf_counter(), error=error_info(exc))
                    raise

        def get_model(*args, **kwargs):
            return ModelProxy(original_get_model(*args, **kwargs))

        self.patch(llm, "get_chat_model", get_model)
        self.patch(qa, "get_chat_model", get_model)
        original_judge = rf.evaluate_clause

        def judge(clause, *args, **kwargs):
            old_scope = getattr(self.local, "scope", None)
            self.local.scope = "clause:" + str(clause.clause_number)
            try:
                result = original_judge(clause, *args, **kwargs)
                self.add("risk_judge", clause=clause, result=result, returned_none=result is None)
                return result
            except Exception as exc:
                self.add("risk_judge", clause=clause, error=error_info(exc))
                raise
            finally:
                self.local.scope = old_scope

        self.patch(rf, "evaluate_clause", judge)
        self.patch(wf, "evaluate_clause", judge)
        original_search = rag._search.search

        def search(*args, **kwargs):
            started = time.perf_counter()
            result = original_search(*args, **kwargs)
            self.add("seed_candidates" if not kwargs.get("doc_ids") else "within_document_search",
                     query=args[0] if args else kwargs.get("query"), options=kwargs,
                     chunks=[chunk_json(c) for c in result], start=started, end=time.perf_counter())
            return result

        self.patch(rag._search, "search", search)
        original_expand = rag._expand

        def expand(seed_paths):
            result = original_expand(seed_paths)
            self.add("graph_expansion", seed_paths=seed_paths, expansion=result)
            return result

        self.patch(rag, "_expand", expand)
        original_order = rag._order_for_prompt

        def order(chunks, as_of=None):
            self.add("graph_expanded", chunks=[chunk_json(c) for c in chunks])
            result = original_order(chunks, as_of=as_of)
            self.add("graph_expanded_ranked", chunks=[chunk_json(c) for c in result], as_of_date=as_of)
            return result

        self.patch(rag, "_order_for_prompt", order)
        original_retrieve = rag.retrieve_for_clause

        def retrieve(*args, **kwargs):
            old_id = getattr(self.local, "rag_id", None)
            call_id = str(uuid.uuid4())
            self.local.rag_id = call_id
            started = time.perf_counter()
            try:
                result = original_retrieve(*args, **kwargs)
                self.add("final_retrieval", query_args=args, options=kwargs,
                         chunks=[chunk_json(c) for c in result], start=started, end=time.perf_counter())
                return result
            except Exception as exc:
                self.add("retrieval_error", error=error_info(exc), start=started, end=time.perf_counter())
                raise
            finally:
                self.local.rag_id = old_id

        self.patch(rag, "retrieve_for_clause", retrieve)

    def restore(self):
        for obj, name, original in reversed(self.restores):
            setattr(obj, name, original)
        self.restores = []


def interval_ms(events, kind):
    spans = sorted((e["start"], e["end"]) for e in events if e["kind"] == kind and "start" in e)
    total, end = 0.0, float("-inf")
    for start, stop in spans:
        total += max(0, stop - max(start, end))
        end = max(end, stop)
    return round(total * 1000, 3) if spans else None


async def legal_qa(case):
    """Existing QA nodes, with an empty contract scope and no persistence side effects."""
    import app.agents.qa_agent as qa
    original_retrieve, original_memory = qa.retrieve_contract, qa.load_qa_memory

    async def no_memory(*args, **kwargs):
        return ""

    qa.retrieve_contract = lambda *args, **kwargs: []
    qa.load_qa_memory = no_memory
    state = qa._qa_input(question_text(case), "evaluation-session-" + str(uuid.uuid4()), "gemini")

    def merge(update):
        update = dict(update)
        if "messages" in update:
            state["messages"].extend(update.pop("messages"))
        state.update(update)

    try:
        while True:
            merge(await qa._retrieve_node(state))
            route = qa._route_after_retrieve(state)
            if route == "rewrite":
                merge(await qa._rewrite_query_node(state))
                continue
            if route == "refusal":
                merge(await qa._refusal_node(state))
                break
            while True:
                merge(await qa._generate_node(state))
                route = qa._route_after_generate(state)
                if route == "generate":
                    continue
                if route == "finalize":
                    merge(await qa._finalize_node(state))
                break
            break
        return {"answer": state["messages"][-1].content, "source_clauses": state.get("source_clauses", []),
                "needs_clarification": state.get("needs_clarification", False),
                "qa_parse_ok": state.get("_parse_ok", False), "retrieval_rewrites": state.get("attempts", 0),
                "generation_attempts": state.get("generate_attempts", 0),
                "final_legal_context": state.get("_legal_context"), "final_contract_context": state.get("_contract_context")}
    finally:
        qa.retrieve_contract, qa.load_qa_memory = original_retrieve, original_memory


def question_text(case):
    parts = []
    if case.get("scenario"):
        parts.append("Bối cảnh: " + str(case["scenario"]))
    parts.append(str(case["question"]))
    return "\n\n".join(parts)


class Runtime:
    def __init__(self, isolated):
        self.isolated = isolated
        self.container = None
        self.user = None
        self.observer = Observer()
        self.fixture_uploads = {}

    async def start(self):
        if self.isolated and os.environ.get("CONTRACTLENS_EVAL_ISOLATED") != "1":
            raise RuntimeError("Isolated writes require CONTRACTLENS_EVAL_ISOLATED=1 from the dedicated evaluation Compose project.")
        from app.infrastructure.container import build_container
        from app.infrastructure.retrieval.context import bind_retrieval, get_graph_rag
        self.container = build_container()
        c = self.container
        bind_retrieval(c.contract_search, c.legal_search, c.graph, c.legal_chunks, c.contract_chunks)
        # Same configured embedder. Failure is not converted into a different model.
        await asyncio.to_thread(c.embedder.embed_query, "warmup")
        if self.isolated:
            from app.agents.checkpointer import init_checkpointer
            await init_checkpointer()
            self.user = c.users.create("eval-" + str(uuid.uuid4()) + "@example.invalid", "evaluation-only-disabled-login")
        self.observer.install(get_graph_rag())

    async def upload_fixture(self, fixture_id):
        from app.application.use_cases.contracts import UploadContract
        if not self.isolated:
            raise RuntimeError("Contract fixture indexing is permitted only in the isolated corpus clone.")
        # A fresh upload per case prevents QA history or analysis caches leaking between cases.
        path = BENCHMARK / "contracts" / (fixture_id + ".docx")
        raw = path.read_bytes()
        c = self.container
        result = await UploadContract(c.contracts, c.contract_chunks, c.storage, c.embedder).execute(raw, path.name, self.user.id)
        if result["status"] != "parsed" or result["chunk_count"] == 0:
            raise RuntimeError("Real UploadContract could not parse/index benchmark fixture: " + str(result))
        return {**result, "fixture_id": fixture_id, "sha256": hashlib.sha256(raw).hexdigest()}

    async def run(self, case):
        self.observer.reset()
        started = time.perf_counter()
        result = {"id": case["id"], "input": copy.deepcopy(case), "status": "failed", "execution_status": "failed",
                  "actual_answer": None, "legal_relations": None, "capabilities": {}, "adapter": None}
        try:
            contract_id = None
            if case.get("contract_id") and self.isolated:
                upload = await self.upload_fixture(case["contract_id"])
                result["fixture_upload"] = upload
                contract_id = upload["contract_id"]
            inference_start = time.perf_counter()
            if case["task"] == "risk":
                if contract_id:
                    from app.agents.workflow import run_analysis_workflow
                    contract = self.container.contracts.get(contract_id)
                    analysis, risks = await run_analysis_workflow(contract.full_text, contract_id, "gemini")
                    result["actual_answer"] = {"analysis": dumpable(analysis), "risks": dumpable(risks)}
                    result["adapter"] = "real UploadContract + run_analysis_workflow"
                    if not analysis.clauses:
                        result["pipeline_failure"] = "No clauses extracted; the workflow may have swallowed extraction errors."
                elif not case.get("contract_id"):
                    from app.agents.risk_flagger import evaluate_clause
                    from app.schemas.contract import Clause
                    clause = Clause(clause_number="scenario", title=None, summary=question_text(case))
                    risk = await asyncio.to_thread(evaluate_clause, clause, "gemini", contract_id=None)
                    result["actual_answer"] = {"risks": dumpable([risk] if risk else [])}
                    result["adapter"] = "risk_flagger.evaluate_clause on supplied scenario; no contract assigned"
                else:
                    raise RuntimeError("Contract fixture upload requires an isolated database.")
            elif case["task"] in ("qa", "multi_hop", "classification"):
                if contract_id:
                    from app.agents.qa_agent import answer_question
                    answer = await answer_question(question_text(case), contract_id, "gemini")
                    result["actual_answer"] = dumpable(answer)
                    result["adapter"] = "real UploadContract + qa_agent.answer_question"
                elif not case.get("contract_id"):
                    result["actual_answer"] = await legal_qa(case)
                    result["adapter"] = "legal-only adapter executing original QA retrieve/rewrite/generate/refusal nodes; no contract or persisted memory"
                else:
                    raise RuntimeError("Contract fixture upload requires an isolated database.")
            else:
                result["status"] = "unsupported_capability"
                result["execution_status"] = "not_run"
                result["error"] = {"type": "UnsupportedTask", "message": str(case["task"])}
                return result
            result["execution_status"] = "completed"
            result["status"] = "completed"
            result["inference_total_ms"] = round((time.perf_counter() - inference_start) * 1000, 3)
            if case["id"].startswith("TEMP-"):
                result["status"] = "unsupported_capability"
                result["capabilities"]["temporal_retrieval"] = "unsupported: standard QA/risk entry points do not forward benchmark dates; observed current-pipeline output is retained"
            if case["task"] == "classification":
                result["capabilities"]["structured_classification"] = "No classifier head; natural-language question answered by existing QA pipeline. Label requires review."
        except Exception as exc:
            result["error"] = error_info(exc)
        finally:
            result["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
            result["trace"] = copy.deepcopy(self.observer.events)
            result["retrieval_ms"] = interval_ms(result["trace"], "final_retrieval")
            result["generation_ms"] = interval_ms(result["trace"], "llm")
            result["model_calls"] = sum(e["kind"] == "llm" for e in result["trace"])
            result["model_errors"] = [e["error"] for e in result["trace"] if e["kind"] == "llm" and e.get("error")]
            prompts = Counter(json.dumps(e.get("prompt"), ensure_ascii=False, sort_keys=True, default=str) for e in result["trace"] if e["kind"] == "llm")
            result["retry_count"] = sum(max(0, count - 1) for count in prompts.values())
            result["retry_count_note"] = "Repeated invocations of the same model prompt beyond its first attempt; graph retrieval rewrites are separate events."
            result["config"] = settings_summary()
        if result.get("pipeline_failure"):
            result["status"] = result["execution_status"] = "failed"
            result["error"] = {"type": "PipelineExtractionFailure", "message": result["pipeline_failure"]}
        elif result.get("model_calls") and len(result["model_errors"]) == result["model_calls"]:
            result["status"] = result["execution_status"] = "failed"
            result["error"] = {"type": "AllModelCallsFailed", "message": "Application fallback output retained; no successful model response."}
        return result

    async def close(self):
        self.observer.restore()
        if self.isolated:
            from app.agents.checkpointer import close_checkpointer
            await close_checkpointer()
        if self.container:
            self.container.graph.close()
