# ContractLens — AI rà soát hợp đồng tiếng Việt

Stack: FastAPI · Postgres/pgvector · Neo4j · Gemini · BAAI/bge-m3 · React (Vite)

## Chạy bằng Docker

Cần [Docker Desktop](https://www.docker.com/products/docker-desktop/). Không cần cài Python/Node trên máy.

```powershell
# 1) Cấu hình
copy .env.example .env
# Điền GEMINI_API_KEY và JWT_SECRET (không để giá trị mặc định)

# 2) Build & chạy toàn bộ stack
docker compose up --build -d
```

Mở:

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| API      | http://localhost:8010/health |

Lần đầu API sẽ tải model embedding (`BAAI/bge-m3`) — có thể mất vài phút.

### Nạp database từ dump (tuỳ chọn)

Đặt file dump ở root repo rồi chạy script tương ứng.

**Windows (PowerShell):**

```powershell
# Postgres (contractlens_backup.dump)
docker compose up -d postgres
powershell -File scripts\restore_db.ps1

# Neo4j (neo4j.dump) — service sẽ bị stop/start trong lúc nạp
powershell -File scripts\restore_neo4j.ps1

docker compose up -d
```

**macOS / Linux:**

```bash
docker compose up -d postgres
sh scripts/restore_db.sh
chmod +x scripts/restore_neo4j.sh
./scripts/restore_neo4j.sh
docker compose up -d
```

### Lệnh thường dùng

```bash
docker compose up --build -d    # build lại & chạy
docker compose logs -f api      # xem log API
docker compose down             # dừng stack
```

## Pipeline pháp điển (crawl → extract → DB)

Mỗi văn bản là **một folder** (đặt dưới `data/crawl_data/…`, không để rải ở root repo) với:

| File | Bắt buộc | Vai trò |
|------|----------|---------|
| `thuoc_tinh.json` | có | metadata VB |
| `van_ban.md` | có | toàn văn |
| `muc_luc.json` | có | cây Phần→…→Điểm → hierarchy + chunk path |
| `luoc_do.json` | không | quan hệ doc↔doc → `legal_document_relations` |
| `clause_amendments.json` | không | sửa đổi Điều/Khoản/Điểm → `legal_path_relations` |

Path hierarchy / `legal_path_relations` root theo **số hiệu** (`100_2015_QH13.P1.C13…`). Embeddings hiện vẫn root theo `doc_id` portal (`96122.…`).

### Extract vs ingest (khi nào chạy gì)

**Extract** = parse folder trong RAM (chưa ghi DB). **Ingest** = embed + upsert Postgres/Neo4j. Cả hai chạy khi gọi `ingest_legal_corpus` (trừ `--dry-run` chỉ extract).

```
crawl → folder JSON/MD
         │
         ▼
load_document_folder (EXTRACT)
  muc_luc          → legal_nodes (parts…points paths)
  van_ban          → chunks; tiêu đề "Hiệu lực thi hành" → chunk_type=effectivity
  body citations   → path_relations (dan_chieu, cùng VB)
  luoc_do          → relations doc↔doc
  thuoc_tinh       → metadata + eff_from/eff_to/status_flag
         │
         ▼
IngestLegalDocument.execute (GHI DB) — thứ tự:
  1. legal_documents
  2. hierarchy (legal_parts … legal_points) — inherit HL từ doc nếu thiếu
  3. embed → legal_embeddings (path, chunk_type, is_effective khởi tạo)
  4. legal_document_relations (luoc_do + stub doc nếu thiếu)
  5. legal_path_relations (dẫn chiếu nội bộ vừa extract)
  6. Neo4j tree (nodes + chunks)

clause_amendments — lệnh riêng: scripts.ingest_clause_amendments
  → cũng ghi legal_path_relations (sửa đổi/bãi bỏ, ref_type khác dan_chieu)
```

| Cờ / lệnh | Việc |
|-----------|------|
| `--dry-run` | Chỉ extract + in số chunk/relations; không DB, không checkpoint |
| ingest thật | Extract rồi ghi DB như trên |
| `ingest_clause_amendments` | Extract `clause_amendments.json` → `legal_path_relations` |

**`chunk_type=effectivity`** chỉ là nhãn nội dung (Điều “Hiệu lực thi hành”). **Còn/hết hiệu lực pháp lý** = `status_flag` / `eff_*` trên hierarchy (+ cache `legal_embeddings.is_effective`), không gắn vì title.

Index (HNSW, GiST ltree, btree status…) nằm trong `schema.sql` — mỗi INSERT/UPDATE tự cập nhật; ingest **không** rebuild index.

### Trigger Postgres (ngầm trong transaction)

Không có worker/cron trong Docker (`pg_cron` cũng không cài). Trigger fire khi INSERT/UPDATE:

| Trigger | Khi | Việc |
|---------|-----|------|
| sync `eff_flag` ↔ `status_flag` | đổi một trong hai | đồng bộ cặp cột; **sau đó** `eff_from`/`eff_to` thắng nhãn crawl |
| dates → status | đổi `eff_from` / `eff_to` | so `CURRENT_DATE` → chưa HL / còn HL / hết HL |
| cascade doc | doc chuyển còn HL | đánh hết HL doc bị thay thế/bãi bỏ (qua quan hệ) |
| cascade hierarchy | node `status_flag=2` | hết HL lan xuống con (Điều→Khoản→Điểm) |
| sync embeddings | đổi status/path hierarchy | cập nhật `legal_embeddings.is_effective` |

**Hạn chế:** ngày trôi qua mà không có UPDATE thì trigger **không chạy** → `status_flag` có thể lệch (vd `eff_to` đã qua vẫn còn `status_flag=1`). Quét lại theo lịch (tay hoặc cron ngoài):

```sql
SELECT * FROM refresh_status_flags();        -- cấp văn bản
SELECT refresh_hierarchy_status_flags();     -- cấp Điều/Khoản/Điểm + is_effective
```

Query-time GraphRAG / citation vẫn so `as_of` với `eff_to` — không tin riêng nhãn “Còn hiệu lực”.

Schema rỗng để dựng DB mới / gửi đối tác: `schemas/empty/` (`contractlens_postgres.sql`, `contractlens_neo4j.cypher`).

### 1) Crawl VBPL

```powershell
$env:PYTHONPATH = "D:\contract-agent"   # root repo

python -m scripts.crawl_vbpl.crawl_all
python -m scripts.crawl_vbpl.crawl_all --doc-type "Bộ luật"
python -m scripts.crawl_vbpl.crawl_all --limit 5
```

Output: `data/crawl_data/documents/…`  
(Module lẻ trong `scripts/crawl_vbpl/`: `fetch_list`, `fetch_van_ban`, `fetch_thuoc_tinh`, `fetch_luoc_do`, `convert`.)

Bổ sung `muc_luc.json` (+ `clause_amendments.json` nếu có) vào từng folder trước khi ingest.

### 2) Schema DB / Neo4j

DB mới: apply `schema.sql` (hoặc `schemas/empty/contractlens_postgres.sql`) + `schema.cypher`.  
Docker Postgres đã mount `schema.sql` vào init. Neo4j: chạy constraint/index trong `schema.cypher`.

### 3) Ingest corpus → Postgres + Neo4j

Extract (assemble) rồi ghi DB như mục **Extract vs ingest** ở trên.

```powershell
$env:PYTHONPATH = "D:\contract-agent"

python -m scripts.ingest_legal_corpus "data\crawl_data\documents" --dry-run --limit 3
python -m scripts.ingest_legal_corpus "data\crawl_data\documents"
python -m scripts.ingest_legal_corpus "data\crawl_data\documents\…\SomeDoc--96122" --force

# Fixture nhỏ không cần dump
python -m scripts.ingest_legal_sample
```

Code: `assemble.py` (extract) → `legal_ingest.py` (ghi DB).

### 4) Ingest clause amendments → `legal_path_relations`

```powershell
python -m scripts.ingest_clause_amendments "data\crawl_data\documents" --dry-run
python -m scripts.ingest_clause_amendments "data\crawl_data\documents"
```

### 5) Test unit liên quan

```powershell
python -m pytest tests/unit/test_legal_corpus_parser.py tests/unit/test_clause_amendments.py tests/unit/test_effectivity_internal_refs.py tests/unit/test_legal_ingest_unit.py -q
```

## API chính

- `POST /api/v1/auth/register` · `login`
- `POST /api/v1/upload` · `analyze` · `chat`
- `GET /api/v1/contracts`
- `GET /health`
