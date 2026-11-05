# Quy ước code

Rút ra từ mã hiện có; áp dụng cho mã mới. Quy tắc chung cho agent ở [`../AGENTS.md`](../AGENTS.md).

## Đặt tên và cấu trúc file
- Python: `snake_case` cho module/hàm, `PascalCase` cho class, hàm/biến nội bộ bắt đầu bằng `_`. Use case là class có `__init__` nhận port và `execute` (xem `application/use_cases/contracts.py`). Adapter Postgres đặt tên `Pg<Tên>Repository`.
- Mỗi port ở `domain/ports/`, adapter tương ứng ở `infrastructure/`. Đăng ký adapter trong `infrastructure/container.py`.
- Test đặt ở `tests/unit/test_<module>.py`, tên theo module được test.
- Frontend: component React ở `frontend/src/components/`, gọi API qua `frontend/src/api.js`.

## Cấu hình
- Mọi cấu hình đọc qua `get_settings()` (`core/settings.py`, pydantic-settings, nạp `.env`). Không đọc `os.environ` rải rác; thêm biến mới vào `Settings` và `.env.example`.

## Xử lý lỗi
- Lỗi nghiệp vụ dùng lớp trong `domain/errors.py` (`NotFoundError`, `AuthError`, `ConflictError`, `ValidationError`); route dịch sang HTTP.
- Lỗi không lường trước đi qua `_http_error` ở `api/routes.py`: không trả `str(e)` của driver; mất kết nối DB trả 503.
- Bước tùy chọn lúc khởi động (Neo4j, checkpointer, warmup embedding) bắt `Exception` và ghi `logger.warning`; bước bắt buộc (JWT secret) thì raise.
- Gọi LLM/mạng có thể lỗi tạm thời: thử lại ngay trong node (`_judge_clause_node`) hoặc ở pipeline (`_retry_on_dropped_connection`), không nuốt lỗi im lặng.

## Logging
- Dùng `from app.core.logging import logger` (logger tên `contractlens`). Không dùng `print` trong `app/` (hiện 0 chỗ). Ghi kèm `contract_id` khi có.
- Không log nội dung hợp đồng đầy đủ, token hay khóa; cắt ngắn chuỗi dài (xem `_judge_clause_node`).

## Validation
- Request/response khai báo bằng Pydantic ở `schemas/contract.py` hoặc cạnh route (`AuthRequest`, `ChatRequest`). Đầu ra LLM phải qua `parse_json_object` rồi ép sang model Pydantic, không tin JSON thô.
- Upload kiểm tra phần mở rộng và đọc được văn bản ngay trong `UploadContract.execute` (`application/use_cases/contracts.py`); tệp không đọc được bị từ chối (400), không lưu.

## Async và đồng thời
- Route và use case là `async`; việc đồng bộ nặng hoặc blocking (LLM, Postgres, embedding) chạy qua `asyncio.to_thread` (xem `workflow.py`).
- Fan-out song song dùng `Send` của LangGraph với giới hạn `_MAX_CONCURRENT_CLAUSE_CHECKS`; không tự tạo thread pool.
- SSE: `StreamingResponse` kèm header `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Kiểm tra quyền **trước** khi mở stream.
- Trên Windows `app/main.py` đặt `WindowsSelectorEventLoopPolicy` ngay đầu file (lý do chưa được ghi trong mã; nhiều khả năng liên quan psycopg async). Giữ nguyên và giữ trước các import khác.

## Test
- `pytest` + `pytest-asyncio`. Test unit không được cần Postgres/Neo4j/Gemini: fake port hoặc monkeypatch hàm theo module sử dụng (ví dụ `monkeypatch.setattr(wf, "parse_contract", ...)`).
- Fake phải khớp chữ ký thật (kinh nghiệm: `retrieve_legal` đã thêm tham số `title`, fake cũ trong `test_qa_memory.py` vỡ).
- Test cần dịch vụ ngoài đặt ở `tests/integration/`.

## Bảo mật
- Không commit `.env`; chỉ `.env.example` với tên biến. JWT bắt buộc secret khác mặc định.
- Mật khẩu băm bcrypt (`BcryptPasswordHasher`); token qua `JwtTokenService`.
- Giá trị SQL luôn qua tham số `%s` của driver. Chỉ tên bảng/cột được ghép bằng f-string (`db/hierarchy_chain.py`, `db/legal_repository.py`); phải là hằng nội bộ, không bao giờ từ input người dùng.
- Mọi truy cập dữ liệu hợp đồng phải gắn `user_id` (`contracts.get_owned`).

## Driver Postgres
- Dùng **hai driver có chủ đích**: `psycopg2` cho repository và script (`db/connection.py`); `psycopg` v3 + `psycopg_pool` cho LangGraph checkpoint/memory (`agents/checkpointer.py`, `agents/memory.py`) và retry trong `pipelines.py`. Không viết SQL mới trong `agents/` hay `api/`; thêm method vào repository tương ứng (`PgLegalDocumentRepository`, `PgLegalChunkRepository`, ...) và lấy qua `retrieval/context.py` hoặc `AppContainer`.
