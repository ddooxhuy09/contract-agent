# ContractLens — empty schema handoff (Postgres + Neo4j)

Gói schema **rỗng** (không data) để dựng DB rồi nạp corpus pháp lý / hợp đồng.

| File | Hệ | Nội dung |
|------|-----|----------|
| `contractlens_postgres.sql` | PostgreSQL 16+ + **pgvector** | Tables, indexes, triggers, refresh functions |
| `contractlens_neo4j.cypher` | Neo4j 5+ | Constraints + indexes GraphRAG (không chứa text/embedding) |

Nguồn gốc trong repo: `schema.sql`, `schema.cypher` (giữ đồng bộ với thư mục này).

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

### Neo4j
- Neo4j **5.x** (Community/Enterprise)
- Chỉ cần chạy các câu `CREATE CONSTRAINT` / `CREATE INDEX` trong file `.cypher` (phần comment là tài liệu mô hình)

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

### Neo4j

Trong Neo4j Browser / `cypher-shell`, chạy lần lượt các dòng bắt đầu bằng `CREATE CONSTRAINT` và `CREATE INDEX` (bỏ qua comment `//`).

```bash
cypher-shell -u neo4j -p PASSWORD -f contractlens_neo4j.cypher
# hoặc paste các CREATE CONSTRAINT / CREATE INDEX vào Browser
```

---

## 3. Phân công: Postgres vs Neo4j

| Dữ liệu | Postgres (SoT) | Neo4j |
|---------|----------------|-------|
| Metadata VB (`doc_id`, số hiệu, hiệu lực…) | `legal_documents` | mirror nhẹ `:Document` |
| Cây Phần→…→Điểm | `legal_parts` … `legal_points` | `:Node` + `PARENT_OF` / `NEXT` |
| Nội dung chunk + embedding + FTS | `legal_embeddings` | chỉ `:Chunk {path, doc_id, chunk_type}` — **không** text/embed |
| Quan hệ VB↔VB | `legal_document_relations` | cạnh `REPEALS` / `SUPERSEDES` / `AMENDS` / … |
| Dẫn chiếu Điều/Khoản (ltree) | `legal_path_relations` | `(:Chunk)-[:REFERS_TO]->(:Chunk)` |
| User + hợp đồng upload | `users`, `uploaded_contracts`, `contract_chunks` | — |

**Khóa nối PG ↔ Neo4j:** `doc_id` (TEXT) và `path` (ltree text, ví dụ `45_2019_QH14.C3.D21.K1`).

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

## 5. Thứ tự nạp data (Neo4j)

1. `:Document` (`doc_id`, `doc_num`, `doc_type`, optional `status_flag`)
2. `:Node` theo path (MERGE `(d)-[:HAS_NODE]->(n)`, `PARENT_OF`, optional `NEXT`)
3. `:Chunk` keyed by `path` → `OF_DOC`, `OF_NODE`
4. Cạnh văn bản (map từ `legal_document_relations.relation_type`):

| `relation_type` (PG) | Rel type (Neo4j) |
|----------------------|------------------|
| `van_ban_bi_bai_bo` | `REPEALS` |
| `thay_the` | `SUPERSEDES` |
| `sua_doi_bo_sung` | `AMENDS` |
| `can_cu_ban_hanh` | `BASED_ON` |
| `dan_chieu` | `CITES` |
| `quy_dinh_chi_tiet_huong_dan_thi_hanh` | `DETAILS` |
| `huong_dan_ap_dung` | `GUIDES` |
| … | xem comment trong `.cypher` |

5. `(:Chunk)-[:REFERS_TO]->(:Chunk)` từ `legal_path_relations`

GraphRAG chỉ expand cấu trúc/quan hệ; **hydrate nội dung** từ Postgres `legal_embeddings` theo `path`.

---

## 6. Ràng buộc kỹ thuật quan trọng

- Embedding dimension cố định: **`vector(1024)`** (đổi model → phải đổi schema + re-embed).
- `path` ltree: ký tự ngoài `[A-Za-z0-9_]` trong `doc_id` được sanitize thành `_`.
- `eff_from < eff_to` khi cả hai NOT NULL (CHECK).
- Không có cron trong schema: cần job ngoài gọi `refresh_status_flags()` định kỳ.

---

## 7. Kiểm tra nhanh sau khi dựng

```sql
-- Postgres
SELECT extname FROM pg_extension WHERE extname IN ('vector','ltree','pg_trgm','pgcrypto');
SELECT COUNT(*) FROM legal_documents;           -- 0 khi rỗng
SELECT COUNT(*) FROM legal_embeddings;
```

```cypher
// Neo4j
SHOW CONSTRAINTS;
SHOW INDEXES;
MATCH (n) RETURN count(n);   // 0 khi rỗng
```
