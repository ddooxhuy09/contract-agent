# Báo cáo tiến độ: ContractLens — Hệ thống AI rà soát hợp đồng tiếng Việt

*Cập nhật lần cuối dựa trên soát xét toàn bộ source ngày hiện tại. Test suite: 11/11 pass.*

---

## 1. Tổng quan kiến trúc hiện tại

```
app/
  main.py              # Khởi tạo FastAPI, CORS, mount static frontend, quản lý vòng đời checkpointer
  api/routes.py         # Toàn bộ endpoint REST (/api/v1/...)
  core/                 # config, database (Postgres/Supabase), auth (Supabase JWT), prompts (tiếng Anh)
  schemas/contract.py    # Pydantic schema dùng chung cho toàn bộ API
  agents/               # Các "agent" chuyên biệt hóa (xem mục 2)
  document/              # parser (docx/pdf/ảnh+OCR), chunker theo Điều/Khoản, file_handler
  vectorstore/           # FAISS (qua LangChain) + embedding tiếng Việt
  knowledge_base/loader.py  # Nạp dữ liệu luật từ Supabase vào FAISS
  services/contract_service.py  # Tầng orchestrator: upload/analyze/chat/list, ownership check
scripts/load_legal_kb.py  # Script vận hành nạp lại kho luật
tests/                   # 11 test (unit + integration), pass 100%
frontend/                # React + Vite + Tailwind, Supabase Auth
```

**Ngăn xếp công nghệ chính:** FastAPI · LangChain · LangGraph · Google Gemini 2.5 Flash · FAISS · PostgreSQL (Supabase) · React.

---

## 2. Kiến trúc Multi-Agent đã triển khai

| Agent | File | Vai trò |
|---|---|---|
| **Extractor** | `agents/clause_parser.py` | Rule-based (regex), trích xuất bên tham gia/ngày tháng/tiền/điều khoản — không dùng LLM |
| **Judge** | `agents/risk_flagger.py` (`evaluate_clause`) | Với **từng điều khoản riêng**: retrieve luật liên quan (RAG) → đánh giá vi phạm bằng Gemini |
| **QA Agent** | `agents/qa_agent.py` | LangGraph `StateGraph`: retrieve → route (generate/refusal) → generate, có memory persistent |
| **Orchestrator** | `agents/workflow.py` | LangGraph `StateGraph` với `Send` fan-out — chạy Judge song song cho tất cả điều khoản (giới hạn 4 luồng đồng thời qua `max_concurrency`) |

---

## 3. Đã hoàn thành (Complete)

### 3.1 Pipeline phân tích hợp đồng
- ✅ Trích xuất thông tin cơ bản bằng rule-based (loại HĐ, các bên, ngày tháng, giá trị, thanh toán)
- ✅ Tách điều khoản theo "Điều X" (chunker riêng cho từng điều khoản)
- ✅ RAG retrieval theo **từng điều khoản cụ thể** (không dùng 1 query chung cho cả hợp đồng)
- ✅ Đánh giá tuân thủ 3 mức: `critical`/`warning`/`ok`, kèm căn cứ pháp lý + khuyến nghị sửa đổi
- ✅ **Refusal cứng**: nếu không tìm thấy luật liên quan đủ ngưỡng similarity → trả `insufficient_evidence`, không để LLM tự bịa
- ✅ Chạy song song có kiểm soát qua LangGraph (không dùng `asyncio.gather` tự viết tay nữa)
- ✅ **Cache kết quả phân tích** vào DB (`analysis`/`risks` JSONB) — mở lại hợp đồng cũ không tốn LLM call, có cờ `force` để chạy lại

### 3.2 Chatbot hỏi đáp
- ✅ RAG kết hợp cả nội dung hợp đồng đang mở lẫn kho luật chung
- ✅ Refusal cứng khi cả 2 nguồn đều rỗng
- ✅ Chủ động hỏi lại (`needs_clarification`) khi câu hỏi thiếu thông tin
- ✅ **Validate citation**: loại bỏ số điều khoản LLM tự trích dẫn nếu không thực sự có trong kết quả retrieval
- ✅ **Chat memory persistent xuyên phiên** qua LangGraph `AsyncPostgresSaver` (Postgres checkpointer) — dùng `trim_messages` làm eviction policy (kiểu `TokenWindowChatMemory`), không cần bảng SQL tự viết tay
- ✅ Sửa bug retrieval: câu hỏi chung chung ("hợp đồng này có vấn đề gì không") từng bị chặn nhầm do áp ngưỡng similarity quá chặt cho phạm vi đã lọc sẵn theo `contract_id`

### 3.3 OCR & đa định dạng đầu vào
- ✅ Hỗ trợ `.docx`/`.doc`/`.pdf`
- ✅ Hỗ trợ ảnh chụp hợp đồng (`.png`/`.jpg`/`.jpeg`) qua **Gemini Vision OCR** — verify bằng ảnh test tiếng Việt có dấu, đọc chính xác 100%
- ✅ Frontend đồng bộ định dạng cho phép với backend

### 3.4 Quản lý workspace
- ✅ Danh sách hợp đồng đã upload (`GET /api/v1/contracts`)
- ✅ Mở lại hợp đồng cũ xem kết quả đã lưu, không cần phân tích lại
- ✅ Frontend: màn hình danh sách → chọn cũ hoặc upload mới → xem kết quả

### 3.5 Bảo mật
- ✅ Supabase Auth (email/password) + JWT verify ở backend
- ✅ **Row Level Security (RLS) đầy đủ** trên toàn bộ bảng expose qua Supabase API (`uploaded_contracts`, `scraped_contracts`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) — phát hiện và vá 2 đợt lỗ hổng critical trong quá trình phát triển
- ✅ Xử lý input không hợp lệ (contract_id sai định dạng UUID) không còn rò rỉ lỗi SQL thô (500) → trả 404 sạch

### 3.6 Chất lượng kỹ thuật
- ✅ Migrate toàn bộ sang **LangChain + LangGraph OOTB** thay vì tự viết tay (vectorstore, embeddings, LLM client, orchestration, chat memory) — giảm code tự bảo trì, dễ audit hơn
- ✅ Toàn bộ prompt viết bằng tiếng Anh (chuẩn hiệu suất mô hình tốt hơn), ép LLM trả lời nội dung bằng tiếng Việt
- ✅ Test suite: 11/11 pass (unit + integration), đã sửa 2 nhóm bug tồn đọng (parser exception handling, auth-before-validation trong test)
- ✅ Toàn bộ đã verify bằng test **thật** (không mock) trên Supabase production ở từng bước quan trọng, không chỉ dựa vào mock

---

## 4. Chưa hoàn thành / Cần cải thiện thêm

### 4.1 Ưu tiên cao (giá trị lớn cho đồ án)
| Việc | Ghi chú |
|---|---|
| **Tính toán rủi ro/bồi thường** (VD: "chấm dứt HĐ tháng 3 thì bồi thường bao nhiêu") | Hiện chatbot **chủ động tránh** để LLM tự tính toán (đúng nguyên tắc chống hallucination), nhưng chưa có tool/agent tính toán thay thế — cần thiết kế 1 "Calculator Agent" tách biệt |
| **Đánh giá định lượng (benchmark)** | Chưa có bộ test case với nhãn rủi ro chuẩn (do luật sư/giảng viên gán) để đo accuracy — cần cho phần "kết quả thực nghiệm" của báo cáo tốt nghiệp |
| **Export báo cáo** (PDF/DOCX) | Đã cân nhắc nhưng **chủ động hoãn** theo quyết định của bạn để tập trung nguồn lực vào OCR trước |

### 4.2 Ưu tiên trung bình (trải nghiệm người dùng)
| Việc | Ghi chú |
|---|---|
| Đăng nhập OAuth (Google/GitHub) | Hiện chỉ có email/password |
| Quên mật khẩu | Chưa có luồng reset password |
| Hồ sơ cá nhân (nghề nghiệp → ngữ cảnh cho AI) | Chưa có trang profile |
| Đổi tên / gắn thẻ / bookmark / xóa hợp đồng | Danh sách hợp đồng hiện chỉ xem + mở, chưa thao tác quản lý |
| Feedback 👍👎 cho câu trả lời AI | Chưa có, hữu ích để tối ưu prompt sau này |

### 4.3 Ưu tiên thấp (polish)
- Dark/Light mode
- Onboarding tour cho người dùng mới
- Chia sẻ link báo cáo tự hủy sau N ngày
- Chuyển `@app.on_event` (deprecated) sang FastAPI `lifespan` context manager — hiện vẫn hoạt động bình thường nhưng sẽ bị loại bỏ ở version FastAPI tương lai

### 4.4 Nợ kỹ thuật nhỏ đã biết
- `helpers/text_normalizer.py` hiện không được import ở đâu cả (dead code, an toàn để xóa hoặc dùng sau)
- Có 1 bộ bảng khác trên Supabase (`contracts`, `contract_chunks`, `contract_types`, `scraped_contracts`) không được backend Python nào sử dụng — chưa rõ mục đích ban đầu, cần xác nhận có phải bỏ hẳn hay dự định dùng

---

## 5. Đề xuất thứ tự làm tiếp theo

1. **Benchmark định lượng** — quan trọng nhất cho báo cáo tốt nghiệp, chứng minh được độ chính xác bằng số liệu thay vì chỉ demo định tính
2. **Calculator Agent** cho tính toán bồi thường/phạt — điểm nhấn kỹ thuật thể hiện tư duy "không để LLM làm việc nó làm không tốt"
3. Các tính năng UX còn lại tùy thời gian còn lại của đồ án

---

*Ghi chú: Báo cáo này phản ánh đúng trạng thái source tại thời điểm viết — đã đọc lại toàn bộ `app/`, `frontend/src/`, `tests/`, chạy lại test suite (11/11 pass) và kiểm tra `git log` để xác nhận, không suy diễn từ lịch sử hội thoại.*
