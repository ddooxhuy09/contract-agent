# Kiến trúc hệ thống

Tài liệu này mô tả kiến trúc **hiện có** của mã nguồn. Sơ đồ nằm ở [`diagrams/`](diagrams/); bản đồ file ở [`CODEBASE_MAP.md`](CODEBASE_MAP.md). Tài liệu chi tiết cũ hơn (`PROJECT_TECHNICAL_DOCUMENTATION.md`, `processing-design.md`, `dfd.md`) vẫn giữ nguyên và chưa được đối chiếu lại trong đợt này.

## Thành phần chính

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| API | FastAPI (`app/main.py`, `app/api/routes.py`), prefix `/api/v1` | Auth JWT, upload, phân tích, chat (JSON + SSE) |
| Agents | LangGraph (`app/agents/`) | Đồ thị phân tích hợp đồng và đồ thị hỏi đáp |
| Retrieval | Postgres/pgvector + Neo4j (`app/infrastructure/retrieval/`, `vector/`) | Tìm điều luật theo vector, mở rộng theo cây Phần→Điểm |
| LLM | Gemini qua LangChain (`agents/llm_client.py`, `infrastructure/llm/gemini_chat.py`) | Trích xuất điều khoản, đánh giá rủi ro, trả lời |
| Embedding | `BAAI/bge-m3` (`infrastructure/embeddings/hf_embedder.py`) | Vector hóa hợp đồng và văn bản luật |
| Lưu trữ | Postgres (`schema.sql`), Neo4j (`schema.cypher`), file cục bộ (`data/uploads`) | Dữ liệu người dùng, hợp đồng, corpus pháp luật, checkpoint LangGraph |
| Frontend | React + Vite (`frontend/`) | Giao diện; build ra `frontend/dist`, API mount tĩnh nếu thư mục tồn tại |

## Phân lớp

```
api  ──►  application/use_cases  ──►  domain (entities, ports, errors)
                                           ▲
                          infrastructure (adapter) ┘   agents (LangGraph)
```

- `domain/`: entity, `ports` (Protocol cho repository và service), `errors`. Docstring ghi rõ không import framework.
- `application/use_cases/`: `auth.py`, `contracts.py`, `legal_ingest.py`. Nhận port qua constructor.
- `infrastructure/`: adapter Postgres (`db/`), Neo4j, vector search, embedding, Gemini, JWT/bcrypt, lưu file, `legal_corpus/` (parse folder crawl), `retrieval/`, `agents/pipelines.py`.
- `infrastructure/container.py`: `AppContainer` + `build_container()` dựng adapter; `lifespan` trong `app/main.py` gán `analyze_pipeline`, `qa_pipeline`, gọi `bind_retrieval(...)`.
- `agents/`: logic LangGraph và các bộ kiểm tra xác định (red-flag lao động, đủ nội dung Điều 21, trích dẫn phần căn cứ, hiệu lực văn bản).
- `schemas/contract.py`: Pydantic cho request/response và `ContractAnalysis`, `RiskItem`, `LegalCitation`.

### Ngoại lệ phân lớp còn lại (đã xác minh bằng AST, xem `REFACTOR_PLAN.md`)
- `agents/` → `infrastructure/retrieval/` (8 import: `context`, `query_rewrite`, `scope_match`) và `vectorstore/`: **chấp nhận có chủ đích**. `retrieval/context.py` là chỗ giữ repository/search đã `bind_retrieval` để agents không import vòng; `query_rewrite`, `scope_match` là logic thuần. Agents không còn truy vấn SQL hay import `db.connection`: các câu truy vấn nằm trong `PgLegalDocumentRepository` / `PgLegalChunkRepository`, agents lấy qua `get_legal_docs()` / `get_legal_chunks()` (mặc định là repository Postgres không trạng thái khi chưa bind).
- `infrastructure/` → `agents/`: chỉ `infrastructure/agents/pipelines.py` (đúng vai trò bọc đồ thị thành `AnalyzePipeline` / `QaPipeline`). `document/parser.py` import `agents.llm_client` (OCR ảnh).
- `application/use_cases/legal_ingest.py` → `infrastructure.legal_corpus.muc_luc_paths`.
- Không có import vòng ở mức module (kiểm tra bằng script AST trên toàn bộ `app/`, tính cả import trong hàm).

## Vòng đời request

1. `app/main.py` khởi động: kiểm tra `JWT_SECRET`, `build_container()`, áp `schema.sql` (`apply_postgres_schema`) và `graph.ensure_schema()` đọc `schema.cypher` (lỗi chỉ cảnh báo), tạo pipeline, `bind_retrieval`, `init_checkpointer`, làm nóng embedding.
2. Route nhận request, `get_current_user_id` giải JWT (`api/deps.py`), `get_container_dep` lấy `AppContainer`.
3. Route tạo use case từ container và gọi `execute`. Use case kiểm tra quyền sở hữu hợp đồng bằng `contracts.get_owned`, rồi gọi repository hoặc pipeline.
4. Tại route: `NotFoundError` → 404, `AuthError` (login) → 401, lỗi đăng ký trùng và lỗi file upload không hợp lệ → 400; lỗi khác qua `_http_error` (lỗi mất kết nối DB → 503, còn lại không lộ chi tiết driver).
5. `/chat/stream` kiểm tra quyền trước khi mở stream, rồi trả `StreamingResponse` (`text/event-stream`) từ `qa_pipeline.stream`.

Sơ đồ: [`diagrams/api-request-lifecycle.md`](diagrams/api-request-lifecycle.md).

## Luồng nghiệp vụ chính

**Upload** (`UploadContract`): lưu file → `parse_document` → `chunk_by_clause` → embed → ghi `contracts` và `contract_chunks`.

**Phân tích** (`AnalyzeContract` → `LangGraphAnalyzePipeline` → `agents/workflow.py`): đồ thị supervisor điều phối ba subgraph `extract` (parse điều khoản, thử lại khi lỗi tạm thời), `evaluate` (bước xác định `deterministic` rồi fan-out `judge_clause` song song bằng `Send`, gom ở `aggregate`) và `review` (chỉ khi `review_mode`, dừng chờ người duyệt; tiếp tục bằng `/analyze/resume`). Kết quả lưu qua `contracts.save_analysis`.

**Hỏi đáp** (`agents/qa_agent.py`): `retrieve` (hợp đồng + luật, có `as_of_date`) → `generate`, hoặc `rewrite` rồi `retrieve` lại, hoặc `refusal` khi không có ngữ cảnh; `generate` → `remember` hoặc `finalize`. Có checkpoint (rewind theo `checkpoint_id`) và bộ nhớ dài hạn (`agents/memory.py`).

Sơ đồ: [`diagrams/analysis-workflow.md`](diagrams/analysis-workflow.md), [`diagrams/qa-workflow.md`](diagrams/qa-workflow.md).

## Luồng dữ liệu

- Ghi: file upload → `data/uploads`; chunk và vector hợp đồng → Postgres; corpus pháp luật → Postgres (`legal_documents`, hierarchy, `legal_embeddings`, quan hệ) và cây Neo4j qua `IngestLegalDocument`.
- Đọc: vector search (Postgres, RRF ở `vector/rrf.py`) lấy seed; với câu hỏi về lao động còn tìm riêng trong Bộ luật Lao động 2019 và Nghị định 145/2020 (`RAG_LABOR_SCOPE`, role `labor_scope`) → mở rộng cây qua Neo4j và/hoặc ltree Postgres (`LEGAL_EXPAND_BACKEND`) → hydrate theo path (`legal_graph_rag.py`).
- Hiệu lực: `agents/effectivity.py` dùng `status_flag` 0..5 cùng `eff_from`/`eff_to` để quyết định có được trích dẫn theo ngày hợp đồng hay không.

Sơ đồ: [`diagrams/system-architecture.md`](diagrams/system-architecture.md), [`diagrams/module-dependencies.md`](diagrams/module-dependencies.md).

## Tích hợp ngoài

Gemini (cần `GEMINI_API_KEY`), Hugging Face (tải model embedding, tùy chọn `HF_TOKEN`), LangSmith (`LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, tùy chọn), cổng VBPL qua `scripts/crawl_vbpl/` (chỉ dùng lúc crawl, không phải runtime).

## Quyết định và đánh đổi

- Port/adapter ở `domain/ports` cho phép test use case bằng fake; đổi lại `agents/` vẫn lấy repository qua service-locator `retrieval/context.py` thay vì nhận qua constructor (chọn cách này để tránh import vòng và để script/evaluation dùng được mà không phải truyền tham số).
- Retrieval đa nguồn (Postgres + Neo4j) tăng độ phủ nhưng thêm hai hệ phụ thuộc runtime; Neo4j hoặc schema lỗi chỉ ghi cảnh báo lúc khởi động, nên API lên được dù thiếu dịch vụ, và lỗi lộ ra ở request đầu dùng đến nó.
- Bước xác định (`deterministic`) chạy trước LLM và có thể bỏ qua LLM cho điều khoản đã có red-flag (`skip_llm_clauses`) để giảm chi phí và tăng tính lặp lại.
