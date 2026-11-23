"""Post-run evidence tables. Scores only already-written real outputs."""
from __future__ import annotations

import csv
import json
import random
import re
from collections import defaultdict

from evaluation.contract_eval_v2.full_audit import OUT, ROOT, read_rows, write_json


def number(ref):
    match = re.fullmatch(r'(?:Điều\s*)?(\d+(?:\.\d+)*)[.:]?\s*', str(ref).strip(), re.I)
    return match.group(1).split('.')[0] if match else None


def focal_rows(refs, flows):
    """Post-hoc focal matching; unannotated clauses are never false positives."""
    result = []
    for ref in refs:
        if ref['task'] != 'targeted_review' or ref['gold_label'] not in ('violation', 'compliant'):
            continue
        path = ref['contract_path']
        if path not in flows:
            continue
        targets = {number(n) for n in ref['gold_clause_ids']} - {None}
        if not targets:
            continue
        flow = flows[path]
        risks = [r for r in flow['risks'] if number(r.get('clause_ref')) in targets
                 and r.get('severity') in ('critical', 'warning')]
        predicted = bool(risks)
        result.append({'id': ref['id'], 'base_case_id': ref['base_case_id'], 'split': ref['split'],
            'source_set': ref['source_set'], 'rule_id': ref['rule_id'], 'gold': ref['gold_label'],
            'expected_positive': ref['gold_label'] == 'violation', 'predicted_positive': predicted,
            'parser_found_focal': bool(targets & {number(c['clause_number']) for c in flow['analysis']['clauses']}),
            'issues': ';'.join(ref['review_issues']),
            'matched_issues': ' | '.join(r['issue'] for r in risks)})
    return result


def detection(rows):
    tp = sum(r['expected_positive'] and r['predicted_positive'] for r in rows)
    fp = sum(not r['expected_positive'] and r['predicted_positive'] for r in rows)
    fn = sum(r['expected_positive'] and not r['predicted_positive'] for r in rows)
    tn = len(rows)-tp-fp-fn
    return {'n': len(rows), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'false_positive_rate': fp/(fp+tn) if fp+tn else None,
            'scope': 'annotated_focal_clauses_after_full_workflow_not_exhaustive_contract_F1'}


def interval(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['base_case_id']].append(row['correctness']/2)
    keys = sorted(groups)
    rng = random.Random(20261118)
    values = []
    for _ in range(1000):
        sample = [v for key in rng.choices(keys, k=len(keys)) for v in groups[key]]
        values.append(sum(sample)/len(sample))
    values.sort()
    return [values[24], values[974]]


def percentile(values, p):
    values = sorted(values)
    return values[round((len(values)-1)*p)] if values else None


def main():
    from evaluation.contract_eval_v2.full_run import check
    check()
    refs = read_rows(OUT / 'gold.jsonl')
    qa = {r['id']: r for r in read_rows(OUT / 'qa.jsonl') if r['status'] == 'completed'}
    judged = {r['id']: r for r in read_rows(OUT / 'judge.jsonl')}
    flows = {r['id']: r for r in read_rows(OUT / 'workflow.jsonl') if r['status'] == 'completed'}
    assert set(qa) == set(judged) == {r['id'] for r in refs}
    assert set(flows) == {r['contract_path'] for r in refs if r['contract_path']}
    detail = []
    for ref in refs:
        uid = ref['id']; j = judged[uid]; a = qa[uid]
        expected = {(r['doc'], int(r['article'])) for r in ref['gold_legal_refs']}
        retrieved = set()
        for hit in a.get('legal_hits', [])[:5]:
            article = re.search(r'(?:^|\.)D(\d+)(?:\.|$)', hit.get('path') or '')
            if article and hit.get('doc_number'):
                retrieved.add((hit['doc_number'], int(article.group(1))))
        detail.append({'id': uid, 'base_case_id': ref['base_case_id'], 'source': ref['source_set'],
            'split': ref['split'], 'task': ref['task'], 'correctness': j['correctness'],
            'faithfulness': j['claims_supported']/j['claims_total'] if j['claims_total'] else None,
            'disputed_gold': j['disputed_gold'], 'generation_valid': a['generation_valid'],
            'legal_recall_at5_article': len(expected & retrieved)/len(expected) if expected else None,
            'source_clause_hit': bool(set(map(str, ref['gold_clause_ids'])) & set(map(str, a.get('source_clauses', []))))
                                if ref['gold_clause_ids'] else None,
            'ms': a['ms'], 'tokens': a['usage']['tokens'], 'reason': j['reason']})
    focal = focal_rows(refs, flows)
    stats = {}
    for split in ('test', 'dev'):
        rows = [r for r in detail if r['split'] == split]
        faith = [r['faithfulness'] for r in rows if r['faithfulness'] is not None]
        retrieval = [r['legal_recall_at5_article'] for r in rows if r['legal_recall_at5_article'] is not None]
        sources = [r['source_clause_hit'] for r in rows if r['source_clause_hit'] is not None]
        stats[split] = {'n': len(rows), 'base_cases': len({r['base_case_id'] for r in rows}),
            'correctness': sum(r['correctness'] for r in rows)/(2*len(rows)),
            'correctness_cluster_ci95': interval(rows),
            'fully_correct': sum(r['correctness'] == 2 for r in rows)/len(rows),
            'faithfulness': sum(faith)/len(faith) if faith else None, 'faithfulness_n': len(faith),
            'legal_recall_at5_article': sum(retrieval)/len(retrieval) if retrieval else None,
            'legal_recall_n': len(retrieval),
            'source_clause_hit': sum(sources)/len(sources) if sources else None,
            'source_clause_n': len(sources),
            'disputed_gold': sum(r['disputed_gold'] for r in rows),
            'latency_ms_p50': percentile([r['ms'] for r in rows], .5),
            'latency_ms_p95': percentile([r['ms'] for r in rows], .95),
            'detection_focal': detection([r for r in focal if r['split'] == split])}
    usage = {stage: {key: sum(r['usage'][key] for r in rows)
                    for key in ('llm_calls', 'llm_errors', 'tokens')}
             for stage, rows in [('qa', list(qa.values())), ('workflow', list(flows.values()))]}
    write_json(OUT / 'detailed_metrics.json', {'splits': stats, 'system_usage': usage,
        'whole_contract_F1': None, 'expert_validated': False})
    for name, rows in [('qa_per_case.csv', detail), ('workflow_focal_per_case.csv', focal)]:
        with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines = ['# Kết quả full QA và phân tích toàn luồng', '',
        'Chạy thật GPT-OSS-120b trên Groq; Qwen chấm QA. Dữ liệu tổng hợp, chưa có chuyên gia xác nhận.', '',
        '| Tập | Số câu | Điểm correctness | Đạt 2/2 | Faithfulness |',
        '|---|---:|---:|---:|---:|']
    for split, s in stats.items():
        lines.append(f"| {split} | {s['n']} | {s['correctness']:.1%} | {s['fully_correct']:.1%} | {s['faithfulness']:.1%} |")
    lines += ['', 'Correctness là điểm 0–2 chuẩn hóa. CI lấy mẫu theo ca gốc; không xem các câu cùng hợp đồng là độc lập.',
        '', '## Phân tích toàn luồng', '',
        f"Đã chạy {len(flows)} hợp đồng qua pipeline phân tích toàn văn; không chọn Điều gold cho bước sinh.",
        'Chỉ chấm detection tại các Điều có nhãn; phát hiện ở Điều chưa chú thích không tự tính là báo nhầm.', '']
    for split, s in stats.items():
        m = s['detection_focal']
        lines.append(f"- {split}: {m['n']} Điều có nhãn, TP={m['tp']}, FP={m['fp']}, FN={m['fn']}, TN={m['tn']}; F1={m['f1']:.3f}.")
    lines += ['', 'Không có F1 toàn hợp đồng vì chưa chú thích đầy đủ mọi rủi ro. Đây là giới hạn của gold, không phải lý do bỏ chạy workflow.',
        '', '## Điểm còn yếu', '']
    for row in sorted([r for r in detail if r['split'] == 'test' and r['correctness'] < 2], key=lambda r:(r['correctness'],r['id'])):
        lines.append(f"- {row['id']}: {row['correctness']}/2 — {row['reason']}")
    lines += ['', '## Bằng chứng và cách hiểu kết quả', '',
        'Đầu vào, gold, hash, context thật, câu trả lời, judge, usage và CSV từng ca nằm trong evaluation/contract_eval_v2/artifacts/full_preflight/.',
        'Rubric theo nhiệm vụ đã thay đổi so với v1/v4; không tuyên bố chênh điểm là A/B cùng rubric. Test từng được sử dụng trong phát triển; không phải benchmark độc lập hoàn toàn mới.',
        'Những ca judge nghi gold vẫn nằm trong điểm chính, được đánh dấu để xem xét; không xóa điểm thấp. OCR/PDF upload và 7 đoạn bổ sung từ PDF thật không thuộc số đo text pipeline này.', '']
    (ROOT / 'docs/bo_test_hoi_dong/KET_QUA_FULL_QA_WORKFLOW.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
