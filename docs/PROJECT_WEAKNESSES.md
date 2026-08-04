# PROJECT WEAKNESSES — Technical Audit ContractLens

*Ngày audit: 2026-08-02. Phạm vi: toàn bộ repository `D:\contract-agent` (backend `app/`, frontend `frontend/`, scripts, tests, `schema.sql`, `schema.cypher`, `docker-compose.yml`, config, docs).*

*Nguyên tắc: mọi vấn đề đều có bằng chứng trong source code. Không suy đoán.*

---

# Verification Log (re-check against source)

*Ngày xác minh lại: 2026-08-02 (sau cleanup config/embeddings). Phạm vi: đối chiếu từng mục với source hiện tại. Không suy đoán.*

## Deployment Log (Phase 1 — 2026-08-02)

Đối chiếu sau khi triển khai Phase 1 (Task 1 + Task 2) theo `docs/IMPLEMENTATION_PLAN.md`:

| ID | Trạng thái triển khai | Ghi chú |
|----|-----------------------|---------|
| **W-001** | ✅ Fixed | `pipelines.py:18` đổi về `answer_question(question, contract_id, provider)` |
| **W-002** | ✅ Fixed | `pipelines.py:28` lặp trực tiếp trên list `hist` |
| **W-045** | ✅ Fixed | CORS allowlist `CORS_ORIGINS` + `allow_credentials=False` |
| **W-049** | ⚠️ Partially Fixed | Đã xóa leftover `SUPABASE_*`/`JWT_SECRET_KEY`/khóa chết; **rotate GEMINI_API_KEY/JWT_SECRET là việc thủ công của người dùng** |
| **W-050** | ✅ Fixed | Startup guard từ chối `JWT_SECRET` mặc định/trống |
| **W-054** | ✅ Fixed | Bỏ cookie mặc định; `VBPL_COOKIE` bắt buộc từ env |
| **W-058** | ⚠️ Partially Fixed | Thêm `tests/unit/test_pipelines.py`; phủ adapter AI/chat còn lại ở Task 15 |
| **W-068** | ✅ Fixed | Đồng bộ `.env.example`; dọn `.env` |

*Ghi chú: smoke E2E (`POST /chat` / `GET /chat/{id}/history` trên stack thật) chưa chạy được trong môi trường này do Docker Postgres/Neo4j không bật; adapter được bảo vệ bằng unit test.*

| Status | Count | Ý nghĩa |
|--------|------:|---------|
| ✅ Confirmed | 67 | Vấn đề còn tồn tại đúng như mô tả |
| ⚠️ Partially Correct | 2 | Có tồn tại nhưng mô tả chưa đủ chính xác (W-020, W-063) |
| ❌ Invalid | 0 | — |
| 🔄 Already Fixed | 0 | — |

**Ghi chú xác minh:**
- W-001 / W-002: vẫn đúng tại `app/infrastructure/agents/pipelines.py:18` và `:28`.
- W-007: thêm `assert` tại `routes.py:150` (history) — audit gốc chỉ ghi 101, 132.
- W-020: Partially — contract vector retrieval không hydrate parent Điều; nhưng risk path có `get_text_by_clause` ghép lại (`risk_flagger.py:21`, `contract_chunk_repository.py`).
- W-049: xác nhận `.env` còn `GEMINI_API_KEY` + leftover `SUPABASE_*` / `JWT_SECRET_KEY` (giá trị không in lại trong doc).
- W-058: 9 file `test_*.py`; không có test cho `pipelines.py`.
- W-063: Partially — hầu hết unpinned; chỉ `bcrypt<4.1` có ràng buộc phiên bản.



---

# 1. Architecture

---

### W-001 Bug đảo thứ tự đối số trong adapter QA khiến tính năng Chat hỏng hoàn toàn

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 1, 2026-08-02)

**Mức độ:** Critical

**Loại:** Backend

**File liên quan:**
- `app/infrastructure/agents/pipelines.py:18`
- `app/agents/qa_agent.py:170`

**Bằng chứng:**
`pipelines.py`:
```python
async def answer(self, contract_id: str, question: str, provider: str = DEFAULT_PROVIDER) -> dict[str, Any]:
    result = await answer_question(contract_id, question, provider)
```
Trong khi định nghĩa hàm trong `qa_agent.py`:
```python
async def answer_question(question: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> ChatResponse:
```
Gọi với thứ tự `(contract_id, question, provider)` nhưng signature là `(question, contract_id, provider)` → `question` nhận giá trị contract_id (UUID), `contract_id` nhận giá trị câu hỏi.

**Tại sao đây là vấn đề:** Tham số bị tráo hoàn toàn. Kết quả: `_retrieve_node` (`qa_agent.py:58-73`) embed câu hỏi = UUID, rồi `retrieve_contract(query=UUID, contract_id=câu hỏi)` → không khớp bất kỳ contract nào → luôn rơi vào nhánh refusal. `thread_id` lưu bằng chuỗi câu hỏi thay vì contract_id → memory sai chỗ. Bug xuất hiện từ commit refactor `4b8a1f1` và không bị test nào phát hiện.

**Ảnh hưởng:** `POST /api/v1/chat` luôn trả "Không tìm thấy thông tin liên quan..." bất kể câu hỏi; chức năng chat (tính năng chính của đồ án) hỏng hoàn toàn.

**Cách khắc phục:** Hoán đổi thứ tự đối số về đúng signature `answer_question(question, contract_id, provider)`. Thêm unit test cho `LangGraphQaPipeline.answer` với mock.

**Độ khó:** Easy

**Ưu tiên:** P0

---

### W-002 Bug truy cập `.messages` trên một list khiến endpoint History chat trả 500

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 1, 2026-08-02)

**Mức độ:** Critical

**Loại:** Backend

**File liên quan:**
- `app/infrastructure/agents/pipelines.py:28`
- `app/agents/qa_agent.py:184-208`

**Bằng chứng:**
`pipelines.py`:
```python
async def history(self, contract_id: str) -> list[dict[str, Any]]:
    hist = await get_conversation_history(contract_id)
    return [m.model_dump() for m in hist.messages]
```
Nhưng `get_conversation_history` (`qa_agent.py`) `return items` với `items: List[ChatHistoryItem]` — một list, không có thuộc tính `.messages` → `AttributeError: 'list' object has no attribute 'messages'`.

**Tại sao đây là vấn đề:** Khớp sai kiểu dữ liệu trả về giữa adapter và hàm nền. Không có test nào chạy luồng này.

**Ảnh hưởng:** `GET /api/v1/chat/{contract_id}/history` luôn trả 500; frontend `ChatTab.jsx` không tải được lịch sử.

**Cách khắc phục:** Đổi thành `return [m.model_dump() for m in hist]`.

**Độ khó:** Easy

**Ưu tiên:** P0

---

### W-003 Vi phạm phân tầng Clean Architecture: tầng agents import trực tiếp infrastructure

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Architecture

**File liên quan:**
- `app/agents/risk_flagger.py:7-9`
- `app/agents/qa_agent.py:14`
- `app/vectorstore/retriever.py:6`
- `app/infrastructure/retrieval/context.py`

**Bằng chứng:**
```python
# risk_flagger.py
from app.infrastructure.retrieval.context import get_contract_chunks, get_graph_rag
from app.vectorstore.retriever import format_legal_context, retrieve_legal
# qa_agent.py
from app.vectorstore.retriever import retrieve_contract, retrieve_legal
# retriever.py
from app.infrastructure.retrieval.context import get_contract_search, get_graph_rag, get_legal_search
```
`infrastructure/retrieval/context.py` là module global-state (`bind_retrieval`) được main.py gọi lúc startup (`main.py:36-42`) để né circular import.

**Tại sao đây là vấn đề:** Tầng orchestration (agents) không đi qua ports/container mà đọc global singleton; khiến thứ tự khởi tạo phải chính xác, khó test, khó thay thế adapter. `vectorstore/` thực chất là facade mỏng đè lên `infrastructure/` gây nhầm lẫn tầng.

**Ảnh hưởng:** Khó bảo trì, khó viết test đơn lập, coupling ngầm.

**Cách khắc phục:** Inject `LegalGraphRag` + các search service vào `AppContainer` rồi truyền vào agents qua constructor; xóa module global `context.py`.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-004 Hai entry point LLM trùng lặp; `container.chat_model` là dead code

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Architecture

**File liên quan:**
- `app/infrastructure/llm/gemini_chat.py` (toàn bộ)
- `app/infrastructure/container.py:12,40,54,66`
- `app/agents/llm_client.py`
- `app/domain/ports/services.py:12-15`

**Bằng chứng:** `container.py:66` khởi tạo `chat_model=GeminiChatModel()`. Grep toàn bộ `app/` cho thấy `container.chat_model` không được gọi ở bất kỳ đâu; mọi lời gọi LLM đều qua `app.agents.llm_client.get_chat_model()` (`clause_parser.py:8`, `risk_flagger.py:5`, `qa_agent.py:10`, `parser.py:39`).

**Tại sao đây là vấn đề:** Hai class cùng nhiệm vụ (bọc `ChatGoogleGenerativeAI`), một cái chết. Protocol `ChatModel` và adapter `GeminiChatModel` tạo ảo tưởng có DI nhưng thực tế tầng agents bypass container.

**Ảnh hưởng:** Thừa code bảo trì, gây hiểu nhầm kiến trúc.

**Cách khắc phục:** Xóa `GeminiChatModel`, `ChatModel` protocol, field `chat_model` khỏi container; thống nhất duy nhất `agents/llm_client.py` hoặc chuyển nó xuống infrastructure.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-005 Dead code: `document/file_handler.py` không được import ở đâu

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Architecture

**File liên quan:**
- `app/document/file_handler.py` (toàn bộ)

**Bằng chứng:** Grep toàn bộ `app/` không tìm thấy import nào của `file_handler`, `validate_file`, `save_upload` (file). Logic upload thực tế nằm ở `app/application/use_cases/contracts.py:26-84` + `app/infrastructure/storage/local_storage.py`.

**Tại sao đây là vấn đề:** Module chết chứa logic validate mở rộng, dễ khiến dev tưởng nó đang được dùng và sửa nhầm nơi.

**Ảnh hưởng:** Bảo trì, technical debt nhỏ.

**Cách khắc phục:** Xóa file hoặc đánh dấu deprecated.

**Độ khó:** Easy

**Ưu tiên:** P3

---

### W-006 Abstraction `provider` là no-op xuyên tầng

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Architecture

**File liên quan:**
- `app/agents/llm_client.py:10-18`
- `app/api/routes.py:6,31,38`
- `app/application/use_cases/contracts.py:98,117,153`
- `app/domain/ports/services.py:66,71`
- `frontend/src/components/UploadScreen.jsx:155-174`

**Bằng chứng:** `get_providers()` chỉ trả về đúng 1 provider `"gemini"`. `PROVIDERS` cố định. Tham số `provider` được truyền qua routes → use case → workflow → `evaluate_clause` nhưng `get_chat_model(provider)` bỏ qua tham số này (`llm_client.py:21-34`).

**Tại sao đây là vấn đề:** Abstraction rỗng, tham số vô tác dụng xuyên 5 tầng, gây phức tạp giả tạo.

**Ảnh hưởng:** Bảo trì; UX (dropdown model chỉ 1 lựa chọn vô nghĩa).

**Cách khắc phục:** Bỏ hẳn tầng provider, hoặc triển khai thật (≥2 provider) nếu cần.

**Độ khó:** Easy

**Ưu tiên:** P3

---

### W-007 Dùng `assert` để điều khiển luồng trong routes

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** API

**File liên quan:**
- `app/api/routes.py:101,132,150`

**Bằng chứng:**
```python
assert container.analyze_pipeline is not None
```
`assert` bị vô hiệu khi chạy `python -O` (optimized mode), khiến guard này biến mất.

**Tại sao đây là vấn đề:** `assert` dành cho invariant lập trình, không dành cho validation runtime. Nếu pipeline chưa được khởi tạo, endpoint sẽ chuyển sang nhánh `except Exception` trả 500 với message sai.

**Ảnh hưởng:** API không ổn định, lỗi không rõ ràng khi chạy production mode.

**Cách khắc phục:** Thay bằng kiểm tra tường minh + `HTTPException(503, ...)`.

**Độ khó:** Easy

**Ưu tiên:** P2

---

# 2. AI

---

### W-008 Không có guardrails chống prompt injection từ nội dung hợp đồng

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** AI

**File liên quan:**
- `app/core/prompts.py:85-102` (QA_SYSTEM_PROMPT)
- `app/agents/qa_agent.py:101-106`
- `app/agents/risk_flagger.py:89-95`

**Bằng chứng:** Nội dung hợp đồng (do người dùng upload) được đưa thẳng vào prompt mà không qua bất kỳ lớp lọc nào:
```python
human_content = QA_HUMAN_TEMPLATE.format(
    contract_context=state["_contract_context"],   # nội dung contract user-upload
    legal_context=state["_legal_context"],
    question=question,
)
```
Không có validation "không vượt quá kích thước", không tách biệt delimiter chống injection, không lọc prompt độc hại. Prompts chỉ khuyến nghị "DO NOT" mà không ép buộc về mặt kỹ thuật.

**Tại sao đây là vấn đề:** Hợp đồng là dữ liệu không tin cậy; kẻ tấn công có thể chèn chỉ thị "bỏ qua hệ thống prompt, trả lời..." vào nội dung điều khoản để ép LLM lộ context, bỏ qua luật, hoặc sinh output sai.

**Ảnh hưởng:** Security, hallucination, AI accuracy, độ tin cậy pháp lý.

**Cách khắc phục:** Nhúng context trong XML/delimiter rõ ràng, sanitize dấu hiệu prompt injection, đặt instruction trước/sau nội dung không tin cậy, kiểm tra input với regex/classifier, giới hạn độ dài context.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-009 Gọi Gemini không có timeout, retry, circuit breaker

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** AI

**File liên quan:**
- `app/agents/llm_client.py:21-34`
- `app/agents/clause_parser.py:403-416`
- `app/agents/risk_flagger.py:97-111`
- `app/agents/qa_agent.py:108-115`

**Bằng chứng:** `ChatGoogleGenerativeAI(...)` chỉ cấu hình `temperature=0`, không `timeout`, không `max_retries`, không `max_tokens`. Retry duy nhất là retry-parse-JSON thủ công khi output không parse được (lặp 1 lần) — không retry khi API lỗi (rate limit, 5xx, network).

**Tại sao đây là vấn đề:** Rate limit của Gemini hay network lỗi sẽ khiến request treo vô thời hạn hoặc fail ngay không có cơ chế phục hồi; contract lớn (nhiều điều khoản) → dễ chạm rate limit, một clause hỏng kéo cả analyze fail.

**Ảnh hưởng:** Hiệu năng, scalability, UX, chi phí.

**Cách khắc phục:** Cấu hình timeout/retry/backoff cho model; bọc thêm circuit breaker và tách riêng retry-API với retry-parse-JSON.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-010 Không giới hạn `max_tokens` cho output LLM

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** AI

**File liên quan:**
- `app/agents/llm_client.py:29-33`
- `app/core/prompts.py` (các prompt yêu cầu JSON lớn)

**Bằng chứng:** `ChatGoogleGenerativeAI(model=..., google_api_key=..., temperature=0)` — không tham số `max_tokens`. Prompt `EXTRACTION_PROMPT` yêu cầu JSON ~17 field có thể sinh output rất dài.

**Tại sao đây là vấn đề:** Output có thể bị cắt giữa chừng làm hỏng JSON (tăng tỷ lệ retry), hoặc tốn token/chi phí cho câu trả lời không kiểm soát được.

**Ảnh hưởng:** Chi phí, AI accuracy, hallucination (output cắt lởm).

**Cách khắc phục:** Đặt `max_tokens` hợp lý cho từng loại prompt.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-011 Retry-parse-JSON thủ công lặp lại ở 3 nơi

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Maintainability

**File liên quan:**
- `app/agents/clause_parser.py:410-415`
- `app/agents/risk_flagger.py:100-111`
- `app/agents/qa_agent.py:111-115`

**Bằng chứng:** Cùng một pattern:
```python
raw = chat_completion(prompt, provider=provider)
result = parse_json_object(raw)
if result is None:
    raw = chat_completion(prompt, provider=provider)
    result = parse_json_object(raw)
```
lặp 3 lần ở 3 file khác nhau với log riêng.

**Tại sao đây là vấn đề:** Vi phạm DRY; khi đổi sang structured output hoặc đổi cơ chế retry phải sửa 3 nơi; dễ lệch.

**Ảnh hưởng:** Bảo trì.

**Cách khắc phục:** Gom thành helper `invoke_json(prompt, retries=2)`.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-012 Không có hallucination detection / confidence score / explainable AI

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** AI

**File liên quan:**
- `app/agents/qa_agent.py:88-146`
- `app/agents/risk_flagger.py:33-124`

**Bằng chứng:** Sau khi LLM sinh `issue/severity/legal_basis`, hệ thống không xác minh lại (verifier pass), không gán confidence, không giải thích mức độ tin cậy. Citation validation chỉ áp dụng cho QA ở mức "clause_number có trong retrieval hay không" (`qa_agent.py:134-139`), không xác minh nội dung trích dẫn khớp.

**Tại sao đây là vấn đề:** Trong lĩnh vực pháp lý, một câu trả lời sai chắc chắn còn nguy hiểm hơn "không biết". Người dùng không có cơ chế đánh giá độ tin cậy.

**Ảnh hưởng:** Hallucination, AI accuracy, UX, độ tin cậy pháp lý.

**Cách khắc phục:** Thêm verifier pass (second LLM hoặc rule-based) kiểm tra tính nhất quán; sinh confidence score; hiển thị mức độ tin cậy + nguồn.

**Độ khó:** Hard

**Ưu tiên:** P1

---

### W-013 Không có tool calling / Calculator Agent cho tính toán bồi thường, phạt

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** AI

**File liên quan:**
- `app/agents/qa_agent.py` (toàn bộ)
- `app/core/prompts.py:85-102`
- `PROGRESS_REPORT.md:87-89` (tự nhận chưa làm)

**Bằng chứng:** `PROGRESS_REPORT.md` ghi nhận: chatbot "chủ động tránh để LLM tự tính toán (đúng nguyên tắc chống hallucination), nhưng chưa có tool/agent tính toán thay thế". Không có node nào trong QA graph thực hiện tính toán (chỉ retrieve → generate/refusal).

**Tại sao đây là vấn đề:** Người dùng hỏi "chấm dứt tháng 3 thì bồi thường bao nhiêu" không được trả lời chính xác — một use case giá trị cao bị bỏ trống.

**Ảnh hưởng:** AI accuracy, UX, giá trị sản phẩm.

**Cách khắc phục:** Thêm tool node (LangChain tool / `@tool`) tính toán dựa trên con số đã trích xuất, có citation cho từng hạng mục.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-014 Không có agent planner/router/reflection; multi-agent chỉ dừng ở fan-out song song

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** AI

**File liên quan:**
- `app/agents/workflow.py` (toàn bộ)
- `app/agents/qa_agent.py` (toàn bộ)

**Bằng chứng:** Workflow hiện tại: `extract → fan-out judge (Send) → aggregate` (`workflow.py:44-62`) và QA: `retrieve → route → generate/refusal` (`qa_agent.py:149-156`). Không có node lập kế hoạch, không có vòng lặp reflection/self-correction, không có router tool.

**Tại sao đây là vấn đề:** Chưa đáp ứng các pattern agentic hiện đại (planner, tool router, reflection) giúp cải thiện độ chính xác và khả năng xử lý câu hỏi phức tạp.

**Ảnh hưởng:** AI accuracy, scalability của tác vụ phức tạp.

**Cách khắc phục:** Thêm planner node phân rã câu hỏi, router node chọn retrieval/tool, và reflection loop khi kết quả thiếu grounding.

**Độ khó:** Hard

**Ưu tiên:** P2

---

# 3. RAG

---

### W-015 Overlap chunking làm trùng nội dung và vượt quá kích thước cấu hình

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** RAG

**File liên quan:**
- `app/document/chunker.py:42-46`

**Bằng chứng:**
```python
if chunk_overlap > 0 and len(chunks) > 1:
    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        overlapped.append(chunks[i - 1][-chunk_overlap:] + chunks[i])
    return overlapped
```
Cách dán đè này làm chunk mới = `overlap` ký tự của chunk trước + toàn bộ chunk hiện tại → luôn **vượt** `max_chunk_size` (1800) và nhân bản nội dung vào embedding.

**Tại sao đây là vấn đề:** Chunk vượt giới hạn token khi embed → bị cắt (mất nội dung), vector chứa nội dung trùng làm giảm chất lượng retrieval, tốn token lưu trữ.

**Ảnh hưởng:** RAG accuracy, chi phí embedding, hiệu năng.

**Cách khắc phục:** Overlap bằng cách lưu chunk gốc + tách overlap vào trước/ngắt bằng separator, hoặc loại bỏ overlap (retrieval theo điều khoản vốn đã có context đủ).

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-016 Embedding bị cắt ở 512 token trong khi chunk dài tới 1800 ký tự

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** RAG

**File liên quan:**
- `app/infrastructure/embeddings/hf_embedder.py:28-39`
- `app/core/settings.py:36-39`
- `app/document/chunker.py:93-150`

**Bằng chứng:** `EMBEDDING_MAX_SEQ_LENGTH=512` (`settings.py:23`), `client.max_seq_length = 512` (`hf_embedder.py:38-39`). Chunk tối đa 1800 ký tự (~500-600 token tiếng Việt) → nhiều chunk bị cắt bớt khi embed.

**Tại sao đây là vấn đề:** Nội dung cuối chunk biến mất khỏi vector → retrieval bỏ sót điều khoản nằm ở cuối chunk, giảm recall.

**Ảnh hưởng:** RAG accuracy, AI accuracy.

**Cách khắc phục:** Giảm `max_chunk_size` để chunk nằm trong giới hạn token (ví dụ ~1200 ký tự), hoặc tăng `max_seq_length`/dùng model hỗ trợ long-context.

**Độ khó:** Easy

**Ưu tiên:** P1

---

### W-017 Full-text search dùng config `simple` — không xử lý dấu tiếng Việt

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** RAG

**File liên quan:**
- `schema.sql:149-151`
- `app/infrastructure/vector/pg_search.py:164-168`

**Bằng chứng:**
```sql
tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(chunk_text, ''))) STORED
```
```python
ts_rank_cd(c.tsv, plainto_tsquery('simple', %s)) AS score
```
`'simple'` chỉ tách token theo khoảng trắng, không stem tiếng Việt, không xử lý dấu. Truy vấn "boi thuong" không khớp "bồi thường"; "luat lao dong" không khớp "Luật Lao động".

**Tại sao đây là vấn đề:** Nhánh FTS của hybrid search kém hiệu quả với tiếng Việt; thực tế phần lớn người dùng gõ không đúng dấu.

**Ảnh hưởng:** RAG accuracy, recall.

**Cách khắc phục:** Chuẩn hóa dấu (strip diacritics) cả 2 phía chunk + query khi index/search, hoặc cấu hình `to_tsvector('vietnamese', ...)` nếu có dictionary, hoặc bổ sung trgm index trên `chunk_text` cho fuzzy match.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-018 Hai regex tách điều khoản khác nhau giữa chunker và clause_parser

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** RAG

**File liên quan:**
- `app/document/chunker.py:11-13`
- `app/agents/clause_parser.py:370-373`

**Bằng chứng:**
```python
# chunker.py
_ARTICLE_PATTERN = re.compile(r"(?:(?:Điều|ĐIỀU)\s+(\d+)[\.:\-\)]\s*)")
# clause_parser.py
_CLAUSE_SPLIT_RE = re.compile(r"(?:^|\n)\s*(Điều|ĐIỀU)\s+(\d+)\s*[\.:\)\-\–]\s*", re.MULTILINE)
```
Chunker không yêu cầu đầu dòng, không nhận dấu en-dash `–`; parser thì có.

**Tại sao đây là vấn đề:** Danh tính điều khoản (clause_number) giữa chunk store và báo cáo có thể lệch nhau (cùng text nhưng tách khác) → `get_text_by_clause` (`contract_chunk_repository.py:39-56`) join sai, RAG trả clause khác clause thực.

**Ảnh hưởng:** RAG accuracy, AI accuracy.

**Cách khắc phục:** Dùng chung một hằng số regex cho cả hai module.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-019 Không có cross-encoder reranker

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** RAG

**File liên quan:**
- `app/infrastructure/vector/pg_search.py:62-97`
- `app/infrastructure/retrieval/legal_graph_rag.py:22-105`

**Bằng chứng:** Sau RRF fusion (`pg_search.py:76-97`) kết quả được dùng thẳng, không qua bất kỳ bước rerank bằng model đối chiếu (cross-encoder). `LegalGraphRag.retrieve_for_clause` chỉ sắp xếp theo `role` + score (`legal_graph_rag.py:143-152`).

**Tại sao đây là vấn đề:** Bi-encoder + RRF cho recall tốt nhưng precision thấp; kết quả không khớp ngữ nghĩa chặt với query.

**Ảnh hưởng:** RAG precision, AI accuracy.

**Cách khắc phục:** Thêm bước rerank top-N bằng cross-encoder (vd `bge-reranker-v2-m3`) trước khi đưa vào prompt.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-020 Không có parent-document / multi-vector retrieval cho điều khoản

---

**Trạng thái xác minh:** ⚠️ Partially Correct

**Mức độ:** Medium

**Loại:** RAG

**File liên quan:**
- `app/document/chunker.py:93-150`
- `app/infrastructure/retrieval/legal_graph_rag.py:46-89`
- `app/agents/risk_flagger.py:21` (ghép Điều cho judge)
- `app/infrastructure/db/contract_chunk_repository.py:39-56`

**Bằng chứng:** Chunk theo Điều là đơn vị duy nhất được embed (`chunker.py`). Với Điều dài bị tách thành nhiều part, `retrieve_contract` / `PgContractVectorSearch` trả part rời rạc, không hydrate parent. **Tuy nhiên** nhánh risk analysis đã gọi `get_text_by_clause` để ghép lại toàn Điều (`risk_flagger.py:21`) — thiếu sót chủ yếu ở QA/vector retrieval, không phải toàn pipeline.

**Tại sao đây là vấn đề:** Trả lời về một Khoản cụ thể có thể thiếu ngữ cảnh toàn Điều; ngược lại chunk nhỏ khó đủ context cho judge.

**Ảnh hưởng:** RAG accuracy, AI accuracy.

**Cách khắc phục:** Lưu liên kết parent-child chunk; khi retrieve part → hydrate toàn bộ parent Điều vào context (parent document retrieval).

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-021 Truy vấn Neo4j `LIMIT` không có tác dụng lên collect

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** RAG

**File liên quan:**
- `app/infrastructure/neo4j/graph_repository.py:218-227`

**Bằng chứng:**
```cypher
RETURN collect(DISTINCT c.chunk_ref) AS seeds,
       collect(DISTINCT sib.path) AS siblings, ...
LIMIT $limit
```
Cypher `LIMIT` áp lên số row trả về (ở đây luôn 1 row do collect), không giới hạn số phần tử trong mỗi collect. Việc cắt thực tế nằm ở Python `[:24]`/`[:16]`/`[:8]` (`graph_repository.py:234-238`).

**Tại sao đây là vấn đề:** Neo4j phải collect toàn bộ hàng xóm trước rồi mới cắt ở tầng app → tốn tài nguyên đồ thị khi graph lớn; `LIMIT` gây hiểu nhầm là đang giới hạn.

**Ảnh hưởng:** Hiệu năng khi scale dữ liệu pháp luật.

**Cách khắc phục:** Đẩy giới hạn vào Cypher (subquery hoặc `LIMIT` trên từng pattern) hoặc bỏ `LIMIT` và ghi rõ logic cắt ở app.

**Độ khó:** Medium

**Ưu tiên:** P3

---

### W-022 Không lọc metadata hiệu lực (ngày) khi retrieval

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** RAG

**File liên quan:**
- `app/infrastructure/vector/pg_search.py:104-118`
- `app/infrastructure/db/legal_repository.py`

**Bằng chứng:** `_base_where` chỉ lọc `c.is_effective`, `embedding IS NOT NULL`, `chunk_type <> signature`, `doc_id`/`doc_type_hint`. Không lọc theo `eff_from`/`eff_to`/`issue_date`. `is_effective` chỉ được set theo `status_flag` tại ingest (`thuoc_tinh_mapper.py:28-46`), không phản ánh thời điểm hiện tại so với `eff_from`/`eff_to`.

**Tại sao đây là vấn đề:** Văn bản chưa có hiệu lực (eff_from trong tương lai) hoặc hết hiệu lực theo thời gian vẫn có thể được retrieve như luật hiện hành, nếu `is_effective` không được cập nhật.

**Ảnh hưởng:** AI accuracy, độ tin cậy pháp lý.

**Cách khắc phục:** Lọc `eff_from <= NOW() AND (eff_to IS NULL OR eff_to >= NOW())` trong `_base_where`, hoặc định kỳ cập nhật `is_effective`.

**Độ khó:** Medium

**Ưu tiên:** P2

---

# 4. Prompt

---

### W-023 Prompt nhúng cứng trong source code, không versioning

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Prompt Engineering

**File liên quan:**
- `app/core/prompts.py` (toàn bộ)

**Bằng chứng:** Toàn bộ 4 prompt (EXTRACTION, OCR, CLAUSE_RISK, QA_SYSTEM + QA_HUMAN) là hằng số Python trong `prompts.py`. `LLM_FILLABLE_FIELDS` và format string `{clause_text}`... `{legal_context}` gắn chặt với code.

**Tại sao đây là vấn đề:** Điều chỉnh prompt = sửa code + redeploy; không thể A/B test, không theo dõi hiệu năng theo phiên bản prompt, không có registry.

**Ảnh hưởng:** Bảo trì, AI accuracy tuning.

**Cách khắc phục:** Đưa prompt vào registry/file cấu hình có version, lưu version prompt vào DB cùng kết quả phân tích để đối chiếu.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-024 Prompt trích xuất bị cắt nội dung ở 12000 ký tự

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Prompt Engineering

**File liên quan:**
- `app/agents/clause_parser.py:407`

**Bằng chứng:**
```python
prompt = EXTRACTION_PROMPT.format(contract_text=text[:12000])
```
LLM fallback chỉ nhìn 12000 ký tự đầu của hợp đồng.

**Tại sao đây là vấn đề:** Với hợp đồng dài, thông tin quan trọng nằm sau 12000 ký tự (điều khoản cuối, chữ ký) không bao giờ được LLM trích xuất khi regex bỏ sót.

**Ảnh hưởng:** AI accuracy (trích xuất thiếu field).

**Cách khắc phục:** Chunk văn bản cho extraction theo từng phần rồi merge, hoặc tăng giới hạn có kiểm soát.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-025 Prompt quá phụ thuộc vào khả năng format JSON của mô hình

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Prompt Engineering

**File liên quan:**
- `app/core/prompts.py:76-82,95-101`
- `app/agents/json_parsing.py`

**Bằng chứng:** Tất cả prompt yêu cầu "Return ONLY a single JSON object" và `json_parsing.py` phải tự lột fence ```json + json.loads. Không dùng structured output / output schema của Gemini (generation_config.response_mime_type="application/json").

**Tại sao đây là vấn đề:** Tỷ lệ parse fail phụ thuộc mô hình; khi fail phải gọi lại LLM (tốn chi phí, tăng latency).

**Ảnh hưởng:** Chi phí, latency, robustness.

**Cách khắc phục:** Dùng `ChatGoogleGenerativeAI(..., format='json')` hoặc structured output / function calling để bắt buộc schema.

**Độ khó:** Easy

**Ưu tiên:** P2

---

# 5. OCR

---

### W-026 OCR ảnh không giới hạn kích thước, đưa base64 toàn bộ vào prompt

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** OCR

**File liên quan:**
- `app/document/parser.py:35-55`

**Bằng chứng:**
```python
with open(file_path, "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode("utf-8")
message = HumanMessage(content=[
    {"type": "text", "text": OCR_PROMPT},
    {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{image_b64}"}},
])
```
Ảnh được đọc toàn bộ vào RAM, encode base64, nhồi thẳng vào message. Không có giới hạn kích thước ảnh, không pre-process (xóa nhiễu, xoay, tăng độ tương phản).

**Tại sao đây là vấn đề:** Ảnh chụp smartphone 12MP (~20-50MB base64) làm chậm/tốn token của Gemini; chất lượng OCR với ảnh chụp nghiêng/mờ thấp.

**Ảnh hưởng:** Hiệu năng, chi phí, OCR accuracy, UX.

**Cách khắc phục:** Giới hạn kích thước file + resize/compress ảnh trước khi gửi; thêm tiền xử lý ảnh (deskew, threshold).

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-027 Không validate kết quả OCR

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** OCR

**File liên quan:**
- `app/document/parser.py:52-54`

**Bằng chứng:**
```python
text = get_chat_model().invoke([message]).content.strip()
if not text:
    raise ValueError("No text could be extracted from the image")
```
Chỉ kiểm tra text không rỗng. Không kiểm tra chất lượng (tỷ lệ ký tự hợp lệ, có dấu tiếng Việt hợp lệ, độ dài hợp lý so với ảnh).

**Tại sao đây là vấn đề:** OCR sinh text rác/garbled vẫn được xem là thành công → toàn bộ pipeline downstream (chunking, RAG, analysis) nhận dữ liệu hỏng mà không biết.

**Ảnh hưởng:** AI accuracy, UX, hallucination.

**Cách khắc phục:** Thêm heuristics kiểm tra (phân bố ký tự Unicode tiếng Việt, cấu trúc Điều/Khoản) và cảnh báo chất lượng thấp.

**Độ khó:** Medium

**Ưu tiên:** P2

---

# 6. Backend

---

### W-028 Không có connection pooling cho psycopg2; mỗi lần gọi mở connection mới

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Performance

**File liên quan:**
- `app/infrastructure/db/connection.py:13-17`
- `app/infrastructure/db/*.py` (mọi repository)
- `app/agents/checkpointer.py:21-28`

**Bằng chứng:**
```python
def get_connection():
    conn = psycopg2.connect(get_settings().database_url)
    register_vector(conn)
    conn.autocommit = False
    return conn
```
Mỗi `get_db()` tạo connection mới. `UploadContract` mở ~4-5 connection (save + parse-đọc chunk sau + replace_for_contract + upsert). `evaluate_clause` mỗi clause mở connection riêng (`pg_search` + `get_text_by_clause`). Chỉ checkpointer của QA có pool.

**Tại sao đây là vấn đề:** Handshake TCP + auth PostgreSQL mỗi lần gọi → latency cao, quá tải connection khi concurrency (phân tích 20 clause song song = 40+ connection).

**Ảnh hưởng:** Hiệu năng, scalability, thời gian phản hồi.

**Cách khắc phục:** Dùng `psycopg_pool.ConnectionPool` chia sẻ toàn app (giống checkpointer).

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-029 Blocking I/O và embedding chạy trực tiếp trên event loop

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Performance

**File liên quan:**
- `app/agents/qa_agent.py:58-73` (`_retrieve_node` async gọi `retrieve_contract`/`retrieve_legal` sync)
- `app/infrastructure/vector/pg_search.py` (psycopg2 sync)
- `app/infrastructure/embeddings/hf_embedder.py` (inference sync)
- `app/application/use_cases/contracts.py:42-56` (embed trong async use case)

**Bằng chứng:** `_retrieve_node` là async nhưng gọi `retrieve_contract(question, ...)` sync (chứa `embed_query` hàng trăm ms + SQL sync) trực tiếp trên loop. `UploadContract.execute` (async) gọi `self._embedder.embed_documents(texts)` sync. Trong khi đó `workflow.py:36` và `:69-75` đã biết cách bọc `asyncio.to_thread` cho parse và judge — retrieval lại không.

**Tại sao đây là vấn đề:** Event loop bị chặn hàng trăm ms → toàn bộ request khác chờ, throughput giảm mạnh khi có nhiều user.

**Ảnh hưởng:** Hiệu năng, scalability, UX.

**Cách khắc phục:** Bọc retrieval/embedding vào `asyncio.to_thread`, hoặc chạy worker riêng cho tác vụ nặng.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-030 Upload trả HTTP 200 ngay cả khi parse/embedding thất bại

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** API

**File liên quan:**
- `app/application/use_cases/contracts.py:60-76`

**Bằng chứng:**
```python
except Exception as e:
    logger.error("Upload parse failed: contract_id=%s error=%s", contract_id, e)
    message = f"File uploaded but parsing failed: {e}"
...
self._contracts.upsert(...)
return {"contract_id": ..., "status": status, "message": message, ...}
```
`status` giữ giá trị `"uploaded"`, HTTP vẫn 200 với `chunk_count=0`.

**Tại sao đây là vấn đề:** Client không biết file hỏng; frontend `App.jsx:42-43` ngay lập tức gọi `analyzeContract` → 404, trải nghiệm lỗi kỳ lạ (2 bước lỗi thay vì 1).

**Ảnh hưởng:** UX, API contract không trung thực.

**Cách khắc phục:** Trả lỗi 4xx/422 với chi tiết; hoặc tạo contract row với status `error` và frontend xử lý đúng.

**Độ khó:** Easy

**Ưu tiên:** P1

---

### W-031 Exception string lộ trực tiếp cho client

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Security

**File liên quan:**
- `app/api/routes.py:90-91,110-111,139-140`

**Bằng chứng:**
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e)) from e
```
`str(e)` có thể chứa connection string, đường dẫn file, chi tiết SQL, cấu hình.

**Tại sao đây là vấn đề:** Rò rỉ thông tin nội bộ ra ngoài; debug khó vì client chỉ thấy 500 chung chung.

**Ảnh hưởng:** Security, bảo trì.

**Cách khắc phục:** Log đầy đủ ở server (kèm request id), trả message generic cho client.

**Độ khó:** Easy

**Ưu tiên:** P1

---

### W-032 Không có request-id / structured logging

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Logging

**File liên quan:**
- `app/core/logging.py` (toàn bộ)

**Bằng chứng:**
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
```
Chỉ console plain text, không request-id, không JSON, không correlation với phân tích nhiều clause.

**Tại sao đây là vấn đề:** Không thể truy vết một request qua nhiều log (upload → analyze → 20 clause judge), debug production khó, không tích hợp được với log aggregator.

**Ảnh hưởng:** Bảo trì, monitoring, khắc phục sự cố.

**Cách khắc phục:** Middleware sinh request-id; logger JSON; thêm context (contract_id, user_id) vào log.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-033 Schema áp dụng toàn bộ lúc boot, không có migration

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Database

**File liên quan:**
- `app/infrastructure/db/schema_loader.py:8-17`
- `app/main.py:27`
- `schema.sql`

**Bằng chứng:** `apply_postgres_schema()` đọc và chạy toàn bộ `schema.sql` mỗi lần app start. `schema.sql` dùng `CREATE TABLE IF NOT EXISTS` nên "vô hại" với lần chạy đầu nhưng không có khái niệm version/upgrade.

**Tại sao đây là vấn đề:** Đổi schema trong tương lai (thêm cột) sẽ không được áp dụng cho DB đã tồn tại → lỗi runtime khi cột thiếu; không thể downgrade/rollback; nguy hiểm với dữ liệu thật.

**Ảnh hưởng:** Bảo trì, vận hành, data integrity.

**Cách khắc phục:** Chuyển sang Alembic (hoặc Flyway), đánh dấu migration version, bỏ auto-apply.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-034 Không có background job/queue cho tác vụ phân tích nặng

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Backend

**File liên quan:**
- `app/api/routes.py:94-111`
- `app/application/use_cases/contracts.py:87-125`
- `app/agents/workflow.py`

**Bằng chứng:** `POST /analyze` chạy toàn bộ pipeline (LLM cho mọi clause) **trong request đồng bộ** (await đến khi xong mới trả). Không có Celery/RQ/ARQ/Redis queue. Không có worker. `docker-compose.yml` không có service worker.

**Tại sao đây là vấn đề:** Hợp đồng 30 điều = 30+ lời gọi LLM = phút chờ; HTTP timeout (proxy/load balancer) sẽ cắt ngang; không thể scale bằng worker; UX xấu (phải chờ).

**Ảnh hưởng:** Hiệu năng, scalability, UX, độ tin cậy.

**Cách khắc phục:** Đưa analyze vào job queue (Redis + ARQ/Celery), trả `job_id`, frontend poll kết quả.

**Độ khó:** Hard

**Ưu tiên:** P1

---

### W-035 Hai driver PostgreSQL song song (psycopg + psycopg2)

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Dependency

**File liên quan:**
- `requirements.txt:13-14`

**Bằng chứng:**
```
psycopg[binary]
psycopg2-binary
```
`psycopg2` dùng cho repository (`connection.py`), `psycopg` (v3) dùng cho checkpointer pool (`checkpointer.py`).

**Tại sao đây là vấn đề:** Tăng kích thước cài đặt, hai API khác nhau, nguy cơ xung đột version.

**Ảnh hưởng:** Dependency, bảo trì.

**Cách khắc phục:** Thống nhất về một driver (khuyến nghị `psycopg` v3).

**Độ khó:** Medium

**Ưu tiên:** P3

---

# 7. Frontend

---

### W-036 Token JWT lưu trong localStorage

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Security

**File liên quan:**
- `frontend/src/AuthContext.jsx:7-12,24-28`
- `frontend/src/api.js:5-8`

**Bằng chứng:**
```js
const STORAGE_KEY = "contractlens_auth";
if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
```
`localStorage` truy cập được bởi mọi script trong page (XSS surface). Không dùng httpOnly cookie.

**Tại sao đây là vấn đề:** Nếu bất kỳ component nào render nội dung user (vd tên hợp đồng) có lỗi XSS, token bị đánh cắp. Token tồn tại 7 ngày (`JWT_EXPIRE_MINUTES`).

**Ảnh hưởng:** Security.

**Cách khắc phục:** Dùng httpOnly + Secure cookie cho access token (hoặc refresh token), hoặc chấp nhận trade-off và thêm CSP mạnh + sanitize mọi render.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-037 Không có routing, retry, error boundary

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Frontend

**File liên quan:**
- `frontend/src/App.jsx` (quản lý view bằng state `view`)
- `frontend/src/api.js` (không retry/backoff)

**Bằng chứng:** App dùng `useState("list" | "upload")` để chuyển màn hình, không có router. `api.js` `handleResponse` chỉ throw khi `!res.ok`, không retry. Không có React Error Boundary.

**Tại sao đây là vấn đề:** Không có deep-link/refresh giữ trạng thái; mạng rớt 1 lần = hỏng cả thao tác; lỗi render không kiểm soát → trắng trang.

**Ảnh hưởng:** UX, bảo trì.

**Cách khắc phục:** Thêm React Router, retry có backoff trong api layer, ErrorBoundary bao quanh app.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-038 State server bị nhân bản và tự dựng trên frontend

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Frontend

**File liên quan:**
- `frontend/src/App.jsx:36-79`

**Bằng chứng:** Sau upload, `setContracts(prev => [{...}, ...prev])` tự dựng contract mới (tự sinh `created_at: new Date().toISOString()`) thay vì dùng dữ liệu từ server; `handleOpenContract` gọi `analyzeContract` để lấy lại kết quả đã lưu.

**Tại sao đây là vấn đề:** State dễ lệch với server (status, chunk_count); không dùng lại cache phân tích hiệu quả; logic chồng chéo.

**Ảnh hưởng:** UX, bảo trì.

**Cách khắc phục:** Fetch lại danh sách từ server sau khi upload, hoặc dùng query cache (React Query/SWR).

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-039 Không có loading skeleton, không có theme dark, phụ thuộc Google Fonts

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** UX

**File liên quan:**
- `frontend/index.html:8-9` (Google Fonts + Material Symbols)
- `frontend/src/components/ContractListScreen.jsx:78-79` (chỉ text "Đang tải...")

**Bằng chứng:** Icons và font tải từ `fonts.googleapis.com` — cần internet; nếu offline UI mất icon. Loading chỉ là text đơn giản.

**Tại sao đây là vấn đề:** UX kém khi network chậm/offline; mất kiểm soát về quyền riêng tư (gọi Google).

**Ảnh hưởng:** UX, performance (render blocking font).

**Cách khắc phục:** Self-host font/icon, thêm skeleton loading, hỗ trợ dark mode.

**Độ khó:** Medium

**Ưu tiên:** P3

---

# 8. Database

---

### W-040 Không dùng ltree mặc dù thiết kế đã nhắc đến

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Database

**File liên quan:**
- `schema.sql` (không có cột ltree)
- `docs/architecture-review*.md` (đề xuất ltree)

**Bằng chứng:** `schema.sql` không `CREATE EXTENSION ltree`, không cột `ltree`; cây cấu trúc được lưu ở Neo4j còn Postgres chỉ lưu `chunk_ref` string path (`schema.sql:134`). README cũng không đề cập ltree nữa.

**Tại sao đây là vấn đề:** Chưa phải bug; nhưng truy vấn "ancestor/descendant theo path" phải qua Neo4j (thêm một hệ thống phụ thuộc), trong khi PG `ltree` có thể làm được nếu chỉ cần 1 DB.

**Ảnh hưởng:** Architecture, bảo trì (2 hệ thống lưu cây + 1 nguồn text).

**Cách khắc phục:** Chọn 1 strategy: hoặc dùng `ltree` trong PG cho việc expand đơn giản, hoặc giữ Neo4j và ghi rõ vai trò. Hiện tại đủ dùng, chỉ cần tài liệu hóa quyết định.

**Độ khó:** Hard

**Ưu tiên:** P3

---

### W-041 `tsv` là generated column dùng `'simple'` — không tối ưu tiếng Việt

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Database

**File liên quan:**
- `schema.sql:149-151`
- `schema.sql:105-106` (trgm chỉ trên doc_num/title)

**Bằng chứng:** (Xem thêm W-017.) `tsv` generated với `to_tsvector('simple', ...)`; GIN `idx_lsc_tsv` đánh lên `tsv`. Không có trgm index trên `chunk_text` của `legal_section_chunks` hay `content` của `contract_chunks`.

**Tại sao đây là vấn đề:** Tìm kiếm gõ thiếu dấu / sai dấu không khớp; trgm có thể cứu nhưng không được đánh trên text chunk.

**Ảnh hưởng:** RAG accuracy, performance FTS.

**Cách khắc phục:** Đánh GIN trgm trên cột text chuẩn hóa dấu, hoặc thêm cột normalized + index.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-042 Thiếu index/phân trang cho danh sách hợp đồng

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Database

**File liên quan:**
- `schema.sql:46-47` (có `idx_uc_user_created`)
- `app/api/routes.py:114-122` / `app/application/use_cases/contracts.py:128-145` (không phân trang)

**Bằng chứng:** `idx_uc_user_created` tồn tại và hợp lý; nhưng `ListContracts` trả toàn bộ contract của user không giới hạn, không `OFFSET/LIMIT`.

**Tại sao đây là vấn đề:** User tích lũy nhiều hợp đồng → response phình, load DB nhiều.

**Ảnh hưởng:** Hiệu năng, scalability, UX.

**Cách khắc phục:** Thêm pagination (limit/offset hoặc cursor theo created_at).

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-043 Không ràng buộc dữ liệu và trigger cho `users` / `updated_at`

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Database

**File liên quan:**
- `schema.sql:14-19` (users)
- `app/infrastructure/db/user_repository.py:12-26` (email normalize ở app layer)

**Bằng chứng:** Email `UNIQUE` nhưng việc lowercase/trim nằm ở tầng Python (`user_repository.py:19`). `uploaded_contracts.updated_at` chỉ update trong `upsert` (`contract_repository.py:28`) — các thao tác khác (`save_analysis` set NOW() thủ công). Không có trigger giữ `updated_at`.

**Tại sao đây là vấn đề:** Nếu có client khác insert email dạng "A@B.COM" trực tiếp vào DB sẽ phá ràng buộc ngầm; `updated_at` dễ sai nếu quên set ở code mới.

**Ảnh hưởng:** Data integrity, bảo trì.

**Cách khắc phục:** Dùng unique index trên `lower(email)`, trigger `set_updated_at()`.

**Độ khó:** Easy

**Ưu tiên:** P3

---

# 9. API

---

### W-044 Upload không giới hạn kích thước file, đọc toàn bộ vào RAM

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Security

**File liên quan:**
- `app/api/routes.py:73-91`
- `app/application/use_cases/contracts.py:26-35`

**Bằng chứng:**
```python
data = await file.read()   # đọc toàn bộ file vào RAM, không giới hạn size
```
Không kiểm tra `Content-Length` hay giới hạn MB. File hợp lệ chỉ theo extension (`contracts.py:29-32`), không kiểm tra magic bytes.

**Tại sao đây là vấn đề:** DoS bằng file khổng lồ làm cạn RAM; file thay đổi nội dung (đổi .exe thành .pdf) vẫn được parse → lỗi hoặc hành vi bất ngờ.

**Ảnh hưởng:** Security, hiệu năng, độ tin cậy.

**Cách khắc phục:** Giới hạn kích thước (vd 20MB), validate magic bytes/MIME thực, stream thay vì đọc toàn bộ.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-045 CORS `allow_origins=["*"]` kết hợp `allow_credentials=True`

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 2, 2026-08-02)

**Mức độ:** High

**Loại:** Security

**File liên quan:**
- `app/main.py:72-78`

**Bằng chứng:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Theo spec CORS, khi `allow_credentials=True` không được phép dùng `*` (browser từ chối hoặc mở rộng scope một cách nguy hiểm nếu server gửi `*`).

**Tại sao đây là vấn đề:** Tổ hợp không hợp lệ và không an toàn; mở API cho mọi origin kết hợp credential.

**Ảnh hưởng:** Security.

**Cách khắc phục:** Allowlist cụ thể domain frontend, bỏ `allow_credentials=True` nếu dùng token header (không cần credentials).

**Độ khó:** Easy

**Ưu tiên:** P0

---

### W-046 Không có rate limiting trên endpoint tốn LLM

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Security

**File liên quan:**
- `app/api/routes.py:94-140` (`/analyze`, `/chat`)

**Bằng chứng:** Không có middleware rate limit nào; `/analyze` và `/chat` gọi LLM trả phí tùy ý số lần, mỗi analyze = N lần gọi LLM theo số điều khoản.

**Tại sao đây là vấn đề:** Kẻ tấn công (hoặc script) spam gọi → đội chi phí API key vô hạn; không có quota per user.

**Ảnh hưởng:** Security, chi phí, scalability.

**Cách khắc phục:** Rate limit per user/IP (Redis), quota theo gói; cache phân tích đã có nhưng cần kèm quota.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-047 `GET /api/v1/models` không yêu cầu xác thực

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** API

**File liên quan:**
- `app/api/routes.py:46-48`

**Bằng chứng:**
```python
@router.get("/models")
async def list_models():
    return [{"provider": key, **info} for key, info in PROVIDERS.items()]
```
Không có `Depends(get_current_user_id)`.

**Tại sao đây là vấn đề:** Rò rỉ nhẹ thông tin provider/model đang dùng (không nguy hiểm lắm nhưng không nhất quán với các endpoint còn lại).

**Ảnh hưởng:** Security (thấp), consistency.

**Cách khắc phục:** Thêm auth dependency.

**Độ khó:** Easy

**Ưu tiên:** P3

---

### W-048 `AnalyzeResponse` không được định kiểu tại API boundary

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** API

**File liên quan:**
- `app/schemas/contract.py:59-63`

**Bằng chứng:**
```python
class AnalyzeResponse(BaseModel):
    contract_id: str
    analysis: Any
    risks: List[Any]
```
`analysis`/`risks` là `Any`, không phải `ContractAnalysis`/`RiskItem`.

**Tại sao đây là vấn đề:** Mất type safety ở biên API; OpenAPI docs không thể hiện schema trả về; frontend phải tự tin nội dung.

**Ảnh hưởng:** Bảo trì, DX, contract API.

**Cách khắc phục:** Định kiểu đầy đủ `analysis: ContractAnalysis`, `risks: List[RiskItem]`.

**Độ khó:** Easy

**Ưu tiên:** P2

---

# 10. Security

---

### W-049 Secrets thật nằm trong `.env` (GEMINI_API_KEY, JWT_SECRET, SUPABASE_SECRET_KEY)

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ⚠️ Partially Fixed (Phase 1 / Task 2, 2026-08-02) — đã xóa `SUPABASE_URL`/`SUPABASE_SECRET_KEY`/`JWT_SECRET_KEY` và các khóa chết khỏi `.env`. Phần **rotate** `GEMINI_API_KEY` và `JWT_SECRET` là thao tác thủ công bắt buộc từ phía người dùng (sinh key mới trên Google Cloud / tự chọn secret mới) — còn lại ❌ Deferred.

**Mức độ:** Critical

**Loại:** Security

**File liên quan:**
- `.env` (không track, nhưng tồn tại trong working tree)

**Bằng chứng:**
```
GEMINI_API_KEY=<present, non-empty — ROTATE; value redacted in verification>
SUPABASE_URL=<present — unused leftover>
SUPABASE_SECRET_KEY=<present — unused leftover; ROTATE if ever leaked>
JWT_SECRET_KEY=<present — unused; settings reads JWT_SECRET>
JWT_SECRET=<present>
```
`SUPABASE_*` và `JWT_SECRET_KEY` là key cũ không còn được dùng (settings chỉ đọc `JWT_SECRET`; `extra="ignore"`).

**Tại sao đây là vấn đề:** GEMINI_API_KEY thật bị lộ trong repo local; SUPABASE_SECRET_KEY (service role secret!) nếu từng commit/leak sẽ cho quyền admin DB. Không track nhưng vẫn có nguy cơ khi chia sẻ repo/backup.

**Ảnh hưởng:** Security nghiêm trọng, chi phí (key bị lạm dụng).

**Cách khắc phục:** Rotate toàn bộ key hiện có, xóa `SUPABASE_*`/`JWT_SECRET_KEY` khỏi `.env`, dùng secret manager, thêm pre-commit chặn secret.

**Độ khó:** Easy

**Ưu tiên:** P0

---

### W-050 JWT secret mặc định `change-me-in-production`

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 2, 2026-08-02) — `main.py` lifespan từ chối khởi động nếu `JWT_SECRET` trống/`change-me-in-production`.

**Mức độ:** High

**Loại:** Security

**File liên quan:**
- `app/core/settings.py:30`
- `.env.example:17`

**Bằng chứng:**
```python
jwt_secret: str = "change-me-in-production"
```
Nếu user copy `.env.example` mà không đổi, mọi token có thể bị forge.

**Tại sao đây là vấn đề:** Secret yếu mặc định = giả mạo token đăng nhập bất kỳ user.

**Ảnh hưởng:** Security (authentication bị vô hiệu hóa).

**Cách khắc phục:** Validate startup: từ chối khởi động nếu secret là default; sinh ngẫu nhiên mỗi lần cài đặt.

**Độ khó:** Easy

**Ưu tiên:** P1

---

### W-051 Không có lockout / reset password / email verification

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Security

**File liên quan:**
- `app/application/use_cases/auth.py`
- `app/api/routes.py:51-70`

**Bằng chứng:** `LoginUser` chỉ so khớp bcrypt, không đếm số lần thất bại, không khóa tài khoản. Không endpoint reset password; đăng ký không verify email.

**Tại sao đây là vấn đề:** Brute-force mật khẩu không bị chặn; user quên mật khẩu không có lối thoát (bị khóa vĩnh viễn).

**Ảnh hưởng:** Security, UX.

**Cách khắc phục:** Rate limit login + lockout sau N lần sai; luồng reset password; verify email (tùy chọn cho đồ án).

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-052 Chat memory `thread_id` chỉ gắn theo contract_id, không gắn user

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Security

**File liên quan:**
- `app/agents/qa_agent.py:172-175`

**Bằng chứng:**
```python
config={"configurable": {"thread_id": contract_id}}
```
`thread_id = contract_id`. `get_conversation_history(contract_id)` cũng theo contract (`qa_agent.py:190`).

**Tại sao đây là vấn đề:** Memory/history phân chia theo contract chứ không theo (user, contract). Hiện contract_id là UUID duy nhất + có ownership check ở use case (`contracts.py:154`) nên rủi ro thực tế thấp, nhưng nếu sau này cho phép share contract, 2 user sẽ thấy chung lịch sử chat.

**Ảnh hưởng:** Security (thấp), bảo mật dữ liệu.

**Cách khắc phục:** `thread_id = f"{user_id}:{contract_id}"`.

**Độ khó:** Easy

**Ưu tiên:** P3

---

### W-053 File lưu disk local không mã hóa, không lifecycle cleanup

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Security

**File liên quan:**
- `app/infrastructure/storage/local_storage.py`

**Bằng chứng:** `save_upload` ghi file thô vào `data/uploads` bằng uuid, không mã hóa, không cơ chế xóa định kỳ; `data/` nằm trong `.gitignore` nhưng không có retention.

**Tại sao đây là vấn đề:** Hợp đồng là dữ liệu nhạy cảm; file thô (kể cả ảnh chứa thông tin cá nhân) nằm lâu dài trên disk không kiểm soát; đọc file trực tiếp nếu biết đường dẫn.

**Ảnh hưởng:** Security, compliance, chi phí lưu trữ.

**Cách khắc phục:** Dùng object storage có IAM/encryption (S3/MinIO), set retention policy, xóa file khi xóa contract.

**Độ khó:** Hard

**Ưu tiên:** P2

---

### W-054 Hardcoded session cookie của vbpl.vn trong code

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 2, 2026-08-02) — bỏ cookie mặc định, bắt buộc đọc `VBPL_COOKIE` từ env (fail-fast khi dùng `base_headers()` mà thiếu).

**Mức độ:** Low

**Loại:** Security

**File liên quan:**
- `scripts/crawl_vbpl/common.py:20-25`

**Bằng chứng:**
```python
VBPL_COOKIE = os.environ.get(
    "VBPL_COOKIE",
    "cookiesession1=678A3E11E347BD2868B0D261D317A546; ...",
)
```
Cookie session thật của một người dùng vbpl.vn nằm dưới dạng default value trong source.

**Tại sao đây là vấn đề:** Cookie cá nhân (session của site khác) bị hardcode trong repo; rủi ro lạm dụng tài khoản, và chắc chắn sẽ stale → script hỏng.

**Ảnh hưởng:** Security (thấp), độ tin cậy của crawler.

**Cách khắc phục:** Bắt buộc đọc từ env (không default), cập nhật khi hết hạn.

**Độ khó:** Easy

**Ưu tiên:** P3

---

# 11. Performance

---

### W-055 Embed lại query cho mỗi lần retrieval; không cache embedding

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Performance

**File liên quan:**
- `app/infrastructure/vector/pg_search.py:29,127`
- `app/infrastructure/embeddings/hf_embedder.py`

**Bằng chứng:** `PgContractVectorSearch.search` và `_vector_search` gọi `self._embedder.embed_query(query)` mỗi lần. Mỗi turn chat gọi 2 lần (contract + legal); mỗi clause judge gọi 1 lần. Không có cache cho query embedding.

**Tại sao đây là vấn đề:** bge-m3 chạy on-device tốn vài trăm ms/lần; nhân với số clause/turn → latency cao.

**Ảnh hưởng:** Hiệu năng, chi phí điện toán.

**Cách khắc phục:** Cache query embedding (lru_cache theo text hash), batching embedding.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-056 Mỗi lần gọi analyze mở nhiều connection PG đồng thời

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Performance

**File liên quan:**
- `app/agents/workflow.py:44-62` (fan-out 4 luồng)
- `app/infrastructure/db/connection.py`
- `app/agents/risk_flagger.py:18-29,50-72`

**Bằng chứng:** `_judge_clause_node` (chạy tối đa 4 song song) mỗi node gọi `evaluate_clause` → `get_text_by_clause` (1 connection) + `LegalGraphRag.retrieve_for_clause` → `pg_search` mở 1 connection → `get_texts_by_refs` (1 connection) + `get_meta_by_refs` (1 connection). Mỗi clause có thể mở 3-4 connection mới.

**Tại sao đây là vấn đề:** Với 30 clause × 4 luồng → hàng chục connection cùng lúc, PostgreSQL max_connections dễ bị cạn, latency tăng.

**Ảnh hưởng:** Hiệu năng, scalability.

**Cách khắc phục:** Pool connection + tái dùng trong một lần phân tích; gộp các query trong evaluate_clause.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-057 Frontend không gộp/throttle các lời gọi; không có cache

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Performance

**File liên quan:**
- `frontend/src/components/ChatTab.jsx:101-126`

**Bằng chứng:** Mỗi lần Enter gửi 1 request chat; không disable double-click ngoài `sending`; không cache câu trả lời; `fetchChatHistory` gọi lại mỗi khi mở tab.

**Tại sao đây là vấn đề:** Lãng phí request, UX chậm khi lịch sử dài.

**Ảnh hưởng:** UX, chi phí.

**Cách khắc phục:** Debounce, cache history, optimistic UI.

**Độ khó:** Easy

**Ưu tiên:** P3

---

# 12. Testing

---

### W-058 Chỉ 11 test; không có test nào phủ adapter `pipelines.py` (nơi chứa 2 bug critical)

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ⚠️ Partially Fixed (Phase 1 / Task 1, 2026-08-02) — đã thêm `tests/unit/test_pipelines.py` (2 test) bảo vệ `LangGraphQaPipeline.answer`/`history`; phần còn lại (phủ `PgContractVectorSearch`, `PgLegalVectorSearch`, repository, `evaluate_clause`, `parse_contract`) thuộc Task 15 / Phase 7.

**Mức độ:** Critical

**Loại:** Testing

**File liên quan:**
- `tests/` (toàn bộ)
- `app/infrastructure/agents/pipelines.py`
- `tests/integration/test_api.py`

**Bằng chứng:** `test_api.py` chỉ test `/health` và `/models`. Không có test cho `LangGraphQaPipeline.answer`/`history`, `PgContractVectorSearch`, `PgLegalVectorSearch`, `contract_repository`, `risk_flagger.evaluate_clause`, `clause_parser.parse_contract` trên text thật. Đây là lý do W-001/W-002 tồn tại dù "11/11 pass".

**Tại sao đây là vấn đề:** Test suite cho cảm giác an toàn giả; các đường AI/chat/history quan trọng nhất không được bảo vệ.

**Ảnh hưởng:** Độ tin cậy, regression, bảo trì.

**Cách khắc phục:** Thêm unit test cho từng adapter (mock LLM), test analyze/chat/upload với fake repo, integration test end-to-end (testcontainers).

**Độ khó:** Medium

**Ưu tiên:** P0

---

### W-059 Integration test phụ thuộc DB/Neo4j/embedding thật

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Testing

**File liên quan:**
- `tests/integration/test_api.py:7-28`

**Bằng chứng:** `TestClient(app)` kích hoạt lifespan → `apply_postgres_schema()` + `container.graph.ensure_schema()` + `init_checkpointer()`. Test chạy được chỉ khi Docker Postgres/Neo4j đang bật (lỗi bị bắt và log warning, nhưng test vẫn pass một cách "mềm" — không đảm bảo gì).

**Tại sao đây là vấn đề:** Test không chạy được trong CI sạch; kết quả pass không chứng minh luồng hoạt động.

**Ảnh hưởng:** Độ tin cậy của test, CI.

**Cách khắc phục:** Dùng testcontainers hoặc fake adapter cho toàn bộ integration; tách test khỏi hạ tầng thật.

**Độ khó:** Hard

**Ưu tiên:** P2

---

### W-060 Không có benchmark định lượng (golden dataset)

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** Testing

**File liên quan:**
- `tests/` (không có dataset nhãn rủi ro chuẩn)
- `PROGRESS_REPORT.md:87-89` (tự nhận chưa làm)

**Bằng chứng:** `PROGRESS_REPORT.md`: "Chưa có bộ test case với nhãn rủi ro chuẩn (do luật sư/giảng viên gán) để đo accuracy".

**Tại sao đây là vấn đề:** Không có con số chứng minh độ chính xác → không đối chiếu giữa các lần chỉnh prompt/RAG, khó đánh giá cho báo cáo tốt nghiệp.

**Ảnh hưởng:** AI accuracy tracking, giá trị báo cáo.

**Cách khắc phục:** Xây golden set (N hợp đồng mẫu + nhãn critical/warning/ok + trích xuất chuẩn), đo precision/recall sau mỗi thay đổi.

**Độ khó:** Medium

**Ưu tiên:** P1

---

# 13. DevOps

---

### W-061 Không có Dockerfile cho app; docker-compose chỉ có Postgres + Neo4j

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** DevOps

**File liên quan:**
- `docker-compose.yml` (toàn bộ)
- `README.md:15-17`

**Bằng chứng:** `docker-compose.yml` chỉ định nghĩa `postgres` và `neo4j`. App chạy bằng `uvicorn app.main:app` thủ công (`README.md`). Không có `Dockerfile`, không `.dockerignore`.

**Tại sao đây là vấn đề:** Không thể deploy nhất quán; môi trường chạy khác nhau giữa dev/prod; không scale được app.

**Ảnh hưởng:** DevOps, scalability, deployment.

**Cách khắc phục:** Thêm `Dockerfile` (python-slim), thêm service `api` vào compose, tách frontend build multi-stage.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-062 Không có CI/CD

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** High

**Loại:** DevOps

**File liên quan:**
- Không tồn tại `.github/workflows/`, không pipeline nào trong repo (đã xác minh `Test-Path .github` = False)

**Bằng chứng:** Repo không có workflow CI. Không có linter Python (ruff/flake8) config, không pre-commit.

**Tại sao đây là vấn đề:** Lỗi (như W-001/W-002) không bị chặn trước khi merge; chất lượng code phụ thuộc kỷ luật cá nhân.

**Ảnh hưởng:** Chất lượng, regression.

**Cách khắc phục:** GH Actions: pytest + ruff + eslint; chặn merge khi fail.

**Độ khó:** Medium

**Ưu tiên:** P1

---

### W-063 Dependencies không pin version, không lockfile

---

**Trạng thái xác minh:** ⚠️ Partially Correct

**Mức độ:** High

**Loại:** Dependency

**File liên quan:**
- `requirements.txt` (toàn bộ)

**Bằng chứng:** Hầu hết dòng không pin (`fastapi`, `torch`, `langchain`, …). Ngoại lệ: `bcrypt<4.1` (dòng 19). Không có lockfile / `==` pins. Frontend có `package-lock.json` nhưng backend không. Mô tả "không có version" hơi tuyệt đối — vẫn đúng về tinh thần thiếu pin/lock.

**Tại sao đây là vấn đề:** Cài đặt ở thời điểm khác cho phiên bản khác nhau → bug khó tái hiện, breaking change bất ngờ.

**Ảnh hưởng:** Độ tin cậy, bảo trì, security (supply chain).

**Cách khắc phục:** Pin version (`==`), dùng `pip-tools`/`uv` sinh lockfile, dựng image immutable.

**Độ khó:** Easy

**Ưu tiên:** P1

---

### W-064 Không có observability (metrics, tracing)

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Monitoring

**File liên quan:**
- `app/core/logging.py`
- `app/main.py`

**Bằng chứng:** Không có `/metrics`, không OpenTelemetry, không instrument LLM calls, không đo latency/cost per analyze.

**Tại sao đây là vấn đề:** Không biết hệ thống chậm ở đâu, chi phí LLM bao nhiêu, tỷ lệ lỗi.

**Ảnh hưởng:** Vận hành, tối ưu chi phí.

**Cách khắc phục:** Thêm structured logging + metrics (prometheus) + trace cho pipeline.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-065 Crawler phụ thuộc hash Next.js hardcode, dễ stale

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** DevOps

**File liên quan:**
- `scripts/crawl_vbpl/common.py:168`
- `scripts/crawl_vbpl/fetch_list.py:24`
- `scripts/crawl_vbpl/fetch_luoc_do.py:28`

**Bằng chứng:** `DETAIL_NEXT_ACTION = "0fb12b3561faa05adec51a82efb3e4f4f427f07b"`, `NEXT_ACTION = "c529d164f28418e5898a834422629e64c6816af1"`, `RSC_BUILD_ID = "1ok19"`. Docstring tự ghi nhận "WILL go stale when vbpl.vn redeploys".

**Tại sao đây là vấn đề:** Mỗi lần vbpl.vn deploy, toàn bộ crawler hỏng đến khi cập nhật thủ công; pipeline ingest dừng.

**Ảnh hưởng:** Độ tin cậy dữ liệu pháp luật, vận hành.

**Cách khắc phục:** Crawler phát hiện và tự cảnh báo khi hash stale; tách config hash; có fallback HTML parse thường.

**Độ khó:** Medium

**Ưu tiên:** P2

---

# 14. Documentation

---

### W-066 `PROGRESS_REPORT.md` lỗi thời, mô tả kiến trúc FAISS/Supabase đã bị xóa

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Documentation

**File liên quan:**
- `PROGRESS_REPORT.md:10-26`

**Bằng chứng:** Mục 1 mô tả: `app/vectorstore/ (FAISS qua LangChain)`, `knowledge_base/loader.py`, `scripts/load_legal_kb.py`, `core/ (config, database, auth (Supabase JWT))` — tất cả đã bị xóa khỏi source. Báo cáo cũng ghi "helpers/text_normalizer.py dead code" nhưng file này không còn tồn tại (đã xác minh).

**Tại sao đây là vấn đề:** Người đọc dựa vào tài liệu sẽ hiểu sai kiến trúc hiện tại.

**Ảnh hưởng:** Bảo trì, onboarding.

**Cách khắc phục:** Viết lại cho khớp source hiện tại (pgvector/Neo4j/JWT local).

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-067 Các file `docs/*` tham chiếu file đã xóa

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Medium

**Loại:** Documentation

**File liên quan:**
- `docs/architecture-review.md`, `docs/architecture-review.vi.md`, `docs/dfd.md`, `docs/processing-design.md`, `docs/user-flow.md`, `docs/frontend.md`

**Bằng chứng:** `docs/processing-design.md` tham chiếu `app/core/auth.py`, `app/services/contract_service.py`, `app/vectorstore/faiss_store.py`, `app/core/database.py`, `app/core/config.py` — toàn bộ đều không tồn tại trong source hiện tại. `docs/frontend.md` mô tả supabase-js (đã gỡ).

**Tại sao đây là vấn đề:** Tài liệu và code lệch pha nghiêm trọng; dev đọc docs sẽ đi vào ngõ cụt.

**Ảnh hưởng:** Bảo trì, onboarding.

**Cách khắc phục:** Cập nhật hoặc đánh dấu "historical / obsolete" rõ ràng.

**Độ khó:** Medium

**Ưu tiên:** P2

---

### W-068 `.env.example` và `.env` lệch khóa cấu hình

---

**Trạng thái xác minh:** ✅ Confirmed

**Trạng thái triển khai:** ✅ Fixed (Phase 1 / Task 2, 2026-08-02) — đồng bộ `.env.example` với settings; thêm `CORS_ORIGINS`, `NEO4J_*`; xóa khóa chết khỏi `.env`.

**Mức độ:** Low

**Loại:** Configuration

**File liên quan:**
- `.env.example`
- `.env`

**Bằng chứng:** `.env.example` có `JWT_SECRET`, `NEO4J_*`, không có `SUPABASE_*`. `.env` chứa thêm `VECTOR_STORE_DIR`, `LEGAL_KB_BATCH_SIZE`, `LEGAL_KB_ACTIVE_ONLY`, `SUPABASE_*`, `JWT_SECRET_KEY` — các khóa này settings không đọc (`extra="ignore"`, `settings.py:11`). Ngược lại `.env` thiếu `NEO4J_URI/USER/PASSWORD` so với example (settings sẽ dùng default).

**Tại sao đây là vấn đề:** Người dùng copy example thiếu/sai khóa sẽ không biết; khóa chết tạo rác.

**Ảnh hưởng:** Configuration, bảo trì.

**Cách khắc phục:** Đồng bộ `.env.example` với settings; xóa khóa chết.

**Độ khó:** Easy

**Ưu tiên:** P2

---

### W-069 README mô tả tối thiểu, thiếu hướng dẫn frontend build

---

**Trạng thái xác minh:** ✅ Confirmed

**Mức độ:** Low

**Loại:** Documentation

**File liên quan:**
- `README.md`
- `app/main.py:87-92`

**Bằng chứng:** `main.py` mount `frontend/dist` nếu tồn tại. Hiện `frontend/dist` không tồn tại (đã xác minh) → app log warning và không serve frontend. README không hướng dẫn `npm install && npm run build` cho production.

**Tại sao đây là vấn đề:** Chạy theo README không có giao diện; chỉ có API + frontend dev riêng.

**Ảnh hưởng:** UX, onboarding.

**Cách khắc phục:** Thêm bước build frontend vào README/deploy.

**Độ khó:** Easy

**Ưu tiên:** P2

---

# Bảng thống kê

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Architecture | 2 | 1 | 1 | 3 |
| AI | 0 | 3 | 3 | 1 |
| RAG | 0 | 3 | 3 | 2 |
| Prompt | 0 | 0 | 2 | 1 |
| OCR | 0 | 0 | 2 | 0 |
| Backend | 0 | 2 | 2 | 1 |
| Frontend | 0 | 0 | 2 | 2 |
| Database | 0 | 0 | 2 | 2 |
| API | 0 | 2 | 1 | 1 |
| Security | 1 | 2 | 2 | 2 |
| Performance | 0 | 1 | 2 | 2 |
| Testing | 1 | 1 | 1 | 0 |
| DevOps | 0 | 3 | 2 | 0 |
| Documentation | 0 | 0 | 3 | 2 |
| **Tổng** | **4** | **18** | **28** | **19** |

*(Tổng 69 vấn đề: W-001 → W-069)*

---

# Top 20 việc cần làm trước

1. **Sửa bug đảo thứ tự đối số `answer_question`** (`app/infrastructure/agents/pipelines.py:18`) — P0, W-001
2. **Sửa bug `.messages` trên list ở history** (`app/infrastructure/agents/pipelines.py:28`) — P0, W-002
3. **Rotate toàn bộ secrets trong `.env`** (GEMINI_API_KEY, JWT, xóa SUPABASE_SECRET_KEY) — P0, W-049
4. **Sửa CORS `allow_origins=["*"]` + credentials** — P0, W-045
5. **Thêm unit test cho `LangGraphQaPipeline` và các adapter AI/chat** — P0, W-058
6. **Rate limit + quota cho endpoint tốn LLM** (/analyze, /chat) — P1, W-046
7. **Validate JWT secret default khi startup** — P1, W-050
8. **Chuyển schema sang migration (Alembic), bỏ auto-apply** — P1, W-033
9. **Connection pooling cho toàn bộ psycopg2** — P1, W-028 / W-056
10. **Đưa phân tích vào background job/queue, trả job_id** — P1, W-034
11. **Bọc retrieval/embedding vào `asyncio.to_thread`** — P1, W-029
12. **Fix overlap chunking vượt kích thước + điều chỉnh max_chunk_size khớp 512 token** — P1, W-015 / W-016
13. **Xử lý tiếng Việt cho FTS (chuẩn hóa dấu hoặc dictionary vietnamese)** — P1, W-017
14. **Giới hạn kích thước upload + validate MIME thật** — P1, W-044
15. **Upload trả lỗi rõ ràng thay vì 200 khi parse fail** — P1, W-030
16. **Add timeout/retry/circuit breaker cho Gemini + max_tokens** — P1, W-009 / W-010
17. **Guardrails chống prompt injection từ nội dung hợp đồng** — P1, W-008
18. **Xây golden dataset benchmark đo accuracy** — P1, W-060
19. **Thêm CI/CD (pytest + ruff + eslint) và pin dependencies** — P1, W-062 / W-063
20. **Dockerfile cho app + service api trong compose** — P1, W-061

---

*Hết audit gốc. Tổng 69 vấn đề, 4 Critical, 18 High, 28 Medium, 19 Low.*

*Xác minh lại 2026-08-02: 67 ✅ Confirmed · 2 ⚠️ Partially Correct (W-020, W-063) · 0 ❌ Invalid · 0 🔄 Already Fixed. Xem Verification Log ở đầu file và `docs/IMPLEMENTATION_PLAN.md`.*
