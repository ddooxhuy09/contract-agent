"""Offline QA benchmark checks derived from dataset.csv.

These tests validate the benchmark contract and evidence coverage.  They do
not call Gemini or require PostgreSQL; live retrieval evaluation can consume
the generated JSONL fixture separately.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.infrastructure.retrieval.query_rewrite import expand_legal_topic_query


ROOT = Path(__file__).resolve().parents[2]
LEGAL_FIXTURE = ROOT / "tests" / "fixtures" / "legal_qa.jsonl"
MISSING_REPORT = ROOT / "evaluation_results" / "reports" / "missing_legal_documents.csv"


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_dataset_fixture_schema_and_row_count():
    cases = _load_jsonl(LEGAL_FIXTURE)
    assert len(cases) == 3298
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({case["qid"] for case in cases}) == 3196
    for case in cases:
        assert case["question"]
        assert case["reference_context"]
        assert case["source_doc"]
        assert case["article"].isdigit()
        assert case["expected_citation"] == f"Điều {case['article']}"
        assert case["answerability"] == "answerable"


def test_dataset_fixture_preserves_source_document_inventory():
    cases = _load_jsonl(LEGAL_FIXTURE)
    assert len({case["source_doc_key"] for case in cases}) == 724
    assert all(case["corpus_status"] == "missing" for case in cases)


def test_missing_report_covers_every_dataset_source_document():
    cases = _load_jsonl(LEGAL_FIXTURE)
    with MISSING_REPORT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 724
    assert {row["source_doc"].lower() for row in rows} == {
        case["source_doc"].lower() for case in cases
    }
    assert all(row["status"] == "missing_from_local_corpus" for row in rows)


def test_missing_report_is_prioritised_by_question_count():
    with MISSING_REPORT.open(encoding="utf-8-sig", newline="") as handle:
        counts = [int(row["question_count"]) for row in csv.DictReader(handle)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == 413


def test_labor_followup_retrieval_terms_are_grounded():
    query = expand_legal_topic_query(
        "Điều 4 Công ty chấm dứt hợp đồng vì người lao động mang thai có đúng luật không?"
    )
    lowered = query.lower()
    assert "mang thai" in lowered
    assert "đơn phương chấm dứt" in lowered
    assert "bộ luật lao động" in lowered
