"""Real retrieval-only benchmark: local BGE, PostgreSQL and Neo4j; no LLM client."""
from __future__ import annotations

import asyncio
import argparse
import copy
import hashlib
import json
import os
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

from evaluation.runtime_adapter import BENCHMARK, RUNS, chunk_json, error_info, settings_summary
from evaluation.run_benchmark import fingerprints, write_json, now, source_manifest


class RagObserver:
    def __init__(self, rag):
        self.events = []
        self.call_id = None
        self.restores = []
        original_search = rag._search.search

        def search(*args, **kwargs):
            start = time.perf_counter()
            result = original_search(*args, **kwargs)
            self.add("seed_candidates" if not kwargs.get("doc_ids") else "within_document_search",
                     query=args[0] if args else kwargs.get("query"), options=kwargs,
                     chunks=[chunk_json(c) for c in result], start=start, end=time.perf_counter())
            return result

        self.patch(rag._search, "search", search)
        for method in ("_vector_search", "_fts_search"):
            self.trace_search_method(rag._search, method)
        original_expand = rag._expand

        def expand(seeds):
            result = original_expand(seeds)
            self.add("graph_expansion", seed_paths=seeds, expansion=result)
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
            self.call_id = str(uuid.uuid4())
            start = time.perf_counter()
            result = original_retrieve(*args, **kwargs)
            self.add("final_retrieval", query_args=args, options=kwargs, chunks=[chunk_json(c) for c in result], start=start, end=time.perf_counter())
            return result

        self.patch(rag, "retrieve_for_clause", retrieve)

    def patch(self, obj, name, fn):
        self.restores.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)

    def add(self, kind, **data):
        self.events.append({"kind": kind, "scope": None, "rag_call_id": self.call_id, **data})

    def trace_search_method(self, obj, name):
        original = getattr(obj, name)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = original(*args, **kwargs)
                self.add(name.removeprefix("_"), chunks=[chunk_json(c) for c in result], start=start, end=time.perf_counter())
                return result
            except Exception as exc:
                self.add(name.removeprefix("_"), error=error_info(exc), start=start, end=time.perf_counter())
                raise
        self.patch(obj, name, wrapper)

    def restore(self):
        for obj, name, original in reversed(self.restores):
            setattr(obj, name, original)


async def run(args):
    if os.environ.get("CONTRACTLENS_EVAL_ISOLATED") != "1":
        raise RuntimeError("RAG fixture indexing requires the dedicated isolated corpus clone.")
    from app.core.settings import get_settings
    if get_settings().gemini_api_key:
        raise RuntimeError("Start this worker with GEMINI_API_KEY empty. This RAG run must not have a usable Gemini credential.")
    from app.infrastructure.embeddings.hf_embedder import HuggingFaceEmbedder
    from app.infrastructure.vector.pg_search import PgContractVectorSearch, PgLegalVectorSearch
    from app.infrastructure.db.legal_repository import PgLegalChunkRepository
    from app.infrastructure.db.contract_repository import PgContractRepository
    from app.infrastructure.db.contract_chunk_repository import PgContractChunkRepository
    from app.infrastructure.db.user_repository import PgUserRepository
    from app.infrastructure.storage.local_storage import LocalObjectStorage
    from app.infrastructure.neo4j.graph_repository import Neo4jGraphRepository
    from app.infrastructure.retrieval.context import bind_retrieval, get_graph_rag
    from app.infrastructure.retrieval.query_rewrite import augment_qa_retrieval_query
    from app.vectorstore.retriever import retrieve_contract, retrieve_legal
    from app.application.use_cases.contracts import UploadContract

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "predictions.jsonl").exists():
        raise RuntimeError("Use a fresh output directory; do not overwrite an experiment.")
    cases = json.loads((BENCHMARK / "QUESTIONS_ONLY_NO_GOLD.json").read_text(encoding="utf-8"))
    metadata = {"started_at": now(), "mode": "rag_only_existing_corpus", "selected_ids": [c["id"] for c in cases],
                "config": settings_summary(), "generation_model_calls": 0, "gemini_credential_present": False,
                "gold_used_in_retrieval": False, "legal_fixture_ingestion": False, "source_sha256": source_manifest(),
                "query_adapters": {"qa_multi_hop_classification": "Original QA first pass: rule-based augmentation, retrieve_legal(k=5, contract_type=None). No QA LLM rewrite or answer generation.",
                                   "risk": "Original LegalGraphRag risk entry with question as title and supplied scenario as summary; k_seed=4, max_total=10, no inferred contract type. No LLM clause extraction."},
                "temporal_dates_forwarded": args.date_field != "none", "date_field": args.date_field, "python": sys.version}
    write_json(output / "execution_metadata.json", metadata)
    print("RAG-only: Gemini credential absent, no LLM client is instantiated.", flush=True)
    metadata["corpus_before"] = fingerprints()
    embedder, graph = HuggingFaceEmbedder(), Neo4jGraphRepository()
    contracts, chunks = PgContractRepository(), PgContractChunkRepository()
    legal_search = PgLegalVectorSearch(embedder)
    bind_retrieval(PgContractVectorSearch(embedder), legal_search, graph, PgLegalChunkRepository(), chunks)
    rag = get_graph_rag()
    print("Loading cached BGE-M3 only...", flush=True)
    warmup = time.perf_counter()
    embedder.embed_query("warmup")
    metadata["embedding_warmup_ms"] = (time.perf_counter() - warmup) * 1000
    user = PgUserRepository().create("rag-eval-" + str(uuid.uuid4()) + "@example.invalid", "disabled-evaluation-account")
    uploads = {}
    uploader = UploadContract(contracts, chunks, LocalObjectStorage(), embedder)
    for fixture_id in sorted({c["contract_id"] for c in cases if c.get("contract_id")}):
        path = BENCHMARK / "contracts" / (fixture_id + ".docx")
        data = path.read_bytes()
        upload = await uploader.execute(data, path.name, user.id)
        if upload["status"] != "parsed":
            raise RuntimeError("Real fixture indexing failed: " + str(upload))
        uploads[fixture_id] = {**upload, "sha256": hashlib.sha256(data).hexdigest()}
    metadata["fixture_uploads"] = uploads
    write_json(output / "execution_metadata.json", metadata)
    observer = RagObserver(rag)
    predictions = []
    try:
        for case in cases:
            observer.events, observer.call_id = [], None
            start = time.perf_counter()
            pred = {"id": case["id"], "input": case, "evaluation_mode": "rag_only", "status": "completed",
                    "execution_status": "completed", "actual_answer": None, "generation_ms": None, "model_calls": 0,
                    "legal_relations": None, "contract_retrieval": [], "temporal_capability": "unsupported" if case['id'].startswith('TEMP-') else "not_requested"}
            query = "\n\n".join(str(v) for v in (case.get("scenario"), case["question"]) if v)
            # Benchmark inputs (QUESTIONS_ONLY_NO_GOLD), not gold labels. --date-field picks which
            # one is forwarded as the production `as_of_date` parameter ("none" = old behaviour).
            applicable_date = None if args.date_field == "none" else case.get(args.date_field)
            try:
                if case.get("contract_id"):
                    contract_start = time.perf_counter()
                    docs = retrieve_contract(query, uploads[case["contract_id"]]["contract_id"])
                    pred["contract_retrieval"] = [chunk_json(c) for c in docs]
                    pred["contract_retrieval_ms"] = (time.perf_counter() - contract_start) * 1000
                if case["task"] == "risk":
                    rag.retrieve_for_clause(case["question"], case.get("scenario"), contract_type=None, k_seed=4, max_total=10, as_of_date=applicable_date)
                    pred["adapter"] = "risk GraphRAG with input fact pattern; no extraction/model"
                else:
                    legal_query = augment_qa_retrieval_query(query, [])
                    retrieve_legal(legal_query, k=5, title=legal_query, as_of_date=applicable_date)
                    pred["adapter"] = "QA first-pass legal retrieval; no rewrite LLM/model"
            except Exception as exc:
                pred["status"] = pred["execution_status"] = "failed"
                pred["error"] = error_info(exc)
            pred["total_ms"] = (time.perf_counter() - start) * 1000
            pred["trace"] = copy.deepcopy(observer.events)
            pred["retrieval_ms"] = sum((e['end'] - e['start']) * 1000 for e in pred['trace'] if e['kind']=='final_retrieval')
            pred["config"] = settings_summary()
            predictions.append(pred)
            with (output / "predictions.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(pred, ensure_ascii=False, default=str) + "\n")
            write_json(output / "traces" / (case["id"] + ".json"), pred["trace"])
            print(f"RAG {case['id']} {pred['status']} {pred['retrieval_ms']:.0f}ms", flush=True)
    finally:
        observer.restore()
        graph.close()
        metadata["finished_at"] = now()
        metadata["status_counts"] = dict(Counter(p["status"] for p in predictions))
        metadata["corpus_after"] = fingerprints()
        metadata["legal_corpus_unchanged"] = metadata["corpus_before"] == metadata["corpus_after"]
        metadata["llm_client_modules_loaded"] = [name for name in sys.modules if name.startswith(("google.genai", "langchain_google_genai", "app.agents.llm_client"))]
        write_json(output / "execution_metadata.json", metadata)
    print(json.dumps({"cases": len(predictions), "status_counts": metadata["status_counts"], "gemini_calls": 0, "corpus_unchanged": metadata["legal_corpus_unchanged"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(RUNS / "rag_only"))
    parser.add_argument("--date-field", choices=("as_of_date", "transaction_date", "none"), default="as_of_date",
                        help="case date forwarded to retrieval as as_of_date")
    asyncio.run(run(parser.parse_args()))
