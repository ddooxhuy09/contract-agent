"""Offline checks for integrity and repaired benchmark references."""
import json

from evaluation.contract_eval_v2.full_audit import OUT, ROOT, contract_text, read_rows
from evaluation.contract_eval_v2.full_run import check


def test_full_preflight_preserves_test_population_and_hides_gold():
    result = check()
    assert result['qa_test'] == 314
    assert result['qa_dev'] == 55
    assert result['models_called'] is False


def test_temporal_refs_survive_original_catalog_conversion():
    refs = {r['id']: r for r in read_rows(OUT / 'gold.jsonl')}
    assert {(r['doc'], r['article']) for r in refs['TEMP-006']['gold_legal_refs']} == {
        ('20/2023/QH15', 53), ('20/2023/QH15', 52)}
    assert refs['TEMP-006']['task'] == 'temporal'
    assert refs['TEMP-006']['required_facts']['required_temporal_claims']


def test_snapshot_text_matches_every_referenced_source():
    inventory = json.loads((OUT / 'contract_inventory.json').read_text(encoding='utf-8'))
    assert len(inventory) == 120
    for entry in inventory:
        assert (OUT / entry['snapshot']).read_text(encoding='utf-8') == contract_text(ROOT / entry['source_path'])
