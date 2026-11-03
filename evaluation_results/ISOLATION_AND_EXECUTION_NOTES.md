# Isolation and execution notes

The original PostgreSQL and Neo4j service containers were stopped when inspection began. Source data volumes were physically copied while stopped using read-only source mounts:

| Original source volume | Evaluation copy |
|---|---|
| contractlens_pgdata | contractlens_eval_20261019_01a154eb_pgdata |
| contractlens_neo4jdata | contractlens_eval_20261019_01a154eb_neo4jdata |

The source PostgreSQL volume was approximately 20 GB and Neo4j approximately 2.2 GB. Copy helper containers exited successfully. Existing legal corpus content was used unchanged. Benchmark DOCX inputs and chat checkpoints were created only in the copied PostgreSQL database; no synthetic law fixture was ingested. Application startup schema/migration routines were not invoked.

An initial Compose invocation omitted explicit `-p`. The repository `.env` overrode the YAML project name and Compose recreated the two stopped original service container definitions using the copied **data** volumes. This was detected from container mounts, the services were stopped, and the original definitions were recreated with the original data volumes in a non-running state. Original corpus data volumes were never started by the evaluation. Neo4j's pre-existing anonymous log volume was reused during that brief invocation and may contain startup log entries; it is not the graph data volume. Subsequent commands use explicit `-p contractlens-eval-01a154eb` and dedicated service containers. This resource-definition incident is disclosed separately from the legal data fingerprint checks.

The worker uses the existing application image with the current repository mounted read-only, except `evaluation_results/`. The existing embedding cache is mounted read-only. Model, embedding, retrieval settings, package versions and application source hashes are in `execution_metadata.json`. Legal table row/content fingerprints before and after inference are identical.

The actual five-case smoke run is preserved in `smoke_real/`. An earlier host preflight in `smoke/` produced no model output and is not combined with the baseline. Windows sandbox asyncio initialization stalled; actual inference was therefore run in Linux Docker workers outside that sandbox.

The main baseline was stopped after the provider returned daily quota exhaustion (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, observed limit 20). Eleven case records had been persisted, and MIX-004 was in progress. The worker was stopped during retry, so that case's partial console trace is preserved without an invented answer or latency. Twenty-two cases were never started. `finalize_blocked.py` added only explicit blocked/interrupted records and a read-only corpus fingerprint; it did not generate answers.

The outcome is an incomplete, quota-limited baseline. Scores on the observed subset must not be generalized to all 34 cases. No model substitution or production algorithm changes were made.
