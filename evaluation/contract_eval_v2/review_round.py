"""V4: one evidence-review pass, compared with the frozen V3 implementation."""
from contextlib import contextmanager
import ast
from pathlib import Path
import json
import random
import shutil

from evaluation.contract_eval_v2 import experiment as exp
from evaluation.contract_eval_v2 import research_round as engine

OUTPUT = Path(__file__).parent / "artifacts/reviewed_evidence_v4"
PREVIOUS = engine.OUTPUT
SPLITS = ("regression_test", "fresh_source_checked", "validation")


def prepare():
    if (OUTPUT / "protocol.json").exists():
        engine.check_protocol()
        return
    for split in SPLITS[:2]:
        target = OUTPUT / split
        target.mkdir(parents=True, exist_ok=True)
        for name in ("inputs.jsonl", "gold.jsonl", "manifest.json", "contract_map.json"):
            shutil.copy2(PREVIOUS / split / name, target / name)
        shutil.copytree(PREVIOUS / split / "contracts", target / "contracts", dirs_exist_ok=True)
    used = {x["base_case_id"] for s in ("dev", "regression_test", "fresh_source_checked") for x in exp.rows(PREVIOUS / s / "gold.jsonl")}
    v1_split = exp.read_json(exp.V1 / "split.json")
    excluded = {x["id"] for x in exp.rows(exp.V1 / "quarantine.jsonl")}
    pool = [c for c in exp.rows(exp.V1 / "cases.jsonl") if c["base_case_id"] in v1_split["test"]
            and c["base_case_id"] not in used and c["source_set"] == "injection" and c["template"] == "T1" and c["id"] not in excluded]
    rng, selected = random.Random(20261120), []
    for rule in sorted({c["rule_id"] for c in pool}):
        for label in ("violation", "compliant"):
            group = sorted([c for c in pool if c["rule_id"] == rule and c["gold_label"] == label], key=lambda c: c["id"])
            assert group, (rule, label)
            selected.append(rng.choice(group))
    assert len(selected) == 16
    target = OUTPUT / "validation"
    (target / "contracts").mkdir(parents=True, exist_ok=True)
    inputs, gold, files = [], [], {}
    for i, c in enumerate(selected, 1):
        uid, path = f"VAL-{i:03}", f"contracts/C{i:03}.txt"
        (target / path).write_bytes((exp.ROOT / c["contract_path"]).read_bytes())
        files[path] = exp.digest(target / path)
        inputs.append({"id": uid, "contract_path": path, "question": c["question"], "variant": "T1", "as_of_date": c["as_of_date"]})
        gold.append({**c, "id": uid, "source_id": c["id"], "contract_path": path, "variant": "T1", "human_reviewed": False})
    for name, data in (("inputs.jsonl", inputs), ("gold.jsonl", gold)):
        (target / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data), encoding="utf-8")
        files[name] = exp.digest(target / name)
    exp.write_json(target / "manifest.json", {
        "purpose": "previously_v1_evaluated_cases_not_used_in_v2_v3_diagnosis", "independent_test": False,
        "source_split": "v1/test/injection", "source_sha256": exp.digest(exp.V1 / "cases.jsonl"),
        "n_questions": 16, "n_base_cases": 16, "files": files, "seed": 20261120,
        "selection": "one violating and one compliant per rule, disjoint from all v2/v3 cases",
    })
    reference = OUTPUT / "reference_code"
    exp.write_json(OUTPUT / "protocol.json", {
        "baseline": "v3 production snapshot; new baseline calls, not copied scores",
        "candidate": "focused primary evidence + context article 1 + one same-model evidence review",
        "judge": "unchanged Groq Qwen prompt and rubric",
        "data": {s: exp.digest(OUTPUT / s / "manifest.json") for s in SPLITS},
        "candidate_sha256": {p: exp.digest(exp.ROOT / p) for p in engine.CODE},
        "reference_sha256": {p.name: exp.digest(p) for p in sorted(reference.iterdir())},
        "selection_rule": "one run per system; report errors/regressions; no label or rubric edits",
        "limitations": "40 cases used for v3 diagnosis; 16 validation cases not used for those changes but belong to previously evaluated v1; synthetic and not expert validated",
    })
    print("Frozen v4: 32 known regression, 8 known source-checked, 16 validation cases; 112 QA outputs.")


def install_variant():
    from app.agents import qa_agent as qa
    reference = OUTPUT / "reference_code"
    query_scope, evidence_scope = {"__name__": "reference_query_rewrite"}, {"__name__": "reference_qa_evidence"}
    for filename, scope in (("query_rewrite.py.txt", query_scope), ("qa_evidence.py.txt", evidence_scope)):
        exec(compile((reference / filename).read_text(encoding="utf-8"), str(reference / filename), "exec"), scope)
    qa_source = (reference / "qa_agent.py.txt").read_text(encoding="utf-8")
    qa_scope = dict(vars(qa))
    for name in ("_format_legal_context", "_retrieve_contract_docs", "_verified_contract_citations"):
        node = next(n for n in ast.parse(qa_source).body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.get_source_segment(qa_source, node), str(reference / "qa_agent.py.txt"), "exec"), qa_scope)

    async def no_review(result, *args, **kwargs):
        return result

    @contextmanager
    def variant(module, system):
        replacements = {
            "ground_qa_retrieval_query": query_scope["ground_qa_retrieval_query"],
            "augment_legal_evidence": evidence_scope["augment_legal_evidence"],
            "_format_legal_context": qa_scope["_format_legal_context"],
            "_retrieve_contract_docs": qa_scope["_retrieve_contract_docs"],
            "_verified_contract_citations": qa_scope["_verified_contract_citations"],
            "_review_qa_result": no_review,
            "QA_SYSTEM_PROMPT": (reference / "QA_SYSTEM_PROMPT.txt").read_text(encoding="utf-8"),
        } if system == "baseline" else {}
        saved = {key: getattr(module, key) for key in replacements}
        try:
            for key, value in replacements.items():
                setattr(module, key, value)
            yield
        finally:
            for key, value in saved.items():
                setattr(module, key, value)
    exp.variant, exp.VARIANTS = variant, ("baseline", "grounded")


def main():
    engine.OUTPUT, engine.SPLITS = OUTPUT, SPLITS
    engine.prepare, engine.install_variant = prepare, install_variant
    engine.main()


if __name__ == "__main__":
    main()
