"""Score saved retrieval observations only; this program never calls a model."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.runtime_adapter import ROOT, RUNS
from evaluation.audit import load
from evaluation.scoring import ref, stage_chunks, retrieval_scores, mean_metrics, charts, clause_key, format_metric


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def score(output):
    output = Path(output)
    predictions = [json.loads(line) for line in (output / 'predictions.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    metadata = json.loads((output / 'execution_metadata.json').read_text(encoding='utf-8'))
    if not metadata.get('finished_at'):
        raise RuntimeError('Retrieval has not finished; no gold is read until the run is complete.')
    bundle = load('MIXED_34_TEST_CASES_V04.json')
    cases = {c['id']: c for c in bundle['test_cases']}
    provisions = {p['provision_id']: p for p in load('LEGAL_PROVISIONS.json')}
    aggregate = defaultdict(list)
    rows, expansion_pairs, contract_span_scores, contract_id_scores = [], [], [], []
    for pred in predictions:
        case = cases[pred['id']]
        gold = case['gold']
        expected = gold.get('required_provision_ids', [])
        required = [ref(provisions[pid]) for pid in expected if pid in provisions]
        additional = [ref(provisions[pid]) for pid in gold.get('additional_context_ids', []) if pid in provisions]
        negatives = [ref(provisions[pid]) for pid in gold.get('irrelevant_provision_ids', []) if pid in provisions]
        stages, note = stage_chunks(pred, case)
        values = {stage: retrieval_scores(chunks, required, additional, negatives) for stage, chunks in stages.items()}
        for stage, metrics in values.items():
            if metrics is not None:
                aggregate[stage].append(metrics)
        if values.get('seed') is not None and values.get('final_retrieval') is not None:
            expansion_pairs.append((pred['id'], values['seed']['required_evidence_coverage'], values['final_retrieval']['required_evidence_coverage']))
        span_covered, clause_id_exact = None, None
        if pred.get('contract_retrieval') and case['input'].get('clause_text'):
            text = '\n'.join(c['text'] for c in pred['contract_retrieval'])
            normalize = lambda s: ' '.join(str(s).split())
            span_covered = normalize(case['input']['clause_text']) in normalize(text)
            contract_span_scores.append(int(span_covered))
            target = clause_key(case['input'].get('clause_id'))
            clause_id_exact = any(clause_key(c.get('metadata', {}).get('clause_number')) == target for c in pred['contract_retrieval'])
            contract_id_scores.append(int(clause_id_exact))
        final = values.get('final_retrieval')
        categories = ['Invalid/Unverified Ground Truth']
        if pred['execution_status'] != 'completed':
            categories.append('Retrieval Execution Failure')
        elif final is not None and final['required_evidence_coverage'] < 1:
            categories.append('Retrieval Missing Evidence')
            if final['retrieved_count'] and final['cross_document_retrieval_coverage'] == 0:
                categories.append('Wrong Legal Document')
            elif final['cross_document_retrieval_coverage'] and final['exact_provision_recall'] == 0:
                categories.append('Wrong Article/Clause/Point')
        if case['id'].startswith('TEMP-'):
            categories.append('Unsupported Temporal Capability')
        rows.append({'case_id': pred['id'], 'task': case['task'], 'topic': case.get('topic'), 'difficulty': case['difficulty']['level'],
                     'question': pred['input']['question'], 'context': pred['input'].get('scenario'),
                     'as_of_date': pred['input'].get('as_of_date'), 'transaction_date': pred['input'].get('transaction_date'),
                     'expected_evidence': expected, 'observed_evidence': {s: [c.get('metadata', {}) for c in cs] for s, cs in stages.items()},
                     'retrieval_scores': values, 'execution_status': pred['execution_status'], 'temporal_capability': pred['temporal_capability'],
                     'structural_pass_fail': 'Pass' if final and final['required_evidence_coverage'] == 1 else 'Fail' if final is not None else 'Not scored',
                     'reason': categories, 'contract_text_span_covered': span_covered, 'contract_clause_id_exact': clause_id_exact,
                     'retrieval_latency_ms': pred['retrieval_ms'], 'contract_retrieval_latency_ms': pred.get('contract_retrieval_ms'),
                     'total_latency_ms': pred['total_ms'], 'generation_latency_ms': None, 'model_calls': 0,
                     'adapter': pred.get('adapter'), 'gold_status': 'synthetic_draft_not_independently_reviewed'})
    write_json(output / 'case_scores.json', rows)
    with (output / 'CASE_BY_CASE_RESULTS.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows)
    metrics = {'mode': 'rag_only_existing_corpus', 'case_count': len(predictions), 'execution_counts': dict(Counter(p['execution_status'] for p in predictions)),
               'generation_model_calls': 0, 'stages': {stage: mean_metrics(values) for stage, values in aggregate.items()},
               'stage_case_counts': {stage: len(values) for stage, values in aggregate.items()},
               'graph_expansion_effect': {'paired_cases': len(expansion_pairs), 'improved_coverage': sum(f > s for _, s, f in expansion_pairs),
                                          'reduced_coverage': sum(f < s for _, s, f in expansion_pairs), 'unchanged_coverage': sum(f == s for _, s, f in expansion_pairs),
                                          'mean_coverage_change': sum(f - s for _, s, f in expansion_pairs) / len(expansion_pairs) if expansion_pairs else None},
               'contract_text_span_coverage': {'value': sum(contract_span_scores) / len(contract_span_scores) if contract_span_scores else None, 'sample_count': len(contract_span_scores)},
               'contract_clause_id_exact_match': {'value': sum(contract_id_scores) / len(contract_id_scores) if contract_id_scores else None, 'sample_count': len(contract_id_scores)},
               'precision_at_k': {'value': None, 'sample_count': 0, 'reason': 'Unjudged real-corpus hits prevent exhaustive relevance precision. Pooled diagnostic values treat unjudged as nonrelevant.'},
               'relation_edge_recall': {'value': None, 'sample_count': 0, 'reason': 'Observed expansion returns path/doc IDs; no actual used relation edge IDs are exposed.'},
               'exact_versioned_provision_recall': {'value': None, 'sample_count': 0, 'reason': 'Verified historical provision-version IDs are not present in retrieved metadata.'},
               'llm_context_evidence': {'value': None, 'sample_count': 0, 'reason': 'No model prompt or answer was generated.'},
               'output_citations': {'value': None, 'sample_count': 0, 'reason': 'No answer generation; retrieved chunks are not treated as citations.'},
               'label_quality': 'All labels are synthetic draft. Structural identity scores do not establish legal correctness or correct historical text.'}
    write_json(output / 'RETRIEVAL_METRICS.json', metrics)
    temporal_rows = [r for r in rows if r['case_id'].startswith('TEMP-')]
    temporal = {'case_count': len(temporal_rows), 'temporal_retrieval_supported': False,
                'structural_diagnostic': mean_metrics([r['retrieval_scores']['final_retrieval'] for r in temporal_rows if r['retrieval_scores'].get('final_retrieval') is not None]),
                'temporal_version_accuracy': {'value': None, 'sample_count': 0, 'reason': 'Benchmark dates are not forwarded by baseline QA/risk entry points. No verified version snapshots in output.'},
                'applicable_law_selection_accuracy': {'value': None, 'sample_count': 0}, 'outdated_citation_rate': {'value': None, 'sample_count': 0},
                'note': 'is_effective=false is not interpreted as never legally applicable. No temporal answer/reasoning is generated.'}
    write_json(output / 'TEMPORAL_RETRIEVAL_DIAGNOSTICS.json', temporal)
    by_diff, by_task = defaultdict(list), defaultdict(list)
    for row in rows:
        by_diff[row['difficulty']].append(row)
        by_task[row['task']].append(row)
    lines = ['# ContractLens RAG-only — Existing Corpus Baseline', '',
             f"Đã chạy retrieval cho **{len(predictions)}/34 case**. Trạng thái: {metrics['execution_counts']}. **0 lượt gọi Gemini; không sinh đáp án/citations LLM.**", '',
             f"Thời gian UTC: {metadata['started_at']} → {metadata['finished_at']}. Corpus luật fingerprint trước/sau giống nhau: **{metadata['legal_corpus_unchanged']}**.",
             f"Gemini credential trong worker: {metadata['gemini_credential_present']}. LLM client modules loaded: {metadata.get('llm_client_modules_loaded')}.", '',
             '## Phương pháp', '',
             'Chỉ QUESTIONS_ONLY_NO_GOLD được dùng khi truy xuất. BGE-M3 được đọc từ cache cục bộ; PostgreSQL/Neo4j dùng corpus hiện có trong bản sao. Không ingest luật fixture, sửa cờ hiệu lực, thêm căn cứ gold hay tuning Top-K.',
             'QA/multi-hop/classification chạy first-pass retrieve_legal như QA hiện tại (k=5, không gán cứng contract_type). Risk chạy LegalGraphRag.retrieve_for_clause với question/scenario đầu vào (k_seed=4, max_total=10); không thực hiện LLM clause extraction. Đây là đánh giá retrieval theo fact pattern, không phải đánh giá rủi ro hợp đồng đầu-cuối.',
             '7 DOCX được parse/chunk/embed bằng UploadContract thực tế trong database bản sao; contract retrieval được lưu riêng với legal retrieval. Gold được đọc sau khi hoàn tất toàn bộ retrieval.', '',
             '## Kết quả theo stage', '', '| Stage | n | R@1 | R@3 | R@5 | R@10 | MRR | Provision coverage |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for stage, values in metrics['stages'].items():
        names = ('recall_at_1', 'recall_at_3', 'recall_at_5', 'recall_at_10', 'mrr', 'required_evidence_coverage')
        lines.append(f"| {stage} | {metrics['stage_case_counts'][stage]} | " + ' | '.join(format_metric(values.get(n, {}).get('value')) for n in names) + ' |')
    lines += ['', 'Seed là seed path thực tế đưa vào graph. Graph-expanded ranked được ghi trước lọc/truncation cuối; final retrieval là chunk được trả về. Không có final context gửi LLM hoặc cited chunks trong lần chạy này.',
              f"Hiệu ứng graph trên provision coverage: {metrics['graph_expansion_effect']}.", '', '## Theo độ khó và nhiệm vụ', '', '| Nhóm | n | Final R@5 | Final provision coverage |', '|---|---:|---:|---:|']
    for name, group in [(level, by_diff[level]) for level in ('easy', 'medium', 'hard', 'expert')] + list(sorted(by_task.items())):
        values = [r['retrieval_scores']['final_retrieval'] for r in group if r['retrieval_scores'].get('final_retrieval') is not None]
        mean = mean_metrics(values)
        lines.append(f"| {name} | {len(values)} | {format_metric(mean.get('recall_at_5', {}).get('value'))} | {format_metric(mean.get('required_evidence_coverage', {}).get('value'))} |")
    lines += ['', '## Contract retrieval', '', f"Text-span coverage: {metrics['contract_text_span_coverage']}; exact clause ID: {metrics['contract_clause_id_exact_match']}.",
              'Đây là hai metric khác nhau: tìm thấy toàn bộ text hợp đồng trong một chunk không có nghĩa parser nhận đúng Điều/Mục. Các heading dạng Điều 1 xuống dòng hoặc Mục A không phù hợp regex yêu cầu dấu câu của pipeline hiện tại.', '',
              '## Giới hạn và lỗi cần ưu tiên', '',
              '- Ground truth synthetic draft chưa được chuyên gia xác minh. Các score là cấu trúc so với nhãn nháp, không chứng minh câu trả lời pháp luật đúng.',
              '- Corpus có BLLĐ 2019/NĐ145 nhưng tất cả chunk của các văn bản này đang is_effective=false. Các chunk bị loại ngay ở seed SQL. Luật Thương mại 36/2005/QH11 chưa có trong corpus được tìm thấy. Chi tiết ở báo cáo corpus coverage cấp trên.',
              '- Corpus BHXH 2024 có eff_to/status khác metadata nháp của benchmark; cần đối chiếu nguồn chính thức, chưa tự sửa bên nào.',
              '- 14 case temporal chỉ có structural retrieval diagnostic. Không có time-travel retrieval được xác nhận; không đánh đồng luật hết hiệu lực chung với không áp dụng chuyển tiếp.',
              '- Precision/nDCG pooled có trong JSON và được ghi rõ giả định unjudged=nonrelevant; không phải precision có đánh giá relevance đầy đủ. Exact identity không kiểm chứng lịch sử phiên bản.',
              '- Relation Edge Recall để null: graph có cạnh không chứng minh cạnh đã được pipeline dùng.',
              '- Đề xuất sau baseline: kiểm tra hiệu lực cấp điều khoản và thiếu corpus, cải thiện parser/chunker, routing domain QA và observability edge; sau đó mới triển khai temporal retrieval. Lần chạy này không thay các thuật toán đó.', '',
              '![Trạng thái retrieval](charts/execution_by_difficulty.png)', '', '![Recall theo độ khó](charts/retrieval_by_difficulty.png)', '']
    full_coverage = sum(r['structural_pass_fail'] == 'Pass' for r in rows)
    lines += [f"Full required-provision coverage: {full_coverage}/{len(rows)} case. Đây là structural pass, không phải pass nội dung pháp lý.", '',
              'Coverage tăng không đồng nghĩa ranking tốt hơn: so sánh Recall@1 và MRR ở bảng stage; graph expansion có thể thay đổi thứ tự hoặc đẩy evidence xuống dưới. Không kết luận GraphRAG cải thiện toàn diện từ một metric.', '',
              'Chi tiết lỗi từng case: ERROR_ANALYSIS.md. Corpus coverage: ../CORPUS_COVERAGE_REPORT.md.', '']
    (output / 'RAG_ONLY_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    categories = Counter(reason for row in rows for reason in row['reason'])
    error_lines = ['# RAG-only error analysis', '', 'Các nhãn lỗi dưới đây chỉ là so khớp cấu trúc với ground truth draft. Không có answer generation để chấm hallucination hoặc citation support.', '',
                   *[f"- {category}: {count} case" for category, count in categories.items()], '',
                   '| Case | Final required coverage | Required provisions | Categories |', '|---|---:|---|---|']
    for row in rows:
        value = (row['retrieval_scores'].get('final_retrieval') or {}).get('required_evidence_coverage')
        error_lines.append(f"| {row['case_id']} | {format_metric(value)} | {', '.join(row['expected_evidence'])} | {', '.join(row['reason'])} |")
    (output / 'ERROR_ANALYSIS.md').write_text('\n'.join(error_lines) + '\n', encoding='utf-8')
    for row in rows:
        row['capability_status'] = row['execution_status']
    charts(output, rows, {})
    metadata['posthoc_scoring'] = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'gold_loaded_only_after_retrieval_complete': True}
    write_json(output / 'execution_metadata.json', metadata)
    print(json.dumps({'cases': len(rows), 'stages': metrics['stage_case_counts'], 'final_recall_at_5': metrics['stages'].get('final_retrieval', {}).get('recall_at_5')}, ensure_ascii=False))


if __name__ == '__main__':
    import sys
    score(Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS / 'rag_only')
