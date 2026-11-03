# Status-4 provision audit

Generated 2026-11-03T04:51:28.637324+00:00 from the isolated corpus clone (read-only).

## Verdict

- Status-4 hierarchy nodes in audited documents: **3132**; with `eff_to`: **0** (0.0%).
- Provision-level relation rows in the whole corpus (`legal_path_relations`): **2** {'bai_bo': 1, 'sua_doi': 1}.
- Date-aware status-4 filter supported by the data: **False**.
- status-4 nodes have eff_from only (no eff_to) and the corpus has almost no provision-level relations, so a date window cannot tell which provisions expired; enabling it would admit text whose status is unknown.

## Per document

| Document | doc status | level | node status | nodes | with eff_from | with eff_to |
|---|---:|---|---:|---:|---:|---:|
| 145/2020/NĐ-CP | 4 | articles | 4 | 115 | 115 | 0 |
| 145/2020/NĐ-CP | 4 | clauses | 4 | 367 | 367 | 0 |
| 145/2020/NĐ-CP | 4 | points | 4 | 398 | 398 | 0 |
| 45/2019/NĐ-CP | 4 | articles | 4 | 29 | 29 | 0 |
| 45/2019/NĐ-CP | 4 | clauses | 4 | 161 | 161 | 0 |
| 45/2019/NĐ-CP | 4 | points | 4 | 296 | 296 | 0 |
| 45/2019/QH14 | 4 | articles | 4 | 220 | 220 | 0 |
| 45/2019/QH14 | 4 | clauses | 4 | 638 | 638 | 0 |
| 45/2019/QH14 | 4 | points | 4 | 267 | 267 | 0 |
| 84/2015/QH13 | 4 | articles | 4 | 93 | 93 | 0 |
| 84/2015/QH13 | 4 | clauses | 4 | 357 | 357 | 0 |
| 84/2015/QH13 | 4 | points | 0 | 10 | 0 | 0 |
| 84/2015/QH13 | 4 | points | 4 | 191 | 191 | 0 |

## Chunks by `is_effective`

| Document | is_effective=true | false |
|---|---:|---:|
| 145/2020/NĐ-CP | 0 | 674 |
| 45/2019/NĐ-CP | 0 | 380 |
| 45/2019/QH14 | 0 | 874 |
| 84/2015/QH13 | 0 | 516 |

Nothing here edits flags or the trigger. Provision-level status needs a reviewed source (official consolidated text or amendment mapping) before status-4 chunks can be retrieved.
