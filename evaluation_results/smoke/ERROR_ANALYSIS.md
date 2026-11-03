# Error analysis

Generated: 2026-10-19T16:19:05.673076+00:00

No prediction was produced for a failed preflight. These are execution blocks, not model failures and not scored errors.

## Counts by status

- Completed: 0
- Failed during execution: 0
- Unsupported capability: 0
- Not run: 5

## Error categories

- Retrieval Missing Evidence: not assessable without retrieval outputs.
- Wrong Legal Document / Wrong Article-Clause-Point: not assessable without retrieval outputs.
- Wrong Historical Version / Missing Legal Relationship: not assessable; temporal selection is not wired into QA retrieval and graph edge IDs are not surfaced by the current retriever.
- Incorrect Risk Classification / Unsupported Conclusion / Citation or Answer Hallucination / Incorrect Abstention: not assessable without generated outputs and legal review.
- Unsupported Capability: contract-bound QA cannot use matching fixture contract chunks absent isolated ingestion; classification has no pipeline; temporal date filtering is not exposed in QA/risk paths.
- Invalid/Unverified Ground Truth: all cases are synthetic draft; excerpts marked placeholder or requiring source review must not count as definitive legal evidence.

## Per-case execution notes

- `MIX-017` — not_run: PostgreSQL legal corpus is unavailable or has no ContractLens schema.
- `TEMP-006` — not_run: PostgreSQL legal corpus is unavailable or has no ContractLens schema.
- `MIX-018` — not_run: PostgreSQL legal corpus is unavailable or has no ContractLens schema.
- `TEMP-014` — not_run: PostgreSQL legal corpus is unavailable or has no ContractLens schema.
- `MIX-007` — not_run: PostgreSQL legal corpus is unavailable or has no ContractLens schema.