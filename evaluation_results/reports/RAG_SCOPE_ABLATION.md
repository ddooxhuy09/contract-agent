# QA retrieval scope follow-up

## Change and method

Removed the unconditional `contract_type="Hợp đồng lao động"` from QA's first legal retrieval. The hint had been applied to every topic, including civil, commercial, consumer, and electronic-transaction questions. The follow-up reused the same 34 questions, isolated corpus clone, cached BGE-M3 model, query augmentation, and graph retrieval. It ran with an empty Gemini credential and loaded no LLM client. The corpus fingerprints matched before and after.

The earlier `rag_only/` results are the pre-change reference. The follow-up artifacts are in `rag_only_no_labor_hint/`.

## Retrieval scores

Scores are structural matches against draft benchmark labels, not judgments of legal correctness.

| Stage/metric | With labor hint | Without labor hint |
|---|---:|---:|
| Final R@1 | 0.074 | 0.098 |
| Final R@3 | 0.127 | 0.108 |
| Final R@5 | 0.152 | 0.147 |
| Final R@10 | 0.152 | 0.201 |
| Final MRR | 0.160 | 0.185 |
| Seed R@5, no labor hint | — | 0.201 |

By task, R@5 changed as follows: QA 0.115 → 0.077, multi-hop 0.167 → 0.214, risk stayed 0.192, and classification stayed 0.000. The small mixed set shows a tradeoff: removing the hint improves some mixed-topic retrieval and MRR, while reducing QA R@5.

Without the hint, graph expansion preserved all seed evidence within top 10 across the 34 cases, but final R@5 fell from seed 0.201 to 0.147. This points to ranking as the next retrieval issue: expanded chunks can push useful seeds below rank 5.

## Reranking follow-up (2026-10-26)

The ablation reused the saved candidate pool from `rag_only_no_labor_hint/traces/` (`graph_expanded`, before ordering), so it called no model and used no database. The frozen pre-change ordering reproduced the stored `final_retrieval` order in 34/34 cases. Gold was loaded only after every ranking was fixed. Policies were declared before scoring; no per-case tuning.

The candidate pool already contained all seed evidence: seed and final provision coverage were equal (0.201) in every case. Baseline put at least one expansion chunk above a seed in 16/34 cases. Reordering therefore could only change rank, not reachable evidence.

| Policy | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Pre-change baseline | 0.098 | 0.108 | 0.147 | 0.201 | 0.185 |
| Seeds first, instrument level inside seeds | 0.098 | 0.162 | 0.201 | 0.201 | 0.201 |
| Seeds first, hybrid-search order (shipped) | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 |
| Seeds only (reference) | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 |

Seeds-first improved R@5 in 3 cases (MIX-009, TEMP-009, TEMP-011), left 31 unchanged, and reduced none. `seed_search` and `seed_cosine` tied on this set; `seed_search` was shipped because it preserves the hybrid vector+FTS order instead of overriding it with cosine and a floor for FTS-only seeds. `seed_only` tied too, which is another sign that expansion added prompt context but no benchmark evidence here.

Production change: `app/infrastructure/retrieval/legal_graph_rag.py::_order_for_prompt` now orders by effectiveness bucket, then role, keeping seeds in the order that produced them. Instrument level, status, year and score only order hydrated context chunks. The previous key ranked instrument level before role and score, which is what moved seeds down. `tests/unit/test_scope_match.py` now asserts seed-order preservation and expansion-last ordering; the replaced test had encoded the old instrument-level-first behavior. 17 focused graph/scope tests pass.

End-to-end confirmation used a fresh output directory, `rag_only_seed_first_20261026/`: 34/34 completed, 0 model calls, no Gemini credential, corpus fingerprints unchanged. Final retrieval changed from R@1 0.098 → 0.142, R@3 0.108 → 0.191, R@5 0.147 → 0.201, MRR 0.185 → 0.260; R@10, coverage, returned-chunk count, contract text-span coverage (20/20) and clause-ID match (0/20) were unchanged. The offline production policy reproduced the new saved final order in 34/34 traces, with every seed before every expansion chunk.

Limits: n=34 and synthetic draft labels; the reranker was scored offline and then run once end-to-end. The end-to-end run used `as_of=2026-10-26` versus `2026-10-20` in the earlier run; it reproduced the offline prediction to three decimals, so the date window did not alter the measured scores here. No generation, citation quality, temporal retrieval, or status-4 provision selection was evaluated.

## Effectivity filter audit

The current PostgreSQL trigger marks a chunk effective only when its matching hierarchy node has status 1 or 5. The inspected hierarchy for 145/2020/NĐ-CP, 45/2019/QH14 and its NĐ-CP, and 84/2015/QH13 had status 4 at article, clause, and point levels; all matching embedding chunks were therefore false. Status 4 means partly expired, but this corpus does not identify which individual provisions remain effective. Treating every status-4 chunk as currently usable would include text whose provision-level status is unknown, so the filter was left intact pending reviewed provision-level data.

## Verification limits

The follow-up completed 34/34 retrievals with 0 model calls, no Gemini credential, no LLM client loaded, and unchanged corpus fingerprints. Contract text span coverage remained 20/20; exact clause ID matching remained 0/20 because the parser still groups these heading formats into one chunk. Temporal dates are still not passed into retrieval. No legal answer quality or historical version accuracy was evaluated.
