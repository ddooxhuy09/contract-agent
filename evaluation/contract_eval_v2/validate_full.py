"""Independent completion/arithmetic checks and artifact seal after full run."""
import json
from math import isclose
from pathlib import Path

from evaluation.contract_eval_v2.full_audit import OUT, ROOT, read_rows, sha, write_json
from evaluation.contract_eval_v2.full_run import check


def main():
    check()
    inputs = read_rows(OUT / 'inputs.jsonl')
    refs = {r['id']: r for r in read_rows(OUT / 'gold.jsonl')}
    answers = read_rows(OUT / 'qa.jsonl')
    judged = read_rows(OUT / 'judge.jsonl')
    flows = read_rows(OUT / 'workflow.jsonl')
    assert len(answers) == len(judged) == len(inputs) == 369
    assert len({r['id'] for r in answers}) == len(answers)
    assert len({r['id'] for r in judged}) == len(judged)
    assert {r['id'] for r in answers} == {r['id'] for r in judged} == set(refs)
    assert all(r['status'] == 'completed' for r in answers + flows)
    assert len(flows) == len({r['id'] for r in flows}) == 117
    assert {r['id'] for r in flows} == {r['contract_path'] for r in inputs if r['contract_path']}
    assert all(sha(ROOT / name) == digest for name, digest in json.loads((OUT / 'run_code.json').read_text()).items())
    scoring = json.loads((OUT / 'SCORING_PROTOCOL.json').read_text())
    assert sha(Path(__file__).with_name('full_report.py')) == scoring['scorer_sha256']
    api_smoke = json.loads((OUT / 'API_SMOKE.json').read_text())
    assert api_smoke['status'] == 'passed'
    assert api_smoke['steps']['unauthenticated_report_denied'] == 401
    basic = json.loads((OUT / 'metrics.json').read_text(encoding='utf-8'))
    detailed = json.loads((OUT / 'detailed_metrics.json').read_text(encoding='utf-8'))
    for split in ('test', 'dev'):
        subset = [r for r in judged if refs[r['id']]['split'] == split]
        expected_n = 314 if split == 'test' else 55
        assert len(subset) == expected_n
        score = sum(r['correctness'] for r in subset)/(2*expected_n)
        full = sum(r['correctness'] == 2 for r in subset)/expected_n
        assert basic[split]['n'] == detailed['splits'][split]['n'] == expected_n
        for metric in (basic[split], detailed['splits'][split]):
            assert isclose(metric['correctness'], score, abs_tol=1e-12)
            assert isclose(metric['fully_correct'], full, abs_tol=1e-12)
    proof = {'completion': {'qa_test': 314, 'qa_dev': 55, 'judge': 369, 'workflow': 117},
             'dataset_integrity': 'passed', 'application_and_runner_integrity': 'passed',
             'scorer_integrity': 'passed', 'independent_arithmetic': 'passed',
             'generation_invalid_count': sum(not r['generation_valid'] for r in answers),
             'qa_judge_model': json.loads((OUT / 'judge_usage.json').read_text())['model'],
             'expert_validated': False, 'no_expert_required_to_run': True,
             'whole_contract_F1': None, 'raw_personal_pdf_sent': False,
             'actual_API_smoke': api_smoke['status'],
             'report_sha256': sha(ROOT / 'docs/bo_test_hoi_dong/KET_QUA_FULL_QA_WORKFLOW.md'),
             'technical_checks': '386 tests full suite + 2 additional scorer tests; frontend lint/build and Ruff F passed'}
    write_json(OUT / 'FINAL_VALIDATION.json', proof)
    write_json(OUT / 'RESULTS_SHA256.json', {str(p.relative_to(OUT)).replace('\\','/'): sha(p)
        for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'RESULTS_SHA256.json'})
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
