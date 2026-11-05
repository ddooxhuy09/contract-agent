# AGENTS.md — contract-agent (ContractLens)

Quy tắc cốt lõi cho coding agent.
## Kiến trúc trong 6 dòng
- Backend FastAPI (`app/`), frontend React/Vite (`frontend/`), Postgres+pgvector và Neo4j qua `docker-compose.yml`.
- Phân lớp: `api` → `application/use_cases` → `domain/ports` ← `infrastructure` (adapter). `AppContainer` (`app/infrastructure/container.py`) nối port với adapter.
- `app/agents/` chứa hai đồ thị LangGraph: phân tích hợp đồng (`workflow.py`) và hỏi đáp (`qa_agent.py`); `infrastructure/agents/pipelines.py` bọc chúng thành `AnalyzePipeline` / `QaPipeline`.
- Retrieval pháp luật: `infrastructure/retrieval/` (GraphRAG, rewrite, scope) + `infrastructure/vector/pg_search.py`.
- Nạp corpus pháp luật: `infrastructure/legal_corpus/` + `application/use_cases/legal_ingest.py` + `scripts/`.
- Đọc tiếp khi cần: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) → [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md) → [`docs/diagrams/`](docs/diagrams/).

## Tìm code
1. Biết tên symbol: Serena `find_symbol` / `find_referencing_symbols`. Chưa biết: xem `docs/CODEBASE_MAP.md` mục "Sửa gì ở đâu".
2. Call graph / ảnh hưởng liên module: CodeGraphContext, chỉ index `app/` (đã index; đừng index lại nếu không đổi cấu trúc).
3. Grep/Read chỉ cho config, SQL/Cypher, markdown. Không quét toàn repo; không đọc `.env`, `data/`, `evaluation_results/`.

## Ranh giới module
- `domain/` không import framework hay `infrastructure`. `application/` chỉ phụ thuộc port của `domain`.
- Route chỉ gọi use case qua `AppContainer`; không chứa SQL hay gọi LLM trực tiếp.
- Ngoại lệ có chủ đích: `agents/` lấy repository/search qua `infrastructure/retrieval/context.py` (không import `db.connection`, không viết SQL trong `agents/`); `infrastructure/agents/pipelines.py` import `agents/`. Đừng thêm import ngược khác. Xem `docs/REFACTOR_PLAN.md`.

## Quy tắc refactor
- Không đổi hành vi, request/response schema, `schema.sql`/`schema.cypher`, auth, streaming (SSE), retry, checkpointer.
- Xóa code chết chỉ sau khi `find_referencing_symbols` và grep toàn repo (kể cả `tests/`, `scripts/`, `evaluation/`) đều không có tham chiếu.
- Không thêm dependency, không đổi tên/di chuyển file chỉ vì thẩm mỹ. Nhỏ nhất đủ dùng (xem skill `ponytail`).

## Test
```bash
python -m pytest tests -q --ignore=tests/integration   # unit + evaluation fixtures
python -m pytest tests/integration -q                  # cần Postgres/Neo4j đang chạy
cd frontend && npm run lint && npm run build
```
- Baseline hiện tại: 188 passed, 1 skipped, 0 failed (không cần DB). Test luồng đồ thị dùng fixture `stub_deterministic_checks` (`tests/unit/conftest.py`); fake `evaluate_clause`/`retrieve_legal` phải khớp chữ ký thật (nhận `job_context`, `skip_topics`, `title`...).
- Không có CI (dự án chạy local). Trước khi commit chạy: `python -m ruff check app scripts evaluation --select F`, `pytest --ignore=tests/integration`, và `npm run lint` + `npm run build` trong `frontend/`.
- Đổi hành vi agent/retrieval phải có hoặc cập nhật test trong `tests/unit/`.

## Bảo mật
- Không đọc, in, commit `.env`, khóa, token. Chỉ ghi tên biến môi trường.
- `JWT_SECRET` phải khác mặc định (app từ chối khởi động). Các use case theo hợp đồng (analyze, chat, history, rewind) và `/chat/stream` kiểm tra quyền sở hữu qua `contracts.get_owned`.
- Lỗi trả client qua `_http_error` (`app/api/routes.py`), không trả `str(e)` của driver.

## Tài liệu
Đổi route, node đồ thị, biến môi trường hoặc cấu trúc thư mục thì cập nhật `README.md`, `docs/CODEBASE_MAP.md` và diagram liên quan trong cùng thay đổi. Không commit/push nếu người dùng chưa yêu cầu; không thêm dòng attribution Claude vào commit/PR/file.
