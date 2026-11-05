# Kế hoạch refactor và nợ kỹ thuật

Trạng thái ngày 2026-11-05. Phần "Đã thực hiện" chỉ liệt kê thay đổi thật sự đã áp dụng vào mã; mọi thứ khác là **chưa làm**. Các thay đổi đã được commit trên nhánh `refactor/structure-docs` và đã merge (fast-forward) vào `main`.

## Phương pháp
- Import vòng và ma trận phụ thuộc giữa các gói: script AST trên toàn bộ `app/` (gồm import trong hàm).
- Code chết: ứng viên từ CodeGraphContext `find_dead_code`, sau đó **tự xác minh** bằng Serena `find_referencing_symbols` + grep từ khóa toàn repo. Kết quả thô của CodeGraphContext không đáng tin: nó đánh dấu cả hàm đang dùng (`resolve_provider`, mọi route handler, node LangGraph).
- Tách hàm: với mỗi hàm, chạy kiểm tra trên code cũ, refactor, rồi **so sánh vi sai** bản `HEAD` (lấy bằng `git show`) với bản mới trên hàng nghìn kịch bản ngẫu nhiên, dùng repository/search/LLM giả ghi lại mọi lời gọi. Kết quả trả về, chuỗi lời gọi, SQL (so sánh sau khi gộp khoảng trắng) và log phải bằng nhau. Script so sánh nằm ngoài repo (scratchpad), không commit.
- Baseline test ban đầu: 150 passed, 1 skipped, **12 failed**. Hiện tại: **188 passed, 1 skipped, 0 failed**.

## Đã thực hiện

### Đợt 1: code chết và tài liệu
- Xóa `_citation_status` (`legal_citations.py`), `topic_keys_for_risks` (`labor_red_flags.py`) và `flag_risks` (`risk_flagger.py`): 0 tham chiếu (Serena + grep toàn repo). Xóa import thừa phát sinh.
- Thêm `AGENTS.md`, `docs/ARCHITECTURE.md`, `CODEBASE_MAP.md`, `CODING_STANDARDS.md`, `REFACTOR_PLAN.md`, `docs/diagrams/*`.

### Đợt 2: 12 test fail sẵn (chỉ sửa test)
- `test_qa_memory.py` (3 test): fake `retrieve_legal` là `lambda query, k=3` nên vỡ khi `qa_agent.py` truyền `title=`; đổi thành `**kwargs`.
- `test_analysis_retry.py` (4), `test_analysis_review.py` (5): các fake `evaluate_clause` thiếu `job_context`, `skip_topics` (judge ném `TypeError` bị nuốt thành "không có rủi ro"), và bước `deterministic` chạy thật (thêm risk, truy vấn Postgres). Thêm tham số vào fake và fixture `stub_deterministic_checks` (`tests/unit/conftest.py`).

### Đợt 3: 7 lỗi ESLint frontend
- 5 lỗi `react-hooks/set-state-in-effect`: chuyển sang kiểu "điều chỉnh state ngay lúc render"; `AuthContext` bỏ effect, `loading` khởi tạo `false` (không còn khung hình loading lúc mở trang).
- 2 lỗi `only-export-components`: `useSidebarCollapsed`, `shellMainClass` chuyển sang `src/lib/sidebarShell.js`.
- Đã kiểm tay bằng Vite dev + API giả (không dùng DB/Gemini thật): đăng nhập và giữ phiên, thu gọn sidebar, mở hợp đồng tự mở issue critical đầu tiên, đổi hợp đồng về tab báo cáo, tab chat tải lịch sử, drawer mobile đóng khi chuyển mục. **Chưa kiểm được**: nhánh `ChatTab` đổi `contractId` mà không remount, và luồng upload/analyze/stream với backend thật.

### Đợt 4: tách hàm dài, gỡ phụ thuộc ngược, dọn cấu hình
Tách thành hàm private trong cùng file, không đổi chữ ký public:

| Hàm | Trước | Sau | Kiểm tra |
|---|---|---|---|
| `risk_flagger.evaluate_clause` | 163 dòng | 54 (+4 helper, lớn nhất 68) | `tests/unit/test_risk_flagger.py` mới (15 test, chạy xanh trên code cũ trước khi sửa) |
| `LegalGraphRag.retrieve_for_clause` | 189 | 53 (+4 helper) | so sánh vi sai 6000 kịch bản, 0 lệch; thêm 3 test vào `test_graphrag.py` |
| `IngestLegalDocument.execute` | 171 | 60 (+5 helper) | so sánh vi sai 6000 kịch bản, 0 lệch |
| `PgLegalChunkRepository.upsert_nodes` | 204 | 12 (+7 hàm theo level, bảng `_LEVEL_UPSERTS`) | so sánh vi sai 8000 kịch bản (~20.000 câu SQL), 0 lệch; test bảo đảm mọi level có hàm |
| `PgLegalChunkRepository.expand_paths` | 112 | 31 (+6 helper) | so sánh vi sai 8000 kịch bản (~24.000 câu SQL), 0 lệch |

Gỡ phụ thuộc ngược:
- `_parse_as_of` chuyển từ `agents/labor_code_resolver.py` sang `app/core/dates.py` (`parse_as_of`); `effectivity.py`, `preamble_citations.py`, `legal_graph_rag.py` và test cập nhật import. Hết phụ thuộc `infrastructure/retrieval` → `agents`.
- 4 câu SQL thô trong `agents/` (`labor_code_resolver` 3, `preamble_citations` 1) chuyển nguyên văn thành method của repository: `PgLegalDocumentRepository.find_labor_code_row`, `find_row_by_doc_num`, `PgLegalChunkRepository.find_article_chunks` (dùng chung cho `fetch_article_snippet` và `fetch_article_meta`, vốn có cùng SQL); port ở `domain/ports/repositories.py` được bổ sung. Agents lấy repository qua `retrieval/context.py` (`get_legal_docs`, `get_legal_chunks`). Hai getter mặc định trả về repository Postgres không trạng thái khi chưa `bind_retrieval`, nên hành vi cho caller chưa bind (script, test) **không đổi**; thiết kế này tránh việc bắt buộc thêm tham số vào `bind_retrieval`/`main.py`/`evaluation/`. So sánh vi sai 12.000 kịch bản (5.373 câu SQL, gồm cả nhánh DB lỗi), 0 lệch. Thêm 6 test cho các helper này.

Ruff và cấu hình:
- `ruff --select F` sạch trên `app/`, `scripts/`, `evaluation/`: tự sửa 15 import thừa và 3 f-string thừa; xóa tay 6 biến gán mà không dùng (vế phải đều thuần, không có tác dụng phụ).
- Đã thử thêm workflow CI (GitHub Actions) rồi **gỡ lại** theo quyết định của chủ dự án (dự án cá nhân, chạy local); không còn thư mục `.github/`. Các lệnh kiểm tra (ruff `--select F`, pytest, lint/build frontend) vẫn chạy tay được.
- `requirements.txt` thêm `pytest`, `pytest-asyncio`.
- Xóa dòng `tests/` khỏi `.gitignore`; xóa `app/.cgcignore` (CodeGraphContext tự sinh).

## Kết quả kiểm tra không cần sửa
- Không có import vòng ở mức module (script AST).
- Hai file `effectivity.py` (`agents/` và `infrastructure/legal_corpus/`) **không** trùng nhau: một cái đánh giá hiệu lực văn bản theo ngày, một cái nhận diện tiêu đề "Hiệu lực thi hành".
- Hàm trùng thân thật sự: `_safe_print` ở `scripts/ingest_clause_amendments.py` và `scripts/ingest_legal_corpus.py`; `order` ở `evaluation/rag_only.py` và `evaluation/runtime_adapter.py`. Gộp cần module dùng chung giữa script độc lập, lợi ích nhỏ nên **chưa làm**.
- **Hai driver Postgres là có chủ đích, không phải nợ** (đính chính ghi chú trước đây): `psycopg2` là driver của toàn bộ lớp repository và script; `psycopg` v3 bắt buộc cho `AsyncPostgresSaver`/`AsyncPostgresStore` của LangGraph (`agents/checkpointer.py`, `agents/memory.py`), `psycopg_pool` và retry trong `infrastructure/agents/pipelines.py`. Gộp nghĩa là viết lại cả lớp repository sang psycopg3 hoặc bỏ checkpoint LangGraph: rủi ro cao, lợi ích thấp.
- Phụ thuộc `agents/` → `infrastructure/retrieval/{context,query_rewrite,scope_match}` và `vectorstore/retriever.py` là **chấp nhận có chủ đích**: `context.py` được viết riêng để tránh import vòng; `query_rewrite`, `scope_match` là logic thuần không đụng hạ tầng. `document/parser.py` → `agents.llm_client` (OCR ảnh) cũng giữ nguyên.

## Nợ còn lại

| # | Vấn đề | Mức | Ghi chú |
|---|---|---|---|
| 1 | `docs/presentations/` có 6 bản báo cáo gần giống nhau (3 bản `(n)` ~79 KB, 1 bản 40 KB, `.html` 54 KB, `.pptx` 107 KB) | Thấp | Các file chưa được git theo dõi nên xóa là không hoàn tác được; chờ người dùng chọn bản giữ lại |
| 2 | 7 file test chưa từng được git theo dõi (do `tests/` bị ignore trước đây): `tests/evaluation/test_contract_qa_cases.py`, `test_dataset_qa.py`, `tests/fixtures/contract_qa_cases.json`, `legal_qa.jsonl`, `tests/unit/test_effectivity.py`, `test_llm_retry.py`, `test_qa_query_rewrite.py` | Trung bình | Hiện đang chạy trong bộ test local nhưng sẽ **không có trong repo** cho tới khi `git add`; cần người dùng quyết định (một số fixture lớn) |
| 3 | `test_risk_flagger.py`, `src/lib/sidebarShell.js`, `app/core/dates.py` và các file docs là file mới chưa staged; `tests/unit/conftest.py` đã staged | — | Cần `git add` khi commit |
| 4 | Test luồng `workflow.py` stub bước `deterministic`, nên bước đó chỉ được kiểm bởi test riêng của từng checker, không qua đồ thị | Thấp | Thêm một test tích hợp không stub nếu cần |
| 5 | Tests phụ thuộc file trong `data/` (bị `.gitignore`, không có trong git): `test_labor_completeness.py`, `test_labor_red_flags.py`, `test_preamble_citations.py`, `tests/evaluation/test_contract_qa_cases.py` đọc `data/demo_contracts/CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md` (4,7 KB); `test_dataset_qa.py` cần `tests/fixtures/legal_qa.jsonl` (15 MB, sinh bởi `scripts.build_qa_benchmark`) và `evaluation_results/reports/missing_legal_documents.csv` | Thấp | Không ảnh hưởng chạy local. Trên clone mới các test này sẽ fail vì thiếu file; nếu cần thì `git add -f` file demo 4,7 KB, và thêm `skipif` cho `test_dataset_qa.py` |
| 6 | Một số test và script cần DB thật nhưng không đánh dấu riêng | Thấp | Thêm marker `integration`; hiện `tests/integration/` tách riêng |
| 7 | Hàm trùng nhỏ giữa script/evaluation (xem trên) | Rất thấp | Bỏ qua |
| 8 | 7 hàm 81–111 dòng còn lại trong `app/`, ngoài phạm vi đợt này: `check_preamble_citations` (111), `ground_citations` (104), `parse_internal_refs` (102), `parse_clause_amendments` (95), `check_labor_completeness` (87), `load_document_folder` (85), `evaluate_document_effectivity` (81) | Thấp | Tách khi có test hành vi tương ứng; có thể dùng lại cách so sánh vi sai |

## Không thay đổi (cố ý)
Business logic, route và schema request/response, `schema.sql`/`schema.cypher`, auth, SSE streaming, retry, checkpointer, cấu trúc thư mục `app/` (chỉ thêm `app/core/dates.py`).

## Rủi ro hồi quy
- Bằng chứng không đổi hành vi cho phần tách hàm và chuyển SQL là so sánh vi sai với fake, không phải chạy trên Postgres/Neo4j/Gemini thật. Các câu SQL được so sánh sau khi gộp khoảng trắng; ngữ nghĩa SQL không phụ thuộc thụt lề, nhưng chưa chạy trên DB thật.
- Integration test (`tests/integration/test_api.py`, 2 test, chỉ kiểm `/health` và `/api/v1/models`) chạy xanh **sau đợt 4** (2 passed, ~80s); chúng khởi động cả app nên xác nhận toàn bộ import hoạt động, nhưng không đi qua upload/analyze/chat.
- **Đã chạy đầu-cuối sau đợt 4** (backend từ working tree trên cổng 8001, trỏ vào Postgres/Neo4j Docker thật có corpus 137.151 văn bản / ~1M embedding, Gemini thật, hợp đồng demo chuyển sang `.docx`): đăng ký, upload (6 chunk), analyze (34–36s, 5 điều khoản, 6 risk: 4 critical + 2 warning, 6/6 có trích dẫn pháp luật), phân tích lại trả kết quả đã lưu, danh sách hợp đồng, chat JSON, chat SSE (`step`×3 + `done`), lịch sử (2 tin), checkpoint (10 state), 404 với hợp đồng không tồn tại, 401 khi thiếu token: 13/13 bước đạt. Giới hạn: một hợp đồng mẫu duy nhất; chưa so sánh với bản code cũ (LLM không tất định); phần `review_mode`/`resume`, `rewind` và giao diện thật được thử ở hai mục ngay dưới. Nhật ký backend chỉ có cảnh báo/lỗi mức ứng dụng (loại bỏ điều khoản trích dẫn không xác minh được ở bước hỏi đáp; truy vấn pháp luật rỗng với 2 câu hỏi), không có exception. Các lần chạy test để lại 3 tài khoản test trong DB local (`e2e-refactor-test@example.com`, `e2e-refactor-run2@example.com`, `e2e-ui@example.com`), mỗi tài khoản 1 hợp đồng.
- **Chạy lại trên container Docker thật** sau `docker compose restart api` (không rebuild: `./app` được bind-mount vào container nên container nạp code mới khi khởi động lại; `./frontend/src` cũng được mount nên Vite dev dùng code mới ngay): script 13 bước qua `localhost:8010` đạt 13/13 với cùng kết quả (5 điều khoản, 6 risk). Trên giao diện thật `localhost:5173`: đăng nhập, danh sách hợp đồng, mở hợp đồng (issue critical đầu tiên tự mở, căn cứ pháp luật hiện kèm trạng thái hiệu lực), tab hỏi đáp tải lịch sử, gửi câu hỏi mới qua SSE (hiện bước "Đang truy hồi…", trả lời trích dẫn Điều 17 BLLĐ và Điều 3.2(ii) hợp đồng), thu gọn sidebar rồi reload vẫn giữ trạng thái và phiên đăng nhập.
- **Cổng duyệt (review) và rewind trên container thật**: `review_mode` dừng với bản nháp (6 risk, 35s) và không lưu gì; `resume` từ chối trả `review_rejected` và không lưu; `resume` chấp nhận lưu đúng 6 risk; `resume` kèm `edits` thay risk bằng bản người duyệt; khôi phục bằng `force` về 6 risk; `rewind` tới checkpoint trả đúng snapshot, checkpoint lạ trả 404, chat với `checkpoint_id` rẽ nhánh được. Quan sát (hành vi cũ, không do refactor): `resume` với `review_id` không tồn tại trả **500** thay vì 4xx rõ ràng; câu hỏi sau khi rẽ nhánh trả lời ngắn (65 ký tự), có vẻ là câu trả lời "không đủ ngữ cảnh" (chưa xác minh).
