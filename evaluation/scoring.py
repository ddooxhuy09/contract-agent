"""Post-inference scoring. No code in this module is called by inference adapters."""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.audit import norm_law, load
from evaluation.runtime_adapter import ROOT, BENCHMARK, BASELINE_RUN, RUNS


KS = (1, 3, 5, 10)
LABELS = ("critical", "warning", "ok")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def ref(provision):
    law = provision.get("law_number") or provision.get("doc_number") or provision.get("doc_num")
    article, clause, point = provision.get("article"), provision.get("clause"), provision.get("point")
    path = str(provision.get("path") or provision.get("evidence_path") or "")
    if not article:
        m = re.search(r"(?:^|\.)D(\d+)(?:\.|$)", path)
        article = m.group(1) if m else None
    if not clause:
        m = re.search(r"(?:^|\.)K(\d+)(?:\.|$)", path)
        clause = m.group(1) if m else None
    if not point:
        m = re.search(r"\.K\d+\.([a-zđ])(?:\.|$)", path, re.I)
        point = m.group(1) if m else None
    if not law or not article:
        return None
    version = provision.get("version_id") or provision.get("versioned_chunk_id") or ""
    return (norm_law(law), str(article).strip().lower(), str(clause or "").strip().lower(), str(point or "").strip().lower(), str(version))


def matches(actual, expected):
    if actual is None or expected is None:
        return False
    return all(a == e for a, e in zip(actual, expected) if e)


def clause_key(value):
    value = str(value or "").strip()
    return re.sub(r"^(?:Điều|Mục|Khoản)\s*", "", value, flags=re.I).strip().lower()


def prompt_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(prompt_text(v) for v in value)
    if isinstance(value, dict):
        return prompt_text(value.get("content", value.get("text", "")))
    return ""


def stage_chunks(pred, gold_case):
    events = pred.get("trace", [])
    finals = [e for e in events if e["kind"] == "final_retrieval"]
    target = clause_key(gold_case.get("input", {}).get("clause_id"))
    if gold_case["task"] == "risk" and target and pred.get("evaluation_mode") != "rag_only":
        finals = [e for e in finals if clause_key(str(e.get("scope") or "").removeprefix("clause:")) == target]
    if not finals:
        return {}, "No observed RAG retrieval for the target task/clause; deterministic paths are not seed retrieval."
    final = finals[-1]
    call_id = final["rag_call_id"]
    group = [e for e in events if e.get("rag_call_id") == call_id]
    expansion = next((e for e in group if e["kind"] == "graph_expansion"), None)
    candidates = {c.get("metadata", {}).get("path"): c for e in group if e["kind"] == "seed_candidates" for c in e.get("chunks", [])}
    seeds = [candidates[p] for p in expansion.get("seed_paths", []) if p in candidates] if expansion else []
    expanded = next((e.get("chunks", []) for e in group if e["kind"] == "graph_expanded_ranked"), [])
    llm_calls = [e for e in events if e["kind"] == "llm" and not e.get("error")]
    if target and gold_case["task"] == "risk":
        llm_calls = [e for e in llm_calls if clause_key(str(e.get("scope") or "").removeprefix("clause:")) == target]
    actual_prompt = prompt_text(llm_calls[-1].get("prompt")) if llm_calls else ""
    confirmed_context = [c for c in final.get("chunks", []) if c.get("text") and c["text"] in actual_prompt]
    stages = {"seed": seeds, "graph_expanded_ranked": expanded, "final_retrieval": final.get("chunks", [])}
    if llm_calls:
        stages["confirmed_full_chunks_in_llm_context"] = confirmed_context
    return stages, "Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."


def retrieval_scores(chunks, required, additional, negatives):
    refs = [ref(c.get("metadata", {})) for c in chunks]
    gold = set(x for x in required if x)
    relevant = gold | set(x for x in additional if x)
    negatives = set(x for x in negatives if x)
    if not gold:
        return None
    def coverage(ranked, expected):
        return sum(any(matches(actual, exp) for actual in ranked) for exp in expected)
    scores = {}
    for k in KS:
        top = refs[:k]
        scores[f"recall_at_{k}"] = coverage(top, gold) / len(gold)
        # Open-world real corpus has unjudged hits; pooled precision is explicit.
        seen = set()
        gains = []
        for actual in top:
            matched = {e for e in relevant if matches(actual, e)}
            gains.append(int(bool(matched - seen)))
            seen.update(matched)
        scores[f"pooled_precision_at_{k}"] = sum(gains) / k
        dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
        ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
        scores[f"pooled_binary_ndcg_at_{k}"] = dcg / ideal if ideal else None
    scores["mrr"] = next((1 / (i + 1) for i, actual in enumerate(refs) if any(matches(actual, expected) for expected in gold)), 0)
    scores["exact_provision_recall"] = coverage(refs, gold) / len(gold)
    scores["required_evidence_coverage"] = scores["exact_provision_recall"]
    expected_laws = {e[0] for e in gold}
    retrieved_laws = {a[0] for a in refs if a}
    scores["cross_document_retrieval_coverage"] = len(expected_laws & retrieved_laws) / len(expected_laws)
    scores["explicit_distractor_retrieval_rate"] = sum(any(matches(a, e) for e in negatives) for a in refs) / len(refs) if refs else 0
    scores["unjudged_hit_count"] = sum(not any(matches(a, e) for e in relevant | negatives) for a in refs)
    scores["retrieved_count"] = len(refs)
    return scores


def mean_metrics(rows):
    names = sorted({name for r in rows for name, value in r.items() if isinstance(value, (int, float))})
    out = {}
    for name in names:
        values = [r[name] for r in rows if r.get(name) is not None]
        out[name] = {"value": sum(values) / len(values) if values else None, "sample_count": len(values)}
    return out


def actual_severity(pred, case):
    if pred.get("execution_status") != "completed" or pred.get("pipeline_failure"):
        return None
    answer = pred.get("actual_answer") or {}
    if not isinstance(answer, dict):
        return None
    target = clause_key(case.get("input", {}).get("clause_id"))
    risks = answer.get("risks", [])
    matching = [r.get("severity") for r in risks if not target or clause_key(r.get("clause_ref")) == target]
    matching = [s for s in matching if s in LABELS]
    if matching:
        return min(matching, key=LABELS.index)
    # An absent RiskItem is only 'ok' when the real judge returned a parsed ok result.
    events = [e for e in pred.get("trace", []) if e["kind"] == "llm" and e.get("scope") and clause_key(str(e["scope"]).removeprefix("clause:")) == target]
    for e in reversed(events):
        try:
            raw = json.loads(e.get("raw_response") or "")
            if raw.get("severity") == "ok" and not raw.get("issue"):
                return "ok"
        except (TypeError, ValueError):
            pass
    return None


def observed_citations(pred):
    answer = pred.get("actual_answer") or {}
    if not isinstance(answer, dict):
        return []
    structured = [c for risk in answer.get("risks", []) for c in risk.get("legal_citations") or []]
    citations = [{"reference": ref(c), "citation": c, "source": "structured_risk_output"} for c in structured]
    text = answer.get("answer", "")
    if isinstance(text, str):
        for sentence in re.split(r"[\n;]", text):
            if re.search(r"(?:Điều\s+\d+|\d+/\d{4}/(?:QH\d+|NĐ-CP|ND-CP))", sentence, re.I):
                citations.append({"reference": None, "citation": sentence.strip(), "source": "qa_text_mention_unresolved"})
    return citations


def format_metric(value):
    return "N/A" if value is None else f"{value:.3f}"


def score_and_report(output):
    output = Path(output)
    predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    bundle = load("MIXED_34_TEST_CASES_V04.json")
    cases = {c["id"]: c for c in bundle["test_cases"]}
    pmap = {p["provision_id"]: p for p in load("LEGAL_PROVISIONS.json")}
    metadata = json.loads((output / "execution_metadata.json").read_text(encoding="utf-8"))
    stage_rows = defaultdict(list)
    by_difficulty, by_task = defaultdict(list), defaultdict(list)
    results, severity_pairs, errors = [], [], []
    review_rows = []
    for pred in predictions:
        case = cases[pred["id"]]
        gold = case["gold"]
        req_ids = gold.get("required_provision_ids", [])
        req = [ref(pmap[pid]) for pid in req_ids if pid in pmap]
        add = [ref(pmap[pid]) for pid in gold.get("additional_context_ids", []) if pid in pmap]
        neg = [ref(pmap[pid]) for pid in gold.get("irrelevant_provision_ids", []) if pid in pmap]
        stages, stage_note = stage_chunks(pred, case)
        scores = {stage: retrieval_scores(chunks, req, add, neg) for stage, chunks in stages.items()}
        for stage, metrics in scores.items():
            if metrics is not None:
                stage_rows[stage].append(metrics)
        actual = actual_severity(pred, case)
        expected = gold.get("risk_severity")
        if expected in LABELS and actual in LABELS:
            severity_pairs.append((expected, actual, pred["id"]))
        derived_execution = "failed" if pred.get("pipeline_failure") else pred.get("execution_status", "not_run")
        categories = ["Invalid/Unverified Ground Truth"]
        final = scores.get("final_retrieval")
        if pred.get("status") == "unsupported_capability":
            categories.append("Unsupported Capability")
        if derived_execution == "failed":
            categories.append("Pipeline Execution Failure")
        elif derived_execution == "not_run":
            categories.append("Environment/Dependency Block")
        if final is not None and final["required_evidence_coverage"] < 1:
            categories.append("Retrieval Missing Evidence")
            if final["retrieved_count"] and final["cross_document_retrieval_coverage"] == 0:
                categories.append("Wrong Legal Document")
            elif final["cross_document_retrieval_coverage"] > 0 and final["exact_provision_recall"] == 0:
                categories.append("Wrong Article/Clause/Point")
        if expected in LABELS and actual in LABELS and expected != actual:
            categories.append("Incorrect Risk Classification")
        correctness = "Pending human legal review"
        if derived_execution == "failed":
            correctness = "Fail (execution)"
        elif derived_execution == "not_run":
            correctness = "Not run"
        elif pred.get("status") == "unsupported_capability":
            correctness = "Unsupported capability; observed output retained"
        required_edges = case.get("expected_legal_graph", {}).get("required_relation_edge_ids", [])
        cited = observed_citations(pred)
        row = {"case_id": pred["id"], "topic": case.get("topic"), "task": case["task"], "difficulty": case["difficulty"]["level"],
               "question": pred.get("input", {}).get("question"), "context": pred.get("input", {}).get("scenario"),
               "as_of_date": case["input"].get("as_of_date"), "transaction_date": case["input"].get("transaction_date"),
               "expected_evidence": req_ids, "actual_retrieved_evidence": {stage: [c.get("metadata", {}) for c in chunks] for stage, chunks in stages.items()},
               "expected_answer": gold.get("expected_answer"), "actual_answer": pred.get("actual_answer"),
               "expected_severity": expected, "actual_severity": actual, "expected_relations": required_edges,
               "actual_relations": pred.get("legal_relations"), "actual_structured_legal_citations": cited,
               "execution_status": derived_execution, "capability_status": pred.get("status"), "pass_fail": correctness,
               "reason": pred.get("error") or pred.get("capabilities") or stage_note, "error_categories": categories,
               "retrieval_latency_ms": pred.get("retrieval_ms"), "generation_latency_ms": pred.get("generation_ms"),
               "total_latency_ms": pred.get("total_ms"), "inference_latency_ms": pred.get("inference_total_ms"),
               "retry_count": pred.get("retry_count"), "model_calls": pred.get("model_calls"), "model_config": pred.get("config"),
               "retrieval_scores": scores, "gold_status": "synthetic_draft_not_independently_legally_verified"}
        results.append(row)
        by_difficulty[row["difficulty"]].append(row)
        by_task[row["task"]].append(row)
        errors.append({"id": pred["id"], "categories": categories, "details": pred.get("error") or pred.get("pipeline_failure") or stage_note})
        review_rows.append({"case_id": pred["id"], "task": case["task"], "expected_answer_draft": gold.get("expected_answer"),
                            "actual_answer": pred.get("actual_answer"), "answer_correctness_0_2": "", "faithfulness_0_2": "",
                            "relevance_0_2": "", "citation_support_0_2": "", "legal_grounding_0_2": "", "abstention_0_2": "",
                            "hallucinated_claim_count": "", "reviewed_claim_count": "", "reviewer": "", "reviewed_at": "", "notes": ""})
    def csv_write(name, rows):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else [])
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})
    csv_write("CASE_BY_CASE_RESULTS.csv", results)
    csv_write("HUMAN_REVIEW_TEMPLATE.csv", review_rows)
    write_json(output / "case_scores.json", results)
    retrieval = {"label_status": "Exploratory structural matching to synthetic draft qrels; not legally verified accuracy.",
                 "all_cases": len(predictions), "stages": {stage: mean_metrics(rows) for stage, rows in stage_rows.items()},
                 "stage_case_counts": {stage: len(rows) for stage, rows in stage_rows.items()},
                 "precision_at_k": {"value": None, "sample_count": 0, "reason": "Open real corpus contains unjudged hits. Pooled precision diagnostics are reported separately, treating unjudged as nonrelevant."},
                 "relation_edge_recall": {"value": None, "sample_count": 0, "reason": "Graph expansion exposes paths/documents, not observed relation edge IDs. Corpus edge presence is not evidence of use."},
                 "exact_versioned_provision_recall": {"value": None, "sample_count": 0, "reason": "Retrieved metadata does not expose verified historical provision-version IDs. Structural scores do not establish version identity."},
                 "notes": ["K precision denominator is K, including unfilled slots.", "Article-level labels match descendants of the same article; clause/point labels require the corresponding path level.",
                           "Identity matching does not establish historical text/version correctness; an explicit expected version would require an identical observed version ID.", "Pooled ranking gains count the first hit for each relevant provision only, so duplicate chunk hits cannot inflate nDCG above one.", "Final-context metrics conservatively include full retrieved chunks actually observed in the model prompt. Citations are scored separately.",
                           "Risk deterministic branches without observed RAG calls are not treated as seed retrieval; their citation output remains available."]}
    write_json(output / "RETRIEVAL_METRICS.json", retrieval)
    generation = {"generated_or_fallback_outputs": sum(p.get("actual_answer") is not None for p in predictions),
                  "human_reviewed_cases": 0, "judge": "No calibrated legal judge configured; no semantic-similarity-only correctness score.",
                  "metrics": {name: {"value": None, "sample_count": 0, "reason": "Pending review using rubric and actual prompts/evidence."} for name in
                              ("answer_correctness", "faithfulness", "answer_relevance", "citation_support_accuracy", "hallucination_rate", "legal_grounding", "abstention_quality")},
                  "structured_legal_citation_cases": sum(any(c['source']=='structured_risk_output' for c in r["actual_structured_legal_citations"]) for r in results),
                  "qa_citation_observability": "QA source_clauses identifies contract clauses only; legal citations in answer text have not been silently replaced with retrieved chunks or inferred source IDs."}
    write_json(output / "GENERATION_METRICS.json", generation)
    temporals = [r for r in results if r["case_id"].startswith("TEMP-")]
    temporal = {"case_count": len(temporals), "execution_counts": dict(Counter(r["execution_status"] for r in temporals)),
                "capability_counts": dict(Counter(r["capability_status"] for r in temporals)),
                "metrics": {name: {"value": None, "sample_count": 0, "reason": "No independently reviewed temporal selection/version labels in output; pipeline does not forward benchmark dates into retrieval."} for name in
                            ("temporal_version_accuracy", "applicable_law_selection_accuracy", "outdated_citation_rate", "relation_edge_recall", "transitional_provision_accuracy")},
                "structural_retrieval_diagnostic": mean_metrics([r["retrieval_scores"]["final_retrieval"] for r in temporals if r["retrieval_scores"].get("final_retrieval") is not None]),
                "notes": ["is_effective=false is not equated with never-applicable law; transitional exceptions require reviewed selection reasoning.", "Historical N145 snapshots are unverified and incomplete; no text/version exact score is asserted."]}
    write_json(output / "TEMPORAL_METRICS.json", temporal)
    confusion = {a: {b: 0 for b in LABELS} for a in LABELS}
    for expected, actual, _id in severity_pairs:
        confusion[expected][actual] += 1
    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[a][label] for a in LABELS)
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        f1 = 2 * tp / (support + predicted) if support + predicted else None
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support, "predicted": predicted}
    labeled = [r for r in results if r["expected_severity"] in LABELS]
    critical = [r for r in labeled if r["expected_severity"] == "critical"]
    comparable_critical = [(a, b) for a, b, _id in severity_pairs if a == "critical"]
    correct = sum(a == b for a, b, _id in severity_pairs)
    risk = {"repository_labels": list(LABELS), "risk_task_count": sum(r["task"] == "risk" for r in results), "gold_labeled_cases": len(labeled),
            "comparable_cases": len(severity_pairs), "unobservable_or_failed_labeled_cases": len(labeled) - len(severity_pairs),
            "severity_accuracy": {"value": correct / len(severity_pairs) if severity_pairs else None, "sample_count": len(severity_pairs)},
            "end_to_end_correct_detection_fraction": {"value": correct / len(labeled) if labeled else None, "sample_count": len(labeled), "note": "Unavailable/failed outputs count as no correct detection. This is operational coverage, not conditional classifier accuracy."},
            "confusion_matrix": confusion, "by_severity": per_class,
            "macro_f1": {"value": sum(v['f1'] for v in per_class.values() if v['f1'] is not None) / sum(v['f1'] is not None for v in per_class.values()) if any(v['f1'] is not None for v in per_class.values()) else None, "sample_count": len(severity_pairs), "note": "Mean over classes with nonzero gold or predicted support; absent classes remain null."},
            "critical_risk_recall": {"value": sum(b == "critical" for a, b in comparable_critical) / len(comparable_critical) if comparable_critical else None, "sample_count": len(comparable_critical), "note": "Only comparable observed labels; unavailable outputs are not forced into classification metrics."},
            "false_negative_rate": {"value": sum(b != "critical" for a, b in comparable_critical) / len(comparable_critical) if comparable_critical else None, "sample_count": len(comparable_critical)},
            "end_to_end_critical_detection_fraction": {"value": sum(r["actual_severity"] == "critical" for r in critical) / len(critical) if critical else None, "sample_count": len(critical), "note": "Operational fraction with a confirmed detection across all gold-critical cases, including cases blocked from execution; not conditional classifier recall."},
            "citation_correctness": {"value": None, "sample_count": 0, "reason": "Requires reviewed citation support."},
            "evidence_span_accuracy": {"value": None, "sample_count": 0, "reason": "Output does not expose a comparable normalized predicted input span."}}
    write_json(output / "RISK_CLASSIFICATION_METRICS.json", risk)
    write_json(output / "error_analysis.json", errors)
    render_reports(output, predictions, results, metadata, retrieval, generation, temporal, risk, errors, by_difficulty, by_task)
    charts(output, results, risk)


def render_reports(output, predictions, results, metadata, retrieval, generation, temporal, risk, errors, by_difficulty, by_task):
    status_counts = Counter(r["capability_status"] for r in results)
    execution_counts = Counter(r["execution_status"] for r in results)
    final = retrieval["stages"].get("final_retrieval", {})
    audit_path = BASELINE_RUN / "benchmark_validation.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    coverage_path = BASELINE_RUN / "corpus_coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.exists() else {}
    lines = ["# ContractLens Mixed Temporal Legal Evaluation v0.4.1 — Baseline thực nghiệm", "",
             ("Cập nhật theo yêu cầu dừng Gemini: đã có RAG-only đủ 34 case, không gọi LLM, tại [rag_only/RAG_ONLY_REPORT.md](../rag_only/RAG_ONLY_REPORT.md). Các kết quả generation bị quota bên dưới được giữ riêng." if (output.parent / 'rag_only' / 'RAG_ONLY_REPORT.md').exists() else ""), "",
             f"Thời gian UTC: {metadata.get('started_at')} → {metadata.get('finished_at')}. Múi giờ người dùng: Asia/Bangkok (UTC+7).", "",
             f"Đã ghi trạng thái cho {len(results)} case: thực thi hoàn tất {execution_counts['completed']}, lỗi/bị ngắt {execution_counts['failed']}, chưa chạy {execution_counts['not_run']}. Trong các output quan sát được, {status_counts['unsupported_capability']} case được đánh dấu capability chưa hỗ trợ; các nhóm này chồng với thực thi hoàn tất.",
             "**Baseline chưa chạy đầy đủ do quota API. Các metric trên tập đã chạy không đại diện cho đủ 34 case.**" if metadata.get('termination') else "",
             f"Nguyên nhân dừng: {metadata.get('termination', 'Không có dừng do môi trường được ghi nhận.')} Quota quan sát từ API: {metadata.get('quota_evidence', {})}.",
             "", "## Phạm vi và độ tin cậy", "", "Existing Corpus Baseline chạy trên bản sao vật lý của corpus PostgreSQL/Neo4j hiện có. Chỉ nạp hợp đồng DOCX đầu vào và tạo checkpoint trong bản sao; không ingest luật benchmark. Controlled Fixture Evaluation không chạy vì corpus luật fixture chưa được kiểm chứng độc lập.",
             "34 case và căn cứ benchmark là synthetic draft. Điểm retrieval dưới đây chỉ đo so khớp cấu trúc với nhãn nháp; chưa phải độ chính xác tư vấn pháp luật. Các điểm answer correctness/faithfulness/hallucination chưa có chuyên gia hoặc judge hiệu chuẩn nên để null, không thay bằng similarity.", "",
             "## Cấu hình và corpus", "", "```json", json.dumps(metadata.get("config"), ensure_ascii=False, indent=2), "```", "",
             f"Corpus: {coverage.get('document_metadata_rows')} metadata văn bản; {coverage.get('documents_with_chunks')} văn bản có chunk; {coverage.get('chunk_count')} chunk. Kiểm tra fingerprint bảng luật trước/sau: **{metadata.get('legal_corpus_unchanged')}**.",
             "Metadata có thể là stub; số văn bản có chunk được báo cáo riêng. Định danh Điều=D, Khoản=K, Điểm=chữ trong ltree được chuẩn hóa bằng số hiệu văn bản, không so riêng portal doc_id. Chi tiết bảo vệ volume gốc và sự cố tên project Compose: ISOLATION_AND_EXECUTION_NOTES.md.", "",
             "## Theo độ khó", "", "| Nhóm | Tổng | Hoàn tất | Lỗi | Chưa chạy | Unsupported | Recall@5 (n) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for level in ("easy", "medium", "hard", "expert"):
        group = by_difficulty.get(level, [])
        counts = Counter(r["execution_status"] for r in group)
        values = [r["retrieval_scores"]["final_retrieval"]["recall_at_5"] for r in group if r["retrieval_scores"].get("final_retrieval") is not None]
        lines.append(f"| {level.title()} | {len(group)} | {counts['completed']} | {counts['failed']} | {counts['not_run']} | {sum(r['capability_status']=='unsupported_capability' for r in group)} | {format_metric(sum(values)/len(values) if values else None)} ({len(values)}) |")
    lines += ["", "## Theo nhiệm vụ", "", "| Task | Tổng | Hoàn tất | Lỗi | Chưa chạy |", "|---|---:|---:|---:|---:|"]
    for task, group in sorted(by_task.items()):
        counts = Counter(r["execution_status"] for r in group)
        lines.append(f"| {task} | {len(group)} | {counts['completed']} | {counts['failed']} | {counts['not_run']} |")
    lines += ["", "## Retrieval và GraphRAG", "", "| Stage | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | Exact provision recall |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for stage, metrics in retrieval["stages"].items():
        names = ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "exact_provision_recall")
        lines.append(f"| {stage} | {retrieval['stage_case_counts'][stage]} | " + " | ".join(format_metric(metrics.get(name, {}).get("value")) for name in names) + " |")
    lines += ["", "Seed là các seed path thực tế đưa vào graph. Graph-expanded là danh sách đã mở rộng và xếp hạng trước lọc/truncate cuối. Final retrieval là các chunk trả về. Context stage chỉ đếm full chunk có mặt trong prompt thực tế; raw prompt được lưu trong trace. Citations trong output được giữ riêng.",
             "Precision/nDCG theo pooled qrels chỉ là chẩn đoán mở rộng trong RETRIEVAL_METRICS.json; corpus thật có chunk chưa được gán relevance nên không tuyên bố đó là precision đầy đủ. Relation Edge Recall để null vì pipeline không expose các edge ID đã dùng.", "",
             "## Chất lượng đáp án và rủi ro", "", f"Có {generation['generated_or_fallback_outputs']} output sinh hoặc fallback; 0 case đã được con người thẩm định. Xem ANSWER_RUBRIC.md và HUMAN_REVIEW_TEMPLATE.csv.",
             f"Severity: {risk['comparable_cases']}/{risk['gold_labeled_cases']} case có nhãn gold và output so sánh được; accuracy điều kiện={format_metric(risk['severity_accuracy']['value'])}. Critical Risk Recall={format_metric(risk['critical_risk_recall']['value'])} (n={risk['critical_risk_recall']['sample_count']}). Các output thiếu/lỗi không bị ép thành nhãn ok hoặc false negative.",
             "Chỉ dùng nhãn critical/warning/ok. Không suy ra ok từ kết quả workflow rỗng hoặc từ judge bị lỗi.", "",
             "## Temporal Legal RAG", "", f"Nhóm temporal gồm {temporal['case_count']} case; trạng thái capability: {temporal['capability_counts']}. Output pipeline hiện tại vẫn được lưu để phân tích.",
             "QA chuẩn không forward as_of_date/transaction_date vào retrieve_legal; vector search loại c.is_effective=false và document status_flag=2 trước khi ranking theo thời gian. Risk workflow cũng không nhận hai ngày này. Vì vậy chưa có chứng cứ hỗ trợ time-travel retrieval hay quy định chuyển tiếp đầy đủ.",
             "Không đồng nhất hết hiệu lực chung với không được áp dụng trong ngoại lệ chuyển tiếp. Temporal Version Accuracy, Applicable Law Selection, Outdated Citation Rate và Transitional Accuracy chưa được chấm pháp lý.", "",
             "## Các lỗi quan sát được", ""]
    counts = Counter(category for error in errors for category in error["categories"])
    for name, count in counts.items():
        lines.append(f"- {name}: {count} case.")
    lines += ["", "## Hạn chế benchmark", "", "- Tất cả case synthetic draft; kiểm tra schema không xác nhận tính đúng pháp lý.",
              f"- Status manifest thiếu các luật được provision tham chiếu: {', '.join(audit.get('statute_status_manifest_omissions', []))}.",
              "- Ba snapshot N145 chưa có toàn văn kiểm chứng; các sửa đổi sau 2024 chưa được map đầy đủ.",
              "- Gold risk_severity chỉ có ở 11 case; hai temporal risk không đủ nhãn severity để ép tính classifier metric.",
              "- Qrels chỉ bao phủ một tập provision nhỏ, không gán relevance đầy đủ cho corpus thật. Ground truth citations không phải toàn văn mọi điều luật.",
              "- Các file .txt được manifest khai báo không tồn tại; DOCX là đầu vào thực tế. Text/span trên embedded reference có thể khác header của DOCX.",
              "", "## Ưu tiên cải tiến sau baseline", "", "1. Khôi phục quota model hiện tại để chạy tập đầy đủ. Sửa contract extraction/validation để xử lý tên bên chưa được cung cấp và phân biệt lỗi workflow với kết quả không có rủi ro; thêm đo độ bao phủ điều khoản đã thực sự được đánh giá.",
              "2. Rà soát parser/chunker cho Mục/Điều và cơ chế kiểm tra citations; giữ đúng định danh điều khoản của hợp đồng synthetic.",
              "3. Rà soát hiệu lực cấp điều khoản: BLLĐ 2019/NĐ145 có status_flag=4 nhưng toàn bộ chunk is_effective=false; Luật BHXH 2024 trong DB có eff_to=2026-01-01/status=2, khác draft benchmark. Cần đối chiếu nguồn chính thức, không tự sửa nhãn. Rà soát hardcode Hợp đồng lao động trong QA đa lĩnh vực và corpus Luật Thương mại còn thiếu.",
              "4. Thiết kế retrieval theo phiên bản và thời điểm, quan hệ có phạm vi Điều/Khoản/Điểm, cùng logic chuyển tiếp; bổ sung logging edge thực dùng.",
              "5. Thẩm định gold với chuyên gia pháp luật, hoàn thiện snapshot lịch sử và relevance judgments; sau đó mới dùng tập khác để tuning và chạy lại đánh giá.",
              "", "![Trạng thái thực thi theo độ khó](charts/execution_by_difficulty.png)", "", "![Retrieval theo độ khó](charts/retrieval_by_difficulty.png)", ""]
    (output / "BASELINE_EVALUATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    analysis = ["# ERROR ANALYSIS", "", "Các category tự động dưới đây dựa trên output/trace. Không tự kết luận hallucination, unsupported legal conclusion hay incorrect abstention khi chưa có review nội dung.", "",
                "Lỗi pipeline có thể sinh fallback/analysis rỗng; những trường hợp đó được tách khỏi dự đoán nhãn risk hợp lệ. Có cạnh trong corpus không có nghĩa cạnh được dùng trong answer.", ""]
    for error in errors:
        analysis += [f"## {error['id']}", "", ", ".join(error["categories"]), "", json.dumps(error["details"], ensure_ascii=False), ""]
    (output / "ERROR_ANALYSIS.md").write_text("\n".join(analysis), encoding="utf-8")
    rubric = """# Rubric review nội dung pháp lý

Tất cả điểm sau phải do chuyên gia hoặc judge đã hiệu chuẩn thực hiện trên câu hỏi, facts đầu vào, prompt/evidence thực tế và nguồn pháp luật đúng phiên bản. Nhãn nháp không được dùng như xác minh pháp lý.

- QA: kiểm tra từng claim về chủ thể, điều kiện, ngoại lệ và nghĩa vụ; 0=sai trọng yếu, 1=đúng một phần/cần điều kiện, 2=đúng và đủ trong phạm vi facts.
- Multi-hop: ngoài QA, phải kết nối đủ căn cứ/quan hệ đúng hướng và phạm vi; không cho điểm chỉ vì kể tên nhiều luật.
- Risk: so đúng clause được hỏi, severity theo critical/warning/ok và giải thích mâu thuẫn/nguy cơ; không coi mọi missing evidence là vi phạm luật.
- Classification: dựa trên facts quản lý/tiền lương/độc lập và điều kiện áp dụng; chấp nhận kết luận có điều kiện khi thiếu facts.
- Temporal: xác định as_of và transaction, phiên bản, thời điểm và ngoại lệ chuyển tiếp. Không gán mọi văn bản hết hiệu lực là forbidden citation.

Faithfulness: mỗi claim có được evidence thực sự trong prompt hỗ trợ không (0=không, 1=một phần, 2=đầy đủ). Relevance: có trả lời đúng câu hỏi và facts không. Citation support: câu trích có thật, đúng Điều/Khoản/Điểm/phiên bản và hỗ trợ claim không. Legal grounding: căn cứ có đủ hiệu lực/phạm vi không. Abstention: từ chối/làm rõ có đúng với phần thiếu dữ kiện hay không.

Hallucination rate cần denominator số claim đã review và số claim bị xác nhận bịa/sai; không dùng số chunk không thuộc gold làm số hallucination. Mọi điểm tự động, điểm human và số mẫu phải báo cáo riêng. HUMAN_REVIEW_TEMPLATE.csv để trống đến khi có review thật.
"""
    (output / "ANSWER_RUBRIC.md").write_text(rubric, encoding="utf-8")


def charts(output, results, risk):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        directory = output / "charts"
        directory.mkdir(exist_ok=True)
        levels = ("easy", "medium", "hard", "expert")
        fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
        bottom = [0] * 4
        for status, color in (("completed", "#25806a"), ("failed", "#c34a4a"), ("not_run", "#9ba6b0")):
            values = [sum(r["difficulty"] == level and r["execution_status"] == status for r in results) for level in levels]
            ax.bar([x.title() for x in levels], values, bottom=bottom, label=status, color=color)
            bottom = [a + b for a, b in zip(bottom, values)]
        ax.set(ylabel="Cases", title="Observed execution status by difficulty")
        ax.legend(frameon=False)
        fig.savefig(directory / "execution_by_difficulty.png", dpi=180)
        fig.savefig(directory / "execution_by_difficulty.svg")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
        means, labels = [], []
        for level in levels:
            values = [r["retrieval_scores"]["final_retrieval"]["recall_at_5"] for r in results if r["difficulty"] == level and r["retrieval_scores"].get("final_retrieval") is not None]
            means.append(sum(values) / len(values) if values else float("nan"))
            labels.append(f"{level.title()}\n(n={len(values)})")
        bars = ax.bar(labels, means, color="#3a6d9b")
        ax.bar_label(bars, fmt="%.3f", padding=3)
        ax.set(ylim=(0, 1.08), ylabel="Recall@5", title="Structural retrieval vs draft benchmark labels")
        fig.savefig(directory / "retrieval_by_difficulty.png", dpi=180)
        fig.savefig(directory / "retrieval_by_difficulty.svg")
        plt.close(fig)
        write_json(output / "chart_metadata.json", {"created": True, "notes": "NaN means no scored retrieval case; never plotted as zero."})
    except ImportError as exc:
        write_json(output / "chart_metadata.json", {"created": False, "error": str(exc)})


if __name__ == "__main__":
    import sys
    score_and_report(Path(sys.argv[1]) if len(sys.argv) > 1 else BASELINE_RUN)
