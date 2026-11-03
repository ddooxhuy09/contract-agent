# ContractLens Mixed Temporal Legal Evaluation v0.4.1 — Existing Corpus Baseline

Generated: 2026-10-19T16:19:05.673076+00:00

## Run outcome

Selected cases: 5; completed: 0; failed: 0; unsupported: 0; not run: 5.
Mode: `smoke`. Smoke tests are environment preflight plus selected cases; inference was attempted only when required services were available.

## Environment and reproducibility

- Benchmark schema validator: PASS — PASS: 34 cases; 6 verified relationship definitions; 11 tracked documents
WARN: schema passing is not proof of legal correctness. All cases require review.
- PostgreSQL: available=False; legal document count=None.
- Neo4j: available=False; GraphRAG backend setting=`neo4j`.
- Configured model: `gemini-2.5-flash`; provider `gemini`; embedding `BAAI/bge-m3` (1024 dimensions); Top-K `5`; similarity threshold `0.6`.
- Gold answers were not passed to inference. Predictions contain only supplied inputs and observed outputs. No corpus data was modified.

## Results by difficulty

| Difficulty | Selected | Completed | Failed | Unsupported | Not run |
|---|---:|---:|---:|---:|---:|
| Easy | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 |
| Hard | 0 | 0 | 0 | 0 | 0 |
| Expert | 0 | 0 | 0 | 0 | 0 |

## Results by task

| Task | Selected | Completed | Failed | Unsupported | Not run |
|---|---:|---:|---:|---:|---:|
| multi_hop | 2 | 0 | 0 | 0 | 2 |
| qa | 2 | 0 | 0 | 0 | 2 |
| risk | 1 | 0 | 0 | 0 | 1 |

## Metrics

Retrieval, answer quality, temporal reasoning and risk scores are left null when there are no actual observations. No answer score was inferred from semantic similarity. See the four metric JSON files.

## Technical limits observed

- Docker Desktop daemon returned permission denied; API/PostgreSQL/Neo4j host ports were unreachable.
- Local `.env` has a Gemini key configured, but no model inference was attempted because PostgreSQL retrieval was unavailable.
- Contract QA cases with fixture IDs were not run: their contract chunks are not in an isolated corpus, and uploading to the configured DB would violate the no-production-mutation constraint.
- ContractLens QA does not pass benchmark `as_of_date` or `transaction_date` into retrieval. The risk workflow also does not receive those dates. Existing-corpus outputs therefore cannot support time-travel legal claims.
- `classification` has no corresponding ContractLens endpoint or internal classification pipeline.
- Benchmark excerpts/cases are synthetic draft; the benchmark itself calls for independent legal review. No gold label is represented here as legally verified.

## Error analysis and next steps

See `ERROR_ANALYSIS.md`. Priority: (1) run against a reachable, identified non-production corpus, (2) snapshot actual PG/Neo4j counts, (3) run legal-only QA and matching-document risk cases, (4) assess synthetic gold with a Vietnamese legal expert, (5) only then plan temporal retrieval support outside the baseline.
