# ContractLens evaluation tooling

## Bản đồ: xem gì ở đâu

| Bạn muốn | Mở |
|---|---|
| Xem **câu hỏi** của 34 case | [`benchmark/v04/PREVIEW_34_MIXED_TEMPORAL_CASES.md`](benchmark/v04/PREVIEW_34_MIXED_TEMPORAL_CASES.md) (bảng dễ đọc) hoặc `benchmark/v04/QUESTIONS_ONLY_NO_GOLD.json` (đầu vào runner) |
| Xem **đáp án gold** | `benchmark/v04/MIXED_34_TEST_CASES_V04.json`. Runner không đọc file này, chỉ bước chấm điểm đọc |
| Xem hợp đồng mẫu | `benchmark/v04/contracts/*.docx` (7 file) |
| Xem **kết quả** lần chạy mới nhất | [`../evaluation_results/reports/CHUNKER_ASOF_RUN.md`](../evaluation_results/reports/CHUNKER_ASOF_RUN.md) |
| Xem danh sách mọi lần chạy | [`../evaluation_results/README.md`](../evaluation_results/README.md) |
| **Chạy** benchmark | mục "RAG-only" bên dưới (`rag_only.py`, rồi `score_rag_only.py`) |
| Hiểu trạng thái dự án để tiếp tục | [`HANDOFF_CONTEXT.md`](HANDOFF_CONTEXT.md) |

Dữ liệu vào (`benchmark/`) tách hẳn khỏi kết quả (`../evaluation_results/`). Đường dẫn dùng chung nằm ở một chỗ: `BENCHMARK`, `RESULTS`, `RUNS`, `BASELINE_RUN` trong `runtime_adapter.py`.
Test của phần chấm điểm: `tests/evaluation/test_scoring.py`.

This package records ContractLens retrieval and generation behavior. The current QA change removes the unconditional labor-law hint from mixed-topic questions. Benchmark gold is read only after retrieval finishes.

**Current instruction: do not call Gemini.** The active experiment is `rag_only/`; generation in `run_benchmark.py` is disabled by default. No resumption or scheduled Gemini call has been configured.

## RAG-only (current task)

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -e GEMINI_API_KEY= worker python -m evaluation.rag_only --output-dir /workspace/evaluation_results/runs/rag_only_no_labor_hint
python -m evaluation.score_rag_only evaluation_results/runs/rag_only_no_labor_hint
```

This uses only cached BGE-M3, real PostgreSQL/Neo4j retrieval, and the original query-rewrite rules. It instantiates no LLM client, does not run an LLM query rewrite, and records that no Gemini credential was available. QA cases use the production first-pass QA legal retriever without forcing a labor contract type; risk cases use the production GraphRAG entry with the supplied fact pattern as the query instead of LLM-extracted clauses. All input contracts are indexed using the real local DOCX parser/chunker/embedder in the isolated copy.

On Git Bash, prefix Docker commands with `MSYS_NO_PATHCONV=1` so `/workspace/...` container paths are not rewritten to Windows paths.

### Reranking

`rerank_ablation.py` re-ranks the saved `graph_expanded` pool from a completed RAG-only run without a model or database, then scores against gold. Its frozen baseline must reproduce the stored `final_retrieval` order.

```powershell
python -m evaluation.rerank_ablation
```

Production now keeps seeds in hybrid-search order and places graph expansion after them. The confirming run is `rag_only_seed_first_20261026/`:

```powershell
MSYS_NO_PATHCONV=1 docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -e GEMINI_API_KEY= worker python -m evaluation.rag_only --output-dir /workspace/evaluation_results/runs/rag_only_seed_first_20261026
python -m evaluation.score_rag_only evaluation_results/runs/rag_only_seed_first_20261026
```

Final R@5 moved 0.147 → 0.201 and MRR 0.185 → 0.260 with unchanged coverage; see `../evaluation_results/reports/RAG_SCOPE_ABLATION.md`.

## Experiment files

- `run_benchmark.py`: questions-only inference, incremental JSONL persistence, corpus fingerprints, package/code/config metadata.
- `runtime_adapter.py`: real `UploadContract`, `run_analysis_workflow`, `answer_question`, and legal-only/scenario adapters; passive hooks preserve arguments and return values.
- `audit.py`: JSON/JSONL/reference/date/DOCX checks and read-only PostgreSQL/Neo4j coverage inspection.
- `rerank_ablation.py`: offline reranking policies over saved traces; no model/database, gold read after rankings are fixed.
- `scoring.py`: post-inference structural scoring, CSV, reports, review rubric, charts. It reads gold only after predictions exist.
- `finalize_blocked.py`: one-off, evidence-checked finalization of this quota-interrupted run. It preserves raw predictions and records null output for unexecuted cases.
- `tests/test_scoring.py`: unit checks of metric invariants; these do not run LLM/retrieval or generate benchmark predictions.

## Real execution adapters

| Input | Application code used | Evaluation adaptation |
|---|---|---|
| Contract risk | UploadContract → run_analysis_workflow | Upload exact benchmark DOCX into the isolated corpus copy; fresh UUID per case avoids cache/history contamination. |
| Contract QA/multi-hop/classification question | UploadContract → qa_agent.answer_question | Matching fixture only; classifier questions remain natural-language QA, with no invented classifier head. |
| Legal QA without contract_id | Original QA retrieve/rewrite/generate/refusal nodes | Skip contract retrieval and persisted memory; no unrelated contract is assigned. Actual prompts, legal retrieval and LLM are retained. |
| Risk scenario without contract_id | risk_flagger.evaluate_clause | Use only supplied question/scenario as clause summary; no fabricated contract or legal evidence. |

`rag_only.py --date-field` forwards a benchmark input date (`as_of_date` by default) to retrieval; `execution_metadata.json` records `date_field`. Older runs forwarded none. Temporal outputs from the generation runner are retained and marked `unsupported_capability` when executed. `rag_only/` contains the earlier retrieval baseline with the labor hint; `rag_only_no_labor_hint/` contains the follow-up run after removing it; `rag_only_seed_first_20261026/` contains the run after the seed-first ranking change; `rerank_ablation_20261026/` contains the offline policy comparison; `rag_only_chunker_asof_20261103/` and `rag_only_chunker_txdate_20261103/` contain the runs after the chunker fix and date forwarding (`CHUNKER_ASOF_RUN.md`). `scripts/audit_status4_provisions.py` writes `STATUS4_AUDIT.md`.

`predictions.jsonl`, `traces/` and `corpus_snapshot.json` are git-ignored (tens of MB); regenerate them with the commands above.

## Reproduce safely

Run from the repository root. The original database containers must be stopped before physically copying volumes. The evaluation Compose file uses only the explicitly named copied data volumes. It does not apply `schema.sql`, `ensure_schema`, or ingest law fixtures.

Always pass **`-p contractlens-eval-01a154eb`**. The repository `.env` sets COMPOSE_PROJECT_NAME and can override the YAML name.

The current copied volumes are:

- `contractlens_eval_20261019_01a154eb_pgdata`
- `contractlens_eval_20261019_01a154eb_neo4jdata`

The original source volumes `contractlens_pgdata` and `contractlens_neo4jdata` were mounted read-only by copy helpers. The shared `contractlens_hf_cache` is mounted read-only in workers. The model remains the repository-configured Gemini 2.5 Flash / BAAI bge-m3.

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml up -d postgres neo4j
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps worker python -m evaluation.audit
python -m evaluation.scoring evaluation_results/new_baseline
python -m unittest discover -s evaluation/tests -v
```

Use a new output directory for a new experiment. `--resume` is intended for a process interrupted before all cases were recorded; a finalized `not_run` record is not silently retried or replaced. Keep old quota-limited results as a separate run.

The earlier generation experiment requires available Gemini quota and is now disabled by default. The provider reported a daily limit of 20 requests for the configured model. No alternate model was used, and no wakeup/automation was created. A later generation run would require fresh user authorization and the explicit CLI opt-in; the current task does not use it.

## Results and interpretation

`evaluation_results/` contains the main baseline artifacts, raw prompts/responses/retrieval traces, corpus/benchmark audits, and charts. `smoke_real/` is the actual five-case smoke run. `smoke/` records an earlier host connectivity preflight with zero model calls; it must not be counted as experimental accuracy. Smoke outputs are never substituted for missing baseline cases.

Structural retrieval metrics are relative to draft benchmark labels. Unjudged real-corpus hits prevent an exhaustive precision claim. Pooled precision and binary nDCG are explicitly exploratory. Duplicate provision hits cannot inflate gains. Exact structural provision identity does not verify historical text versions. Empty observed retrieval is scored as zero recall; unavailable execution remains null with its case count visible.

Full-chunk presence in the actual model prompt, returned retrieval, graph expansion, and output citations are distinct observations. Graph edge presence in the corpus is not scored as edge use. QA contract citations are not treated as legal citations.

Generation/legal correctness and unsupported temporal selection metrics remain null until calibrated judge or human legal review. Missing or failed risk outputs are not forced into `ok`/false-negative labels; the scored denominator and operational coverage are both reported.

## Stop isolated services

```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml stop postgres neo4j
```

The copied volumes are retained for review/reproduction. No production volume should be removed or restored by this tooling.

## Gold set and clause-level evaluation (one-week plan)

Separate from the v04 benchmark above: a small human-labelled set of Điều units from anonymised labor contracts. Guide: `gold/HUONG_DAN_GAN_NHAN.md`.

```text
python -m evaluation.gold.prepare_units --input-dir <contracts>   # draw units, write annotation_template.csv + contracts_manifest.json
python -m evaluation.gold.kappa --write                           # KAPPA.md after both annotators finish
python -m evaluation.gold.make_split                              # dev/test split by contract -> split.json
python -m evaluation.run_eval --split test --config rule_only --contracts-dir <contracts>
python -m evaluation.run_eval --split test --config full --contracts-dir <contracts> [--estimate]
python -m evaluation.run_eval --split test --report               # evaluation_results/RESULTS_TUAN.md
python -m evaluation.gold.draw_citations --result evaluation_results/<date>_test_full.json
```

Run the `rule_only` and `full` configs inside the api container (the host cannot reach the database with the default settings), with `evaluation/` mounted and `EVAL_COMMIT` set. Give contracts as `.docx`; markdown files must have `#` and `**` stripped or clause extraction finds no Điều. The `full` config caches finished contracts and never caches a contract with unchecked clauses, so a quota-limited run can be repeated the next day.
