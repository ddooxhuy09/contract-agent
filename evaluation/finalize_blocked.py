"""Preserve a quota-interrupted experiment and mark unexecuted cases explicitly."""
import json
import re
import importlib.metadata
from collections import Counter
from pathlib import Path

from evaluation.runtime_adapter import BENCHMARK, BASELINE_RUN
from evaluation.run_benchmark import fingerprints, write_json, now


def main():
    output = BASELINE_RUN
    path = output / "predictions.jsonl"
    predictions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    log = (output / "baseline_console.log").read_text(encoding="utf-8-sig")
    if "GenerateRequestsPerDayPerProjectPerModel-FreeTier" not in log:
        raise RuntimeError("No daily-quota evidence in saved console log; refusing to label run as quota-blocked.")
    runs = re.findall(r"^RUN (\S+)", log, re.M)
    current = runs[-1]
    cases = json.loads((BENCHMARK / "QUESTIONS_ONLY_NO_GOLD.json").read_text(encoding="utf-8"))
    metadata = json.loads((output / "execution_metadata.json").read_text(encoding="utf-8"))
    seen = {p["id"] for p in predictions}
    for case in cases:
        if case["id"] in seen:
            continue
        inflight = case["id"] == current
        predictions.append({"id": case["id"], "input": case,
                            "status": "failed" if inflight else "not_run", "execution_status": "failed" if inflight else "not_run",
                            "actual_answer": None, "trace": [], "model_calls": None if inflight else 0,
                            "retry_count": None if inflight else 0, "retrieval_ms": None, "generation_ms": None, "total_ms": None,
                            "error": {"type": "InterruptedAfterProviderQuotaExhaustion" if inflight else "ProviderQuotaBlocked",
                                      "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."},
                            "partial_console_trace": "baseline_console.log" if inflight else None,
                            "capabilities": {"temporal_retrieval": "unsupported by current pipeline"} if case['id'].startswith('TEMP-') else {},
                            "config": metadata["config"]})
    path.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in predictions), encoding="utf-8")
    metadata.update({"finished_at": now(), "termination": "Worker stopped after confirmed provider daily quota exhaustion; remaining cases not run.",
                     "quota_evidence": {"source": "baseline_console.log and model_errors in raw predictions", "metric": "generate_content_free_tier_requests",
                                        "quota_id": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "observed_limit": 20,
                                        "interrupted_case": current},
                     "status_counts": dict(Counter(p['status'] for p in predictions)),
                     "execution_counts": dict(Counter(p['execution_status'] for p in predictions)),
                     "inference_attempted_cases": sum(p['execution_status'] != 'not_run' for p in predictions)})
    metadata["corpus_after"] = fingerprints()
    metadata["legal_corpus_unchanged"] = metadata["corpus_before"] == metadata["corpus_after"]
    metadata["model_response_versions"] = sorted({str(e.get('response_metadata', {}).get('model_name') or e.get('response_metadata', {}).get('model_version')) for p in predictions for e in p.get('trace', []) if e['kind']=='llm' and e.get('response_metadata')})
    metadata["embedding_cache_revisions"] = [p.name for p in Path('/cache/huggingface/hub/models--BAAI--bge-m3/snapshots').glob('*') if p.is_dir()]
    for package in ('pydantic', 'pydantic-settings', 'python-docx', 'pgvector', 'langchain-core', 'psycopg'):
        try:
            metadata['packages'][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    write_json(output / 'execution_metadata.json', metadata)
    print(json.dumps({"status_counts": metadata['status_counts'], "execution_counts": metadata['execution_counts'], "legal_corpus_unchanged": metadata['legal_corpus_unchanged']}))


if __name__ == '__main__':
    main()
