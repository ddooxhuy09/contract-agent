# Handoff context: ContractLens RAG evaluation

Updated: 2026-11-03 (Asia/Bangkok)

## Continue from here

The active user instruction is: **do not call Gemini; work on and test RAG first**. Do not run generation, call an LLM provider, or use a Gemini credential unless the user explicitly changes this instruction. Keep the current retrieval-only results separate from the earlier generation run.

The ranking issue is resolved. An offline ablation over the saved candidate pool showed that graph expansion added no gold evidence in this set; the old order ranked instrument level before role/score and buried seeds. Production now keeps seeds in hybrid-search order and places expansion after them. The seed-first run is `rag_only_seed_first_20261026/`: final R@5 0.147 → 0.201, MRR 0.185 → 0.260, coverage unchanged.

Update 2026-11-03 (branch `fix/rag-chunker-temporal-effectivity`; report `evaluation_results/reports/CHUNKER_ASOF_RUN.md`):

- Chunker now matches line-anchored `Điều N`, `Mục X`, `Khoản X` headings: exact clause ID 0/20 → 20/20, text-span 20/20, legal retrieval unchanged.
- `as_of_date` is forwarded through `retrieve_legal` and the QA graph state; the runner has `--date-field {as_of_date,transaction_date,none}`. Run `rag_only_chunker_asof_20261103` (as_of_date) matches the baseline exactly (R@5 0.201, MRR 0.260). Run `rag_only_chunker_txdate_20261103` (transaction_date first) loses TEMP-009 (R@5 0.191). The default was picked after seeing that regression, so treat it as post-hoc.
- Status-4 stays excluded. `scripts/audit_status4_provisions.py` shows 3132 status-4 nodes with no `eff_to` and 2 provision-level relations corpus-wide, so a date-aware filter is not supported by the data; no retrieval change was made (`evaluation_results/reports/STATUS4_AUDIT.md`).
- Still open: a policy for transitional questions (keep pre- and post-effective versions), reviewed provision-level status for status-4 laws, missing 36/2005/QH11, 41/2024 metadata conflict. Do not tune reranking or parsing against individual gold labels without reporting that explicitly.

## Current code changes

- `app/agents/qa_agent.py`: removed the unconditional `contract_type="Hợp đồng lao động"` argument from the first-pass legal QA retrieval. Mixed-topic QA no longer starts with a labor-law context injected for every question.
- `app/infrastructure/retrieval/legal_graph_rag.py::_order_for_prompt`: seed-first ranking. Effectiveness bucket → role; seeds keep the order that produced them; instrument level/status/year/score only order hydrated expansion chunks. The old key ranked instrument level before role and score.
- `tests/unit/test_scope_match.py`: replaced the instrument-level-first test with seed-order-preservation and expansion-last tests.
- `tests/unit/test_qa_self_correct.py`: added a regression test asserting that QA first-pass retrieval leaves `contract_type` unset for a consumer-law question.
- `evaluation/rag_only.py`: the comparison runner also calls QA legal retrieval without a forced labor contract type; it still runs with no LLM client.
- `evaluation/rerank_ablation.py`: new offline reranking ablation over saved traces. It freezes the pre-change order, declares policies before scoring, and reads gold only after rankings are fixed.
- `evaluation/score_rag_only.py`: updated the adapter description.
- `evaluation/README.md`: documents the no-Gemini instruction, the RAG runs, and the reranking workflow.
- `evaluation_results/reports/RAG_SCOPE_ABLATION.md`: documents the labor-hint comparison, reranking ablation, production change, and status-4 corpus audit.

These are incremental edits in a working tree with many pre-existing user changes. **Do not reset, clean, revert, or overwrite unrelated files.** `git status --short` contains unrelated edits and untracked documentation/frontend files from before this handoff.

## Latest RAG-only run (seed-first ranking)

Run: `evaluation_results/runs/rag_only_seed_first_20261026/`

- 34/34 completed; 0 model calls; `gemini_credential_present=false`; `llm_client_modules_loaded=[]`; corpus fingerprints unchanged.
- Offline ablation: `evaluation_results/runs/rerank_ablation_20261026/`. Frozen pre-change baseline reproduced the stored final order 34/34; policies were declared before gold was read.
- Final retrieval: R@1 0.098 → 0.142, R@3 0.108 → 0.191, R@5 0.147 → 0.201, MRR 0.185 → 0.260. R@10, required-evidence coverage (0.201), and returned-chunk count (6.412) unchanged.
- Per-task R@5: QA 0.077 → 0.192, multi-hop 0.214 → 0.262, risk 0.192 → 0.192, classification 0.000. Per-task MRR: QA 0.060 → 0.231, multi-hop 0.357 → 0.405, risk 0.231.
- Every seed precedes every expansion chunk in 34/34 saved finals; the shipped policy reproduces the saved final order 34/34.
- Contract text-span coverage remains 20/20 and exact clause ID remains 0/20 (as of 2026-10-26; fixed on 2026-11-03, see top).
- The end-to-end run used `as_of=2026-10-26`; the offline ablation used `2026-10-20`. End-to-end metrics matched the offline prediction to three decimals.

## Previous RAG-only run (no labor hint)

Run: `evaluation_results/runs/rag_only_no_labor_hint/`

- 34/34 unique cases completed; one trace per case.
- `generation_model_calls=0`, `gemini_credential_present=false`, `llm_client_modules_loaded=[]`.
- The saved console has no Gemini generation endpoint; benchmark used cached local BGE-M3, PostgreSQL and Neo4j on the isolated corpus clone.
- Corpus before/after fingerprints match. These are PostgreSQL hash64 row-fingerprint sums for the audited tables, not cryptographic proofs of every embedding vector byte.
- Benchmark gold was read only after retrieval completed by the offline scorer.
- Aggregate metrics are structural comparisons against synthetic draft labels, not legal correctness scores.

Scores for this run (`final_retrieval`, n=34):

| Metric | With labor hint (earlier run) | Without labor hint (this run) |
|---|---:|---:|
| R@1 | 0.074 | 0.098 |
| R@3 | 0.127 | 0.108 |
| R@5 | 0.152 | 0.147 |
| R@10 | 0.152 | 0.201 |
| MRR | 0.160 | 0.185 |

Without the labor hint, seed R@5 is 0.201 and final R@5 is 0.147; final R@10 remains 0.201. Graph expansion therefore preserved evidence in the top 10 but changed rankings inside the top 5. Task-level R@5: QA 0.115 → 0.077, multi-hop 0.167 → 0.214, risk 0.192 → 0.192, classification 0.000 → 0.000. Small n; treat as an ablation signal, not proof of general performance.

Report links/paths:

- `evaluation_results/runs/rag_only_seed_first_20261026/RAG_ONLY_REPORT.md`
- `evaluation_results/runs/rag_only_seed_first_20261026/RETRIEVAL_METRICS.json`
- `evaluation_results/runs/rag_only_seed_first_20261026/CASE_BY_CASE_RESULTS.csv`
- `evaluation_results/runs/rag_only_seed_first_20261026/predictions.jsonl`
- `evaluation_results/runs/rag_only_seed_first_20261026/traces/`
- `evaluation_results/runs/rerank_ablation_20261026/RERANK_ABLATION.md`
- `evaluation_results/runs/rerank_ablation_20261026/RERANK_METRICS.json`
- `evaluation_results/runs/rerank_ablation_20261026/CASE_RANK_COMPARISON.csv`
- `evaluation_results/runs/rag_only_no_labor_hint/RAG_ONLY_REPORT.md` (previous run)
- `evaluation_results/runs/rag_only/RAG_ONLY_REPORT.md` (pre-labor-hint comparison)
- `evaluation_results/reports/RAG_SCOPE_ABLATION.md`

The retrieval-only runner writes actual retrieval traces. It adapts risk cases to search using the supplied question/scenario; there is no LLM clause extraction. No temporal dates are forwarded into retrieval, so the 14 temporal cases do not demonstrate time-aware retrieval. No final answer, legal citations, or answer quality was generated or scored.

## Corpus and code findings

- Do not broadly include status-4 chunks in retrieval. In the isolated snapshot, status 4 (“hết hiệu lực một phần”) appeared on article/clause/point nodes for 145/2020/NĐ-CP, 45/2019/QH14 and its 45/2019/NĐ-CP, and 84/2015/QH13; corresponding embedding rows all had `is_effective=false`. The hierarchy snapshot does not identify which individual provisions remain in force. A blanket change would risk retrieving expired provisions as current. Keep the filter unchanged until provision-level status is reviewed and corrected.
- 41/2024/QH15 is marked status 2 / `eff_to=2026-01-01` in the snapshot, conflicting with the synthetic draft benchmark. Do not alter legal corpus flags based only on benchmark gold.
- 36/2005/QH11 was absent from the audited corpus snapshot.
- Current SQL in `app/infrastructure/vector/pg_search.py::_base_where` filters `c.is_effective`, non-null embedding, non-signature chunks, and documents with status 2.
- Current `LegalGraphRag._validity_key` understands status 4 as partly expired and ranks it rather than marking it fully unusable. The false chunk cache currently removes those candidates before this ranking logic sees them.
- `PgLegalVectorSearch.search` stores `max(cosine, rrf_score)` in `chunk.score`, so FTS-only seeds carry ~0.016 while vector seeds carry cosine (~0.5–0.7). The shipped order no longer sorts seeds by this field. Do not treat it as calibrated relevance; fixing fusion is a prerequisite for score-based reranking.
- `app/document/chunker.py` recognizes `Điều <n>` only when punctuation follows the number. Benchmark DOCX headings use newline or `Mục A` forms; actual upload parsing produced one chunk per each of seven fixtures. In latest report contract text span coverage is 20/20 and exact clause ID match 0/20.
- Risk retrieval already has optional `as_of_date` in `LegalGraphRag.retrieve_for_clause`, but production QA/risk call paths do not forward benchmark dates consistently. The QA `retrieve_legal` wrapper currently has no date parameter.

## Tests / verification status

- `python -m compileall -q app/infrastructure/retrieval/legal_graph_rag.py evaluation/rerank_ablation.py evaluation/rag_only.py evaluation/score_rag_only.py` passed.
- `python -m pytest tests/unit/test_scope_match.py tests/unit/test_graphrag.py -q` → 17 passed.
- `python -m pytest tests/unit/test_qa_self_correct.py -q` → 11 passed (49.8s). The earlier full-suite collection stall did not reproduce with focused files.
- `python -m evaluation.rerank_ablation` → frozen baseline reproduced 34/34; best decision policy `seed_search`; final R@5 0.201, MRR 0.260.
- Docker RAG-only run `rag_only_seed_first_20261026`: 34/34 completed, 0 model calls, no Gemini credential, corpus unchanged; `score_rag_only` final R@5 0.201.
- The `test_legal_citations.py` failure noted on 2026-10-26 was a stale assertion (the code intentionally returns `"Đã đối chiếu · Còn hiệu lực · <date>"`); the test now asserts the substring and the file passes (14).
- `git diff --check` passed (line-ending conversion warnings only).
- The benchmark Docker image does not include `pytest`; the tests above ran on the host environment.
- `evaluation/tests/test_scoring.py` covers scoring invariants only, not production retrieval.

## Docker / data safety

The original DB volume names are `contractlens_pgdata` and `contractlens_neo4jdata`. The evaluation used copied volumes:

- `contractlens_eval_20261019_01a154eb_pgdata`
- `contractlens_eval_20261019_01a154eb_neo4jdata`

These clones are retained and the evaluation PostgreSQL/Neo4j containers were stopped after each run, including the seed-first run on 2026-10-26. No volume was removed. The original postgres/neo4j containers are currently `created` (not running) and reference their original volumes. Do not remove volumes or run Compose without explicit `-p contractlens-eval-01a154eb`; `.env` defines `COMPOSE_PROJECT_NAME=contractlens` and can otherwise target original services. If DB access is needed, start only the evaluation clones with:

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml up -d postgres neo4j
```

For any new retrieval worker, keep Gemini disabled:

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -e GEMINI_API_KEY= worker python -m evaluation.rag_only --output-dir /workspace/evaluation_results/<new_run_name>
python -m evaluation.score_rag_only evaluation_results/<new_run_name>
```

On Git Bash, prefix Docker commands with `MSYS_NO_PATHCONV=1`; otherwise `/workspace/...` is rewritten to a Windows path and the worker fails on a read-only filesystem.

Use a fresh output directory; the runner refuses to overwrite an existing `predictions.jsonl`. Stop only the evaluation clones after use:

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml stop postgres neo4j
```

## Earlier generation experiment: do not resume

An earlier, separate generation attempt reached the Gemini daily quota limit after a partial run. Its outputs are incomplete and remain at the root of `evaluation_results/`; they must not be combined with the RAG-only runs. The user explicitly said not to call Gemini. Do not run `evaluation.run_benchmark --enable-llm`, resume that run, or schedule any follow-up. Existing generation metrics have null answer-quality metrics and must not be represented as a complete benchmark.

