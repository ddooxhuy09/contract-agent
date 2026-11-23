"""Compare researched evidence retrieval with the frozen v2 implementation."""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import json
from pathlib import Path
import random
import shutil
import asyncio

from evaluation.contract_eval_v2 import experiment as exp

OUTPUT = Path(__file__).parent / "artifacts/research_evidence_v3"
CODE = ["app/agents/qa_agent.py", "app/agents/qa_evidence.py", "app/infrastructure/retrieval/query_rewrite.py", "app/core/prompts.py"]
SPLITS = ("dev", "regression_test", "fresh_source_checked")


def prepare():
    if (OUTPUT / "protocol.json").exists():
        check_protocol()
        return
    original = exp.DEFAULT
    exp.check_manifest(original)
    dev = OUTPUT / "dev"
    dev.mkdir(parents=True, exist_ok=True)
    for filename in ("manifest.json", "inputs.jsonl", "gold.jsonl", "contract_map.json"):
        shutil.copy2(original / filename, dev / filename)
    shutil.copytree(original / "contracts", dev / "contracts", dirs_exist_ok=True)
    split = exp.read_json(exp.V1 / "split.json")
    excluded = {x["id"] for x in exp.rows(exp.V1 / "quarantine.jsonl")}
    candidates = [c for c in exp.rows(exp.V1 / "cases.jsonl") if c["base_case_id"] in split["test"]
                  and c["id"] not in excluded and c["template"] == "T1"]
    rng = random.Random(20261118)
    selected = []
    for source in ("injection", "injection_v2"):
        for rule in sorted({c["rule_id"] for c in candidates if c["source_set"] == source}):
            for label in ("violation", "compliant"):
                group = sorted([c for c in candidates if c["source_set"] == source and c["rule_id"] == rule and c["gold_label"] == label], key=lambda x: x["id"])
                assert group, (source, rule, label)
                selected.append(rng.choice(group))
    assert len(selected) == 32
    test = OUTPUT / "regression_test"
    (test / "contracts").mkdir(parents=True, exist_ok=True)
    inputs, gold, files = [], [], {}
    for i, source in enumerate(selected, 1):
        uid, path = f"REG-{i:03}", f"contracts/C{i:03}.txt"
        (test / path).write_bytes((exp.ROOT / source["contract_path"]).read_bytes())
        files[path] = exp.digest(test / path)
        inputs.append({"id": uid, "contract_path": path, "question": source["question"],
                       "variant": "T1", "as_of_date": source["as_of_date"]})
        gold.append({**source, "id": uid, "source_id": source["id"], "contract_path": path, "variant": "T1", "human_reviewed": False})
    for name, data in (("inputs.jsonl", inputs), ("gold.jsonl", gold)):
        (test / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data), encoding="utf-8")
        files[name] = exp.digest(test / name)
    exp.write_json(test / "manifest.json", {
        "purpose": "frozen_v1_regression_subset_not_new_independent_holdout", "independent_test": False,
        "n_questions": 32, "n_base_cases": 32, "source_split": "v1/test/injection+injection_v2",
        "source_sha256": exp.digest(exp.V1 / "cases.jsonl"), "files": files,
        "seed": 20261118, "selection": "one violating and one compliant case per source and rule; selected before candidate results",
        "qa_subset": ["T1"], "bootstrap_cluster": "base_case_id",
    })
    assert not {x["base_case_id"] for x in gold} & {x["base_case_id"] for x in exp.rows(dev / "gold.jsonl")}
    fresh_spec = exp.read_json(Path(__file__).parent / "fresh_cases.json")
    fresh = OUTPUT / "fresh_source_checked"
    (fresh / "contracts").mkdir(parents=True, exist_ok=True)
    fresh_inputs, fresh_gold, fresh_files = [], [], {}
    for i, case in enumerate(fresh_spec["cases"], 1):
        path = f"contracts/C{i:03}.txt"
        body = "HỢP ĐỒNG LAO ĐỘNG GIẢ LẬP\nCác bên là Công ty Mẫu và người lao động giả định.\n\n" + case["body"]
        (fresh / path).write_text(body, encoding="utf-8")
        fresh_files[path] = exp.digest(fresh / path)
        number = case["body"].split(".", 1)[0].split()[-1]
        question = f"Điều {number} của hợp đồng có trái quy định pháp luật lao động không?"
        fresh_inputs.append({"id": case["id"], "contract_path": path, "question": question, "variant": "T1", "as_of_date": "2026-11-18"})
        fresh_gold.append({"id": case["id"], "source_id": case["id"], "base_case_id": case["id"],
            "source_set": "fresh_source_checked", "variant": "T1", "rule_id": case["rule_id"], "question": question,
            "contract_path": path, "gold_label": case["label"], "gold_clause_ids": [number], "gold_clause_text": case["body"],
            "gold_legal_refs": [{"doc": "45/2019/QH14", "doc_id": "139264", "article": case["article"], "clause": case["clause"]}],
            "source_url": fresh_spec["source"], "as_of_date": "2026-11-18", "human_reviewed": False})
    for name, data in (("inputs.jsonl", fresh_inputs), ("gold.jsonl", fresh_gold)):
        (fresh / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data), encoding="utf-8")
        fresh_files[name] = exp.digest(fresh / name)
    exp.write_json(fresh / "manifest.json", {
        "purpose": "new_synthetic_cases_source_checked_but_author_knows_code", "independent_test": False,
        "n_questions": 8, "n_base_cases": 8, "source_split": "new_source_checked",
        "source_sha256": exp.digest(exp.V1 / "cases.jsonl"), "v1_fingerprint_purpose": "compatibility integrity guard, not label source",
        "legal_source": fresh_spec["source"], "fresh_spec_sha256": exp.digest(Path(__file__).parent / "fresh_cases.json"),
        "files": fresh_files, "qa_subset": ["T1"], "bootstrap_cluster": "base_case_id",
    })
    exp.write_json(OUTPUT / "protocol.json", {
        "baseline": "previous v2 grounded QA, exact source snapshots under reference_code",
        "candidate": "normalized clause query + topic-guided exact corpus evidence + QA reasoning/citation prompt",
        "judge": "unchanged experiment.py judge prompt and rubric; Groq qwen/qwen3.8-27b",
        "generation": "same Groq openai/gpt-oss-120b for both configurations",
        "data": {s: exp.digest(OUTPUT / s / "manifest.json") for s in SPLITS},
        "candidate_sha256": {p: exp.digest(exp.ROOT / p) for p in CODE},
        "reference_sha256": {p.name: exp.digest(p) for p in sorted((OUTPUT / "reference_code").iterdir())},
        "selection_rule": "report all cases, no label/rubric edits, no score-seeking reruns",
        "limitations": "dev already analyzed; regression subset previously evaluated in v1; fresh cases written by coding agent with knowledge of candidate, checked to official source, not expert validated",
    })
    print("Frozen 80 dev questions, 32 regression cases, 8 new source-checked cases before candidate results.")


def check_protocol():
    protocol = exp.read_json(OUTPUT / "protocol.json")
    for name, digest in protocol["candidate_sha256"].items():
        if exp.digest(exp.ROOT / name) != digest:
            raise ValueError(f"Candidate code changed after protocol freeze: {name}")
    for split, digest in protocol["data"].items():
        if exp.digest(OUTPUT / split / "manifest.json") != digest:
            raise ValueError(f"Dataset changed: {split}")
        exp.check_manifest(OUTPUT / split)
    for filename, digest in protocol["reference_sha256"].items():
        if exp.digest(OUTPUT / "reference_code" / filename) != digest:
            raise ValueError(f"Baseline snapshot changed: {filename}")
    return protocol


def install_variant():
    from app.agents import qa_agent as qa
    reference = OUTPUT / "reference_code"

    def load_symbol(filename, symbol, namespace):
        source = (reference / filename).read_text(encoding="utf-8")
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        scope = dict(namespace)
        exec(compile(ast.get_source_segment(source, node), str(reference / filename), "exec"), scope)
        return scope[symbol]

    query_scope = {"__name__": "reference_query_rewrite"}
    reference_query = reference / "query_rewrite.py.txt"
    exec(compile(reference_query.read_text(encoding="utf-8"), str(reference_query), "exec"), query_scope)
    old_ground = query_scope["ground_qa_retrieval_query"]
    old_format = load_symbol("qa_agent.py.txt", "_format_legal_context", vars(qa))
    old_prompt = (reference / "QA_SYSTEM_PROMPT.txt").read_text(encoding="utf-8")

    @contextmanager
    def paired_variant(module, system):
        replacements = {
            "ground_qa_retrieval_query": old_ground,
            "augment_legal_evidence": lambda docs, focus, date, **kwargs: docs,
            "_format_legal_context": old_format,
            "_verified_contract_citations": lambda cited, valid: [c for c in cited if c in valid],
            "QA_SYSTEM_PROMPT": old_prompt,
        } if system == "baseline" else {}
        saved = {key: getattr(module, key) for key in replacements}
        try:
            for key, value in replacements.items():
                setattr(module, key, value)
            yield
        finally:
            for key, value in saved.items():
                setattr(module, key, value)

    exp.variant = paired_variant
    exp.VARIANTS = ("baseline", "grounded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "retrieval", "qa", "judge", "score"])
    parser.add_argument("--split", choices=[*SPLITS, "all"], default="all")
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
        return
    protocol = check_protocol()
    install_variant()
    splits = SPLITS if args.split == "all" else (args.split,)
    if args.stage in ("retrieval", "qa"):
        async def run_splits():
            for split in splits:
                await exp.run(OUTPUT / split, args.stage)
        # Cached async HTTP clients must not cross asyncio.run event loops.
        asyncio.run(run_splits())
        return
    for split in splits:
        path = OUTPUT / split
        if args.stage == "judge":
            exp.judge(path)
        else:
            exp.score(path)
            metrics = exp.read_json(path / "metrics.json")
            metrics["scope"] = exp.read_json(path / "manifest.json")["purpose"]
            metrics["baseline"] = protocol["baseline"]
            metrics["candidate"] = protocol["candidate"]
            exp.write_json(path / "metrics.json", metrics)


if __name__ == "__main__":
    main()
