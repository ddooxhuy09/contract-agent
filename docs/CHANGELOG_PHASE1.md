# CHANGELOG — Phase 1 "Stop the bleeding" (P0)

*Ngày: 2026-08-02. Tasks: 1 (Chat/History bugs + tests) và 2 (Secrets, CORS, JWT guard).*

## Task 1 — Sửa bug Chat/History adapter + khóa bằng test

### File thay đổi

| File | Thay đổi |
|------|----------|
| `app/infrastructure/agents/pipelines.py` | `answer()` gọi `answer_question(question, contract_id, provider)` đúng thứ tự signature (W-001); `history()` lặp trực tiếp trên list `hist` thay vì `hist.messages` (W-002) |
| `tests/unit/test_pipelines.py` *(mới)* | 2 test unit mock `answer_question` / `get_conversation_history`, kiểm tra thứ tự đối số và định dạng lịch sử |

### Lý do thay đổi
- W-001: gọi đảo tham số khiến `POST /api/v1/chat` luôn rơi vào nhánh refusal; tính năng chính của sản phẩm hỏng hoàn toàn.
- W-002: truy cập `.messages` trên một `list` làm `GET /api/v1/chat/{id}/history` trả 500.
- W-058 (phần pipelines): hai bug trên tồn tại vì không có test phủ adapter; cần regression test.

### Ảnh hưởng
- Chat và history trả đúng kết quả theo câu hỏi/contract.
- Bộ test tăng 29 → 31 (toàn bộ pass); 2 test fail khi tái diễn W-001/W-002 (đã kiểm chứng bằng revert tạm thời).

## Task 2 — Secrets, CORS, JWT startup guard

### File thay đổi

| File | Thay đổi |
|------|----------|
| `app/core/settings.py` | Thêm setting `cors_origins` (allowlist, mặc định local Vite dev) |
| `app/main.py` | CORS: `allow_origins` từ `CORS_ORIGINS`, `allow_credentials=False` (W-045); thêm `_validate_security_settings()` từ chối khởi động khi `JWT_SECRET` trống/`change-me-in-production` (W-050) |
| `.env` | Xóa leftover `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `JWT_SECRET_KEY` và các khóa chết `VECTOR_STORE_DIR`, `LEGAL_KB_BATCH_SIZE`, `LEGAL_KB_ACTIVE_ONLY`; thêm `NEO4J_URI/USER/PASSWORD`, `CORS_ORIGINS` (W-049 phần dọn dẹp, W-068) |
| `.env.example` | Thêm `CORS_ORIGINS`; giữ comment yêu cầu đổi `JWT_SECRET` (W-068, W-050) |
| `scripts/crawl_vbpl/common.py` | Bỏ cookie session hardcode; `VBPL_COOKIE` đọc từ env, fail-fast trong `base_headers()` khi thiếu (W-054) |
| `tests/integration/test_api.py` | Set `JWT_SECRET`/`GEMINI_API_KEY` test + `get_settings.cache_clear()` trước khi import `app.main` để lifespan không abort khi chạy không có `.env` |

### Lý do thay đổi
- W-045: `*` + credentials là tổ hợp CORS không hợp lệ/không an toàn.
- W-049: `.env` chứa secret thật + leftover `SUPABASE_SECRET_KEY` (service role) và `JWT_SECRET_KEY` chết.
- W-050: secret mặc định yếu cho phép forge token.
- W-054: cookie session cá nhân hardcode trong repo.
- W-068: `.env`/`.env.example` lệch khóa cấu hình so với settings.

### Ảnh hưởng
- API chỉ chấp nhận origin trong allowlist; không còn credentials CORS.
- App từ chối khởi động khi JWT secret yếu/trống (thay đổi hành vi startup — môi trường dùng `.env.example` nguyên trạng sẽ không boot được cho tới khi set `JWT_SECRET`).
- Crawler vbpl.vn yêu cầu `VBPL_COOKIE` env — chạy không có sẽ lỗi rõ ràng thay vì dùng cookie stale.
- Toàn bộ test (31) pass.

## Rủi ro còn lại

1. **Rotate thủ công (W-049, ⚠️ Partially):** `GEMINI_API_KEY` và `JWT_SECRET` hiện trong `.env` vẫn là giá trị cũ. Người dùng phải sinh key Gemini mới và đổi JWT secret, đồng thời **revoke key cũ** nếu đã từng lộ. Chưa có pre-commit chặn secret.
2. **Smoke E2E (Phase 1 checklist):** `POST /chat` / `GET /chat/{id}/history` trên stack thật chưa chạy (Docker Postgres/Neo4j tắt trong môi trường hiện tại). Adapter được bảo vệ bằng unit test; cần chạy lại khi có `docker compose up` + Gemini key hợp lệ.
3. **JWT guard làm thay đổi hành vi boot:** bất kỳ môi trường nào dùng `JWT_SECRET=change-me-in-production` sẽ không khởi động được — đúng ý đồ (W-050) nhưng cần thông báo khi onboard.
4. **CORS**: origin sản xuất (frontend deployed) phải được bổ sung vào `CORS_ORIGINS` nếu khác origin API.
