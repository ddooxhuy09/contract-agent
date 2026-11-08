import json,pathlib
root=pathlib.Path(__file__).parent
j=json.loads((root/'MIXED_34_TEST_CASES_V04.json').read_text(encoding='utf-8'))
cases=j['test_cases']; ids=[c['id'] for c in cases]
assert len(ids)==len(set(ids))==j['manifest']['n_cases']
provs={p['provision_id'] for p in j['legal_provisions']}
edges={e['edge_id'] for e in j['legal_relations']}
for c in cases:
 assert c['input'].get('question')
 assert c.get('difficulty_v04',c['difficulty'])
 assert all(p in provs for p in c['gold'].get('required_provision_ids',[]))
 assert all(e in edges for e in c['expected_legal_graph'].get('required_relation_edge_ids',[]))
 assert c['input']['as_of_date']
for edge in j['legal_relations']:
 assert edge['affected_scope'] and edge['effective_from']
print('PASS:',len(cases),'cases;',len(j['legal_relations']),'verified relationship definitions;',len(j['statutes']),'tracked documents')
print('WARN: schema passing is not proof of legal correctness. All cases require review.')
