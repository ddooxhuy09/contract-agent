"""Scorer invariants only. These tests do not generate ContractLens predictions."""
import unittest

from evaluation.scoring import ref, matches, retrieval_scores, actual_severity, stage_chunks


class ScoringInvariants(unittest.TestCase):
    def test_actual_ltree_prefixes_and_required_point(self):
        actual = ref({"doc_number": "145/2020/NĐ-CP", "path": "123.P1.C2.D4.K2.a"})
        expected = ref({"law_number": "145/2020/ND-CP", "article": "4", "clause": "2", "point": "a"})
        self.assertTrue(matches(actual, expected))
        self.assertFalse(matches(ref({"doc_number": "145/2020/NĐ-CP", "path": "123.D4.K2"}), expected))

    def test_version_is_not_collapsed(self):
        old = ref({"law_number": "145/2020/NĐ-CP", "article": "4", "clause": "2", "version_id": "original"})
        new = ref({"law_number": "145/2020/NĐ-CP", "article": "4", "clause": "2", "version_id": "amended"})
        self.assertFalse(matches(old, new))

    def test_zero_hits_is_zero_recall_and_stays_in_denominator(self):
        required = [ref({"law_number": "45/2019/QH14", "article": "17", "clause": "1"})]
        scores = retrieval_scores([], required, [], [])
        self.assertEqual(scores["recall_at_5"], 0)
        self.assertEqual(scores["mrr"], 0)

    def test_duplicate_chunks_do_not_inflate_ndcg(self):
        p = {"law_number": "45/2019/QH14", "article": "17", "clause": "1"}
        chunks = [{"metadata": {"doc_number": p["law_number"], "path": "x.D17.K1"}}] * 10
        scores = retrieval_scores(chunks, [ref(p)], [], [])
        self.assertEqual(scores["pooled_binary_ndcg_at_10"], 1)
        self.assertEqual(scores["pooled_precision_at_10"], 0.1)

    def test_failed_empty_analysis_never_becomes_ok(self):
        pred = {"execution_status": "failed", "actual_answer": {"risks": []}, "pipeline_failure": "extraction failed"}
        self.assertIsNone(actual_severity(pred, {"input": {"clause_id": "Điều 2"}}))

    def test_target_severity_is_not_first_unrelated_risk(self):
        pred = {"execution_status": "completed", "actual_answer": {"risks": [{"clause_ref": "Điều 1", "severity": "critical"}, {"clause_ref": "Điều 2", "severity": "warning"}]}}
        self.assertEqual(actual_severity(pred, {"input": {"clause_id": "Điều 2"}}), "warning")

    def test_rag_only_risk_fact_pattern_is_not_filtered_as_missing_clause_scope(self):
        chunk = {"metadata": {"doc_number": "45/2019/QH14", "path": "x.D17.K1"}, "text": "evidence"}
        pred = {"evaluation_mode": "rag_only", "trace": [{"kind": "final_retrieval", "rag_call_id": "x", "scope": None, "chunks": [chunk]}]}
        stages, _ = stage_chunks(pred, {"task": "risk", "input": {"clause_id": "Điều 2"}})
        self.assertEqual(stages["final_retrieval"], [chunk])


if __name__ == "__main__":
    unittest.main()
