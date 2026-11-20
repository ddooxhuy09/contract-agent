"""Generate an evidence-based quality audit without reading evaluation_results."""
from collections import Counter
import csv
from pathlib import Path

from evaluation.contract_eval_v2.experiment import ROOT, V1, digest, read_json, rows, write_json


def audit():
    cases = rows(V1 / "cases.jsonl")
    verification = rows(V1 / "verification.jsonl")
    excluded = {x["id"] for x in rows(V1 / "quarantine.jsonl")}
    split = read_json(V1 / "split.json")
    kept = [c for c in cases if c["id"] not in excluded]
    def csv_rows(path):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    human_gold = csv_rows(ROOT / "evaluation/gold/annotation_template.csv")
    human_review = csv_rows(ROOT / "docs/bo_test_hoi_dong/REVIEW_BO_TEST_HOP_DONG.csv")
    grouped = {}
    for side in ("dev", "test"):
        subset = [c for c in kept if c["base_case_id"] in split[side]]
        grouped[side] = {"questions": len(subset), "base_cases": len({c["base_case_id"] for c in subset}),
                         "sources": dict(Counter(c["source_set"] for c in subset)),
                         "templates": dict(Counter(c["template"] for c in subset))}
    return {
        "source_files": {p: digest(V1 / p) for p in ("cases.jsonl", "split.json", "verification.jsonl")},
        "frozen_files_match": {p: digest(V1 / p) == h for p, h in read_json(V1 / "FROZEN.json")["files"].items()},
        "before_exclusion": {"questions": len(cases), "base_cases": len({c["base_case_id"] for c in cases})},
        "after_exclusion": {"questions": len(kept), "base_cases": len({c["base_case_id"] for c in kept})},
        "splits": grouped, "base_id_overlap": sorted(set(split["dev"]) & set(split["test"])),
        "kept_low_confidence": sum("low_confidence" in x["flags"] and x["id"] not in excluded for x in verification),
        "human_review": {"rows": len(human_review), "user_approved": sum(bool(x["Bạn duyệt (Đ/S)"].strip()) for x in human_review)},
        "separate_gold": {"rows": len(human_gold), **{k: sum(bool(x[k].strip()) for x in human_gold)
            for k in ("ann1_co_rui_ro", "ann2_co_rui_ro", "expert_final")}},
        "gates": {
            "frozen_integrity": "pass" if all(digest(V1 / p) == h for p, h in read_json(V1 / "FROZEN.json")["files"].items()) else "fail",
            "human_confirmed_gold": "not_complete",
            "independent_new_holdout": "not_created",
            "dev_negation_v2_coverage": "missing" if not grouped["dev"]["sources"].get("injection_v2") else "present",
            "temporal_test_only": "v1 report uses all 34 v04 cases; 27 test and 7 dev",
            "full_analysis_workflow_v1": "not_measured_by_evaluate_clause_score",
        },
    }


if __name__ == "__main__":
    result = audit()
    output = Path(__file__).parent / "QUALITY_AUDIT.json"
    write_json(output, result)
    print(output.relative_to(ROOT))
