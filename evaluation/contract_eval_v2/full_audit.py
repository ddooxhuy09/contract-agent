"""Offline audit and versioned preparation; never calls a model or changes v1."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / 'evaluation/contract_eval_v1'
OUT = ROOT / 'evaluation/contract_eval_v2/artifacts/full_preflight'


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def contract_text(path):
    if path.suffix == '.docx':
        with ZipFile(path) as archive:
            tree = ElementTree.fromstring(archive.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return '\n'.join(''.join(p.itertext()) for p in tree.findall('.//w:p', ns))
    return path.read_text(encoding='utf-8')


TASK_RUBRIC = {
    'targeted_review': 'Đánh giá Điều được hỏi trong toàn bộ dữ kiện hợp đồng. Nêu điều kiện, ngoại lệ và căn cứ; không bắt buộc chép mọi Điều trong danh sách ref.',
    'legal_basis': 'Trả lời căn cứ và giải thích liên hệ với nội dung. Không bắt buộc kết luận violation/compliant khi câu hỏi chỉ hỏi căn cứ.',
    'whole_contract_review': 'Tìm rủi ro trong toàn hợp đồng. Gold chỉ chú thích lỗi bơm; phát hiện bổ sung phải được kiểm với nội dung và luật, không tự tính là báo nhầm.',
    'temporal': 'Dựa vào ngày đánh giá, ngày giao kết, điều chuyển tiếp và đáp án tham chiếu; không ép nhãn violation/compliant.',
    'fixed': 'Chấm đúng ý câu hỏi và reference facts; câu hỏi nhận diện quan hệ, nội dung còn thiếu không bị ép kết luận vi phạm.',
}


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'run_code.json').exists():
        raise RuntimeError('Run already frozen: use a new version instead of rebuilding inputs')
    cases = read_rows(V1 / 'cases.jsonl')
    inputs = {r['id']: r for r in read_rows(V1 / 'inputs_no_gold.jsonl')}
    gold = {r['id']: r for r in read_rows(V1 / 'gold.jsonl')}
    ver = {r['id']: r for r in read_rows(V1 / 'verification.jsonl')}
    excluded = {r['id'] for r in read_rows(V1 / 'quarantine.jsonl')}
    split = json.loads((V1 / 'split.json').read_text(encoding='utf-8'))
    side = {k: s for s in ('dev', 'test') for k in split[s]}
    assert len(cases) == len(inputs) == len(gold) == len(ver) == 378
    assert len({r['id'] for r in cases}) == 378
    assert not set(split['dev']) & set(split['test'])
    frozen = json.loads((V1 / 'FROZEN.json').read_text(encoding='utf-8'))
    # v1's immutable artifacts remain the historical comparison track.
    assert all(sha(V1 / name) == value for name, value in frozen['files'].items())
    v04 = json.loads((ROOT / 'evaluation/benchmark/v04/MIXED_34_TEST_CASES_V04.json').read_text(encoding='utf-8'))
    provisions = {r['provision_id']: r for r in v04['legal_provisions']}
    originals = {r['id']: r for r in v04['test_cases']}
    paths = sorted({r['contract_path'] for r in cases if r['contract_path']})
    mapping, inventory, texts = {}, [], {}
    (OUT / 'contracts').mkdir(exist_ok=True)
    for i, source in enumerate(paths, 1):
        # Only explicit contract fixtures referenced by cases, never enumerate data/.
        path = ROOT / source
        text = contract_text(path)
        assert text.strip(), source
        target = f'contracts/C{i:03}.txt'
        (OUT / target).write_text(text, encoding='utf-8')
        mapping[source] = target
        texts[source] = text
        inventory.append({'source_path': source, 'input_sha256': sha(path), 'snapshot': target,
                          'characters': len(text), 'snapshot_sha256': sha(OUT / target)})
    prepared, references, reviews, corrections = [], [], [], []
    for c in cases:
        uid = c['id']
        assert all(c[k] == inputs[uid][k] for k in inputs[uid])
        assert all(c[k] == gold[uid][k] for k in gold[uid])
        task = {'T1': 'targeted_review', 'T2': 'legal_basis', 'T3': 'whole_contract_review'}.get(c['template'], 'fixed')
        if uid.startswith('TEMP-'):
            task = 'temporal'
        issues = list(ver[uid]['flags'])
        if c['source_set'] == 'v04':
            issues.append('source_is_demo_pending_legal_review')
        if c['template'] == 'T3':
            issues.append('non_exhaustive_whole_contract_gold')
        if c['base_case_id'] == 'BH-09':
            issues.append('specialist_BHXH_BHYT_and_time_review')
        if c['rule_id'] == 'training_penalty' or c['base_case_id'].startswith(('DT-', 'DT2-')):
            issues.append('training_contract_and_actual_cost_conditions')
        if c['base_case_id'] in ('TS-10', 'LU-06', 'LU-10'):
            issues.append('conditional_verdict_not_absolute')
        refs = list(c['gold_legal_refs'])
        if c['source_set'] == 'v04':
            refs = []
            for pid in c.get('v04_required_provision_ids', []):
                p = provisions[pid]
                refs.append({'doc': p['law_number'], 'article': int(p['article']),
                             'clause': int(p['clause']) if str(p.get('clause')).isdigit() else None,
                             'point': p.get('point'), 'provision_id': pid,
                             'source_url': p['official_or_state_source_url']})
            if refs != c['gold_legal_refs']:
                corrections.append({'id': uid, 'change': 'restore_required_refs_from_original_provision_catalog',
                                    'old': c['gold_legal_refs'], 'new': refs})
        reviews.append({'id': uid, 'base_case_id': c['base_case_id'], 'source_set': c['source_set'],
                        'split': side[c['base_case_id']], 'task': task, 'original_label': c['gold_label'],
                        'excluded_v1': uid in excluded, 'issues': ';'.join(issues),
                        'review_level': 'structural_and_reference_review_not_expert_legal_signoff'})
        if uid in excluded:
            continue
        prepared.append({**inputs[uid], 'contract_path': mapping.get(c['contract_path']),
                         'split': side[c['base_case_id']], 'task': task})
        references.append({**gold[uid], 'original_contract_path': c['contract_path'],
                           'contract_path': mapping.get(c['contract_path']), 'split': side[c['base_case_id']],
                           'task': task, 'review_issues': issues, 'gold_legal_refs': refs,
                           'required_facts': originals[uid]['gold'] if uid in originals else c['gold_key_facts'],
                           'human_legal_signoff': False})
    assert len(prepared) == 369
    assert Counter(r['split'] for r in prepared) == {'test': 314, 'dev': 55}
    bases = {}
    for c in cases:
        bases.setdefault(c['base_case_id'], c)
    similarities = []
    base_list = list(bases.values())
    for i, left in enumerate(base_list):
        for right in base_list[i+1:]:
            a, b = left['gold_clause_text'], right['gold_clause_text']
            if not a or not b:
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= .9:
                similarities.append({'left': left['base_case_id'], 'right': right['base_case_id'],
                                     'similarity': round(ratio, 4),
                                     'cross_split': side[left['base_case_id']] != side[right['base_case_id']]})
    write_rows(OUT / 'inputs.jsonl', prepared)
    write_rows(OUT / 'gold.jsonl', references)
    write_json(OUT / 'corrections.json', corrections)
    write_json(OUT / 'contract_inventory.json', inventory)
    write_json(OUT / 'near_duplicates.json', similarities)
    write_json(OUT / 'task_rubric.json', TASK_RUBRIC)
    with (OUT / 'case_review.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(reviews[0]));writer.writeheader();writer.writerows(reviews)
    summary = {'questions_scanned': len(cases), 'base_cases_scanned': len(bases),
               'contract_files_read': len(inventory), 'eligible': len(prepared),
               'by_split': dict(Counter(r['split'] for r in prepared)),
               'by_task': dict(Counter(r['task'] for r in prepared)),
               'by_source': dict(Counter(r['source_set'] for r in references)),
               'low_confidence_kept': sum('low_confidence' in r['review_issues'] for r in references),
               'reference_corrections': len(corrections), 'near_duplicate_pairs': len(similarities),
               'cases_with_missing_refs_restored': sum(len(r['new']) > len(r['old']) for r in corrections),
               'cross_split_near_duplicate_pairs': sum(r['cross_split'] for r in similarities),
               'excluded_preserved': len(excluded), 'original_labels_changed': 0,
               'original_files_modified': False, 'expert_validated': False}
    write_json(OUT / 'audit_summary.json', summary)
    write_json(OUT / 'manifest.json', {'scope': 'all_v1_369_preserve_test314_dev55',
        'files': {str(p.relative_to(OUT)).replace('\\','/'): sha(p) for p in OUT.rglob('*')
                  if p.is_file() and p.name != 'manifest.json'},
        'source_files': {str(p.relative_to(ROOT)).replace('\\','/'): sha(p)
                         for p in V1.iterdir() if p.suffix in ('.json', '.jsonl')},
        'full_run_started': False, 'warning': 'Preparatory audit; no new model scores.'})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    prepare()
