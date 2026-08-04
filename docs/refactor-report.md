# Báo cáo refactor Clean Architecture (schema.sql + schema.cypher)

## Đã thay đổi

1. **Kiến trúc lớp**
   - `app/domain` — entities, ports (Protocol), errors
   - `app/application/use_cases` — auth, contracts, legal_ingest
   - `app/infrastructure` — Postgres repos, pgvector search, Neo4j, JWT/bcrypt, embeddings, storage, agent adapters
   - `app/api` — routes mỏng + DI deps
   - `main.py` lifespan wire container

2. **Auth**
   - Bỏ Supabase; JWT local (`users` + register/login)
   - Frontend `AuthContext` / `api.js` dùng localStorage token

3. **Vector**
   - Bỏ FAISS khỏi hot path; `contract_chunks` / `legal_section_chunks` + HNSW
   - Retrieve qua `PgContractVectorSearch` / `PgLegalVectorSearch`

4. **Schema**
   - Boot apply `schema.sql`; Neo4j apply constraints từ `schema.cypher`
   - `docker-compose.yml`: pgvector + Neo4j
   - FK trên `legal_chunk_relations`

5. **Legal**
   - Xóa loader dump; skeleton `IngestLegalDocument` + `scripts/ingest_legal_sample.py`

## Lý do

- Bám SoT: Postgres (nội dung/embed/cạnh id) + Neo4j (cây/traversal)
- Giảm coupling singleton FAISS/Supabase; tăng testability (ports + fake)
- Data thật chưa có — code chạy DB trống; ingest sau

## Cải thiện kiến trúc / SOLID

- **SRP**: use case / repo / search tách riêng
- **DIP**: application phụ thuộc Protocol, không phụ thuộc psycopg/neo4j
- **OCP**: đổi MinIO/Neo4j adapter không đụng domain
- **ISP**: ports nhỏ (UserRepo, VectorSearch, Graph…)
- DI qua `AppContainer` + FastAPI `Depends`

## Việc còn lại (tương lai)

- Parser `muc_luc`/`van_ban` thật → chunk_ref path đầy đủ
- Hybrid FTS + RRF ranking
- Graph expand hydrate text anh em Điểm vào prompt QA
- Alembic migrations thay vì apply full `schema.sql` mỗi boot
- Testcontainers integration cho upload/analyze end-to-end
- Pin versions trong `requirements.txt`
- ~~Xóa hẳn `frontend/src/supabaseClient.js`~~ (đã xóa; gỡ `@supabase/supabase-js`)
- Embedding SoT: `BAAI/bge-m3` / 1024-d / `max_seq_length=512` / `normalize_embeddings=True` / `trust_remote_code=True` qua `infrastructure/embeddings/hf_embedder.py` + `core/settings.py` (đã bỏ `core/config.py`)
