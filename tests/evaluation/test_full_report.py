from evaluation.contract_eval_v2.full_report import detection, focal_rows, number


def test_focal_scoring_does_not_count_unannotated_findings_as_false_positive():
    refs = [{'id': 'X', 'task': 'targeted_review', 'gold_label': 'compliant',
             'contract_path': 'C', 'gold_clause_ids': ['4'], 'base_case_id': 'X',
             'split': 'test', 'source_set': 'fixture', 'rule_id': 'R', 'review_issues': []}]
    flows = {'C': {'risks': [{'clause_ref': 'Điều 5', 'severity': 'critical', 'issue': 'other'}],
                   'analysis': {'clauses': [{'clause_number': '4'}]}}}
    rows = focal_rows(refs, flows)
    assert detection(rows)['fp'] == 0
    assert detection(rows)['tn'] == 1
    flows['C']['risks'].append({'clause_ref': 'Điều 4', 'severity': 'warning', 'issue': 'focal'})
    assert detection(focal_rows(refs, flows))['fp'] == 1


def test_clause_reference_is_strict_to_prevent_matching_law_or_multiple_articles():
    assert number('Điều 4.2') == '4'
    assert number('4') == '4'
    assert number('Điều 4 và Điều 5') is None
    assert number('Điều 4 BLLĐ') is None
