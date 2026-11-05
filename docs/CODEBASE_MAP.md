# Bản đồ mã nguồn

Tra cứu nhanh "sửa gì ở đâu". Tên symbol lấy từ mã hiện tại; tra chi tiết bằng Serena `find_symbol`, đừng đọc cả file. Hiểu hệ thống: [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Thư mục gốc

| Đường dẫn | Vai trò |
|---|---|
| `app/` | Backend FastAPI |
| `frontend/` | React/Vite (`src/App.jsx`, `api.js`, `AuthContext.jsx`, `components/`, `lib/`, `content/`) |
| `scripts/` | Nạp corpus, backfill, restore DB, audit, crawl (`crawl_vbpl/`) |
| `tests/` | `unit/`, `integration/test_api.py`, `evaluation/`, `fixtures/` |
| `evaluation/` | Mã benchmark (đề bài ở `benchmark/v04/`); xem `evaluation/README.md` |
| `evaluation_results/`, `data/` | Kết quả và dữ liệu cục bộ; không đọc/index |
| `schema.sql`, `schema.cypher` | Schema Postgres, Neo4j (nạp lúc khởi động) |
| `docker-compose.yml`, `Dockerfile`, `docker/` | Triển khai (postgres, neo4j, api, frontend) |

## `app/` theo lớp

| Gói | Nội dung chính |
|---|---|
| `main.py` | `lifespan` (khởi tạo), `health`, CORS, mount `frontend/dist` |
| `api/` | `routes.py` (12 route dưới `/api/v1`), `deps.py` (`get_current_user_id`, `get_container_dep`) |
| `application/use_cases/` | `auth.py` (`RegisterUser`, `LoginUser`), `contracts.py` (`UploadContract`, `AnalyzeContract`, `ResumeAnalysisReview`, `ListContracts`, `ChatWithContract`, `GetChatHistory`, `GetChatStates`, `RewindChat`), `legal_ingest.py` (`IngestLegalDocument`) |
| `domain/` | `entities/`, `ports/repositories.py`, `ports/services.py`, `errors.py` |
| `schemas/contract.py` | Pydantic: request/response, `ContractAnalysis`, `Clause`, `RiskItem`, `LegalCitation` |
| `core/` | `settings.py` (`Settings`, `get_settings`), `logging.py` (`logger`), `prompts.py`, `dates.py` (`parse_as_of`) |
| `document/` | `parser.py` (`parse_document`), `chunker.py` (`chunk_by_clause`), `file_handler.py` |
| `vectorstore/retriever.py` | `retrieve_contract`, `retrieve_legal`, `format_legal_context` (cầu nối agents → search) |
| `agents/` | Xem bảng dưới |
| `infrastructure/` | Adapter; xem bảng dưới |

### `agents/`

| File | Việc |
|---|---|
| `workflow.py` | Đồ thị phân tích: `run_analysis_workflow`, `run_analysis_workflow_review`, `resume_analysis_review`; node `_supervisor_node`, `_extract_node`, `_deterministic_node`, `_judge_clause_node`, `_review_node` |
| `qa_agent.py` | Đồ thị hỏi đáp: `answer_question`, `stream_answer_events`, `get_state_history`, `rewind_state`, `get_conversation_history` |
| `clause_parser.py` | `parse_contract` (LLM trích xuất điều khoản) |
| `risk_flagger.py` | `evaluate_clause` (LLM + RAG cho một điều khoản) |
| `labor_red_flags.py` | Pattern xác định cho điều khoản trái luật lao động: `check_labor_red_flags`, `skip_llm_clause_numbers` |
| `labor_completeness.py` | Nội dung bắt buộc Điều 21 BLLĐ: `check_labor_completeness` |
| `preamble_citations.py` | Kiểm tra phần "Căn cứ…": `check_preamble_citations` |
| `legal_citations.py` | Chuẩn hóa/ground trích dẫn: `resolve_legal_citations`, `ground_citations` |
| `effectivity.py` | `evaluate_document_effectivity`, `citation_status_for_labor` |
| `labor_code_resolver.py` | Tìm BLLĐ có hiệu lực theo ngày và lấy chunk Điều N, qua `get_legal_docs()` / `get_legal_chunks()` |
| `llm_client.py` | `get_providers`, `resolve_provider`, `get_chat_model`, `chat_completion` (backoff 429) |
| `checkpointer.py`, `memory.py` | Checkpoint LangGraph và bộ nhớ hỏi đáp dài hạn (Postgres) |
| `json_parsing.py` | `parse_json_object` cho đầu ra LLM |

### `infrastructure/`

| Gói | Việc |
|---|---|
| `container.py` | `AppContainer`, `build_container` |
| `db/` | `connection.py`, `*_repository.py` (Pg adapter), `hierarchy_chain.py`, `schema_loader.py` |
| `vector/` | `pg_search.py` (`PgContractVectorSearch`, `PgLegalVectorSearch`), `rrf.py` |
| `retrieval/` | `legal_graph_rag.py` (`LegalGraphRag`), `query_rewrite.py`, `scope_match.py`, `normative_rank.py`, `context.py` (`bind_retrieval`, `get_legal_docs`, `get_legal_chunks`) |
| `neo4j/graph_repository.py` | `Neo4jGraphRepository` |
| `legal_corpus/` | Parse folder crawl → artifact ingest: `assemble.load_document_folder`, `muc_luc_paths`, `van_ban_chunker`, `thuoc_tinh_mapper`, `internal_refs`, `clause_amendments`, `luoc_do_flatten`, `appendix`, `checkpoint`, `discover`, `effectivity` (nhận diện tiêu đề "Hiệu lực thi hành", khác với `agents/effectivity.py`) |
| `agents/pipelines.py` | `LangGraphAnalyzePipeline`, `LangGraphQaPipeline` (bọc đồ thị, retry khi mất kết nối DB) |
| `embeddings/`, `llm/`, `auth/`, `storage/` | `HuggingFaceEmbedder`, `GeminiChatModel`, `JwtTokenService`/`BcryptPasswordHasher`, `LocalObjectStorage` |

## Ánh xạ API → use case → adapter

| Route | Use case | Phụ thuộc chính |
|---|---|---|
| `POST /auth/register`, `/auth/login` | `RegisterUser`, `LoginUser` | `users`, `password_hasher`, `tokens` |
| `POST /upload` | `UploadContract` | `storage`, `embedder`, `contracts`, `contract_chunks` |
| `POST /analyze`, `/analyze/resume` | `AnalyzeContract`, `ResumeAnalysisReview` | `analyze_pipeline` → `agents/workflow.py` |
| `GET /contracts` | `ListContracts` | `contracts` |
| `POST /chat`, `/chat/stream` | `ChatWithContract`; stream gọi `qa_pipeline.stream` | `qa_pipeline` → `agents/qa_agent.py` |
| `GET /chat/{id}/history`, `/states`; `POST /chat/{id}/rewind` | `GetChatHistory`, `GetChatStates`, `RewindChat` | `qa_pipeline` |
| `GET /models` | gọi thẳng `get_providers` | `agents/llm_client.py` |
| `GET /health` (ngoài prefix) | — | `app/main.py` |

## Sửa gì ở đâu

| Việc | Nơi sửa | Test liên quan |
|---|---|---|
| Thêm/đổi route hoặc mã lỗi HTTP | `api/routes.py`, `schemas/contract.py` | `tests/integration/test_api.py` |
| Đổi luồng phân tích (node, retry, review) | `agents/workflow.py` | `test_analysis_retry.py`, `test_analysis_review.py` |
| Thêm red-flag lao động | `agents/labor_red_flags.py` (`_FLAGS`) | `test_labor_red_flags.py` |
| Đổi cách kiểm tra hiệu lực/trích dẫn | `agents/effectivity.py`, `legal_citations.py`, `preamble_citations.py` | `test_effectivity.py`, `test_legal_citations.py`, `test_preamble_citations.py` |
| Đổi truy xuất điều luật | `infrastructure/retrieval/`, `vector/pg_search.py` | `test_graphrag.py`, `test_qa_query_rewrite.py`, `test_scope_match.py` |
| Đổi luồng hỏi đáp | `agents/qa_agent.py`, `memory.py` | `test_qa_memory.py`, `test_qa_self_correct.py` |
| Đổi parse/chunk hợp đồng | `document/` | `test_parser.py`, `test_chunker.py`, `test_upload.py` |
| Đổi nạp corpus pháp luật | `infrastructure/legal_corpus/`, `application/use_cases/legal_ingest.py`, `scripts/ingest_*.py` | `test_legal_corpus_parser.py`, `test_legal_ingest_unit.py`, `test_ingest_checkpoint.py`, `test_clause_amendments.py` |
| Đổi schema DB | `schema.sql`/`schema.cypher` (cần migration thủ công, ngoài phạm vi refactor) | — |
| Thêm biến môi trường | `core/settings.py`, `.env.example`, README | — |
| Prompt LLM | `core/prompts.py` (xem `docs/PROMPT_ARCHITECTURE.md`) | — |
