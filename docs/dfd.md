# ContractLens — Sơ đồ luồng dữ liệu (DFD)

> Cập nhật theo **mã nguồn hiện tại** (JWT + PostgreSQL/pgvector + Neo4j + Gemini + BGE-M3).
> Không còn Supabase Auth hay FAISS.
>
> File PlantUML: thư mục [`docs/dfd/`](dfd/).

## Cách xem sơ đồ

Mở file `.puml` bằng extension PlantUML trong VS Code / Cursor, hoặc:

```text
java -jar plantuml.jar docs/dfd/*.puml
```

Mỗi file `!include _skin.puml` — render từ đúng thư mục `docs/dfd/`.

## Mục lục

| DFD | Tiến trình | File PlantUML | Nguồn chính |
|-----|------------|---------------|-------------|
| Mức 0 | Ngữ cảnh hệ thống | [dfd-0-context.puml](dfd/dfd-0-context.puml) | — |
| Mức 1 | Bảy tiến trình 1.0–7.0 | [dfd-1-overview.puml](dfd/dfd-1-overview.puml) | — |
| Mức 2 | 1.0 Xác thực | [dfd-2-auth.puml](dfd/dfd-2-auth.puml) | `app/application/use_cases/auth.py`, `app/api/deps.py` |
| Mức 2 | 2.0 Tải lên & lập chỉ mục | [dfd-2-upload.puml](dfd/dfd-2-upload.puml) | `UploadContract`, `parser.py`, `chunker.py` |
| Mức 2 | 3.0 Phân tích rủi ro | [dfd-2-analyze.puml](dfd/dfd-2-analyze.puml) | `AnalyzeContract`, `app/agents/workflow.py` |
| Mức 2 | 4.0 Hỏi đáp | [dfd-2-qa.puml](dfd/dfd-2-qa.puml) | `app/agents/qa_agent.py` |
| Mức 2 | 5.0 Danh sách HĐ | [dfd-2-list-contracts.puml](dfd/dfd-2-list-contracts.puml) | `ListContracts` |
| Mức 2 | 6.0 Crawl VBPL | [dfd-2-crawl.puml](dfd/dfd-2-crawl.puml) | `scripts/crawl_vbpl/crawl_all.py` |
| Mức 2 | 7.0 Ingest pháp điển | [dfd-2-ingest.puml](dfd/dfd-2-ingest.puml) | `IngestLegalDocument`, `scripts/ingest_legal_corpus.py` |
| Mức 2 | GraphRAG (dùng bởi 3.0 và 4.0) | [dfd-2-retrieval.puml](dfd/dfd-2-retrieval.puml) | `app/infrastructure/retrieval/` |
| Mức 2 | Giao diện React | [dfd-2-frontend.puml](dfd/dfd-2-frontend.puml) | `frontend/src/App.jsx`, `api.js` |

---

## Ký hiệu

| Ký hiệu PlantUML | Ý nghĩa DFD |
|------------------|-------------|
| `actor` | Thực thể ngoài (người dùng, người vận hành) |
| `rectangle` bo góc, đánh số `n.n` | Tiến trình biến đổi dữ liệu |
| `database` | Kho dữ liệu |
| `cloud` | Hệ thống bên ngoài |
| Mũi tên có nhãn | Luồng dữ liệu (không phải luồng điều khiển thuần) |

---

## Mức 0 — Ngữ cảnh

Nhìn từ ngoài: người dùng và người vận hành trao đổi với **một** hệ thống ContractLens. Hệ thống gọi Gemini và (khi crawl) VBPL.vn; lưu dữ liệu vào PostgreSQL, Neo4j và ổ đĩa cục bộ.

Embedding `BAAI/bge-m3` chạy **trong** process API nên không vẽ là thực thể ngoài ở mức 0.

---

## Mức 1 — Bảy tiến trình

| Số | Tên | Tác nhân | I/O chính |
|----|-----|----------|-----------|
| 1.0 | Xác thực | Người dùng | email/mật khẩu → JWT; JWT → `user_id` |
| 2.0 | Tải lên & lập chỉ mục | Người dùng | file HĐ → `contract_id` + chunks đã embed |
| 3.0 | Phân tích rủi ro | Người dùng | `contract_id` → `analysis` + `risks` JSONB |
| 4.0 | Hỏi đáp | Người dùng | câu hỏi → câu trả lời SSE + trích dẫn |
| 5.0 | Danh sách HĐ | Người dùng | `user_id` → danh sách metadata |
| 6.0 | Crawl VBPL | Người vận hành | HTTP VBPL → folder JSON/MD |
| 7.0 | Ingest pháp điển | Người vận hành | folder crawl → PG + Neo4j |

6.0 và 7.0 **không** có REST; chạy script.

---

## Kho dữ liệu (từ điển)

| ID | Kho | Nội dung | Ai đọc / ghi |
|----|-----|----------|----------------|
| D1.1 | `users` | email, `password_hash`, UUID | 1.0 ghi/đọc |
| D1.2 | `uploaded_contracts` | metadata HĐ, `full_text`, `analysis`/`risks` JSONB | 2.0, 3.0, 4.0, 5.0 |
| D1.2b | `contract_chunks` | Điều + `embedding vector(1024)` | 2.0 ghi; 3.0/4.0 đọc |
| D1.3 | `legal_documents` + hierarchy 7 tầng | metadata + cây Điều/Khoản/Điểm (`ltree`) | 7.0 ghi; 3.0/4.0 đọc |
| D1.3c | `legal_embeddings` | chunk luật + vector + FTS + `is_effective` | 7.0 ghi; GraphRAG đọc |
| D1.3d | `legal_document_relations`, `legal_path_relations` | cạnh VB↔VB và path↔path | 7.0 ghi; GraphRAG đọc |
| D1.4 | bảng checkpoint LangGraph (thư viện tạo lúc startup) | lịch sử chat, HITL, memory store | 4.0; 3.0 khi `review_mode` |
| D2 | Neo4j `:Document` `:Node` `:Chunk` | **chỉ** id/path/quan hệ — không text/embedding | 7.0 ghi; GraphRAG expand |
| D3.1 | `data/uploads` | file HĐ gốc | 2.0 ghi; parse đọc |
| D3.2 | `data/crawl_data` | folder crawl | 6.0 ghi; 7.0 đọc |

---

## Luồng API tương ứng (runtime)

```text
Đăng ký/nhập     → 1.0   POST /api/v1/auth/register | /login
Tải HĐ           → 2.0   POST /api/v1/upload
Phân tích        → 3.0   POST /api/v1/analyze
Danh sách        → 5.0   GET  /api/v1/contracts
Chat (UI)        → 4.0   POST /api/v1/chat/stream
Lịch sử chat     → 4.8   GET  /api/v1/chat/{id}/history
Danh sách model  → UI    GET  /api/v1/models          (không JWT)
```

API có trên backend nhưng frontend **không** gọi: `POST /analyze/resume`, `POST /chat`, `GET /chat/{id}/states`, `POST /chat/{id}/rewind`. Vẫn được vẽ ở mức 2 phân tích / hỏi đáp vì đã implement.

---

## Ghi chú khác biệt so với DFD cũ (2026-07)

| Cũ (sai với code hiện tại) | Nay |
|----------------------------|-----|
| Supabase Auth | JWT nội bộ + bcrypt, bảng `users` |
| FAISS hợp đồng / luật | pgvector trên `contract_chunks` và `legal_embeddings` |
| `app/core/auth.py`, `app/services/contract_service.py` | `use_cases/auth.py`, `use_cases/contracts.py` |
| `app/knowledge_base/loader.py` | `IngestLegalDocument` + `scripts/ingest_legal_corpus.py` |
| Không có Neo4j | Neo4j expand GraphRAG |
| Chat REST thuần | UI dùng SSE `/chat/stream` |

---

## Danh sách kiểm tra

| # | Tiêu chí | Trạng thái |
|---|----------|------------|
| 1 | Thực thể ngoài | Người dùng, người vận hành, Gemini, VBPL.vn |
| 2 | Kho dữ liệu runtime + offline | PostgreSQL (tách logic), Neo4j, uploads, crawl |
| 3 | Mỗi luồng chính có dữ liệu đi và kết quả về | Có |
| 4 | Cache phân tích | 3.3 đọc JSONB `analysis` |
| 5 | Tác vụ nền / thủ công | 6.0 crawl, 7.0 ingest |
| 6 | Xác thực trên API bảo vệ | 1.3 gác cổng |
| 7 | Không bịa thành phần đã gỡ | Không vẽ Supabase, FAISS, MinIO |
