"""Execute real ContractLens pipelines; load scoring labels only after inference."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.runtime_adapter import ROOT, BENCHMARK, RUNS, BASELINE_RUN, Runtime, error_info, settings_summary


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def quota_exhausted(pred) -> bool:
    """True when this case failed only because every Gemini key is out of per-day quota.

    Recording such a case would mark a quota stop as a system failure and make
    ``--resume`` skip it, so the caller drops the record and stops the run instead.
    """
    from app.agents.llm_client import _is_daily_quota, keys_remaining
    if pred.get("execution_status") == "completed":
        return False
    errors = [pred.get("error") or {}]
    errors += [event["error"] for event in pred.get("trace") or []
               if isinstance(event, dict) and event.get("error")]
    blob = json.dumps(errors, ensure_ascii=False, default=str)
    return _is_daily_quota(Exception(blob)) and keys_remaining() == 0


def fingerprints():
    from app.core.settings import get_settings
    import psycopg2
    conn = psycopg2.connect(get_settings().database_url, connect_timeout=5)
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='120s'")
            out = {}
            for table in ("legal_documents", "legal_embeddings", "legal_document_relations", "legal_path_relations"):
                cur.execute("SELECT to_regclass(%s)", (table,))
                if not cur.fetchone()[0]:
                    out[table] = None
                    continue
                value = "concat_ws('|',doc_id,path::text,chunk_text,is_effective::text)" if table == "legal_embeddings" else "to_jsonb(t)::text"
                cur.execute(f'SELECT count(*), sum(hashtextextended({value},0)::numeric)::text FROM "{table}" t')
                count, content_hash = cur.fetchone()
                out[table] = {"rows": count, "postgres_hash64_sum": content_hash}
        conn.rollback()
        return out
    finally:
        conn.close()


def source_manifest():
    out = {}
    for path in sorted((ROOT / "app").rglob("*.py")):
        out[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((ROOT / "evaluation").glob("*.py")):
        out[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


async def run(args):
    output = Path(args.output_dir).resolve() if args.output_dir else RUNS / "smoke" if args.smoke else BASELINE_RUN
    output.mkdir(parents=True, exist_ok=True)
    if args.score_only:
        from evaluation.scoring import score_and_report
        score_and_report(output)
        return 0
    if not args.enable_llm:
        raise RuntimeError("Gemini generation is disabled. Use evaluation.rag_only; --enable-llm is reserved for a later explicitly authorized generation experiment.")
    validator = subprocess.run([sys.executable, str(BENCHMARK / "validate_schema.py")], capture_output=True, text=True, encoding="utf-8")
    print(validator.stdout.strip(), flush=True)
    if validator.returncode:
        raise RuntimeError("Benchmark schema validation failed: " + validator.stderr)
    # No gold, evidence labels, fixture law chunks or relation graph are loaded
    # into this inference process before predictions have been persisted.
    questions_path = BENCHMARK / "QUESTIONS_ONLY_NO_GOLD.json"
    cases = json.loads(questions_path.read_text(encoding="utf-8"))
    if args.smoke:
        cases = cases[:5]
    if args.case_id:
        cases = [c for c in cases if c["id"] in args.case_id]
    packages = {}
    for name in ("langgraph", "langchain-google-genai", "langchain-huggingface", "psycopg2-binary", "neo4j", "torch", "sentence-transformers"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    metadata = {"started_at": now(), "mode": "Existing Corpus Baseline on isolated copy" if args.isolated_db else "Existing Corpus Baseline (no fixture writes)",
                "smoke": args.smoke, "selected_ids": [c["id"] for c in cases], "config": settings_summary(),
                "python": sys.version, "platform": platform.platform(), "packages": packages,
                "questions_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
                "source_sha256": source_manifest(), "schema_validation": validator.stdout.strip(),
                "gold_used_in_inference": False, "legal_fixture_ingestion": False}
    write_json(output / "execution_metadata.json", metadata)
    predictions_path = output / "predictions.jsonl"
    predictions = []
    if args.resume and predictions_path.exists():
        predictions = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif predictions_path.exists():
        raise RuntimeError("Output already contains predictions; choose a new directory or --resume.")
    done = {p["id"] for p in predictions}
    runtime = Runtime(args.isolated_db)
    started = False
    try:
        print("Taking read-only legal-corpus fingerprint...", flush=True)
        metadata["corpus_before"] = fingerprints()
        write_json(output / "execution_metadata.json", metadata)
        print("Loading configured embedding model and real application adapters...", flush=True)
        await runtime.start()
        started = True
        for case in cases:
            if case["id"] in done:
                continue
            print(f"RUN {case['id']} task={case['task']} difficulty={case['difficulty']['level']}", flush=True)
            pred = await runtime.run(case)
            if quota_exhausted(pred):
                # This case is not recorded, so it counts as left along with the untouched ones.
                left = len(cases) - len(predictions)
                metadata["stopped_on_quota"] = {"case": case["id"], "at": now(), "cases_left": left}
                print(f"STOP {case['id']}: all Gemini keys are out of per-day quota; "
                      f"{left} cases left, re-run with --resume when quota resets", flush=True)
                break
            predictions.append(pred)
            with predictions_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(pred, ensure_ascii=False, default=str) + "\n")
                file.flush()
            write_json(output / "traces" / (case["id"] + ".json"), pred.get("trace", []))
            print(f"DONE {case['id']} status={pred['status']} execution={pred['execution_status']} model_calls={pred.get('model_calls', 0)} latency_ms={pred.get('total_ms')}", flush=True)
    except Exception as exc:
        metadata["startup_or_run_error"] = error_info(exc)
        print(json.dumps(metadata["startup_or_run_error"], ensure_ascii=False), flush=True)
        for case in cases:
            if case["id"] not in {p["id"] for p in predictions}:
                predictions.append({"id": case["id"], "input": case, "status": "not_run", "execution_status": "not_run",
                                    "actual_answer": None, "trace": [], "error": error_info(exc), "model_calls": 0})
        predictions_path.write_text("".join(json.dumps(p, ensure_ascii=False, default=str) + "\n" for p in predictions), encoding="utf-8")
    finally:
        if started:
            await runtime.close()
        try:
            metadata["corpus_after"] = fingerprints()
            metadata["legal_corpus_unchanged"] = metadata.get("corpus_before") == metadata["corpus_after"]
        except Exception as exc:
            metadata["corpus_after_error"] = error_info(exc)
        metadata["finished_at"] = now()
        metadata["status_counts"] = dict(Counter(p["status"] for p in predictions))
        metadata["execution_counts"] = dict(Counter(p["execution_status"] for p in predictions))
        write_json(output / "execution_metadata.json", metadata)
    if not args.inference_only:
        from evaluation.scoring import score_and_report
        score_and_report(output)
    print(json.dumps({"output_dir": str(output), "status_counts": metadata["status_counts"],
                      "execution_counts": metadata["execution_counts"], "legal_corpus_unchanged": metadata.get("legal_corpus_unchanged")}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--isolated-db", action="store_true", help="Permit contract/checkpoint writes in the dedicated corpus copy only.")
    parser.add_argument("--output-dir")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--inference-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--enable-llm", action="store_true", help="Explicit opt-in for generation; do not use during the current RAG-only task.")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
