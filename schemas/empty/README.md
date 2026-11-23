# ContractLens — empty schema handoff (Postgres)

Gói schema **rỗng** (không data) để dựng DB rồi nạp corpus pháp lý / hợp đồng.

| File | Hệ | Nội dung |
|------|-----|----------|
| `contractlens_postgres.sql` | PostgreSQL 16+ + **pgvector** | Tables, indexes, triggers, refresh functions |

Nguồn gốc trong repo: `schema.sql` (giữ đồng bộ với thư mục này). Từ 15/11/2026 hệ thống không còn dùng Neo4j; toàn bộ dữ liệu nằm trong Postgres.

---

## 1. Yêu cầu môi trường

### Postgres
- PostgreSQL **16+** (hoặc image có sẵn extension)
- Extensions (script tự `CREATE EXTENSION IF NOT EXISTS`):
  - `vector` (pgvector) — embedding **1024** chiều (BGE-M3)
  - `ltree` — khóa phân cấp `path`
  - `pg_trgm` — tìm gần đúng số hiệu / tiêu đề
  - `pgcrypto` — `gen_random_uuid()` cho bảng `users`

Ví dụ image: `pgvector/pgvector:pg16`

---

## 2. Áp schema (DB trống)

### Postgres

```bash
# DB mới, user có quyền CREATE EXTENSION
psql "postgresql://USER:PASS@HOST:5432/DBNAME" -v ON_ERROR_STOP=1 -f contractlens_postgres.sql
```

Docker volume init (gắn file vào `/docker-entrypoint-initdb.d/`):

```bash
psql -U postgres -d contractlens -f /docker-entrypoint-initdb.d/01-schema.sql
```

Script **idempotent** (`IF NOT EXISTS` / `CREATE OR REPLACE`) — chạy lại an toàn trên DB đã có schema.

---

---

## 3. Đồ thị pháp luật cho GraphRAG (trong Postgres)

| Thành phần đồ thị | Bảng / cột | Dùng khi expand |
|-------------------|------------|-----------------|
| Cây Phần→…→Điểm | `legal_parts` … `legal_points`, cột `path` (ltree) | anh em cùng cha, tổ tiên, khoản cha của seed |
| Chunk nội dung + embedding + FTS | `legal_embeddings` (`path` UNIQUE) | seed (vector/FTS) và hydrate text theo `path` |
| Quan hệ VB↔VB | `legal_document_relations` (`relation_type`) | văn bản liên quan (`can_cu_ban_hanh`, `dan_chieu`, `sua_doi_bo_sung`) và văn bản bãi bỏ/thay thế (`van_ban_bi_bai_bo`, `thay_the`) |
| Dẫn chiếu Điều/Khoản | `legal_path_relations` | dẫn chiếu nội bộ và sửa đổi/bãi bỏ ở cấp khoản |

Truy vấn expand: `PgLegalChunkRepository.expand_paths` (`app/infrastructure/db/legal_repository.py`).

---

## 4. Thứ tự nạp data (Postgres)

1. `legal_documents`
2. Hierarchy (FK chain):  
   `legal_parts` → `legal_chapters` → `legal_sections` → `legal_sub_sections` → `legal_articles` → `legal_clauses` → `legal_points`  
   - Cấp thiếu vẫn có row với `title`/`content` = `'Không có'`.
3. `legal_embeddings` (`path` UNIQUE, `embedding vector(1024)`, `is_effective`)
4. `legal_document_relations`
5. `legal_path_relations`
6. (App) `users` / `uploaded_contracts` / `contract_chunks` — không bắt buộc cho corpus luật

Sau khi nạp / khi lịch đổi ngày:

```sql
SELECT * FROM refresh_status_flags();
SELECT refresh_hierarchy_status_flags();
```

### `status_flag` (0..5)

| Mã | Ý nghĩa |
|----|---------|
| 0 | Chưa xác định |
| 1 | Còn hiệu lực |
| 2 | Hết hiệu lực toàn bộ |
| 3 | Chưa có hiệu lực |
| 4 | Hết hiệu lực một phần |
| 5 | Có hiệu lực một phần |

Trigger đồng bộ `eff_flag` ↔ `status_flag`; cửa sổ `eff_from` / `eff_to` thắng nhãn crawl cũ khi INSERT/UPDATE.

---

---

## 5. Ràng buộc kỹ thuật quan trọng

- Embedding dimension cố định: **`vector(1024)`** (đổi model → phải đổi schema + re-embed).
- `path` ltree: ký tự ngoài `[A-Za-z0-9_]` trong `doc_id` được sanitize thành `_`.
- `eff_from < eff_to` khi cả hai NOT NULL (CHECK).
- Không có cron trong schema: cần job ngoài gọi `refresh_status_flags()` định kỳ.

---

## 6. Kiểm tra nhanh sau khi dựng

```sql
-- Postgres
SELECT extname FROM pg_extension WHERE extname IN ('vector','ltree','pg_trgm','pgcrypto');
SELECT COUNT(*) FROM legal_documents;           -- 0 khi rỗng
SELECT COUNT(*) FROM legal_embeddings;
```
