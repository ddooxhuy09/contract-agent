# Corpus coverage report

Generated: 2026-10-19T16:19:05.671060+00:00

## Evidence available locally

- Local `thuoc_tinh.json` metadata files: 2. These are source folders, not proof of database ingestion.
- Benchmark legal documents: 11; local exact document-number overlap: 0 (comparison uses local metadata only).
- Benchmark excerpts: 43. They are illustrative excerpts, not full statutes.
- Version timeline rows needing source/full-text review: 3.

## Existing PostgreSQL and Neo4j corpus

- PostgreSQL reachable: False. Legal-document count: None.
- Neo4j reachable: False. Node/relationship inventory: unknown.
- The configured Docker engine was unavailable during this run, and host ports 5433/7688/8010 did not accept connections. Database corpus contents and ingest state therefore remain unknown; no count is inferred from local files.

### Local corpus documents

| Document number | Title | Local path | Status metadata |
|---|---|---|---|
| 100/2015/QH13 | Bộ luật Hình sự số 100/2015/QH13 | `Bộ luật Hình sự số 100-2015-QH13--96122` | Hết hiệu lực một phần |
| 168/2024/NĐ-CP | Nghị định số 168/2024/NĐ-CP (fixture) | `tests\fixtures\legal_sample` | Còn hiệu lực |

### Benchmark documents not matched in local metadata

| Benchmark ID | Title | Status label |
|---|---|---|
| 10/2012/QH13 | Bộ luật Lao động 2012 | expired |
| 45/2019/QH14 | Bộ luật Lao động 2019 | in_force_with_amendments |
| 58/2014/QH13 | Luật BHXH 2014 | expired_with_transitional_possibility |
| 41/2024/QH15 | Luật BHXH 2024 | in_force |
| 51/2005/QH11 | Luật Giao dịch điện tử 2005 | expired_with_transitional_exceptions |
| 20/2023/QH15 | Luật Giao dịch điện tử 2023 | in_force |
| 59/2010/QH12 | Luật BVQLNTD 2010 | expired_with_transitional_exceptions |
| 19/2023/QH15 | Luật BVQLNTD 2023 | in_force |
| 145/2020/NĐ-CP | Nghị định 145/2020/NĐ-CP | partially_amended_or_expired |
| 35/2022/NĐ-CP | Nghị định 35/2022/NĐ-CP | in_force_at_relevant_2022_snapshot |
| 10/2024/NĐ-CP | Nghị định 10/2024/NĐ-CP | in_force_at_relevant_2024_snapshot |

### Unverified or incomplete provision-version text

The benchmark README labels all 34 cases as synthetic draft and says legal review remains pending. Placeholder/historical excerpts are excluded from any claim of verified retrieval ground truth.

- `N145-4.2` / `N145_ART4_CLAUSE2_ORIGINAL`: full_text_available=False; source review=needs_exact_historical_snapshot_text_validation; Chưa trích toàn văn nguyên bản, không đánh giá text exact match ở bản này.
- `N145-4.2` / `N145_ART4_CLAUSE2_AMENDED_2022`: full_text_available=False; source review=needs_exact_historical_snapshot_text_validation; Phải cập nhật tiếp các văn bản sửa đổi sau 2022 trước khi kết luận hiệu lực nội dung năm 2026.
- `N145-4.4` / `N145_ART4_CLAUSE4_ADDED_2024`: full_text_available=False; source review=needs_exact_historical_snapshot_text_validation; Đánh giá tại 01/04/2024; không khẳng định toàn bộ nội dung hiện còn nguyên ở 2026.

### Scope

This Existing Corpus Baseline did not ingest benchmark statutes, update PostgreSQL, or alter Neo4j. Controlled Fixture Evaluation was not run: there is no isolated test database available and the legal excerpts have not all been independently verified.
