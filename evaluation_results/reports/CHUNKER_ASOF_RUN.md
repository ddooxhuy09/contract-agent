# Chunker fix and date forwarding — RAG-only follow-up (2026-11-03)

Retrieval-only: 0 Gemini/model calls, no credential, no LLM client loaded, corpus fingerprints unchanged, 34/34 cases completed in both runs. Scores are structural matches against synthetic draft labels (n=34), not judgments of legal correctness.

## What changed

1. `app/document/chunker.py`: headings are matched line-anchored (`Điều N` alone on a line, then `Mục X`, then `Khoản X` when no Điều exists). Offline check on the 7 benchmark DOCX: every one of the 20 clause texts lands in a chunk whose label equals the expected one.
2. `retrieve_legal` and the QA graph state carry `as_of_date` to `LegalGraphRag.retrieve_for_clause`. `evaluation/rag_only.py --date-field` chooses which benchmark input date is forwarded (`as_of_date` default, `transaction_date`, or `none`).
3. Status-4: **no retrieval change**. See `STATUS4_AUDIT.md`.

## Results (final retrieval)

| Run | Date forwarded | R@1 | R@3 | R@5 | R@10 | MRR | Exact clause ID |
|---|---|---:|---:|---:|---:|---:|---:|
| `rag_only_seed_first_20261026` (baseline) | none | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | 0/20 |
| `rag_only_chunker_asof_20261103` | `as_of_date` | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | **20/20** |
| `rag_only_chunker_txdate_20261103` | `transaction_date`, else `as_of_date` | 0.142 | 0.181 | 0.191 | 0.191 | 0.245 | **20/20** |

Contract text-span coverage stays 20/20. Temporal subset (14 cases) R@5: 0.238 baseline and `as_of_date` run, 0.214 for the `transaction_date` run.

## Reading the numbers

- The chunker fix moves exact clause-ID match from 0/20 to 20/20 and does not touch legal retrieval, so legal scores are unchanged.
- Forwarding `as_of_date` leaves every case's retrieval metrics identical to the baseline: on this set the date only reorders chunks that were already retrieved.
- The `transaction_date` run lost one case, TEMP-009 (R@5 0.333 → 0.000). Its transaction date (2024-05-20) precedes the 2024-07-01 effective date of Luật 19/2023/QH15, so those chunks are demoted as not yet in force and dropped because in-force alternatives exist. That is the date logic working as written, but the case asks about both laws, so the filter removes evidence the labels require.
- **Caveat on the choice of default.** The first run used `transaction_date` before `as_of_date`; the default was changed to `as_of_date` after TEMP-009 regressed, because `as_of_date` is the name of the production parameter. That is a post-hoc choice, so both runs are kept and reported. It is not evidence that `as_of_date` is better in general. The `txdate` run's `execution_metadata.json` predates the `--date-field` flag and still says `temporal_dates_forwarded: false`; its dates were forwarded (see `traces/TEMP-009.json`, `as_of_date: 2024-05-20`).
- Dropping not-yet-effective documents when the question concerns a pre-effective transaction (transitional rules) needs a retrieval policy decision, not a tweak: it should keep both versions and let generation select. Not implemented.

## Not addressed

- Status-4 provisions (BLLĐ 2019, NĐ 145/2020, 84/2015) remain excluded: the 3132 status-4 nodes have `eff_from` but no `eff_to`, and the corpus has 2 provision-level relations in total (`STATUS4_AUDIT.md`).
- Luật Thương mại 36/2005/QH11 is absent from the corpus; Luật BHXH 41/2024 is stored as status 2 / `eff_to=2026-01-01`, conflicting with the draft benchmark. Neither was changed; they need an official-source review.
- No generation, citation or answer quality was evaluated.
