import json

import pytest

from evaluation.contract_eval_v2 import experiment as exp


def test_dev_bundle_is_blind_and_never_takes_v1_test_cases(tmp_path):
    exp.prepare(tmp_path)
    manifest = exp.check_manifest(tmp_path)
    inputs, gold = exp.rows(tmp_path / "inputs.jsonl"), exp.rows(tmp_path / "gold.jsonl")
    split = exp.read_json(exp.V1 / "split.json")
    assert manifest["n_questions"] == 80
    assert manifest["n_base_cases"] == 16
    assert {g["base_case_id"] for g in gold} <= set(split["dev"])
    assert not {g["base_case_id"] for g in gold} & set(split["test"])
    assert all(not any("gold" in key or "label" in key or "rule" in key for key in row) for row in inputs)
    assert all(not g["human_reviewed"] for g in gold)
    assert {g["variant"] for g in gold} == {"T1", "T2", "T3", "paraphrase", "renumbered"}
    for g in gold:
        if g["variant"] == "renumbered":
            text = (tmp_path / g["contract_path"]).read_text(encoding="utf-8")
            assert f"Điều {g['gold_clause_ids'][0]}." in text


def test_manifest_rejects_changed_input(tmp_path):
    exp.prepare(tmp_path)
    path = tmp_path / "inputs.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + json.dumps({"id": "extra"}), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        exp.check_manifest(tmp_path)


def test_renumbering_changes_headings_and_subclauses_only():
    original = "Điều 2. Lương\n2.1. Trả 200 đồng.\nĐiều 3. Bảo hiểm\n3.1. BHXH.\n"
    changed = exp.renumber_clause(original, "2", "32")
    assert changed == "Điều 32. Lương\n32.1. Trả 200 đồng.\nĐiều 3. Bảo hiểm\n3.1. BHXH.\n"
    with pytest.raises(ValueError, match="Missing"):
        exp.renumber_clause(original, "9", "39")


def test_cluster_bootstrap_does_not_treat_question_copies_as_new_cases():
    pairs = [("a", 1.0), ("b", -1.0)]
    assert exp.cluster_interval(pairs) == exp.cluster_interval(pairs * 10)
    assert exp.cluster_interval([]) is None


def test_partial_run_reports_missing_denominators_without_inventing_qa_scores(tmp_path):
    exp.prepare(tmp_path)
    first = exp.rows(tmp_path / "gold.jsonl")[0]
    ref = first["gold_legal_refs"][0]
    exp.append(tmp_path / "retrieval.jsonl", {
        "id": first["id"], "system": "grounded", "legal_hits": [{"path": f"{ref['doc_id']}.D{ref['article']}"}],
        "contract_clauses": first["gold_clause_ids"], "ms": 1,
    })
    exp.score(tmp_path)
    result = exp.read_json(tmp_path / "metrics.json")
    assert result["retrieval"]["grounded"]["completed"] == 1
    assert result["retrieval"]["grounded"]["expected"] == 80
    assert result["qa"]["grounded"]["completed"] == 0
    assert result["qa"]["grounded"]["expected"] == 32
    assert result["qa"]["grounded"]["correctness"] is None
