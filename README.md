# ContractLens — AI rà soát hợp đồng lao động tiếng Việt

Stack: FastAPI · Postgres/pgvector · Neo4j · Groq (gpt-oss-120b) / Gemini · BAAI/bge-m3 · React (Vite)

Phạm vi: hợp đồng lao động. Đây không phải tư vấn pháp lý; xem [`docs/PHAM_VI.md`](docs/PHAM_VI.md).

## Giới hạn

- Chưa đo được độ chính xác của câu trả lời hỏi đáp. Bộ gold set có chuyên gia kiểm đang được xây dựng (`evaluation/gold/`); số đo đầu ra ở `evaluation_results/RESULTS_TUAN.md` kèm cỡ mẫu và khoảng tin cậy. Chưa kiểm chứng trên hợp đồng ngoài bộ dữ liệu.
- Điều khoản mà mô hình không đánh giá được (lỗi, hết quota, JSON hỏng) được báo là "chưa kiểm" trong `analysis.coverage`, không phải "ổn".
- Một nhà cung cấp LLM mỗi lần chạy, chọn bằng `LLM_PROVIDER`: mặc định `groq` (model `openai/gpt-oss-120b`, cấu hình đã dùng để đánh giá), tuỳ chọn `gemini`. Tham số `provider` của API chỉ có một giá trị.
- Không hỗ trợ `.doc` (chuyển sang `.docx`) và PDF dạng ảnh quét không có lớp chữ (tải ảnh `.png/.jpg` để dùng OCR). Giới hạn tải lên 10 MB.
- Bước duyệt thủ công (`review_mode`, `POST /analyze/resume`) chỉ có ở API, giao diện chưa dùng. API không nhận ngày hiệu lực (`as_of`); ngày áp dụng luật lấy từ ngày ký trong hợp đồng.
- Hiệu lực luật: văn bản có trạng thái "hết hiệu lực một phần" mặc định bị loại khỏi truy xuất; chỉ Bộ luật Lao động 2019, Nghị định 145/2020 và Luật An toàn vệ sinh lao động 2015 đã được bật lại (xem [`docs/kiem_tra_hieu_luc.md`](docs/kiem_tra_hieu_luc.md)).
- Mật khẩu và cổng mặc định trong `docker-compose.yml` (`contractlens`, 5433/7688/8010) chỉ dành cho môi trường phát triển; không đưa lên production. Giới hạn đăng nhập sai chỉ có tác dụng trong một tiến trình.

## Chạy bằng Docker

Cần [Docker Desktop](https://www.docker.com/products/docker-desktop/). Không cần cài Python/Node trên máy.

```powershell
# 1) Cấu hình
copy .env.example .env
# Điền GROQ_API_KEY (hoặc GROG_KEY) và JWT_SECRET; muốn dùng Gemini thì đặt LLM_PROVIDER=gemini và điền GEMINI_API_KEY (không để giá trị mặc định)

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

## Yêu cầu và phát triển cục bộ

- Docker Desktop (cách chạy chính, xem trên). Image API dùng Python 3.12, image frontend dùng Node 22; máy dev hiện kiểm thử với Python 3.11.
- Chạy backend ngoài Docker (cần Postgres/Neo4j đang chạy, ví dụ `docker compose up -d postgres neo4j`):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Windows: giữ --reload. Không có nó uvicorn dùng ProactorEventLoop và psycopg async (checkpoint LangGraph) báo lỗi, /chat trả 503.
cd frontend && npm install && npm run dev      # lint: npm run lint, build: npm run build
```

### Biến môi trường (chỉ tên; mẫu ở `.env.example`, mặc định ở `app/core/settings.py`)

| Nhóm | Biến |
|---|---|
| Bắt buộc | `GROQ_API_KEY` (hoặc `GROG_KEY`; hoặc `GEMINI_API_KEY` khi `LLM_PROVIDER=gemini`), `JWT_SECRET` (khác giá trị mặc định, nếu không app không khởi động) |
| LLM | `LLM_PROVIDER` (`groq` mặc định | `gemini`), `GROQ_MODEL` (mặc định `openai/gpt-oss-120b`) |
| LLM dự phòng (Gemini) | `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`: key bổ sung. Khi key đang dùng hết quota theo ngày, client chuyển sang key kế tiếp (`app/agents/llm_client.py`). Quota theo phút vẫn chờ rồi thử lại trên cùng key. |
| LLM / embedding | `GEMINI_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `EMBEDDING_DEVICE`, `EMBEDDING_TRUST_REMOTE_CODE`, `EMBEDDING_NORMALIZE`, `EMBEDDING_MAX_SEQ_LENGTH`, `HF_TOKEN` |
| Database | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Auth / API | `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `CORS_ORIGINS`, `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_SECONDS`, `API_PORT`, `FRONTEND_PORT`, `VITE_API_BASE_URL` |
| Retrieval | `MAX_CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RETRIEVAL`, `SIMILARITY_THRESHOLD`, `LEGAL_EXPAND_BACKEND`, `RAG_LABOR_SCOPE` |
| Tùy chọn | `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `COMPOSE_PROJECT_NAME`, `DEV_RELOAD` |

### Test

```bash
python -m pytest tests -q --ignore=tests/integration   # unit + fixture QA, không cần dịch vụ ngoài
python -m pytest tests/integration -q                  # cần stack đang chạy
```

Test unit không cần Postgres/Neo4j/Gemini (hiện 227 passed, 1 skipped khi có thư mục `data/` và `evaluation_results/`; clone mới không có hai thư mục này sẽ fail 17 test đọc dữ liệu, xem `docs/test_baseline.txt`).

## Tài liệu

| Cần gì | Đọc |
|---|---|
| Quy tắc cho coding agent | [`AGENTS.md`](AGENTS.md) |
| Hiểu hệ thống | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Tìm nơi cần sửa | [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md) |
| Quy ước code | [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) |
| Nợ kỹ thuật, thay đổi đã làm | [`docs/REFACTOR_PLAN.md`](docs/REFACTOR_PLAN.md) |
| Phạm vi, hiệu lực luật, nhật ký thay đổi | [`docs/PHAM_VI.md`](docs/PHAM_VI.md), [`docs/kiem_tra_hieu_luc.md`](docs/kiem_tra_hieu_luc.md), [`docs/NHAT_KY_THAY_DOI.md`](docs/NHAT_KY_THAY_DOI.md) |
| Gold set và đánh giá | [`evaluation/README.md`](evaluation/README.md), [`evaluation/gold/`](evaluation/gold/) |
| Sơ đồ (Mermaid) | [`docs/diagrams/`](docs/diagrams/) |
| Tài liệu thiết kế khác | [`docs/README.md`](docs/README.md) |

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

### 5) Bộ test hỏi đáp từ `data/dataset.csv`

Sinh fixture QA offline và danh sách văn bản pháp luật chưa có trong local corpus:

```powershell
python -m scripts.build_qa_benchmark
python -m pytest tests/evaluation -q
```

Các file được sinh:

- `tests/fixtures/legal_qa.jsonl`: 3.298 mẫu, giữ `context` làm căn cứ tham chiếu và thêm Điều/số hiệu văn bản.
- `evaluation_results/reports/missing_legal_documents.csv`: văn bản nguồn trong dataset chưa có metadata corpus tương ứng.
- `evaluation_results/reports/qa_coverage.md`: thống kê độ bao phủ và các khoảng trống pháp lý quan trọng cho ContractLens.
- `tests/fixtures/contract_qa_cases.json`: các câu hỏi trọng tâm trên hợp đồng lao động mẫu.

Nhóm test này không gọi Gemini hoặc PostgreSQL. Trạng thái `missing_from_local_corpus` chỉ phản ánh file corpus trong repository; nếu database dùng dump riêng thì cần kiểm tra bổ sung trên database.

### 6) Test unit liên quan

```powershell
python -m pytest tests/unit/test_legal_corpus_parser.py tests/unit/test_clause_amendments.py tests/unit/test_effectivity_internal_refs.py tests/unit/test_legal_ingest_unit.py -q
```

## Cấu trúc thư mục

| Thư mục | Chứa gì |
|---|---|
| `app/` | Backend (FastAPI, agents, retrieval, ingest) |
| `frontend/` | Giao diện React |
| `scripts/` | Crawl, ingest, backfill, restore DB, audit |
| `tests/` | Test tự động (unit, integration, QA fixture, chấm điểm benchmark) |
| `evaluation/` | Code benchmark và **đề bài** (`benchmark/v04/`). Bắt đầu từ `evaluation/README.md` |
| `evaluation_results/` | **Kết quả** benchmark: `reports/` (tổng hợp) và `runs/` (từng lần chạy) |
| `docs/` | Tài liệu thiết kế, slide, prompt. Xem `docs/README.md` |
| `data/` | Dữ liệu cục bộ, không đưa lên git (dataset.csv, corpus mẫu, hợp đồng demo, upload) |
| `schema.sql`, `schema.cypher` | Schema Postgres/Neo4j mà docker-compose và app nạp trực tiếp |
| `schemas/empty/` | Bản sao schema rỗng để bàn giao |

## API chính

- `POST /api/v1/auth/register` · `auth/login`
- `POST /api/v1/upload` · `analyze` · `analyze/resume`
- `POST /api/v1/chat` · `chat/stream` (SSE) · `chat/{contract_id}/rewind`
- `GET /api/v1/contracts` · `models` · `chat/{contract_id}/history` · `chat/{contract_id}/states`
- `GET /health`
