import argparse,json,collections,pathlib
p=argparse.ArgumentParser();p.add_argument('--pred',required=True,help='JSONL rows: id, cited_provision_ids, relation_edge_ids, claimed_statute_ids')
a=p.parse_args();root=pathlib.Path(__file__).parent
samples={r['id']:r for r in json.loads((root/'MIXED_34_TEST_CASES_V04.json').read_text(encoding='utf-8'))['test_cases']}
rows=[json.loads(line) for line in pathlib.Path(a.pred).read_text(encoding='utf-8').splitlines() if line.strip()]
metrics=collections.defaultdict(list)
for x in rows:
 c=samples[x['id']];gold=c['gold']; preds=set(x.get('cited_provision_ids') or []); gp=set(gold.get('required_provision_ids') or [])
 if gp:metrics['evidence_recall'].append(len(gp&preds)/len(gp))
 edges=set(x.get('relation_edge_ids') or []);ge=set(c['expected_legal_graph'].get('required_relation_edge_ids') or [])
 if ge:metrics['relation_recall'].append(len(edges&ge)/len(ge))
 bad=set(gold.get('forbidden_as_primary_provision_ids') or [])
 if bad:metrics['forbidden_citation_rate'].append(len(preds&bad)/len(bad))
 expected_laws=set(gold.get('relevant_statute_numbers') or []); actual=set(x.get('claimed_statute_ids') or [])
 if expected_laws:metrics['statute_selection_exact_match'].append(float(actual==expected_laws))
for k,values in metrics.items():print(f'{k}: {sum(values)/len(values):.4f} (n={len(values)})')
print('NOTE: this runner does NOT verify legal conclusion, applicability, correctness of content or quoted statute text.')
