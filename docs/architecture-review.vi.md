# ContractLens — Rà soát Kiến trúc & Cơ sở dữ liệu ở mức Production

**Phạm vi rà soát:** toàn bộ repository `D:\contract-agent` tại commit `a92dd52`, file `schema.sql` chưa được track, và thư mục output của crawler chưa được track `Nghị định số 168-2024-NĐ-CP …`.

**Cập nhật hướng kiến trúc (sau rà soát ban đầu):** **Postgres** = SoT nền (metadata, content, embeddings, audit, transaction); **Neo4j** = SoT quan hệ (cây traversal, `luoc_do`, dẫn chiếu) phục vụ GraphRAG. **Điểm map duy nhất:** `doc_id`, `section_id`. Không nhân bản bảng cạnh trong Postgres. FAISS và Supabase bị loại; DB chạy Docker Compose.

**Phương pháp:** đã đọc toàn bộ mọi file source được track, test, config, tài liệu, và mọi artifact của crawler. Các khẳng định về cấu trúc dữ liệu crawl được tạo ra bằng cách **chạy script đo lường** trên chính file JSON/Markdown thực tế, không phải đọc mẫu. Các khẳng định về hành vi thư viện được kiểm chứng trực tiếp trên source của package **đã cài đặt** (`langchain-community 0.4.1`, `langchain 1.3.1`).

**Nhãn tri thức dùng xuyên suốt tài liệu:**

| Nhãn | Ý nghĩa |
|---|---|
| **THỰC TẾ** | Quan sát được trực tiếp trong code, SQL, config, hoặc dữ liệu đã đo. Có dẫn chứng. |
| **SUY LUẬN** | Suy ra một cách logic từ các sự thật. Có trình bày lập luận. |
| **ĐỀ XUẤT** | Phán đoán kỹ thuật của tôi. Có nêu trade-off và phương án thay thế. |
| **CHƯA RÕ** | Không thể xác định được từ repository. Được nêu rõ ràng, tuyệt đối không phỏng đoán. |

**Những điều CHƯA RÕ ở phạm vi toàn cục giới hạn bản rà soát này** (nêu trước để không có kết luận nào âm thầm dựa trên phỏng đoán):

1. **Không có quyền truy cập database thật.** `.env` không tồn tại (đã kiểm chứng). Vì vậy mọi phát biểu về schema **đang chạy** đều là suy luận từ DDL trong code. Mục tiêu hạ tầng là Postgres/Neo4j trên Docker — chưa có `docker-compose.yml` trong repo (BƯỚC 1). Ở những chỗ DDL trong code và `schema.sql` không khớp nhau, tôi báo cáo sự không khớp thay vì tự chọn bên nào đúng.
2. **Không có source code của crawler trong repository này.** Đã kiểm chứng: `git ls-files` không trả về bất kỳ module crawler, scraper, hay ingestion nào. Chỉ có **output** của crawler. Các phát biểu về hành vi crawler là suy luận từ hình dạng output của nó.
3. **Chỉ có duy nhất một văn bản đã crawl** (`doc_id=173920`). Mọi thống kê về kích thước và cấu trúc theo từng văn bản đều là **mẫu đơn lẻ**. Những phép ngoại suy lên 100k/1M văn bản đều được gắn nhãn ở chỗ cỡ mẫu có ảnh hưởng.
4. **`docs/dfd.md`, `docs/frontend.md`, `docs/user-flow.md`, `docs/processing-design.md` và `schema.sql` đều chưa được track** (`git status`). Chúng là *ý định thiết kế*, không phải hợp đồng đã commit. Ở chỗ chúng trái với code, code thắng cho "trạng thái hiện tại" và tài liệu được coi là trạng thái *dự kiến*.

---

# MỤC LỤC

- [BƯỚC 1 — Kiểm kê repository](#bước-1--kiểm-kê-repository)
- [BƯỚC 2 — Giải thích hệ thống và toàn bộ các luồng](#bước-2--giải-thích-hệ-thống-và-toàn-bộ-các-luồng)
- [BƯỚC 3 — Đồ thị phụ thuộc](#bước-3--đồ-thị-phụ-thuộc)
- [BƯỚC 4 — Rà soát code đầy đủ (vấn đề I-1 … I-41)](#bước-4--rà-soát-code-đầy-đủ)
- [BƯỚC 5 — Phân tích database và dữ liệu crawler](#bước-5--phân-tích-database-và-dữ-liệu-crawler)
- [BƯỚC 6 — Đánh giá phản biện: PostgreSQL + pgvector + ltree + Neo4j](#bước-6--đánh-giá-phản-biện-postgresql--pgvector--ltree--neo4j)
- [BƯỚC 7 — Kiến trúc mục tiêu](#bước-7--kiến-trúc-mục-tiêu)
- [BƯỚC 8 — Thiết kế schema PostgreSQL](#bước-8--thiết-kế-schema-postgresql)
- [BƯỚC 9 — Chiến lược pgvector](#bước-9--chiến-lược-pgvector)
- [BƯỚC 10 — Thiết kế ltree](#bước-10--thiết-kế-ltree)
- [BƯỚC 11 — Thiết kế Neo4j (GraphRAG)](#bước-11--thiết-kế-neo4j-graphrag)
- [BƯỚC 12 — Đồng bộ hoá và tính nhất quán](#bước-12--đồng-bộ-hoá-và-tính-nhất-quán)
- [BƯỚC 13 — Ước lượng khả năng mở rộng](#bước-13--ước-lượng-khả-năng-mở-rộng)
- [BƯỚC 14 — Lộ trình refactor](#bước-14--lộ-trình-refactor)

---

# BƯỚC 1 — Kiểm kê repository

**THỰC TẾ.** 76 file được track + 5 đường dẫn chưa track. Lịch sử git có 3 commit (`b01cd39` initial, `4fcea5c` update, `a92dd52` flowchart md).

```
D:\contract-agent
├── app/                              # Backend FastAPI (Python)
│   ├── main.py                       # app factory, CORS, startup/shutdown, mount static
│   ├── api/routes.py                 # 6 REST endpoint dưới /api/v1
│   ├── core/
│   │   ├── config.py                 # env → biến global cấp module + logging
│   │   ├── database.py               # psycopg2 tạo connection mỗi lần gọi + init_db() DDL
│   │   ├── auth.py                   # HIỆN TẠI: introspect JWT Supabase qua HTTP — MỤC TIÊU: verify JWT tự host (bỏ Supabase)
│   │   └── prompts.py                # 5 prompt template (tiếng Anh, output tiếng Việt)
│   ├── schemas/contract.py           # 10 model Pydantic
│   ├── agents/
│   │   ├── workflow.py               # graph phân tích LangGraph (extract → fan-out judge → aggregate)
│   │   ├── clause_parser.py          # extractor rule-based 485 dòng + LLM điền chỗ trống
│   │   ├── risk_flagger.py           # RAG theo từng điều khoản + LLM phán quyết tuân thủ
│   │   ├── qa_agent.py               # graph QA LangGraph (retrieve → route → generate/từ chối)
│   │   ├── llm_client.py             # singleton Gemini
│   │   ├── checkpointer.py           # AsyncPostgresSaver + pool psycopg
│   │   └── json_parsing.py           # trích JSON trong code fence
│   ├── document/
│   │   ├── parser.py                 # docx / pdf / ảnh (Gemini OCR)
│   │   ├── chunker.py                # splitter đệ quy nhận biết điều khoản
│   │   └── file_handler.py           # allowlist theo đuôi file + ghi đĩa
│   ├── vectorstore/
│   │   ├── faiss_store.py            # wrapper FAISS, 2 singleton toàn process
│   │   ├── embeddings.py             # singleton HuggingFaceEmbeddings
│   │   └── retriever.py              # 2 hàm truy hồi
│   ├── knowledge_base/loader.py      # rebuild KB pháp luật từ Postgres → FAISS
│   ├── services/contract_service.py  # điều phối + kiểm tra quyền sở hữu
│   └── helpers/text_normalizer.py    # CODE CHẾT (0 nơi import)
├── scripts/load_legal_kb.py          # entry CLI cho việc rebuild KB
├── tests/                            # 11 test (4 integration, 7 unit)
├── frontend/                         # React 19 + Vite 8 + Tailwind 3; HIỆN TẠI supabase-js — MỤC TIÊU: auth JWT tự host
├── requirements.txt                  # 21 dependency, KHÔNG pin version nào
├── .env.example                      # 15 khoá cấu hình
├── schema.sql                        # CHƯA TRACK — schema pgvector, không khớp với code
├── docs/                             # CHƯA TRACK (3/4) — DFD, frontend, user flow, processing design
└── Nghị định số 168-2024-NĐ-CP …/    # CHƯA TRACK — output crawler, 4 file
    ├── thuoc_tinh.json               #    700 B  — thuộc tính văn bản
    ├── luoc_do.json                  #  6.4 KB  — đồ thị quan hệ (15 loại × 2 hướng)
    ├── muc_luc.json                  #  474 KB  — cây mục lục, 1308 node
    └── van_ban.md                    #  364 KB  — toàn văn với anchor id nội tuyến
```

**THỰC TẾ — hạ tầng còn thiếu.** Không có `Dockerfile`, không `docker-compose.yml`, không CI workflow, không `pyproject.toml`/`setup.cfg`/`pytest.ini`, không công cụ migration (Alembic/Flyway/sqitch), không `.dockerignore`, không config linter/formatter cho Python, không pre-commit config, không artifact OpenAPI spec, không bộ load-test, không config observability. **ĐỀ XUẤT mục tiêu:** `docker-compose.yml` chạy `postgres` (pgvector), `neo4j`, `minio`, (tuỳ chọn) `api`/`worker` — không phụ thuộc Supabase.

**THỰC TẾ — code mà tài liệu hàm ý nhưng không tồn tại.** Không có crawler, không có parser cho `van_ban.md`/`muc_luc.json`/`luoc_do.json`, không có pipeline ingestion ghi vào `legal_documents` hay `legal_document_sections`, không có code trích xuất tham chiếu, không có scheduler, không có queue worker. Đường ingestion duy nhất trong code là `app/knowledge_base/loader.py`, và nó **đọc** các bảng pháp luật mà không có gì trong repository này **ghi** vào.

**SUY LUẬN.** Repository chứa một sản phẩm rà soát hợp đồng đang hoạt động, cộng với *output và schema mục tiêu* của một hệ thống con về kho văn bản pháp luật riêng biệt, chưa được tích hợp. Bản rà soát phải coi đây là hai hệ thống ở hai mức độ trưởng thành rất khác nhau.

---

# BƯỚC 2 — Giải thích hệ thống và toàn bộ các luồng

## 2.0 Kiến trúc như đang được xây dựng

**THỰC TẾ.** Sơ đồ dưới đây mô tả **code hiện tại** (vẫn gọi Supabase Auth + Postgres qua `DATABASE_URL`, FAISS local). **Kiến trúc mục tiêu** ở BƯỚC 7 thay toàn bộ bằng Docker Compose (Postgres/pgvector + Neo4j + MinIO) và **bỏ Supabase**.

```mermaid
graph TB
    subgraph Browser
      UI[React 19 SPA<br/>máy trạng thái App.jsx]
      SB[supabase-js<br/>HIỆN TẠI — sẽ bỏ]
    end
    subgraph FastAPI["Process FastAPI (đơn lẻ, có state)"]
      R[api/routes.py]
      A[core/auth.py]
      S[services/contract_service.py]
      W[agents/workflow.py<br/>LangGraph]
      Q[agents/qa_agent.py<br/>LangGraph]
      E[vectorstore/embeddings.py<br/>SentenceTransformer trong process]
      F1[(FAISS 'contracts'<br/>singleton toàn process)]
      F2[(FAISS 'legal'<br/>singleton toàn process)]
    end
    subgraph External
      SA[Supabase Auth<br/>HIỆN TẠI — sẽ bỏ]
      G[Gemini 2.5 Flash]
      PG[(PostgreSQL<br/>HIỆN TẠI qua DATABASE_URL)]
      FS[(Đĩa local<br/>data/uploads, data/vector_store)]
    end
    UI --> SB --> SA
    UI -->|Bearer JWT| R --> A -->|HTTP mỗi request| SA
    R --> S --> W & Q
    S --> PG
    W & Q --> G
    W & Q --> F1 & F2
    F1 & F2 --> E
    F1 & F2 <--> FS
    S --> FS
    Q -->|checkpoint| PG
```

**THỰC TẾ — process có state.** `app/vectorstore/faiss_store.py:80-95` giữ hai singleton cấp module; `app/vectorstore/embeddings.py:5` giữ cái thứ ba. Trạng thái vector nằm trong bộ nhớ process và trên filesystem local của chính process đó, không phải trong một store dùng chung.

## 2.1 Luồng request (tổng quát)

| # | Bước | Vị trí |
|---|---|---|
| 1 | Browser gắn `Authorization: Bearer <access_token>` (HIỆN TẠI: token Supabase) | `frontend/src/api.js:5-9` |
| 2 | FastAPI resolve `Depends(get_current_user_id)` | `app/api/routes.py:30,40,50,58,68` |
| 3 | HIỆN TẠI: `httpx.AsyncClient` **mới** gọi `GET {SUPABASE_URL}/auth/v1/user` — MỤC TIÊU: verify JWT local, không gọi Supabase | `app/core/auth.py:13-17` |
| 4 | Không phải 200 → 401; lỗi transport → 503 | `app/core/auth.py:18-23` |
| 5 | Route uỷ quyền cho một hàm service | `app/api/routes.py` |
| 6 | Service kiểm tra quyền sở hữu bằng một connection psycopg2 mới | `contract_service.py:23-33` |
| 7 | Business logic chạy; exception được map `ValueError→404`, còn lại `→500 detail=str(e)` | `routes.py:43-46` v.v. |

**THỰC TẾ.** Auth tốn một vòng HTTPS ra ngoài cho **mỗi** lần gọi API, không có xác thực chữ ký JWT tại local và không có cache. `httpx.AsyncClient` được tạo rồi hủy mỗi lần gọi, nên không tái dùng session TLS hay connection.

## 2.2 Luồng upload / lập chỉ mục

Entry: `POST /api/v1/upload` → `routes.upload` → `contract_service.upload_contract`.

| Thứ tự | Hàm | File:dòng | Ghi chú |
|---|---|---|---|
| 1 | `save_upload` | `document/file_handler.py:21-29` | `validate_file` allowlist theo đuôi file; `contract_id = uuid4()`; **`content = await file.read()` nạp toàn bộ body vào RAM**; ghi `data/uploads/<uuid><ext>` |
| 2 | `parse_document` | `document/parser.py:58-66` | phân nhánh theo đuôi file |
| 2a | `parse_docx` | `parser.py:1-16` | các paragraph rồi bảng được làm phẳng thành `a \| b \| c` |
| 2b | `parse_pdf` | `parser.py:19-32` | `pdfplumber`, chỉ lớp text, không fallback OCR |
| 2c | `parse_image` | `parser.py:35-55` | base64 → Gemini Vision với `OCR_PROMPT` |
| 3 | `chunk_by_clause` | `document/chunker.py:44-105` | cắt theo `Điều|ĐIỀU|Khoản|KHOẢN\s+\d+[.:\-)]`; đoạn quá dài đi qua `_split_text`; fallback toàn văn nếu chỉ tìm được phần mở đầu |
| 4 | `get_contract_collection().add_documents(docs)` | `faiss_store.py:47-60` | embed dưới `threading.Lock`, rồi `save_local()` **ghi lại toàn bộ file index** |
| 5 | Upsert dòng | `contract_service.py:53-58` | `ON CONFLICT (contract_id) DO UPDATE` |

**THỰC TẾ.** Bước 2–4 được bọc trong `try/except Exception` (`contract_service.py:42-51`) chỉ log rồi tiếp tục. Parse thất bại vẫn trả về HTTP 200 với `status="uploaded"`.

**THỰC TẾ.** Chunk chỉ được ghi vào FAISS. Không có gì trong `app/` ghi vào bảng `contract_chunks`, mặc dù `schema.sql:69-81` định nghĩa bảng đó.

## 2.3 Luồng phân tích

Entry: `POST /api/v1/analyze` → `contract_service.analyze_contract:86-107`.

```
_assert_owns_contract            → connection DB #1
if not force: _load_cached_analysis → connection DB #2 (trả về sớm nếu hit)
get_contract_collection().get(where={"contract_id": …})   ← QUÉT TOÀN BỘ trong RAM tất cả hợp đồng
full_text = "\n".join(documents)
run_analysis_workflow(...)
_save_analysis_result            → connection DB #3
```

Graph LangGraph (`agents/workflow.py:74-82`):

```
START → extract ──┬─(Send mỗi điều khoản, max_concurrency=4)→ judge_clause → aggregate → END
                  └─(không có điều khoản)──────────────────────────────────→ aggregate
```

- `_extract_node:33-40` → `asyncio.to_thread(parse_contract, …)`.
  - `parse_contract:453-484` chạy ~15 nhóm extractor regex, rồi `_fill_gaps_with_llm:419-450` gọi Gemini **một** lần trên `text[:12000]` và chỉ điền những field mà regex để trống.
- `_judge_clause_node:55-67` → `asyncio.to_thread(evaluate_clause, …)`.
  - `evaluate_clause:10-61` xây query từ `title + summary`, gọi `retrieve_legal(query, k=3)` với `min_score=0.6`. **Nếu truy hồi rỗng thì trả về một RiskItem `warning` mà không gọi LLM** (`risk_flagger.py:20-30`) — một sự từ chối có chủ ý. Ngược lại một lần gọi Gemini, retry một lần nếu JSON không parse được.
- `_aggregate_node:70-71` trả về `{}`; nó tồn tại chỉ để làm điểm hợp nhất cho reducer `operator.add` trên `risks`.

**THỰC TẾ — số lần gọi LLM cho mỗi lần phân tích không cache** = 1 lần extraction + (1 hoặc 2) cho mỗi điều khoản có căn cứ pháp lý. Với hợp đồng 20 điều khoản: 21–41 lần gọi Gemini, 4 lần song song.

## 2.4 Luồng truy hồi / tìm kiếm

```
retriever.retrieve_contract(q, contract_id, k=None)   # retriever.py:7-15
  → FaissStore.similarity_search(q, k=TOP_K_RETRIEVAL(5), where={"contract_id": …})  # KHÔNG min_score, có chủ ý
retriever.retrieve_legal(q, k=3)                      # retriever.py:18-19
  → FaissStore.similarity_search(q, k=3, min_score=SIMILARITY_THRESHOLD(0.6))
```

**THỰC TẾ (đã kiểm chứng trên `langchain_community 0.4.1` đã cài).** `FAISS.similarity_search_with_score_by_vector` thực thi:

```python
scores, indices = self.index.search(vector, k if filter is None else fetch_k)   # fetch_k mặc định = 20
...
if filter is not None: ... filter_func(doc.metadata) ...
return docs[:k]
```

Lọc metadata là **hậu kiểm trên top-`fetch_k`=20 toàn cục**. Xem vấn đề **I-1**; đây là khiếm khuyết có hệ quả lớn nhất trong toàn hệ thống.

**THỰC TẾ.** Ngữ nghĩa similarity là đúng: `encode_kwargs={"normalize_embeddings": True}` (`embeddings.py:22`) + `DistanceStrategy.MAX_INNER_PRODUCT` (`faiss_store.py:55`) = cosine, và code FAISS đã cài chọn `operator.ge` cho ngưỡng MAX_INNER_PRODUCT. Vậy `min_score=0.6` đúng nghĩa "cosine ≥ 0.6" như dự định.

## 2.5 Luồng chat / QA

Entry: `POST /api/v1/chat` → `qa_agent.answer_question:170-181`, `thread_id = contract_id`.

```
START → retrieve ─(_has_context)→ generate → END
                └─(ngược lại)───→ refusal  → END
```

- `_retrieve_node:58-73` — cả hai retriever; cắt context xuống 8000/3000 ký tự; ghi lại `_valid_clause_numbers`.
- `_generate_node:88-146` — `trim_messages(messages[:-1], max_tokens=2000, strategy="last")` là chính sách loại bỏ bộ nhớ; system prompt + history đã cắt + human message vừa dựng; retry một lần nếu JSON không parse được; **xác minh trích dẫn** loại bỏ mọi phần tử `cited_clauses` không có trong `_valid_clause_numbers` (`:134-139`).
- `get_conversation_history:184-208` phát lại toàn bộ danh sách message đã checkpoint và ghép cặp Human/AI.

**THỰC TẾ.** Persistence dùng LangGraph `AsyncPostgresSaver` trên `psycopg_pool.AsyncConnectionPool` với `prepare_threshold=None` (`checkpointer.py:20-32`) — một xử lý đúng và không hiển nhiên cho chế độ pooling transaction của Supavisor.

## 2.6 Luồng ingestion kho tri thức pháp luật

Entry: `python scripts/load_legal_kb.py` → `knowledge_base/loader.load_legal_documents:16-58`.

```sql
SELECT dc.chunk_ref, dc.doc_id, dc.chunk_index, dc.chunk_text, dc.section_type,
       ld.title, ld.doc_number, ld.category
FROM document_chunks dc JOIN legal_documents ld ON ld.doc_id = dc.doc_id
WHERE ld.status_flag = 1
ORDER BY dc.doc_id, dc.chunk_index
```

Named cursor phía server, `itersize=256`, gọi `collection.reset()` trước (rebuild toàn bộ), `persist=False` mỗi batch và một lần `save()` ở cuối.

**THỰC TẾ — query này không thể chạy được với `schema.sql`.** So từng cột:

| Query tham chiếu | Có trong `schema.sql`? | Tên thực tế ở đó |
|---|---|---|
| `document_chunks` (bảng) | **Không** | `legal_document_sections` (`schema.sql:40`) |
| `dc.chunk_ref` | Không | — |
| `dc.chunk_index` | Không | `order_index` (`:46`) |
| `dc.chunk_text` | Không | `content` (`:48`) |
| `dc.section_type` | Không | `level` (`:44`) / `ptype` (`:45`) |
| `ld.doc_number` | **Không** | `doc_num` (`:8`) |
| `ld.category` | Không | `majors[]` / `fields[]` (`:11-12`) |
| `ld.status_flag` | **Không** | `eff_status_code` (`:17`) |

Xem **I-2**.

## 2.7 Tương tác frontend ↔ backend

**THỰC TẾ.** `frontend/src/App.jsx` là một máy trạng thái 4 trạng thái điều khiển bởi ba biến: `loading` → trắng; `!session` → `LoginScreen`; `result` → `AnalysisResult`; `view` → `UploadScreen` | `ContractListScreen`. Không có router; không deep link; refresh là mất hợp đồng đang mở.

**THỰC TẾ.** Mở một hợp đồng đã có sẽ gọi `analyzeContract(contract.contract_id)` (`App.jsx:67`) — nghĩa là một hành động *đọc* lại được biểu diễn bằng `POST /api/v1/analyze`. Nó trả về dòng đã cache khi hit nhưng kích hoạt cả một lượt chạy nhiều LLM khi miss. Xem **I-24**.

## 2.8 Background job, scheduled job, cache, xử lý lỗi

| Hạng mục | Trạng thái | Dẫn chứng |
|---|---|---|
| Background job | **Không có.** Không BackgroundTasks, Celery, RQ, arq, hay worker process. Toàn bộ công việc LLM chạy đồng bộ trong request. | không tồn tại trong toàn `app/` |
| Scheduled job | **Không có.** Rebuild KB là chạy CLI thủ công. | `scripts/load_legal_kb.py`; `docs/dfd.md:466` |
| Cache — phân tích | Cột JSONB `analysis`, `risks` trong Postgres; `force=true` để bỏ qua. Không TTL, không invalidate khi KB đổi. | `contract_service.py:63-84` |
| Cache — bộ nhớ chat | Bảng checkpoint LangGraph; chỉ cắt xuống 2000 token lúc tạo prompt. | `qa_agent.py:94-99` |
| Cache — embedding / LLM | **Không có.** Cùng một đoạn điều khoản vẫn embed lại và prompt lại mỗi lần chạy. | — |
| Xử lý lỗi | `try/except` ở tầng route; `ValueError→404`; `Exception` trần `→500 detail=str(e)`. Upload nuốt lỗi parse. Không phân loại lỗi, không correlation id, không retry/backoff với Gemini hay Postgres. | `routes.py:31-74`, `contract_service.py:42-51` |
| Logging | Một root logger ra stdout, mức INFO. Có cấu trúc kiểu chuỗi f-string, không JSON, không request id, không trace context. `logger.error` bị dùng cho những việc không phải lỗi (ví dụ trích dẫn bị loại, `qa_agent.py:139`). | `core/config.py:27-33` |

---

# BƯỚC 3 — Đồ thị phụ thuộc

## 3.1 Đồ thị phụ thuộc module (import thực tế)

```
app.main
 ├→ app.agents.checkpointer ─→ app.core.config
 ├→ app.api.routes
 │   ├→ app.agents.llm_client ─→ app.core.config
 │   ├→ app.core.auth        ─→ app.core.config
 │   ├→ app.schemas.contract
 │   └→ app.services (barrel) ─→ app.services.contract_service
 │        ├→ app.core.config
 │        ├→ app.core.database        ─→ app.core.config
 │        ├→ app.schemas.contract
 │        ├→ app.document.file_handler ─→ app.core.config
 │        ├→ app.document.parser       ─→ (lazy) app.agents.llm_client, app.core.prompts
 │        ├→ app.document.chunker      ─→ app.core.config
 │        ├→ app.vectorstore.faiss_store ─→ app.core.config, app.vectorstore.embeddings
 │        ├→ app.agents.workflow
 │        │    ├→ app.agents.clause_parser ─→ app.core.prompts, app.agents.llm_client,
 │        │    │                              app.agents.json_parsing, app.schemas.contract
 │        │    ├→ app.agents.risk_flagger  ─→ app.core.prompts, app.agents.llm_client,
 │        │    │                              app.agents.json_parsing,
 │        │    │                              app.vectorstore.retriever
 │        │    └→ app.agents.llm_client
 │        ├→ app.agents.qa_agent
 │        │    ├→ app.agents.checkpointer
 │        │    ├→ app.agents.llm_client, app.agents.json_parsing
 │        │    ├→ app.core.prompts, app.schemas.contract
 │        │    └→ app.vectorstore.retriever ─→ app.vectorstore.faiss_store
 │        └→ app.agents.llm_client
 └→ app.core.{config,database}

app.knowledge_base.loader ─→ app.core.{config,database}, app.vectorstore.faiss_store
      ↑ nơi import duy nhất: scripts/load_legal_kb.py

app.helpers.text_normalizer ← KHÔNG AI IMPORT
```

**Phân tầng, từ trên xuống:** `main` → `api` → `services` → {`agents`, `document`, `vectorstore`} → {`core`, `schemas`}.

## 3.2 Phụ thuộc vòng

**THỰC TẾ: không có ở cấp module.** `app/document/parser.py:35-40` import `app.agents.llm_client` *bên trong* `parse_image`, một import trì hoãn mà tình cờ cũng tránh được cạnh `document → agents` ở thời điểm import.

**SUY LUẬN.** Import trì hoãn đó tuy vậy vẫn là một **vi phạm phân tầng**: `document/` (tầng trích xuất văn bản thuần cơ học) vươn lên `agents/` (tầng AI) và vào `core/prompts`. Phụ thuộc đó tồn tại, chỉ là vô hình với đồ thị import tĩnh.

## 3.3 Phụ thuộc ẩn

| # | Phụ thuộc ẩn | Dẫn chứng | Hệ quả |
|---|---|---|---|
| H-1 | Singleton FAISS toàn process, mutable, là phụ thuộc dùng chung ngầm của `services`, `agents`, `knowledge_base` | `faiss_store.py:80-95` | Không module nào test hay scale độc lập được; hai uvicorn worker sẽ âm thầm phân kỳ |
| H-2 | `core/config.py` gây **side effect lúc import**: `os.makedirs` ×2 và `logging.basicConfig` | `config.py:24-32` | Import bất cứ thứ gì cũng tạo thư mục và chiếm quyền root logging; không tránh được trong test |
| H-3 | Thay đổi event-loop policy toàn cục lúc import | `main.py:9-10` | Bất kỳ ai import `app.main` (ví dụ `tests/integration/test_api.py:2`) đều bị đổi loop policy |
| H-4 | `qa_agent._get_graph()` phụ thuộc việc `init_checkpointer()` đã chạy trước đó | `qa_agent.py:161-167`, `checkpointer.py:44-47` | Ràng buộc thời gian chỉ được thực thi bằng một `RuntimeError` lúc runtime |
| H-5 | `services` phụ thuộc kiểu cột thực tế của DB đang deploy, thứ mà `init_db()` chỉ kiểm soát một phần | `database.py:27-49` vs `schema.sql:71` | Xem I-3 |
| H-6 | `loader.py` phụ thuộc các bảng mà không code nào trong repo tạo ra | `loader.py:6-13` | KB pháp luật không thể được build chỉ từ repository này |
| H-7 | Tính đúng đắn của `retrieve_legal` phụ thuộc việc FAISS store `legal` đã được build từ bên ngoài | `retriever.py:18-19` | Trên một deploy mới `_store is None` → mọi điều khoản trả về cảnh báo "không đủ căn cứ", và sản phẩm âm thầm suy thoái thành "không phân tích" trong khi vẫn báo thành công |

**H-7 là nguy hiểm nhất về mặt vận hành**: `faiss_store.similarity_search:74-75` trả về `[]` khi `_store is None`, và `risk_flagger.py:20-30` biến điều đó thành một cảnh báo trông rất hợp lý hiển thị cho người dùng. Một kho tri thức bị thiếu là **không thể phân biệt** với một điều khoản thực sự không có căn cứ pháp lý.

## 3.4 Module gắn kết quá chặt

| Gắn kết | Dẫn chứng | Vì sao gây hại |
|---|---|---|
| `contract_service` ↔ nội bộ FAISS | `contract_service.py:96` gọi `.get(where=…)`, mà cách hiện thực của nó đọc `self._store.docstore._dict` (`faiss_store.py:65`) | Tầng service bị gắn vào một attribute private của thư viện bên thứ ba. Đổi vector store là phải sửa cả service. |
| `agents` ↔ vector store cụ thể | `risk_flagger.py:7`, `qa_agent.py:14` import hàm cụ thể, không phải interface | Không có đường ráp để test hay để làm hybrid retriever |
| `services` ↔ chuỗi SQL psycopg2 | 5 câu SQL nội tuyến trong `contract_service.py` | Không có tầng repository; đổi schema là lan vào business logic |
| Mọi thứ ↔ biến global của `core.config` | 9 module import hằng số cấp module | Config không thể override theo request/test/tenant mà không monkeypatch |
| State LangGraph ↔ payload truy hồi | `QAState` mang `_contract_context`, `_legal_context` (`qa_agent.py:35-36`) | Những payload đó bị checkpoint vào Postgres mỗi lượt — xem I-14 |

## 3.5 Code chết

| Hạng mục | Dẫn chứng |
|---|---|
| Toàn bộ `app/helpers/text_normalizer.py` (3 hàm) | grep khắp `app/`, `scripts/`, `tests/`: không nơi nào import |
| `risk_flagger.flag_risks` (`:64-75`) | không nơi nào import; docstring nói "dùng ngoài async workflow (ví dụ test, script)" — không có test hay script nào dùng |
| `ON CONFLICT (contract_id) DO UPDATE` (`contract_service.py:56`) | `contract_id` là một `uuid4()` sinh mới mỗi lần gọi (`file_handler.py:23`); nhánh conflict không bao giờ tới được |
| `except psycopg2.DataError` (`contract_service.py:28-31`) | `database.py:33` khai báo `contract_id TEXT`; một chuỗi sai định dạng không thể gây `DataError` khi so sánh với TEXT. Chỉ tới được nếu cột đang deploy thực ra là `UUID` — xem I-3 |
| `idx_contracts_id` (`database.py:47`) | trùng lặp với index đã có do `contract_id … UNIQUE` (`:33`) |
| Toàn bộ đường ống `PROVIDERS` / `provider` | xem I-4 — tham số được nhận ở 9 chỗ gọi và bị bỏ qua ở đúng chỗ duy nhất có ý nghĩa |

## 3.6 Logic trùng lặp

| # | Trùng lặp | Vị trí |
|---|---|---|
| D-1 | Cắt điều khoản được hiện thực hai lần với **regex khác nhau** | `clause_parser.py:370-373` (chỉ `Điều`, có capture số) vs `chunker.py:46` (`Điều` **và** `Khoản`) |
| D-2 | Chuẩn hoá Unicode NFC | `clause_parser.py:21,455` và `chunker.py:45` |
| D-3 | "gọi LLM, parse JSON, retry một lần, log rồi bỏ" | `clause_parser.py:407-416`, `risk_flagger.py:40-48`, `qa_agent.py:109-117` — ba khối gần như giống hệt |
| D-4 | Chuẩn hoá gộp khoảng trắng | `clause_parser.py:20-22` vs `helpers/text_normalizer.py:5-12` (cái sau là code chết) |
| D-5 | Regex trích địa chỉ được gõ lại lần hai | `clause_parser.py:75-78` (`_ADDRESS_RE`) được gõ lại nguyên văn ở `:117` |
| D-6 | Định dạng context cho prompt | `qa_agent.py:44-55` được nhân bản trong `docs/processing-design.md:448-451` dưới dạng biến thể nội tuyến (lệch tài liệu, không phải lệch code) |

## 3.7 Trừu tượng không cần thiết

| # | Trừu tượng | Vì sao không cần |
|---|---|---|
| U-1 | Dict `PROVIDERS` + `provider: str` xuyên qua routes → service → workflow → graph state → agents | Chỉ đúng một provider; `get_chat_model` bỏ qua tham số của chính nó (`llm_client.py:12-20`). ~9 signature và 2 field TypedDict tồn tại chỉ để chuyên chở một hằng số. |
| U-2 | Barrel re-export `app/services/__init__.py` | 5 tên được re-export cho một consumer duy nhất; thêm một lớp gián tiếp mà không giảm kết dính (barrel import module cụ thể một cách eager) |
| U-3 | `_aggregate_node` trả về `{}` | Một node no-op; LangGraph cần điểm hợp nhất, nhưng đặt tên "aggregate" hàm ý một logic không tồn tại |
| U-4 | `FaissStore.get(where=…)` bắt chước API của Chroma | Kiểu trả về hình dạng Chroma `{"documents": [...], "metadatas": [...]}` để lọt hợp đồng của một vendor khác vào, rồi buộc `contract_service.py:97-100` phải kiểm tra khoá dict một cách phòng vệ |
| U-5 | `chunker._split_text` hiện thực lại `RecursiveCharacterTextSplitter` | LangChain đã là dependency và có sẵn splitter này; bản tự viết có một bug overlap riêng (I-19) |

---

# BƯỚC 4 — Rà soát code đầy đủ

41 vấn đề. Sắp theo mức ưu tiên, rồi theo hạng mục. Mỗi vấn đề đều dẫn chứng file:dòng.

---

## MỨC NGHIÊM TRỌNG (CRITICAL)

### I-1 · Lọc metadata của FAISS chỉ tìm trong top-20 toàn cục, âm thầm phá vỡ truy hồi theo từng hợp đồng

**Hạng mục:** Thiết kế query / tính đúng đắn / khả năng mở rộng
**Vấn đề.** Mọi truy hồi theo hợp đồng đều đi qua `FaissStore.similarity_search(..., where={"contract_id": …})`, được map sang tham số `filter=` của LangChain. Trong `langchain_community 0.4.1`, filter đó được áp dụng **sau** một lần tìm ANN bị giới hạn ở `fetch_k` (mặc định **20**) trên *toàn bộ index dùng chung*.

**Vì sao tệ.** Số kết quả trả về cho hợp đồng *X* không phải `min(k, số_chunk_của_X)`; nó là số chunk của *X* tình cờ nằm trong 20 láng giềng gần nhất toàn cục xét trên **tất cả** hợp đồng của **tất cả** người dùng. Khi index dùng chung lớn lên, con số đó tiến về 0.

**Dẫn chứng.**
```7:15:app/vectorstore/retriever.py
def retrieve_contract(query: str, contract_id: str, k: int = None) -> List[Document]:
    return get_contract_collection().similarity_search(
        query, k=k or TOP_K_RETRIEVAL, where={"contract_id": contract_id}
    )
```
```73:77:app/vectorstore/faiss_store.py
    def similarity_search(self, query: str, k: int = 5, where: dict | None = None, min_score: float | None = None) -> list[Document]:
        if self._store is None:
            return []
        kwargs = {"score_threshold": min_score} if min_score is not None else {}
        return self._store.similarity_search(query, k=k, filter=where, **kwargs)
```
Thư viện đã cài (kiểm chứng bằng `inspect.getsource`, `langchain_community/vectorstores/faiss.py`):
```python
scores, indices = self.index.search(vector, k if filter is None else fetch_k)  # fetch_k = 20
...
if filter is not None:
    if filter_func(doc.metadata): docs.append(...)
return docs[:k]
```
Codebase này không bao giờ truyền `fetch_k`, nên nó vẫn là 20.

**Tác động.**
- *Tính đúng đắn:* câu trả lời chat suy thoái thành "không đủ căn cứ" với những hợp đồng mà chunk của nó không nằm trong top-20 toàn cục — và thông điệp từ chối (`qa_agent.py:16-19`) làm điều này trông như hành vi có chủ ý.
- *Khả năng mở rộng:* xác suất thất bại tăng đơn điệu theo kích thước corpus. Với 1 hợp đồng thì không bao giờ xảy ra; với 1.000 hợp đồng thì gần như luôn xảy ra. Đây là dạng khiếm khuyết kinh điển: qua được mọi buổi demo và sụp ở mọi lần launch.
- *Hiệu năng:* không có lợi ích nào — `fetch_k=20` ở đây không phải tối ưu tốc độ.

**Đề xuất refactor.** Ngắn hạn: truyền `fetch_k=max(200, k*40)` và giữ một FAISS index riêng cho từng `contract_id` thay vì một index chung. Đúng đắn: chuyển chunk hợp đồng sang `pgvector`, nơi `WHERE contract_id = $1 ORDER BY embedding <=> $2 LIMIT k` là **tiền lọc** với ngữ nghĩa chính xác (xem BƯỚC 9 về cảnh báo filtered-recall của pgvector và cách khắc phục).

**Độ khó:** Dễ (giảm nhẹ) / Trung bình (sửa đúng, thuộc phần migration sang pgvector).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-2 · Loader KB pháp luật query một schema không tồn tại trong `schema.sql`; tám tên bảng/cột không khớp

**Hạng mục:** Quản lý cấu hình / tính toàn vẹn dữ liệu / kiến trúc
**Vấn đề.** SQL của `loader.py` và `schema.sql` mô tả hai thế hệ schema không tương thích với nhau.

**Vì sao tệ.** Đường ingestion duy nhất vào vector store pháp luật không thể chạy được với schema đã được ghi trong tài liệu. Kết hợp với H-7, chế độ thất bại là im lặng: không có KB pháp luật → mọi điều khoản trả về cảnh báo "cần rà soát thủ công" trong khi HTTP 200 vẫn được báo về.

**Dẫn chứng.**
```6:13:app/knowledge_base/loader.py
_QUERY = """
    SELECT dc.chunk_ref, dc.doc_id, dc.chunk_index, dc.chunk_text, dc.section_type,
           ld.title, ld.doc_number, ld.category
    FROM document_chunks dc
    JOIN legal_documents ld ON ld.doc_id = dc.doc_id
    {where_clause}
    ORDER BY dc.doc_id, dc.chunk_index
"""
```
```18:18:app/knowledge_base/loader.py
    where_clause = "WHERE ld.status_flag = 1" if LEGAL_KB_ACTIVE_ONLY else ""
```
so với `schema.sql:8` (`doc_num`), `:17` (`eff_status_code`), `:11-12` (`majors`, `fields`), `:40` (`legal_document_sections`), `:44` (`level`), `:46` (`order_index`), `:48` (`content`). Bảng đối chiếu đầy đủ ở §2.6.

**Tác động.** Khả năng bảo trì (hai schema trong một repo), tính đúng đắn (query không chạy được), và chất lượng sản phẩm (phân tích âm thầm không dùng được).

**Đề xuất refactor.** Chọn `schema.sql` làm đích, viết lại `_QUERY` theo `legal_document_sections`, và — theo BƯỚC 8 — loại bỏ hẳn loader khi truy hồi đọc trực tiếp từ pgvector, vì bước copy Postgres→FAISS lúc đó không còn cần thiết.

**Độ khó:** Dễ (viết lại query) / Trung bình (khi loại bỏ FAISS).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-3 · Khoá ngoại `contract_chunks` trong `schema.sql` không tương thích kiểu với bảng mà `init_db()` tạo ra

**Hạng mục:** Thiết kế database / an toàn kiểu
**Vấn đề.** `schema.sql:71` khai báo `contract_id UUID NOT NULL REFERENCES uploaded_contracts(contract_id)`, nhưng `database.py:33` khai báo `uploaded_contracts.contract_id TEXT`.

**Dẫn chứng.**
```69:72:schema.sql
CREATE TABLE IF NOT EXISTS contract_chunks (
    id              SERIAL PRIMARY KEY,
    contract_id     UUID NOT NULL REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
```
```31:34:app/core/database.py
                CREATE TABLE IF NOT EXISTS uploaded_contracts (
                    id BIGSERIAL PRIMARY KEY,
                    contract_id TEXT NOT NULL UNIQUE,
```

**Vì sao tệ.** PostgreSQL yêu cầu có toán tử bằng giữa kiểu tham chiếu và kiểu được tham chiếu. Không có toán tử `uuid = text`, nên câu `CREATE TABLE` này thất bại với thông báo *"foreign key constraint … cannot be implemented / Key columns are of incompatible types: uuid and text."* **CHƯA RÕ:** chưa chạy được trên database thật (không có `.env`), nên tôi không thể xác nhận cột đang deploy thực sự có kiểu gì. `schema.sql:69` còn tạo `contract_chunks` *trước khi* `uploaded_contracts` tồn tại theo thứ tự file, nên `psql -f schema.sql` trên một database mới cũng thất bại vì lý do đó.

**Tác động.** `schema.sql` không phải một artifact chạy được. Ai coi nó là script khởi tạo sẽ nhận được một schema tạo dở.

**Đề xuất refactor.** Chuẩn hoá `UUID` cho `contract_id` ở mọi nơi (nó *đúng là* UUID — `file_handler.py:23`), đưa `uploaded_contracts` vào `schema.sql` theo thứ tự phụ thuộc, xoá DDL khỏi `init_db()`, và chuyển toàn bộ tiến hoá schema sang migration có version (I-9).

**Độ khó:** Trung bình (cần migrate dữ liệu nếu cột đang deploy là TEXT với các dòng không phải UUID).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-4 · Singleton FAISS toàn process, lưu xuống đĩa, khiến ứng dụng không thể scale ngang

**Hạng mục:** Kiến trúc / khả năng mở rộng
**Vấn đề.** Trạng thái vector là bộ nhớ riêng của process cộng với đĩa local riêng của process, và nó bị **ghi** ngay trên đường xử lý request.

**Dẫn chứng.**
```80:95:app/vectorstore/faiss_store.py
_contract_collection = None
_legal_collection = None

def get_contract_collection() -> FaissStore:
    global _contract_collection
    if _contract_collection is None:
        _contract_collection = FaissStore("contracts")
    return _contract_collection
```
```47:60:app/vectorstore/faiss_store.py
    def add_documents(self, docs: list[Document], persist: bool = True):
        ...
        with self._lock:
            if self._store is None:
                self._store = FAISS.from_documents(...)
            else:
                self._store.add_documents(docs)
        if persist:
            self.save()
```

**Vì sao tệ.** Với `--workers N` hoặc nhiều hơn một container: (a) chunk do worker 1 ghi thì worker 2 không thấy, nên `analyze`/`chat` thất bại một cách phi tất định tuỳ vào worker nào phục vụ request; (b) `save_local` từ hai worker sẽ đua nhau trên cùng một thư mục và có thể làm hỏng hoặc ghi đè index; (c) mục tiêu "hàng triệu request" là không thể đạt được vì đường ghi bản chất chỉ chạy trên một node.

**Tác động.** Khả năng mở rộng (giới hạn cứng ở một process), tính đúng đắn khi có concurrency, tính khả dụng (phải rebuild index khi restart), bộ nhớ (mỗi worker giữ toàn bộ index trong RAM).

**Đề xuất refactor.** Chuyển cả hai collection sang pgvector (BƯỚC 9). Trạng thái vector trở thành dùng chung, có transaction, được backup cùng database, và scale ngang được qua read replica.

**Độ khó:** Trung bình.
**Ưu tiên:** **Nghiêm trọng.**

---

### I-5 · Ghi lại toàn bộ index mỗi lần upload; ghi đĩa O(N) cho mỗi request

**Hạng mục:** Hiệu năng / async
**Dẫn chứng.** `faiss_store.py:59-60` gọi `self.save()` sau mỗi `add_documents`, và `save()` → `FAISS.save_local()` serialize **toàn bộ** index cùng docstore (`faiss_store.py:35-38`).

**Vì sao tệ.** Chi phí mỗi lần upload tỉ lệ với tổng kích thước corpus, không phải với văn bản vừa upload. Ở mức 1M chunk × 768 chiều × 4 B ≈ 3 GB, mỗi lần upload đơn lẻ ghi ~3 GB — trong lúc đang giữ `self._lock`, và trên thread event loop (`upload_contract` là `async` nhưng gọi `add_documents` đồng bộ ở `contract_service.py:45`), chặn **toàn bộ** request đồng thời khác.

**Tác động.** Hiệu năng (độ trễ tăng theo corpus), throughput (lock toàn cục + event loop bị chặn), khuếch đại I/O đĩa, bộ nhớ (buffer serialize).

**Đề xuất refactor.** `INSERT` của pgvector là O(số dòng chèn). Tạm thời: dùng `persist=False` trên đường request cộng với flush định kỳ.

**Độ khó:** Dễ (tạm thời) / Trung bình (pgvector).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-6 · `analyze_contract` dựng lại văn bản hợp đồng bằng cách quét toàn bộ mọi hợp đồng trong index

**Hạng mục:** Thiết kế query / bộ nhớ / hiệu năng
**Dẫn chứng.**
```96:100:app/services/contract_service.py
    all_docs = get_contract_collection().get(where={"contract_id": contract_id})
    ...
    full_text = "\n".join(all_docs["documents"])
```
```62:71:app/vectorstore/faiss_store.py
    def get(self, where: dict | None = None) -> dict:
        if self._store is None: return {"documents": [], "metadatas": []}
        all_docs = list(self._store.docstore._dict.values())
        if where:
            all_docs = [d for d in all_docs if all(d.metadata.get(k) == v for k, v in where.items())]
        return {"documents": [d.page_content for d in all_docs], ...}
```

**Vì sao tệ.** Ba vấn đề cộng dồn. (a) `list(...)` hiện thực hoá **mọi chunk của mọi hợp đồng của mọi người dùng** vào một list Python ở mỗi lần gọi analyse — ở mức 1M chunk × ~500 ký tự đó là ~500 MB cấp phát tạm chỉ để lấy ra một hợp đồng. (b) Nó chạm vào `docstore._dict`, một attribute private. (c) Lọc `where` thực hiện ở phía Python, O(N) mỗi lần gọi.

Tệ hơn, việc dựng lại này **mất mát và sai thứ tự**: thứ tự chèn của dict không phải thứ tự điều khoản, và `chunker.py:79` chia chunk với `CHUNK_OVERLAP=50` ký tự, nên `"\n".join(...)` nhân đôi 50 ký tự tại mỗi biên chunk trước khi văn bản được đưa cho extractor regex.

**Tác động.** Bộ nhớ (cấp phát tạm không giới hạn), hiệu năng (O(toàn corpus) mỗi lần analyse), tính đúng đắn (extraction chạy trên văn bản bị đảo thứ tự và trùng lặp một phần).

**Đề xuất refactor.** Lưu văn bản đã parse một lần (`uploaded_contracts.full_text`, hoặc tốt hơn là một dòng `contract_documents`) lúc upload và đọc lại theo primary key. Không bao giờ dựng lại văn bản gốc từ các chunk.

**Độ khó:** Dễ.
**Ưu tiên:** **Nghiêm trọng.**

---

### I-7 · Upload file vào RAM không giới hạn

**Hạng mục:** Bảo mật (DoS) / bộ nhớ
**Dẫn chứng.**
```26:29:app/document/file_handler.py
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
```
Không có `MAX_UPLOAD_SIZE` trong `.env.example` hay `core/config.py`; không có config reverse proxy trong repository.

**Vì sao tệ.** Một client đã xác thực có thể POST một body vài gigabyte và server sẽ buffer toàn bộ vào RAM trước bất kỳ kiểm tra nào. Chỉ vài request đồng thời là OOM-kill process, mang theo cả FAISS index đang nằm trong RAM (I-4).

**Tác động.** Tính khả dụng, bộ nhớ, bảo mật.

**Đề xuất refactor.** Stream theo khối cố định (`while chunk := await file.read(1 << 20)`), áp trần byte có cấu hình ngay giữa stream, và từ chối theo `Content-Length` trước khi đọc. Đồng thời đặt giới hạn kích thước body ở ingress.

**Độ khó:** Dễ.
**Ưu tiên:** **Nghiêm trọng.**

---

### I-8 · `allow_dangerous_deserialization=True` biến thư mục vector store thành một vector thực thi mã

**Hạng mục:** Bảo mật
**Dẫn chứng.**
```28:30:app/vectorstore/faiss_store.py
                return FAISS.load_local(
                    self.folder_path, get_embeddings(), allow_dangerous_deserialization=True
                )
```

**Vì sao tệ.** `load_local` unpickle docstore. Bất kỳ ai ghi được vào `data/vector_store/` — một tenant khác trên cùng host, một process lân cận bị xâm nhập, một bug path traversal ở nơi khác, một bản backup phục hồi từ nguồn không tin cậy — đều đạt được thực thi mã tuỳ ý dưới quyền user ứng dụng ngay lúc startup. Cờ này tồn tại chính là để làm rủi ro đó hiện rõ.

**Tác động.** Bảo mật (RCE), tuân thủ (đây là hệ thống về văn bản pháp lý đang giữ hợp đồng của khách hàng).

**Đề xuất refactor.** Loại bỏ hoàn toàn đường pickle bằng cách chuyển sang pgvector. Nếu buộc phải giữ FAISS ngắn hạn: đặt thư mục ở mode `0700` thuộc user ứng dụng, lưu HMAC của các file index và xác minh trước khi load, và tuyệt đối không load store từ volume dùng chung hoặc user ghi được.

**Độ khó:** Dễ (permission + HMAC) / Trung bình (loại bỏ).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-9 · Tiến hoá schema bằng side effect lúc startup; không có migration

**Hạng mục:** Quản lý cấu hình / vận hành
**Dẫn chứng.**
```27:49:app/core/database.py
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS uploaded_contracts ( ... )""")
            cur.execute("ALTER TABLE uploaded_contracts ADD COLUMN IF NOT EXISTS user_id UUID")
            cur.execute("ALTER TABLE uploaded_contracts ADD COLUMN IF NOT EXISTS analysis JSONB")
            cur.execute("ALTER TABLE uploaded_contracts ADD COLUMN IF NOT EXISTS risks JSONB")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_contracts_id ON uploaded_contracts(contract_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_contracts_user ON uploaded_contracts(user_id)")
```
Được gọi từ `main.py:30` ở mỗi lần startup.

**Vì sao tệ.** Không có version schema, nên không có cách nào biết database đang ở trạng thái nào, không có down-migration, không có artifact để review khi đổi schema, và không có cách chạy một thay đổi *trước khi* code mới deploy. `ADD COLUMN IF NOT EXISTS` là một lịch sử patch được mã hoá thành danh sách chỉ-thêm các câu lệnh idempotent — nó chỉ có thể thêm, không bao giờ đổi tên, đổi kiểu, hay backfill. Lưu ý `ALTER TABLE … ADD COLUMN user_id UUID` ở `:44` không thể backfill các dòng đã có, nên `user_id` trên thực tế là nullable dù `CREATE TABLE` ở `:35` ghi `NOT NULL`. `CREATE INDEX` (không `CONCURRENTLY`) lấy lock `ACCESS EXCLUSIVE` — trên bảng lớn điều này chặn mọi write trong lúc boot.

**Tác động.** Vận hành, khả năng bảo trì, tính khả dụng khi deploy, tính toàn vẹn dữ liệu (nullability của `user_id`).

**Đề xuất refactor.** Dùng Alembic. Đưa `uploaded_contracts` và mọi thứ trong `schema.sql` thành các revision có số. Biến `init_db()` thành bước **kiểm chứng**, khẳng định `alembic_version` khớp head kỳ vọng và từ chối khởi động nếu không.

**Độ khó:** Trung bình.
**Ưu tiên:** **Nghiêm trọng.**

---

### I-10 · `eff_status` trong thuộc tính đã crawl trái với đồ thị quan hệ đã crawl — KB sẽ phục vụ luật đã bị bãi bỏ như luật hiện hành

**Hạng mục:** Tính toàn vẹn dữ liệu / tính đúng đắn nghiệp vụ
**Vấn đề.** Với `doc_id=173920`, `thuoc_tinh.json` nói nghị định còn hiệu lực và không có ngày kết thúc, trong khi `luoc_do.json` ghi lại rằng một văn bản sau đó bãi bỏ nó và một văn bản khác sửa đổi nó.

**Dẫn chứng (đã đo).**
```13:14:Nghị định số 168-2024-NĐ-CP …/thuoc_tinh.json
  "eff_status": "Còn hiệu lực",
  "eff_status_code": "CHL",
```
```12:12:Nghị định số 168-2024-NĐ-CP …/thuoc_tinh.json
  "eff_to": null,
```
Nhưng quan hệ đến (incoming) lại ghi `van_ban_bi_bai_bo → 336/2025/NĐ-CP` (doc_id 185666) và `sua_doi_bo_sung → 238/2026/NĐ-CP` (doc_id `f4b0c320-79e6-11f1-8c8a-3587e086d762`) — nghĩa là nghị định này đã bị sửa đổi và bãi bỏ bởi các văn bản sau (`luoc_do.json:122-130` và `:176-184`).

**Vì sao tệ.** `loader.py:18` lọc KB bằng `WHERE ld.status_flag = 1` — một boolean đơn lẻ dẫn xuất từ đúng cái thuộc tính đã lỗi thời. Một nghị định đã bị bãi bỏ vẫn vượt qua filter đó, được embed, được `retrieve_legal` truy hồi, và được đưa cho Gemini như "các đoạn pháp luật liên quan". Hệ thống sau đó sinh ra một phát hiện `critical` viện dẫn luật không còn áp dụng. Với một sản phẩm tư vấn pháp lý, đây là loại lỗi tệ nhất có thể: **sai một cách tự tin, kèm trích dẫn**.

**SUY LUẬN.** `eff_status` là một ảnh chụp tại một thời điểm, được lấy lúc crawl; đồ thị quan hệ mới hơn và có thẩm quyền hơn. Hiệu lực phải được **dẫn xuất**, không được lưu như một scalar đơn lẻ được tin cậy.

**Tác động.** Tính đúng đắn với hệ quả pháp lý/trách nhiệm; chất lượng truy hồi; niềm tin vào sản phẩm.

**Đề xuất refactor.** (1) Lưu quan hệ `luoc_do` trên **Neo4j** (không bảng cạnh SoT trong Postgres). (2) Job đọc cạnh bãi bỏ/thay thế trên Neo4j → ghi cờ/`legal_document_effectivity` trên Postgres. (3) Lọc retrieval theo cờ đó. (4) Đưa cửa sổ hiệu lực vào prompt. (5) Crawl lại khi quan hệ đến đổi.

**Độ khó:** Trung bình.
**Ưu tiên:** **Nghiêm trọng.**

---

### I-11 · Mỗi request phải trả một vòng HTTPS đồng bộ tới Supabase để auth — và bản thân phụ thuộc Supabase Auth

**Hạng mục:** Hiệu năng / khả năng mở rộng / thiết kế API / phụ thuộc bên thứ ba
**Dẫn chứng.**
```12:17:app/core/auth.py
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_SECRET_KEY},
            )
```

**Vì sao tệ.** (a) Tail latency trên **mọi** endpoint vì introspection từ xa + TLS mới mỗi lần (client httpx tạo rồi hủy). (b) Supabase Auth là SPOF và rate-limit cho toàn API. (c) **Hướng sản phẩm đã chốt bỏ Supabase** — giữ introspection này là nợ kỹ thuật và nợ vận hành.

**Tác động.** Latency, khả dụng, vendor lock-in, chi phí.

**Đề xuất refactor (mục tiêu Docker, không Supabase).**
1. Thay Supabase Auth bằng **JWT tự host**: endpoint `POST /auth/login|register` (hoặc IdP nhẹ trong Compose như Keycloak/Authentik nếu cần SSO sau này).
2. Backend verify chữ ký JWT local (HS256 với `JWT_SECRET` trong env, hoặc RS256 + JWKS nội bộ) — không HTTP ra ngoài mỗi request.
3. Frontend bỏ `supabase-js`; lưu access/refresh token theo cùng contract API.
4. Migration: map `user_id` cũ (Supabase `sub`) sang bảng `users` nội bộ nếu đã có dữ liệu production.

**Độ khó:** Trung bình (thay auth end-to-end).
**Ưu tiên:** **Nghiêm trọng.**

---

### I-12 · Không có connection pooling cho psycopg2; 2–3 connection PostgreSQL mới cho mỗi lần gọi API

**Hạng mục:** Hiệu năng / khả năng mở rộng
**Dẫn chứng.**
```8:24:app/core/database.py
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

@contextmanager
def get_db() -> Generator:
    conn = get_connection()
    try:
        yield conn; conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
```
`analyze_contract` mở ba connection: `_assert_owns_contract:25`, `_load_cached_analysis:64`, `_save_analysis_result:78`.

**Vì sao tệ.** Một connection Postgres mới tốn TCP (+ TLS nếu bật), auth, và backend process — thường vài–vài chục ms, so với micro giây từ pool. Ở concurrency thực tế sẽ cạn `max_connections` của Postgres Docker và bỏ đói pool checkpointer LangGraph (cùng DB). Lưu ý: `checkpointer.py:20-29` đã dùng pool `psycopg` đúng cách; đường dữ liệu chính thì không.

Thêm nữa, đây là các lệnh **blocking** được gọi từ hàm `async def` (`contract_service.py:86`, `110`, `133`), nên mỗi lệnh làm treo event loop và mọi request đang bay khác.

**Tác động.** Độ trễ (nhân lên theo mỗi request), throughput (event loop bị treo), tính khả dụng (cạn connection).

**Đề xuất refactor.** Một pool async duy nhất. Hoặc chuẩn hoá về `psycopg` 3 + `AsyncConnectionPool` (đã là dependency thông qua checkpointer, và cho phép xoá `psycopg2-binary` — xem I-31), hoặc dùng SQLAlchemy 2 async với `asyncpg`. Gộp ba vòng round-trip của `analyze_contract` thành một câu lệnh vừa kiểm quyền sở hữu vừa trả về phân tích đã cache.

**Độ khó:** Trung bình.
**Ưu tiên:** **Nghiêm trọng.**

---

## MỨC CAO (HIGH)

### I-13 · Input embedding bị cắt ở 256 token trong khi chunk được tính theo ký tự — mất nội dung đo được trên văn bản pháp luật thật

**Hạng mục:** Chất lượng tìm kiếm / cấu hình
**Dẫn chứng.**
```24:26:app/vectorstore/embeddings.py
        # PhoBERT max is 256 tokens; prevents CUDA scatter/gather OOB. Not exposed as a
        # constructor kwarg by HuggingFaceEmbeddings, so set it on the underlying model directly.
        _embeddings._client.max_seq_length = 256
```
Việc chia chunk thì dựa trên ký tự: `MAX_CHUNK_SIZE=500` (`.env.example:8`, `config.py:17`). Loader pháp luật thì **không** chia chunk gì cả — nó embed nguyên giá trị `chunk_text` như lấy từ database (`loader.py:33-44`).

**Đã đo trên chính nghị định đã crawl** (phân đoạn `van_ban.md` tại các anchor điều khoản): 333 đoạn, trung bình **779** ký tự, p90 **1.749**, tối đa **8.704**.

**Vì sao tệ.** Văn xuôi pháp luật tiếng Việt vào khoảng 3–4 ký tự cho mỗi token PhoBERT, nên 256 token ≈ 800–1.000 ký tự. Đoạn trung bình nằm ngay tại giới hạn, p90 vượt ~2×, và đoạn lớn nhất vượt ~9×. Mọi thứ sau điểm cắt bị **âm thầm loại bỏ** — không cảnh báo, không log. Với các quy định xử phạt, mô tả hành vi cụ thể và mức tiền phạt thường nằm ở *cuối* điều khoản, đúng là phần bị mất. Cũng lưu ý `_embeddings._client` là attribute private; một lần refactor của `langchain-huggingface` sẽ âm thầm làm hỏng dòng này và bật lại đúng lỗi CUDA out-of-bounds mà comment đang mô tả.

**Tác động.** Chất lượng tìm kiếm (cần điều khiển chất lượng chính trong một sản phẩm RAG), tính đúng đắn của phán quyết tuân thủ, và một mối nguy ẩn khi nâng cấp.

**Đề xuất refactor.** Chia chunk theo *token* bằng chính tokenizer của model, nhắm ~220 token với ~40 token overlap, và ưu tiên cắt tại biên điều khoản/điểm (dữ liệu có cấu trúc `Điểm a/b/c` tường minh để cắt). Log mỗi khi input vượt giới hạn model. Dài hạn hãy đánh giá một model có cửa sổ lớn hơn; giữ 768 chiều để schema không bị ảnh hưởng.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-14 · Context đã truy hồi nằm trong state LangGraph, nên ~11 KB văn bản dư thừa bị checkpoint vào Postgres mỗi lượt chat

**Hạng mục:** Bộ nhớ / lưu trữ / hiệu năng
**Dẫn chứng.**
```28:37:app/agents/qa_agent.py
class QAState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    contract_id: str
    provider: str
    source_clauses: List[str]
    needs_clarification: bool
    _has_context: bool
    _contract_context: str
    _legal_context: str
    _valid_clause_numbers: List[str]
```
```70:71:app/agents/qa_agent.py
        "_contract_context": _format_contract_context(contract_docs)[:8000],
        "_legal_context": _format_legal_context(legal_docs)[:3000],
```
Graph được compile **cùng với** checkpointer (`qa_agent.py:166`).

**Vì sao tệ.** Dấu gạch dưới đầu tên chỉ là quy ước đặt tên Python; nó không có ý nghĩa gì với `TypedDict` hay với LangGraph. Mọi field của `QAState` đều thuộc state được checkpoint, nên tới 11.000 ký tự văn bản đã truy hồi được serialize vào `checkpoint_blobs` ở mỗi lần chuyển node, mỗi lượt, mãi mãi. Dữ liệu này là cache dẫn xuất thuần khiết — tái tạo được bằng một lần gọi truy hồi. Ở mức 100k cuộc hội thoại × 20 lượt, đó là cỡ **20+ GB** blob dư thừa, đồng thời làm phình mọi bản backup và làm chậm `aget_state` trong `get_conversation_history` (`:190-191`).

**Tác động.** Tăng trưởng lưu trữ, kích thước và thời gian backup, độ trễ đọc lịch sử chat, chi phí database.

**Đề xuất refactor.** Giữ payload truy hồi tạm thời ra khỏi state được checkpoint: hoặc truyền chúng qua một channel không persist, hoặc tách thành một state nhỏ được persist và một object context theo từng lần invoke. Độc lập với việc đó, hãy thêm retention: prune checkpoint của các thread không hoạt động quá N ngày.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-15 · `similarity_search` không được đồng bộ hoá với việc mutate index đồng thời

**Hạng mục:** Async / concurrency / tính đúng đắn
**Dẫn chứng.** `add_documents` (`faiss_store.py:50`) và `reset` (`:42`) lấy `self._lock`; `get` (`:62-71`) và `similarity_search` (`:73-77`) không lấy gì. Upload và chat/analysis chạy đồng thời trong cùng process (`--reload`/`--workers 1` cộng với fan-out `asyncio.to_thread` ở `workflow.py:59`).

**Vì sao tệ.** Một reader có thể quan sát `self._store` khi đang bị mutate. `get` lặp trên `docstore._dict.values()` trong lúc `add_documents` chèn vào chính dict đó → `RuntimeError: dictionary changed size during iteration`. Đọc `index_to_docstore_id` khi FAISS đang append có thể ném lỗi hoặc trả về một id đã cũ, mà việc tra docstore sau đó ném `ValueError: Could not find document for id` (câu `raise` đó nằm trong source thư viện đã cài). `reset()` gán `_store = None` giữa lúc reader kiểm `is None` và lúc dùng → `AttributeError`.

**Tác động.** Lỗi 500 gián đoạn cực khó tái hiện; tính đúng đắn.

**Đề xuất refactor.** Ngắn hạn: một `threading.RLock` phủ cả phần đọc, hoặc copy-on-write (dựng index mới và swap reference nguyên tử). Sửa đúng: pgvector, nơi MVCC cho reader một snapshot nhất quán miễn phí.

**Độ khó:** Dễ (lock) / Trung bình (pgvector).
**Ưu tiên:** **Cao.**

---

### I-16 · Chuỗi exception thô được trả về cho client

**Hạng mục:** Bảo mật (tiết lộ thông tin) / xử lý lỗi
**Dẫn chứng.** Năm lần xuất hiện cùng một mẫu:
```34:36:app/api/routes.py
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```
cộng với `:45-46`, `:53-54`, `:63-64`, `:73-74`. Và trên đường upload, nội dung exception được **lưu lại và trả về** trong một response thành công:
```51:51:app/services/contract_service.py
        message = f"File uploaded but parsing failed: {str(e)}"
```

**Vì sao tệ.** `str(e)` trên một lỗi psycopg2 chứa cả câu SQL bị lỗi, tên cột, và thường cả host. Trên lỗi `httpx` nó chứa URL nội bộ. Trên lỗi filesystem nó chứa đường dẫn tuyệt đối trên server. Đây là tài liệu trinh sát miễn phí cho kẻ tấn công và làm lộ chi tiết schema cho bất kỳ người dùng đã xác thực.

**Tác động.** Bảo mật; và cả khả năng vận hành — client nhìn thấy chi tiết mà log có cấu trúc lại không bao giờ nhận được ở dạng tìm kiếm được.

**Đề xuất refactor.** Định nghĩa một cây exception ứng dụng (`NotFoundError`, `ValidationError`, `UpstreamError`, `DomainError`). Đăng ký exception handler của FastAPI map mỗi loại sang một status code và một thông điệp **ổn định, chung chung** cho client cùng một `correlation_id`; log toàn bộ exception ở phía server theo id đó. Tuyệt đối không nội suy `str(e)` vào response.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-17 · `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` — một tổ hợp vừa không hợp lệ vừa không an toàn

**Hạng mục:** Bảo mật
**Dẫn chứng.**
```23:23:app/main.py
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

**Vì sao tệ.** Đặc tả CORS cấm `Access-Control-Allow-Origin: *` đi cùng `Access-Control-Allow-Credentials: true`; browser từ chối nó, nên cấu hình này vừa **hỏng** vừa cho phép tối đa với các request không kèm credential. Cách xử lý của Starlette (phản chiếu lại `Origin` của request) biến nó thành "cho phép mọi origin kèm credential", đúng là điều CORS tồn tại để ngăn. Bất kỳ website nào một người dùng đã đăng nhập ghé qua đều gọi được API này.

**Tác động.** Bảo mật (truy cập dữ liệu cross-origin kiểu CSRF), cộng với hành vi gây nhầm lẫn.

**Đề xuất refactor.** Một danh sách env `CORS_ALLOWED_ORIGINS` tường minh, không wildcard ở bất kỳ môi trường đã deploy nào, `allow_credentials=False` trừ khi thực sự dùng cookie (hiện không dùng — auth qua header Bearer, `api.js:8`), và allowlist method/header tường minh.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-18 · Chỉ kiểm tra file theo đuôi; kiểu được khai báo không bao giờ được đối chiếu với nội dung

**Hạng mục:** Bảo mật / xử lý lỗi
**Dẫn chứng.**
```11:18:app/document/file_handler.py
def validate_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "unknown")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not supported. ...")
    return ext
```
Sau đó việc phân nhánh tin vào đuôi file đó (`parser.py:58-66`); `.doc` bị đưa tới `python-docx`, mà thư viện này chỉ đọc được OOXML.

**Vì sao tệ.** Không kiểm magic byte, không kiểm `content_type`, không kiểm kích thước, không kiểm tỉ lệ nén. Một zip bomb đổi tên sẽ tới được `python-docx`; một PDF được chế tác tới được `pdfplumber`; một file `.doc` legacy thật (OLE2) được validation cho qua rồi thất bại sâu bên trong parser, nổi lên thành một thông báo chung chung. Cả hai parser là bề mặt C/Python lớn đang được cho ăn byte chưa kiểm chứng.

**Tác động.** Bảo mật (khai thác parser, DoS bằng giải nén), độ tin cậy, UX.

**Đề xuất refactor.** Sniff magic byte (`PK\x03\x04` cho OOXML, `%PDF-` cho PDF, `\xD0\xCF\x11\xE0` cho OLE2) và yêu cầu khớp với đuôi file. Từ chối `.doc` legacy một cách tường minh kèm thông báo hành động được, hoặc convert nó. Áp trần kích thước sau giải nén và số entry cho các định dạng nền zip. Áp trần kích thước ảnh trước khi OCR.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-19 · Cách hiện thực overlap làm chunk phình quá mức tối đa đã cấu hình và nhân bản nội dung

**Hạng mục:** Tính đúng đắn / chất lượng tìm kiếm
**Dẫn chứng.**
```36:41:app/document/chunker.py
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            overlapped.append(chunks[i - 1][-chunk_overlap:] + chunks[i])
        return overlapped
```

**Vì sao tệ.** Overlap được *nối thêm* sau khi các chunk đã được đóng gói đủ `chunk_size`, nên mọi chunk từ cái thứ hai trở đi có thể lên tới `chunk_size + chunk_overlap` = 550 ký tự — vi phạm chính bất biến mà phần đệ quy của hàm dựa vào. Phần prefix lấy từ `chunks[i-1]` *trước* overlap, điều đó là đúng, nhưng kết quả vẫn khiến ~10% corpus bị embed hai lần, và các vector gần trùng nhau chen chỗ trong top-k (làm tình trạng bỏ đói `fetch_k` của I-1 tệ hơn). Kết hợp với I-6, 50 ký tự bị nhân bản đó cũng bị chèn lại vào văn bản đưa cho extractor.

**Tác động.** Chất lượng tìm kiếm (láng giềng dư thừa), lưu trữ (+10%), tính đúng đắn của việc dựng lại văn bản ở hạ nguồn.

**Đề xuất refactor.** Xoá `_split_text` và dùng `RecursiveCharacterTextSplitter` (đã có sẵn qua `langchain-text-splitters`), thư viện này áp overlap trong lúc đóng gói và tôn trọng mức tối đa. Tốt hơn nữa, theo I-13, dùng splitter nhận biết token.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-20 · `provider` là một trừu tượng no-op xuyên năm tầng

**Hạng mục:** Trừu tượng không cần thiết / thiết kế API / dependency injection
**Dẫn chứng.**
```12:20:app/agents/llm_client.py
def get_chat_model(provider: str = DEFAULT_PROVIDER) -> ChatGoogleGenerativeAI:
    global _gemini_chat
    if _gemini_chat is None:
        _gemini_chat = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)
    return _gemini_chat
```
`provider` được nhận rồi bỏ qua. Dù vậy nó vẫn được chuyên chở qua `routes.py:14,21,42,60` → `contract_service.py:86,133` → `workflow.py:22,30,50,59,85` → `qa_agent.py:31,108,170` → `risk_flagger.py:10,40` → `clause_parser.py:403,419,453`, và nó chiếm một field trong **cả hai** TypedDict của LangGraph, nghĩa là nó cũng bị checkpoint.

**Vì sao tệ.** Nó có hình dạng của một trừu tượng mà không có chút thực chất nào: không chọn được provider, không validate được (mọi chuỗi đều được `AnalyzeRequest.provider: str` chấp nhận rồi âm thầm bỏ qua), và cho client API một tham số không làm gì. Thứ duy nhất mà một trừu tượng provider thật cần — một registry map khoá → factory model — lại chính là thứ đang thiếu.

**Tác động.** Khả năng bảo trì, tính trung thực của API, state bị lãng phí.

**Đề xuất refactor.** Hoặc làm cho nó thật — `PROVIDERS: dict[str, Callable[[], BaseChatModel]]`, một factory có cache theo provider, và validate `Literal[...]` trên request model để provider không rõ trả 422 — hoặc xoá tham số này khỏi cả năm tầng và chỉ expose một model đã cấu hình. Đừng để nguyên như hiện tại.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-21 · "God function": `clause_parser.py` là một module thủ tục 485 dòng với ~30 regex và không có đường ráp theo domain

**Hạng mục:** SOLID / clean architecture / khả năng bảo trì
**Dẫn chứng.** `app/agents/clause_parser.py`, 485 dòng, 20 pattern compile cấp module cộng ~10 lệnh `re.search` nội tuyến, 17 hàm extractor private, và `parse_contract:453-484` dựng một object 20 field trong một lần gọi. Các extractor bị hard-code cho hợp đồng **lao động** Việt Nam: `_extract_party_a` mặc định vai trò là `"Người sử dụng lao động"` (`:97`), `_extract_party_b` là `"Người lao động"` (`:130`), `_VALUE_PATTERNS` mở đầu bằng `Lương căn bản` (`:218`), `_extract_governing_law` mở đầu bằng `pháp luật lao động` (`:302`).

**Vì sao tệ.** Open/Closed bị vi phạm ở đúng chỗ tệ nhất: thêm loại hợp đồng thứ hai (thuê nhà, mua bán, dịch vụ) nghĩa là phải sửa chính những hàm mà mọi loại hiện có đang phụ thuộc, với 11 test làm lưới an toàn (không test nào phủ module này — I-27). Single Responsibility bị vi phạm: một module vừa lo phát hiện loại văn bản, trích xuất bên, parse ngày, parse tài chính, cắt điều khoản, fallback LLM, và chính sách merge. Các con số magic không được giải thích: `end = start + 2000` (`:99`), `len(text) * 3 // 4` (`:136`), `[:120]` (`:123`), `[:150]` (`:387`), `[:12000]` (`:407`), `[:3000]`/`[:4000]` (`risk_flagger.py:36-37`). `_extract_party_b:136` chỉ tìm trong một phần tư cuối văn bản mà không nêu lý do, và `:129` đọc `match.group("role")` bảo vệ bằng toán tử ba ngôi trong khi `_extract_party_a:94` bảo vệ bằng early return — hai quy ước cho cùng một vấn đề.

**Tác động.** Khả năng bảo trì (file thay đổi nhiều nhất, khả năng test thấp nhất), khả năng mở rộng (chặn đúng lộ trình sản phẩm hiển nhiên), độ phức tạp.

**Đề xuất refactor.** Giới thiệu một protocol `FieldExtractor` (`name`, `applies_to(doc_type)`, `extract(text) -> value | None`) và một registry. Chuyển mỗi nhóm field vào extractor riêng với unit test và fixture riêng. Biến việc phát hiện loại văn bản thành bước đầu tiên chọn một *profile* (một danh sách extractor + giá trị mặc định) để heuristic riêng của hợp đồng lao động nằm trong profile lao động thay vì trong code dùng chung. Nâng mọi con số magic thành hằng số cấp module có tên kèm comment giải thích giới hạn.

**Độ khó:** Khó.
**Ưu tiên:** **Cao.**

---

### I-22 · Không có tầng repository: chuỗi SQL nhúng trong tầng service

**Hạng mục:** Clean architecture / repository pattern / khả năng test
**Dẫn chứng.** Năm câu lệnh nội tuyến trong `contract_service.py` (`:27`, `:56`, `:66-69`, `:80-83`, `:113-117`) cộng với DDL trong `core/database.py` và query KB trong `knowledge_base/loader.py`.

**Vì sao tệ.** Điều phối nghiệp vụ và lưu trữ bị hợp nhất. Mỗi lần đổi schema là chạm vào code nghiệp vụ; mỗi test nghiệp vụ cần một database thật (đó chính là lý do `tests/integration/test_api.py:24` cần một cái — I-27). Việc giải nén result set là theo vị trí (`contract_service.py:128`: `for contract_id, filename, status, chunk_count, created_at in rows`), nên đổi thứ tự danh sách `SELECT` sẽ âm thầm gán sai field mà không có lỗi kiểu nào.

**Tác động.** Khả năng bảo trì, khả năng test, sự mong manh về tính đúng đắn.

**Đề xuất refactor.** Một `ContractRepository` với các method đặt tên theo ý định (`get_owned(contract_id, user_id)`, `save_analysis(...)`, `list_for_user(user_id, limit, cursor)`), trả về dòng có kiểu (`dict_row` hoặc Pydantic). Inject nó vào service. Service khi đó chỉ còn chính sách và điều phối, và trở thành unit-test được với một repository giả.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-23 · Thiếu index composite cho query danh sách duy nhất; có một index dư thừa

**Hạng mục:** Thiết kế query / hiệu năng
**Dẫn chứng.** Query: `WHERE user_id = %s ORDER BY created_at DESC` (`contract_service.py:113-117`). Index được tạo: `idx_contracts_id ON (contract_id)` và `idx_contracts_user ON (user_id)` (`database.py:47-48`).

**Vì sao tệ.** `idx_contracts_user` thoả được predicate nhưng không thoả thứ tự, nên Postgres thêm một bước sort trên mọi dòng thuộc user đó. Với một user nặng có hàng nghìn hợp đồng, đó là một lần sort toàn bộ mỗi lần load trang. Trong khi đó `idx_contracts_id` trùng lặp với index mà `contract_id … UNIQUE` (`:33`) đã tạo — chỉ thuần khuếch đại ghi và tốn lưu trữ ở mọi lần insert.

**Tác động.** Độ trễ đọc ở màn hình chính của app; chi phí ghi không cần thiết.

**Đề xuất refactor.** `CREATE INDEX idx_contracts_user_created ON uploaded_contracts (user_id, created_at DESC);` và `DROP INDEX idx_contracts_id;`. Kết hợp với keyset pagination (I-25).

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-24 · `POST /analyze` trộn lẫn "đọc kết quả đã cache" với "chạy một job đắt đỏ"

**Hạng mục:** Thiết kế API / ngữ nghĩa REST
**Dẫn chứng.** `analyze_contract:86-107` trả về dòng đã cache nếu có, ngược lại chạy toàn bộ workflow nhiều LLM ngay trong request. Frontend dùng nó thuần như một hành động đọc khi mở một hợp đồng đã lưu:
```67:67:frontend/src/App.jsx
      const analyzed = await analyzeContract(contract.contract_id);
```

**Vì sao tệ.** Một endpoint có hai profile chi phí và độ trễ khác nhau một trời một vực — vài milli giây khi cache hit so với 30–60 giây và 21–41 lần gọi LLM khi miss (`docs/user-flow.md:123` ghi ~30–60 s). Người gọi không thể biết mình sẽ nhận cái nào. Nó không cache được bởi bất kỳ tầng HTTP nào, không retry an toàn được, không có idempotency key, và giữ một connection HTTP mở suốt một phút — sẽ đụng idle timeout của proxy và load balancer từ rất lâu trước khi đụng giới hạn ứng dụng. Mở một hợp đồng cũ mà cache đã bị xoá sẽ âm thầm tiêu tiền thật.

**Tác động.** Khả năng mở rộng (connection giữ lâu, không có queue), khả năng dự đoán chi phí, UX (không tiến trình, không huỷ được), khả năng vận hành.

**Đề xuất refactor.** Tách đọc khỏi ghi:
- `GET /api/v1/contracts/{id}/analysis` → `200` với kết quả đã lưu, `404` nếu chưa từng phân tích. Cache được, rẻ, retry an toàn.
- `POST /api/v1/contracts/{id}/analysis-runs` → `202 Accepted` + `{run_id, status_url}`; công việc đi vào background worker.
- `GET /api/v1/analysis-runs/{run_id}` → `pending|running|succeeded|failed` kèm tiến trình (số điều khoản đã xét / tổng), và SSE hoặc polling cho UI.

Việc này cũng bỏ được `force` như một boolean magic và cho bạn một chỗ tự nhiên để ghi lại chi phí, thời lượng, và version model cho từng lần chạy.

**Độ khó:** Khó (cần worker và bảng job — xem BƯỚC 7).
**Ưu tiên:** **Cao.**

---

### I-25 · `GET /api/v1/contracts` không phân trang và trả về một mảng không giới hạn

**Hạng mục:** Thiết kế API / hiệu năng
**Dẫn chứng.** `contract_service.list_contracts:110-130` — `SELECT … WHERE user_id = %s ORDER BY created_at DESC` không có `LIMIT`, `fetchall()` vào một list, trả về dưới dạng `ContractListResponse.contracts` (`schemas/contract.py:93-94`). Frontend load tất cả lúc mount (`App.jsx:21-23`).

**Vì sao tệ.** Kích thước response và bộ nhớ tăng không giới hạn theo lịch sử của user. Không `LIMIT` cũng nghĩa là index composite của I-23 không thể dừng sớm.

**Tác động.** Độ trễ, bộ nhớ, băng thông trên mobile.

**Đề xuất refactor.** Keyset pagination: `?limit=50&cursor=<created_at,contract_id>`, với `WHERE user_id = $1 AND (created_at, contract_id) < ($2, $3) ORDER BY created_at DESC, contract_id DESC LIMIT $4` — index-only và ổn định khi có insert đồng thời, khác với `OFFSET`. Trả về `{items, next_cursor}`.

**Độ khó:** Dễ (backend) / Trung bình (kèm UI).
**Ưu tiên:** **Cao.**

---

### I-26 · Upload báo HTTP 200 khi parse thất bại, và frontend lập tức lỗi ở lần gọi tiếp theo

**Hạng mục:** Xử lý lỗi / thiết kế API / UX
**Dẫn chứng.**
```42:51:app/services/contract_service.py
    try:
        text = parse_document(file_path, file_ext)
        ...
    except Exception as e:
        logger.error(f"Upload parse failed: contract_id={contract_id} error={e}")
        message = f"File uploaded but parsing failed: {str(e)}"
```
Frontend nối upload → analyze một cách vô điều kiện:
```40:43:frontend/src/App.jsx
      const upload = await uploadContract(file);
      setStatusText("Đang chạy AI phân tích rủi ro & sai luật...");
      const analyzed = await analyzeContract(upload.contract_id, provider);
```
Khi không có chunk nào được index, `analyze_contract:97-99` ném `ValueError` → 404 → người dùng thấy *"No documents found for contract: …"*.

**Vì sao tệ.** `except Exception` trần không phân biệt được "PDF bị mã hoá" với "PDF scan không có lớp text" với "hết quota Gemini" với một bug — tất cả thành cùng một response 200. Lỗi thật nổi lên một request sau đó dưới dạng một 404 gây nhầm lẫn, và dòng dữ liệu bị để lại ở `status='uploaded'` mà không có đường retry. `chunk_count=0` là một tín hiệu hoàn toàn tốt mà không ai kiểm tra.

**Tác động.** UX, khả năng hỗ trợ, tính đúng đắn của việc xử lý lỗi.

**Đề xuất refactor.** Bắt exception cụ thể và map chúng sang các outcome có kiểu. Trả `422` kèm lý do hành động được cho input không parse được (và một mã riêng cho "PDF không có lớp text — hãy thử upload ảnh", điều mà đường OCR thực sự xử lý được). Cho frontend rẽ nhánh theo `status`/`chunk_count` trước khi gọi analyse. Lưu một mã `failure_reason`, không phải một thông báo thô.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-27 · Bộ test: 11 test, không phủ bất kỳ module AI hay truy hồi nào, và integration test cần một database production thật

**Hạng mục:** Testing
**Dẫn chứng.** Toàn bộ test: `tests/unit/test_agents.py` (2 — chỉ khởi tạo Pydantic), `test_chunker.py` (2), `test_parser.py` (3), `tests/integration/test_api.py` (4).

Module chưa được test: `risk_flagger`, `qa_agent`, `workflow`, `retriever`, `faiss_store`, `embeddings`, `knowledge_base/loader`, `core/auth`, `core/database`, `services/contract_service`, `agents/json_parsing`, `agents/llm_client`, `agents/checkpointer`, và **toàn bộ** logic extraction trong `clause_parser` (485 dòng, 0 test).

`tests/unit/test_agents.py` không test agent nào — nó khởi tạo hai model Pydantic. Và:
```23:25:tests/integration/test_api.py
def test_analyze_invalid_id():
    resp = client.post("/api/v1/analyze", json={"contract_id": "00000000-0000-0000-0000-000000000001"})
    assert resp.status_code == 404
```
Test này khẳng định 404, điều đòi hỏi `_assert_owns_contract` phải tới được một database thật và không tìm thấy gì. Không có `DATABASE_URL` (và `.env` không tồn tại), `psycopg2.connect("")` ném lỗi, handler trần biến nó thành 500, và test fail. Vì vậy bộ test hiện chỉ pass khi trỏ vào một Postgres thật — **ĐỀ XUẤT:** Postgres test container / Compose profile `test`, không phụ thuộc SaaS.

**Vì sao tệ.** Logic rủi ro cao nhất trong sản phẩm — truy hồi, ngưỡng từ chối, xác minh trích dẫn, graph fan-out, sửa JSON — có độ phủ tự động bằng không, trong khi độ sâu assertion của những gì *được* phủ thì rất thấp (`assert len(docs) >= 2`). Việc đòi một database dùng chung thật khiến bộ test không hermetic, chậm, phụ thuộc thứ tự, và không dùng được trong CI.

**Tác động.** Mọi refactor trong tài liệu này rủi ro hơn mức cần thiết. Không có lưới hồi quy nào cho I-1, I-10, hay I-13 — cả ba đều là bug suy thoái âm thầm mà chỉ test mới bắt được.

**Đề xuất refactor.**
1. `pytest.ini`/`pyproject.toml` với marker `unit` / `integration`, và `--strict-markers`.
2. Unit test hermetic: một hàm embedding giả (hash tất định → vector) và một store double trong RAM, để logic truy hồi và graph test được mà không cần mạng.
3. **Test hồi quy cho I-1**: index 500 chunk trên 50 hợp đồng, khẳng định `retrieve_contract` trả về đúng chunk của hợp đồng đích và ít nhất `min(k, n)` cái. Test này **fail ngày hôm nay**.
4. Golden-file test cho `clause_parser` trên các hợp đồng đã ẩn danh, một file cho mỗi nhóm field.
5. Contract test cho hình dạng JSON của LLM dùng response đã ghi lại (không gọi Gemini thật).
6. Integration test trên một Postgres tạm (testcontainers hoặc một CI service) đã áp migration — không bao giờ dùng môi trường dùng chung.
7. Nối tất cả vào CI với một sàn coverage.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-28 · I/O blocking và công việc nặng CPU chạy trên event loop

**Hạng mục:** Async
**Dẫn chứng.** Các hàm `async def` thực hiện công việc đồng bộ:
- `contract_service.upload_contract:36` → `parse_document` (pdfplumber / một lần gọi HTTP Gemini), `chunk_by_clause`, `add_documents` (suy luận SentenceTransformer + lưu toàn bộ index) — tất cả đồng bộ, không cái nào trong thread.
- `contract_service.analyze_contract:86`, `list_contracts:110`, `chat_with_contract:133`, `get_chat_history:138` → `psycopg2` blocking qua `get_db()`.
- `document/file_handler.save_upload:27-28` → `open()`/`write()` đồng bộ.
- `parse_image:52` → `get_chat_model().invoke(...)` blocking bên trong đường upload async.

`workflow.py:35,59` dùng `asyncio.to_thread` đúng cách; đường upload thì không.

**Vì sao tệ.** Một lần upload PDF lớn chặn event loop suốt cả parse + embed + lưu toàn bộ index (I-5). Trong khoảng đó process không phục vụ ai: health check timeout, các cuộc chat không liên quan bị treo, và load balancer có thể loại bỏ instance. Đây là khác biệt giữa một *endpoint* chậm và một *service* chậm.

**Tác động.** Throughput, tail latency trên mọi endpoint, tính khả dụng.

**Đề xuất refactor.** Đẩy công việc CPU/blocking ra khỏi loop (`asyncio.to_thread` hoặc `ProcessPoolExecutor` cho embedding), dùng truy cập DB async (I-12), dùng `aiofiles` hoặc ghi qua thread, và dùng `ainvoke` cho lệnh OCR. Về chiến lược, chuyển parse+embed vào background worker của I-24 để đường request chỉ còn việc đưa vào queue.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-29 · Không có timeout, retry, hay circuit breaking cho các lệnh gọi Gemini

**Hạng mục:** Xử lý lỗi / tính khả dụng
**Dẫn chứng.** `ChatGoogleGenerativeAI(model=…, google_api_key=…, temperature=0)` (`llm_client.py:19`) — không `timeout`, không `max_retries`. Nơi gọi retry đúng một lần và chỉ khi *JSON không parse được* (`clause_parser.py:411-415`, `risk_flagger.py:43-48`, `qa_agent.py:112-114`); một lỗi 429 hay 503 lan lên thành exception. Trong `_judge_clause_node:65-67` exception đó bị nuốt thành `{"risks": []}`.

**Vì sao tệ.** Một lần rate-limit tạm thời trên 5 trong 20 điều khoản âm thầm tạo ra một bản phân tích **thiếu 5 điều khoản đó** — không có dấu hiệu nào cho người dùng biết báo cáo bị thiếu. Đó là một thất bại về **tính đúng đắn** khoác áo khả năng chịu lỗi. Và không có timeout, một lệnh gọi upstream bị treo sẽ giữ một worker thread và một slot fan-out vô thời hạn.

**Tác động.** Tính đúng đắn (kết quả thiếu một cách âm thầm), tính khả dụng, chi phí (bão retry không backoff).

**Đề xuất refactor.** `timeout` và `max_retries` tường minh với exponential backoff và jitter trên client. Phân biệt lỗi *retry được* (429, 5xx, timeout) với lỗi *chấm hết* (4xx, bị chặn vì safety). Theo dõi trạng thái từng điều khoản trong kết quả (`judged | skipped_rate_limited | skipped_no_grounding | error`) và đưa một chỉ báo mức đầy đủ vào `AnalyzeResponse` để một báo cáo thiếu thì thiếu một cách hiển thị. Thêm circuit breaker để fail nhanh cả lượt chạy thay vì đốt 20 slot điều khoản vào một provider đang chết.

**Độ khó:** Trung bình.
**Ưu tiên:** **Cao.**

---

### I-30 · `AnalyzeResponse` không có kiểu ở biên API

**Hạng mục:** An toàn kiểu / thiết kế API
**Dẫn chứng.**
```59:62:app/schemas/contract.py
class AnalyzeResponse(BaseModel):
    contract_id: str
    analysis: Any
    risks: List[Any]
```
Trong khi `ContractAnalysis` và `RiskItem` đã được đặc tả đầy đủ ở `:27-47` và `:19-24`. Service dump ra dict trước khi trả về (`contract_service.py:107`), và đường cache trả JSONB thô trực tiếp từ database (`:74`).

**Vì sao tệ.** Hai đường response — cache và tươi — không bao giờ được validate theo cùng một hình dạng, nên một thay đổi schema của `ContractAnalysis` để lại JSONB cache cũ không tương thích một cách âm thầm và hợp đồng API không phát hiện được. `Any` cũng có nghĩa là OpenAPI schema sinh ra rỗng cho response quan trọng nhất của sản phẩm, nên không client nào sinh được và frontend phải viết tay việc truy cập field (`AnalysisResult.jsx:11-17`).

**Tác động.** An toàn kiểu, lệch client/server, chất lượng tài liệu API.

**Đề xuất refactor.** `analysis: ContractAnalysis` và `risks: List[RiskItem]`. Validate JSONB đã cache qua chính các model đó khi đọc (`ContractAnalysis.model_validate(row)`) để những entry cache không tương thích fail ồn ào và có thể tái tạo. Thêm một cột `schema_version` bên cạnh JSONB để việc migrate là tường minh.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

### I-31 · Không pin dependency nào, hai driver PostgreSQL, và không có lockfile

**Hạng mục:** Quản lý cấu hình / khả năng tái lập
**Dẫn chứng.**
```1:21:requirements.txt
fastapi
uvicorn[standard]
torch
sentence-transformers
faiss-cpu
numpy
langchain
langchain-core
langchain-community
langchain-huggingface
langchain-google-genai
langgraph
langgraph-checkpoint-postgres
psycopg[binary]
pdfplumber
pydantic
python-dotenv
python-multipart
python-docx
psycopg2-binary
httpx
```

**Vì sao tệ.** Không version nào bị ràng buộc, nên hai lần cài cách nhau một tuần cho ra hai phần mềm khác nhau — và stack này đặc biệt biến động (LangChain đã tổ chức lại theo cách phá vỡ tương thích nhiều lần; bộ đã cài ở đây là `langchain 1.3.1` + `langchain-community 0.4.1`). Code còn phụ thuộc vào attribute **private** của hai trong số các package này (`faiss_store.py:65` `docstore._dict`; `embeddings.py:26` `_embeddings._client`), đúng là thứ mà một bản minor bump sẽ làm hỏng. `torch` không pin và không chỉ định biến thể sẽ kéo về bản CUDA ~2,5 GB trên Linux ngay cả với deploy chỉ dùng CPU. `psycopg[binary]` (v3, cho checkpointer) và `psycopg2-binary` (v2, cho mọi thứ còn lại) đều có mặt — hai driver, hai mô hình connection, hai câu chuyện pooling trong một process.

**Tác động.** Khả năng tái lập, độ tin cậy khi deploy, kích thước image và cold start, khả năng bảo trì.

**Đề xuất refactor.** Chuyển sang `pyproject.toml` với một lockfile đã resolve (`uv lock` hoặc `poetry.lock`); pin version chính xác cho dependency ứng dụng và chỉ dùng khoảng tương thích cho library. Cài `torch` từ index CPU một cách tường minh. Xoá `psycopg2-binary` và chuẩn hoá về `psycopg` 3 (điều này cũng mở đường cho pool async dùng chung ở I-12). Thêm một job cập nhật dependency theo lịch để việc pin không biến thành lạc hậu.

**Độ khó:** Dễ.
**Ưu tiên:** **Cao.**

---

## MỨC TRUNG BÌNH (MEDIUM)

### I-32 · Hook startup/shutdown `@app.on_event` đã deprecated
**Hạng mục:** Khả năng bảo trì. **Dẫn chứng:** `main.py:27,35`. Đã deprecated từ FastAPI 0.93, thay bằng `lifespan`. Cũng làm startup/shutdown không unit-test được và ngăn `TestClient` thực thi chúng một cách dự đoán được (liên quan I-27). **Đề xuất:** `@asynccontextmanager async def lifespan(app)` và `FastAPI(lifespan=lifespan)`; chuyển `init_db()` ra hẳn theo I-9. **Độ khó:** Dễ. **Ưu tiên:** Trung bình. *(Cũng được ghi trong `PROGRESS_REPORT.md:104`.)*

### I-33 · Cấu hình là biến global cấp module không được validate
**Hạng mục:** Quản lý cấu hình / DI. **Dẫn chứng:** `core/config.py:8-25` — 15 lệnh `os.getenv`, ép kiểu `int()`/`float()` ném một `ValueError` không hữu ích ngay lúc import nếu gõ sai, không kiểm biên (`SIMILARITY_THRESHOLD=5.0` được chấp nhận và âm thầm vô hiệu hoá toàn bộ truy hồi pháp luật), không cưỡng chế field bắt buộc (`GEMINI_API_KEY` rỗng chỉ fail ở lần gọi LLM đầu tiên), và hai side effect `os.makedirs` lúc import (H-2). **Vì sao tệ:** cấu hình sai nổi lên muộn và xa nguyên nhân; không gì override được theo từng test. **Đề xuất:** `pydantic-settings` `BaseSettings` với biên `Field(ge=…, le=…)`, field bắt buộc, `SecretStr` cho khoá, một accessor `get_settings()` có cache được inject qua `Depends`, và validate fail-fast lúc startup kèm báo cáo dễ đọc. **Độ khó:** Dễ. **Ưu tiên:** Trung bình.

### I-34 · Không có dependency injection: singleton và module import khắp nơi
**Hạng mục:** Dependency injection / khả năng test. **Dẫn chứng:** 3 singleton global cấp module (`faiss_store.py:80-81`, `embeddings.py:5`, `llm_client.py:9`), 2 cái nữa trong `checkpointer.py:7-8`, 2 graph LangGraph compile cấp module (`workflow.py:82`, `qa_agent.py:158`), config là biến global. `Depends` của FastAPI chỉ dùng cho auth. **Vì sao tệ:** không có đường ráp cho test double, nên mọi test cần đồ thật (một database, một model 500 MB, một API trả phí); và tuổi thọ singleton gắn với tuổi thọ process, đó chính là điều làm I-4 không sửa được tại chỗ. **Đề xuất:** định nghĩa protocol cho `VectorStore`, `Embedder`, `ChatModel`, `ContractRepository`; tạo instance cụ thể một lần trong `lifespan` và lưu trên `app.state`; inject qua `Depends`. Giữ đúng phong cách FastAPI và không cần framework DI nào. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình.

### I-35 · `logger.error` dùng cho luồng điều khiển bình thường; không có logging có cấu trúc hay correlation id
**Hạng mục:** Logging / observability. **Dẫn chứng:** `qa_agent.py:139` log trích dẫn bị loại ở mức ERROR (một *thành công* của cơ chế an toàn); `clause_parser.py:411` và `risk_flagger.py:43` log ở ERROR trước một lần retry thường thành công. Toàn bộ logging là nội suy f-string vào một stream text (`config.py:27-33`) không có request id, user id, trace id, hay JSON. Không có metric và không có tracing. **Vì sao tệ:** ERROR mất ý nghĩa, nên không thể alert trên lỗi thật; và với fan-out đồng thời (4 điều khoản song song), các dòng text thuần xen kẽ không thể tương quan về một request hay một điều khoản. **Đề xuất:** sửa lại mức (trích dẫn bị loại → WARNING kèm counter; trước retry → INFO/DEBUG). Dùng logging JSON có cấu trúc với một correlation id `contextvar` do middleware đặt và lan truyền vào các node LangGraph. Phát metric cho những thứ quan trọng về vận hành: tỉ lệ hit truy hồi, tỉ lệ từ chối, tỉ lệ `insufficient_evidence`, độ trễ/chi phí/token của LLM mỗi lượt chạy, tỉ lệ cache hit. Thêm span OpenTelemetry quanh truy hồi và mỗi lệnh gọi LLM. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình.

### I-36 · Hai regex cắt điều khoản khác nhau tạo ra danh tính điều khoản không nhất quán
**Hạng mục:** Logic trùng lặp / tính đúng đắn. **Dẫn chứng:** `clause_parser.py:370-373` chỉ khớp `Điều|ĐIỀU`; `chunker.py:46` khớp `Điều|ĐIỀU|Khoản|KHOẢN`. **Vì sao tệ:** danh sách điều khoản của bộ phân tích và metadata `clause_number` của chunker được tạo bởi hai luật khác nhau trên cùng một văn bản, nên `RiskItem.clause_ref` ("Điều 5", `risk_flagger.py:16`) và không gian trích dẫn của chat (`metadata["clause_number"]`, có thể là số *Khoản*, `chunker.py:76`) không cùng một không gian định danh. Việc xác minh trích dẫn ở `qa_agent.py:136` so sánh xuyên hai không gian này, nên một trích dẫn hợp lệ có thể bị loại và một trích dẫn sai có thể được chấp nhận khi số Khoản trùng với số Điều. **Đề xuất:** một module `clause_identity` duy nhất sở hữu ngữ pháp cho Điều/Khoản/Điểm, trả về một `ClauseRef(article, clause, point)` có cấu trúc. Dùng nó ở cả hai nơi; làm không gian trích dẫn tường minh và so sánh được. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình.

### I-37 · Frontend không có routing, không retry, và nhân bản state của server
**Hạng mục:** Kiến trúc frontend. **Dẫn chứng:** `App.jsx:9-132` — bốn trạng thái view trong `useState` local, không router (`package.json` không có dependency routing nào), không deep link, và refresh trang là mất hợp đồng đang mở. State server bị nhân bản một cách optimistic lúc upload (`App.jsx:45-48` chèn một dòng với `status: "analyzed"` và `created_at` do client sinh) và lỗi của `listContracts()` bị nuốt thành list rỗng (`:25-27`) nên người dùng thấy "không có hợp đồng" thay vì một lỗi. Không có huỷ request và không có retry ở đâu cả. **Vì sao tệ:** URL không chia sẻ được, mất việc khi refresh, sự phân kỳ sự thật client/server trong danh sách, và các lỗi trông như trạng thái rỗng. **Đề xuất:** thêm router với `/contracts`, `/contracts/:id`, `/upload`; dùng một thư viện server-state (TanStack Query) cho cache, retry, invalidation, và trạng thái loading/error để việc chèn optimistic được thay bằng invalidate cache; render một trạng thái lỗi tường minh khác với trạng thái rỗng. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình.

### I-38 · Không rate limit, quota, hay kiểm soát lạm dụng trên các endpoint tiêu tiền LLM
**Hạng mục:** Bảo mật / chi phí. **Dẫn chứng:** không có middleware rate-limit trong `main.py`; `POST /analyze` với `force=true` (`routes.py:15`) chạy lại toàn bộ workflow theo yêu cầu, và `POST /chat` là một lệnh gọi LLM cho mỗi request. **Vì sao tệ:** bất kỳ người dùng đã xác thực có thể lặp `force=true` và biến ngân sách Gemini của bạn thành một cuộc tấn công denial-of-wallet của họ, đồng thời làm bão hoà 4 slot fan-out với mọi người dùng khác. **Đề xuất:** rate limit theo user và theo IP ở ingress; một quota phân tích/chat hằng ngày theo user được cưỡng chế trong ứng dụng với 429 rõ ràng; hạch toán chi phí theo lượt chạy (tự nhiên khi bảng run của I-24 đã có); một trần concurrency toàn cục cho lệnh gọi LLM dùng chung giữa các request, không phải theo từng request. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình.

### I-39 · `GET /api/v1/models` không yêu cầu xác thực
**Hạng mục:** Thiết kế API / bảo mật. **Dẫn chứng:** `routes.py:24-26` không có `Depends(get_current_user_id)`, khác mọi route khác. Nó làm lộ chính xác định danh model (`GEMINI_MODEL`, `llm_client.py:5`). **Vì sao tệ:** tiết lộ thông tin ở mức nhỏ và một điểm bất nhất trong câu chuyện auth; nó cũng là một endpoint không xác thực có thể bị dội tuỳ ý. **Đề xuất:** yêu cầu auth cho nhất quán, hoặc chuyển nó thành hằng số lúc build trong frontend, vì giá trị này là cấu hình tĩnh chứ không phải dữ liệu. **Độ khó:** Dễ. **Ưu tiên:** Trung bình.

### I-40 · Danh tính thread của `chat` là hợp đồng, không phải (user, hợp đồng)
**Hạng mục:** Kiến trúc / mô hình hoá dữ liệu. **Dẫn chứng:** `qa_agent.py:174` — `config={"configurable": {"thread_id": contract_id}}`. **Vì sao tệ:** nó chỉ hoạt động hôm nay vì `_assert_owns_contract` bảo đảm mỗi hợp đồng có một chủ. Ngay khi có chia sẻ, workspace nhóm, hay chuyển quyền sở hữu (đều là các tính năng tiếp theo hợp lý), hai người dùng sẽ dùng chung một cuộc hội thoại một cách trong suốt, bao gồm cả câu hỏi của nhau. Cũng không có cách nào bắt đầu một cuộc hội thoại thứ hai, riêng biệt, về cùng một hợp đồng. **Đề xuất:** `thread_id = f"{user_id}:{contract_id}:{conversation_id}"`, với `conversation_id` là một thực thể hạng nhất. Làm việc này *trước* bất kỳ tính năng chia sẻ nào, vì migrate các checkpoint thread đã có sau đó rất khó chịu. **Độ khó:** Dễ bây giờ, Khó về sau. **Ưu tiên:** Trung bình.

### I-41 · File upload được ghi xuống đĩa local không có lifecycle, mã hoá, hay dọn dẹp
**Hạng mục:** Kiến trúc / bảo mật / vận hành. **Dẫn chứng:** `file_handler.py:25` ghi vào `UPLOAD_DIR` (`data/uploads`, `config.py:16`); `data/` bị git-ignore (`.gitignore:9`); không có đường xoá nào ở đâu trong `app/`; `uploaded_contracts.file_path` được lưu (`database.py:37`) nhưng chỉ được ghi, không bao giờ được đọc. **Vì sao tệ:** hợp đồng đã ký — dữ liệu cá nhân nhạy cảm về thương mại — tích tụ mãi mãi trên một filesystem container tạm thời: mất khi redeploy (nên `file_path` trở thành treo lơ lửng), không mã hoá at rest, không backup, không xoá được theo yêu cầu người dùng. Với nghĩa vụ về dữ liệu cá nhân của Việt Nam (và mọi yêu cầu tương tự GDPR) thì không có cách nào thực hiện một yêu cầu xoá. Nó cũng cố định thêm ràng buộc một-node của I-4. **Đề xuất:** object storage S3-compatible (**MinIO trong Docker Compose** cho dev/prod tự host, hoặc S3 managed sau này) với mã hoá phía server, lifecycle policy, và pre-signed URL; lưu object key thay vì đường dẫn local; hiện thực hard delete object + dòng dữ liệu + chunk + checkpoint theo yêu cầu người dùng.dùng; nếu buộc phải giữ đĩa local, mount một volume persistent đã mã hoá và thêm job retention. **Độ khó:** Trung bình. **Ưu tiên:** Trung bình. *(Nâng lên Cao nếu hệ thống đang xử lý hợp đồng khách hàng thật.)*

---

## Tổng hợp các vấn đề

| Mức ưu tiên | Số lượng | Mã |
|---|---|---|
| Nghiêm trọng | 12 | I-1 … I-12 |
| Cao | 19 | I-13 … I-31 |
| Trung bình | 10 | I-32 … I-41 |

**Độ phủ hạng mục của bản rà soát** (các hạng mục được yêu cầu trong đề bài, và nơi từng cái được xử lý): Kiến trúc I-4, I-24, I-41 · SOLID I-21, I-22 · Clean Architecture I-22, I-34 · Vi phạm phân tầng §3.2, I-6 · God object I-21 · Hàm dài I-21 · Logic trùng lặp I-19, I-36, §3.6 · Đặt tên §3.7, I-35 · Async I-15, I-28 · Rò rỉ/phình bộ nhớ I-7, I-14, I-6 · Xử lý lỗi I-16, I-26, I-29 · Logging I-35 · Cấu hình I-31, I-33, I-9 · Dependency Injection I-34 · Testing I-27 · An toàn kiểu I-30, I-3 · Xử lý exception I-16, I-26 · Thiết kế API I-24, I-25, I-39 · Thiết kế query I-1, I-6, I-23 · Xử lý theo batch I-5, và `loader.py:26-28` (làm đúng: server-side cursor với `itersize`) · Streaming I-7, I-28 (không có; cũng không stream response LLM, đó là vì sao chat cảm giác chậm) · Cache §2.8, I-14 · Xử lý transaction ở dưới · Tái dùng code §3.6 · Cấu trúc thư mục ở dưới · Phân tách domain I-21 · Repository pattern I-22 · Service pattern I-22 · Mức phù hợp của CQRS ở dưới · Mức phù hợp của event-driven ở dưới.

**Xử lý transaction (đánh giá).** `get_db()` cho một transaction cho mỗi context manager và rollback đúng khi có exception (`database.py:14-24`). Nhưng `upload_contract` thực hiện ba side effect — ghi đĩa, mutate FAISS, insert DB — mà không có hành động bù trừ, nên một lỗi DB sau khi FAISS insert thành công để lại một vector mồ côi không có dòng dữ liệu (và theo I-4, không có cách nào tìm được nó). Khi chunk sống trong pgvector, đây trở thành một transaction duy nhất và sự bất nhất biến mất. Đó là một luận cứ phụ đáng kể cho việc migration.

**Cấu trúc thư mục (đánh giá).** Bố cục hợp lý và tốt hơn phần lớn dự án ở giai đoạn này: phân tách rõ `api / services / agents / document / vectorstore / core / schemas`, test phản chiếu source. Hai vấn đề thật: `agents/` trộn agent thật (`qa_agent`, `risk_flagger`) với hạ tầng (`llm_client`, `checkpointer`, `json_parsing`) và một module xử lý văn bản thuần (`clause_parser` không dùng bộ máy agent nào); và `helpers/` là một cái tên hút code không liên quan (hiện chỉ chứa code chết). **Đề xuất:** `agents/` chỉ dành cho điều phối; chuyển `llm_client`/`checkpointer`/`json_parsing` sang `infrastructure/llm/`; chuyển `clause_parser` sang `document/extraction/`; xoá `helpers/`. Thêm `repositories/` (I-22) và `workers/` (I-24).

**Mức phù hợp của CQRS (đánh giá).** CQRS đầy đủ với store riêng biệt là không chính đáng — lượng ghi thấp và không có tranh chấp read-model. Nhưng *việc tách command/query* lại chính xác là cách sửa đúng cho I-24, và đáng áp dụng ở tầng API và service: `AnalysisReadService` (rẻ, cache được, thân thiện với replica) so với `AnalysisRunCommand` (đắt, xếp hàng, idempotent). Lấy phần kỷ luật đặt tên và phân tách; bỏ phần bộ máy event-sourcing.

**Mức phù hợp của event-driven (đánh giá).** Chính đáng ở đúng một chỗ: pipeline phân tích (I-24, I-28). `upload → parse → chunk → embed → judge` là một pipeline dài, dễ lỗi, đắt, song song hoá được — trường hợp kinh điển cho một queue có retry và dead-lettering. Chính đáng về sau cho ingestion corpus: khi một lần crawl lại làm thay đổi một văn bản, một event `document.updated` nên kích hoạt re-embed các section bị ảnh hưởng và invalidate các phân tích phụ thuộc (đó là cách để sửa I-10 một cách bền vững). *Không* chính đáng cho CRUD (`GET /contracts`), và không chính đáng như một event bus toàn hệ thống — điều đó sẽ thêm gánh nặng distributed tracing lên một codebase còn chưa có cả correlation id.

---

# BƯỚC 5 — Phân tích database và dữ liệu crawler

## 5.1 Các nguồn sự thật về schema (ba nguồn, không nhất quán với nhau)

| Nguồn | Trạng thái | Định nghĩa |
|---|---|---|
| `app/core/database.py:27-49` | Được track, chạy ở mỗi lần startup | `uploaded_contracts` (+3 cột thêm muộn, 2 index) |
| `schema.sql` | **Chưa track**, không bao giờ được code chạy | `legal_documents`, `legal_document_sections`, `contract_chunks`, extension pgvector |
| `app/knowledge_base/loader.py:6-13` | Được track, chạy bởi CLI | Hàm ý `legal_documents(doc_number, category, status_flag)` + `document_chunks(chunk_ref, chunk_index, chunk_text, section_type)` |
| LangGraph `AsyncPostgresSaver.setup()` | Thư viện quản lý | `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` |

**THỰC TẾ.** Không có hai nguồn nào trong ba nguồn đầu khớp nhau. Xem I-2 và I-3.

**THỰC TẾ.** `PROGRESS_REPORT.md:108` ghi lại các bảng bổ sung trên instance DB từng dùng (`contracts`, `contract_chunks`, `contract_types`, `scraped_contracts`) mà không có code Python nào dùng, và `schema.sql` nhắc tới một `contract_chunks` đã *bị xoá trước đó*. **CHƯA RÕ:** schema thực tế đang chạy. Cái này phải được dump (`pg_dump --schema-only`) từ Postgres Docker/instance hiện có và đối chiếu trước bất kỳ migration nào — task **P0-1** / **P1-0** trong lộ trình.

## 5.2 ERD hiện tại (as-is, hợp của mọi nguồn)

```mermaid
erDiagram
    uploaded_contracts {
        BIGSERIAL id PK
        TEXT contract_id UK "chuỗi uuid4(); là UUID trong schema.sql"
        UUID user_id "thực tế nullable (thêm bằng ALTER)"
        TEXT filename
        TEXT file_type
        TEXT file_path "được ghi, không bao giờ được đọc"
        TEXT status "uploaded|parsed|analyzed - không CHECK"
        TEXT message
        INTEGER chunk_count
        JSONB analysis "dump ContractAnalysis - không có version schema"
        JSONB risks "dump RiskItem[]"
        TIMESTAMP created_at "không tz; không có updated_at"
    }
    legal_documents {
        TEXT doc_id PK
        TEXT doc_num "loader.py gọi là doc_number"
        TEXT title
        TEXT doc_type
        TEXT_ARRAY majors
        TEXT_ARRAY fields
        DATE issue_date
        DATE eff_from
        DATE eff_to
        TEXT eff_status
        TEXT eff_status_code "loader.py mong đợi status_flag"
        TEXT agency
        JSONB signers
        TEXT source_url
        TEXT full_text "nhân bản toàn bộ nội dung section"
        TEXT preamble
        TEXT closing
        TIMESTAMPTZ crawled_at
        TIMESTAMPTZ updated_at
    }
    legal_document_sections {
        TEXT id PK "id node vbpl"
        TEXT doc_id FK
        TEXT parent_id FK "tự tham chiếu, ON DELETE CASCADE"
        TEXT level "Chapter|Section|Article|Clause|Point - không CHECK"
        INTEGER ptype "mã vbpl thô - trùng lặp với level"
        INTEGER order_index
        TEXT title
        TEXT content "NULL với Chapter/Section"
        TEXT breadcrumb "đường dẫn phi chuẩn hoá dạng text tự do"
        VECTOR768 embedding "HNSW partial trên Article|Clause"
        TIMESTAMPTZ created_at
    }
    contract_chunks {
        SERIAL id PK
        UUID contract_id FK "LỆCH KIỂU so với uploaded_contracts.contract_id TEXT"
        INTEGER chunk_index
        TEXT content
        VECTOR768 embedding
        TIMESTAMPTZ created_at
    }
    checkpoints {
        TEXT thread_id PK "= contract_id"
        TEXT checkpoint_ns PK
        TEXT checkpoint_id PK
        JSONB metadata
    }
    checkpoint_blobs { TEXT thread_id PK }
    checkpoint_writes { TEXT thread_id PK }

    legal_documents ||--o{ legal_document_sections : "1:N, CASCADE"
    legal_document_sections ||--o{ legal_document_sections : "parent_id, 1:N"
    uploaded_contracts ||--o{ contract_chunks : "1:N (constraint không hợp lệ)"
    checkpoints ||--o{ checkpoint_blobs : "thread_id"
    checkpoints ||--o{ checkpoint_writes : "thread_id"
```

**Lực lượng quan hệ (đo từ văn bản duy nhất có sẵn):** `legal_documents 1 : 1308 legal_document_sections`, trong đó 387 (29,6%) sẽ có anchor nội dung và embed được.

### Kiểm kê và đánh giá index

| Index | Định nghĩa tại | Đánh giá |
|---|---|---|
| `uploaded_contracts` UNIQUE(contract_id) | `database.py:33` | Cần thiết |
| `idx_contracts_id (contract_id)` | `database.py:47` | **Dư thừa** — trùng với cái trên (I-23) |
| `idx_contracts_user (user_id)` | `database.py:48` | Không đủ — query còn sắp xếp theo `created_at DESC` (I-23) |
| `idx_ld_doc_type`, `idx_ld_eff_status`, `idx_ld_issue_date DESC` | `schema.sql:31-33` | Hợp lý, dù btree một cột với lực lượng thấp (`doc_type`, `eff_status_code`) hiếm khi thắng seq scan nếu đứng một mình; chỉ hữu ích khi là phần của composite |
| `idx_ld_title_gin USING gin(to_tsvector('simple', title))` | `schema.sql:34` | **`'simple'` là sai cho tiếng Việt.** `simple` không stem và không xử lý stop-word; nó cũng không bỏ dấu, nên `"lao động"` và `"lao dong"` không khớp nhau. Cần `unaccent` + một configuration tiếng Việt, hoặc tìm kiếm trigram. |
| `idx_lds_doc (doc_id, order_index)` | `schema.sql:56` | Tốt — hỗ trợ render văn bản theo thứ tự |
| `idx_lds_parent (parent_id)` | `schema.sql:57` | Cần cho việc đi xuống đệ quy |
| `idx_lds_level (level)` | `schema.sql:58` | Giá trị thấp nếu đứng một mình (5 giá trị phân biệt trên hàng triệu dòng); chỉ hữu ích trong composite hoặc partial index |
| `idx_lds_content_gin` | `schema.sql:59` | Cùng vấn đề `'simple'` như trên, trên cột quan trọng hơn nhiều |
| `idx_lds_embedding` HNSW partial `WHERE level IN ('Article','Clause')` | `schema.sql:60-62` | **Trực giác tốt** — predicate partial giữ 909 dòng Point mỗi văn bản ra ngoài index. Nhưng không nêu `m`/`ef_construction`, nên mặc định pgvector (16/64) được áp dụng, và không xem xét phương án `vector_l2_ops`/`ip_ops`. Ngoài ra: một partial HNSW index chỉ dùng được khi query lặp lại đúng predicate — xem BƯỚC 9. |
| `idx_cc_contract (contract_id, chunk_index)` | `schema.sql:80` | Tốt |
| `idx_cc_embedding` HNSW, không partial | `schema.sql:81` | Đúng cho bảng này, nhưng xem cảnh báo filtered-recall ở BƯỚC 9 |

### Constraint: những gì đang thiếu

**THỰC TẾ.** Trên cả ba nguồn **không có một** constraint `CHECK` nào, không `NOT NULL` cho `legal_documents.eff_from`/`issue_date`, không unique constraint trên `(doc_id, order_index)` hay trên `legal_documents.doc_num`, không `CHECK (level IN (...))`, không `CHECK (eff_to IS NULL OR eff_to >= eff_from)`, không `CHECK (status IN ('uploaded','parsed','analyzed'))`, không `CHECK (severity IN ('critical','warning','ok'))` trên JSONB, và không trigger `updated_at` nào ở đâu (`legal_documents.updated_at` mặc định `NOW()` ở `schema.sql:25` và không bao giờ được cập nhật). Severity chỉ được validate trong Pydantic (`schemas/contract.py:22`), điều này không bảo vệ database khỏi bất kỳ writer nào khác.

**SUY LUẬN.** Database đang bị dùng như một kho lưu ngu ngơ với mọi bất biến nằm trong code ứng dụng. Điều đó bảo vệ được với một prototype một writer và không thể duy trì với một hệ thống có crawler, một script backfill, và một API cùng ghi đồng thời.

### Đánh giá mức chuẩn hoá

- `uploaded_contracts` — vi phạm 1NF có chủ ý: `analysis` và `risks` JSONB giữ các nhóm lặp (bên, điều khoản, mục rủi ro). Chấp nhận được như một *cache* của kết quả đã tính; không chấp nhận được như bề mặt query (bạn không thể hỏi "cho tôi mọi hợp đồng có rủi ro nghiêm trọng ở điều khoản chấm dứt" mà không quét toàn bộ JSONB).
- `legal_documents` — phần lớn ở 3NF. Hai phi chuẩn hoá có chủ ý: `full_text` (`:21`) nhân bản việc ghép nối toàn bộ nội dung section, và `majors`/`fields` là array thay vì bảng nối. Lựa chọn array là ổn (từ vựng nhỏ, khá đóng, GIN-index được); `full_text` làm **nhân đôi** dung lượng corpus một cách xấp xỉ (BƯỚC 13).
- `legal_document_sections` — 3NF, ngoại trừ `breadcrumb` (`:49`) và `ptype` (`:45`) đều là dẫn xuất (`breadcrumb` từ chuỗi cha, `ptype` từ `level` — quan hệ 1:1 trong dữ liệu đã đo: 2↔Chapter, 3↔Section, 5↔Article, 6↔Clause, 7↔Point). `breadcrumb` ở dạng text tự do là không query được về mặt cấu trúc, và đó chính xác là khoảng trống mà `ltree` lấp (BƯỚC 10).

## 5.3 Phân tích output crawler (đo lường, không lấy mẫu)

Mọi con số dưới đây được tạo ra bằng cách chạy script đo lường trên bốn file trong `Nghị định số 168-2024-NĐ-CP …`. Cỡ mẫu: **1 văn bản**.

### Dữ liệu nào được thu thập

| File | Kích thước | Nội dung |
|---|---|---|
| `thuoc_tinh.json` | 700 B | 13 khoá: `doc_id, doc_num, doc_type, title, majors, fields, issue_date, eff_from, eff_to, eff_status, eff_status_code, agency, signers` |
| `luoc_do.json` | 6.4 KB | `doc_id`, `relations` (đi ra), `relations_incoming` — **15 loại quan hệ mỗi bên** |
| `muc_luc.json` | 474 KB | Cây mục lục lồng nhau, 1308 node, 7–8 khoá mỗi node |
| `van_ban.md` | 364 KB (278k ký tự) | Toàn văn, Markdown, với anchor id dạng HTML comment |

**THỰC TẾ — các khoá của `thuoc_tinh.json` map 1:1 lên `schema.sql:8-20`** (trừ `doc_num`). Phần schema này có cơ sở tốt trong output crawler thật. `source_url`, `full_text`, `preamble`, `closing` không có trong output crawler và phải được dẫn xuất.

**THỰC TẾ — `doc_id` có hai định dạng khác nhau trong cùng một corpus.** Chuỗi số (`"173920"`, `"70821"`, `"140152"`) và UUID (`"b043c150-7924-11f1-85a7-e1f385e447d3"`, `"c30f4280-751b-11f1-9da1-8d4aca03d986"`), cả hai đều xuất hiện trong `luoc_do.json`. **Điều này xác nhận lựa chọn `TEXT` cho `doc_id` của `schema.sql`** — một cột `UUID` hay `BIGINT` sẽ từ chối một nửa corpus. Hãy giữ nó, và thêm một `CHECK` ghi lại cả hai hình dạng được chấp nhận.

### Cấu trúc phân cấp văn bản (đo được)

```
Cấp:   Chapter 4  ·  Section 8  ·  Article 55  ·  Clause 332  ·  Point 909      (tổng 1308)
ptype:      2           3              5             6              7
Histogram độ sâu (đánh số từ 1): {1: 4, 2: 17, 3: 80, 4: 376, 5: 831}   → độ sâu tối đa 5
```

**THỰC TẾ — cây *không* đồng nhất theo cấp.** Các cặp cha→con quan sát được:

| Cha → Con | Số lượng |
|---|---|
| (gốc) → Chapter | 4 |
| Chapter → Section | 8 |
| Chapter → **Article** | **9** |
| Section → Article | 46 |
| Article → Clause | 332 |
| Clause → Point | 909 |

Chín Điều treo trực tiếp dưới một Chương trong khi 46 Điều nằm dưới một Mục. **Đây là sự thật cấu trúc quan trọng nhất cho thiết kế ltree**: *độ sâu* trên cây không xác định *cấp* ngữ nghĩa, nên bất kỳ lược đồ path nào mã hoá vị trí theo độ sâu (`doc.1.2.3`) đều sai. Nhãn phải mã hoá cấp một cách tường minh (BƯỚC 10).

**THỰC TẾ — không có cấp nào dưới `Point`.** Văn bản VN quy phạm thường **hết ở Điểm**. **ĐỀ XUẤT sản phẩm:** bỏ `Subpoint` khỏi schema; cây = Chương → Mục → **Điều → Khoản → Điểm**, cộng nhánh **Phụ lục → Nhóm**.

**THỰC TẾ — `id == key` với cả 1308 node**, và `orderIndex` là một **chuỗi DFS pre-order dày đặc 1…1308** không có khoảng trống hay trùng lặp. Điều này có giá trị: chỉ riêng `order_index` tái tạo đúng thứ tự đọc cho toàn văn bản bằng một `ORDER BY`, và việc đánh số pre-order nghĩa là subtree của một node là một khoảng liên tục — một khoảng nested-set miễn phí nếu bạn cũng lưu kích thước subtree của mỗi node.

### Neo nội dung — hạn chế then chốt

**THỰC TẾ (đo được).** `van_ban.md` chứa đúng hai loại marker:

```
<!-- article_id: 2acb4400-2db9-11f1-8a65-454fe993a476 -->     × 55  (tất cả duy nhất)
<!-- clause_id:  2acbe040-2db9-11f1-b74c-ddf3a70d5e51 -->     × 332 (tất cả duy nhất)
```

Kết quả đối chiếu:
- marker article không có trong mục lục: **0**; Article trong mục lục không có trong Markdown: **0**
- marker clause không có trong mục lục: **0**; Clause trong mục lục không có trong Markdown: **0**
- id **Point** trong mục lục xuất hiện ở bất cứ đâu trong Markdown: **0** (trên 909)
- id **Chapter/Section** trong mục lục xuất hiện ở bất cứ đâu trong Markdown: **0** (trên 12)

Tổng: **387 trên 1308 node (29,6%) có thể định địa chỉ nội dung.**

**Điều này trực tiếp trái với một khẳng định trong `schema.sql`:**
```37:39:schema.sql
-- id == id tu API muc luc vbpl == id cua the <p> trong HTML noi dung (da xac
-- nhan khop 1-1 qua vi du thuc te Luat Thue TNCN 109/2025/QH15).
```
**THỰC TẾ.** Với `doc_id=173920`, tương ứng 1:1 chỉ đúng **ở cấp Điều và Khoản**. Nội dung cấp Điểm có mặt dưới dạng text nội tuyến (`a) …`, `b) …`) mà không có id. **SUY LUẬN:** hoặc bộ render Markdown của crawler chỉ phát anchor cho hai cấp đó, hoặc HTML của vbpl chỉ có `<p id>` ở hai cấp đó với loại văn bản này. Dù thế nào, `legal_document_sections.content` **không thể được điền cho 909 dòng Point** từ những artifact này, và partial HNSW index ở `schema.sql:60-62` (`WHERE level IN ('Article','Clause')`) tình cờ lại chính xác đúng — có lẽ vì một lý do sai.

**Hệ quả cho thiết kế.** Văn bản cấp Điểm phải được lấy bằng cách *phân đoạn* nội dung của Khoản theo mẫu marker `^[a-zđ])\s`, một bước parse mà hiện không có code nào hiện thực. Cho tới khi có nó, độ mịn nhỏ nhất truy hồi được là Khoản. **ĐỀ XUẤT:** lấy Khoản làm đơn vị truy hồi chính và coi Điểm là một tinh chỉnh cho trình bày/trích dẫn dẫn xuất từ việc parse — đừng chặn pipeline vì những anchor cấp Điểm mà nguồn không cung cấp.

### Tiêu đề — mục lục và phần thân mỗi bên giữ một nửa

**THỰC TẾ.** Tiêu đề trong `muc_luc.json` là nhãn trần: `"Điều 1"`, `"Chương I"`, `"Mục 1"`, `"Khoản 1"`, `"Điểm a"`. Phần *tên điều* chỉ tồn tại trong `van_ban.md` dưới dạng heading H2: `## **Điều 1. Phạm vi điều chỉnh**` (55 heading như vậy, khớp chính xác 55 Điều). Tên chương (`**NHỮNG QUY ĐỊNH CHUNG**`) xuất hiện trong phần thân dưới dạng dòng in đậm, không phải heading.

`schema.sql:47` comment rằng `title` giữ `"Dieu 1. Pham vi dieu chinh"`. **SUY LUẬN:** điều đó đòi hỏi *join* nhãn mục lục với heading phần thân; không artifact nào tự mình cung cấp được. Pipeline ingestion phải làm việc này, và nó chưa được viết.

**THỰC TẾ — dữ liệu bẩn.** Một tiêu đề trong mục lục chứa một non-breaking space: `"Điều \xa02"`. **SUY LUẬN:** `title.split()` ngây thơ hoặc regex `Điều\s+(\d+)` trên `\s` sẽ xử lý được `\xa0` trong Python 3 (`\s` khớp nó với `re.UNICODE`, là mặc định), nhưng so sánh chuỗi bằng nhau và việc sinh nhãn `ltree` thì không. **ĐỀ XUẤT:** chuẩn hoá NFC + gộp mọi khoảng trắng Unicode (bao gồm `\xa0`, `\u2009`, `\u200b`) làm bước ingestion đầu tiên, và khẳng định bộ chữ của nhãn trước khi dựng bất kỳ path `ltree` nào.

### Tham chiếu pháp luật và tham chiếu chéo (đo được)

| Mẫu | Số lần xuất hiện |
|---|---|
| `Điều\s+\d+` | 419 |
| `khoản\s+\d+\s+Điều\s+\d+` | 193 |
| `điểm\s+\w+\s+khoản\s+\d+\s+Điều\s+\d+` | 119 |
| `Điều này` (tự tham chiếu) | 204 |
| `Nghị định này` (tự tham chiếu) | 123 |
| `Luật\s+[A-ZĐ]` (văn bản bên ngoài) | 24 |

Các văn bản bên ngoài được viện dẫn nhiều nhất: `Luật Xử lý vi phạm hành chính` (8), `Luật Trật tự, an toàn giao thông đường bộ` (7), `Luật Doanh nghiệp`, `Luật Hợp tác xã`.

**SUY LUẬN — ba kết luận định hình toàn bộ thiết kế.**
1. **Tham chiếu nội bộ văn bản chiếm ưu thế theo tỉ lệ ~17:1** (419 nội bộ so với 24 bên ngoài). Đồ thị tham chiếu áp đảo nằm *bên trong* một văn bản, đó là một bài toán cây/khoảng, không phải bài toán graph database.
2. **Tham chiếu được định danh theo phân cấp** (`điểm a khoản 3 Điều 6`), nên đích của một tham chiếu đã giải là một *path*, không phải một document id. Đây là luận cứ trực tiếp cho `ltree`: biểu diễn tự nhiên của một đích tham chiếu chính xác là một path ltree.
3. **Hiện không có gì trích xuất chúng.** Không code nào trong repository parse tham chiếu. 731 tham chiếu trong văn bản này chưa được khai thác, và chúng là tính năng chưa xây dựng có giá trị cao nhất (chúng cho phép "cho tôi xem mọi thứ phụ thuộc vào điều khoản này", chính là giá trị cốt lõi của một KB pháp luật).

### Sửa đổi và version (đo được)

**THỰC TẾ — `luoc_do.json` cung cấp 15 loại quan hệ theo cả hai hướng.** Khác 0 với văn bản này:

| Hướng | Loại | Số lượng | Ý nghĩa |
|---|---|---|---|
| đi ra | `can_cu_ban_hanh` | 5 | căn cứ pháp lý mà nghị định này được ban hành theo |
| đi ra | `sua_doi_bo_sung` | 1 | nó sửa đổi `100/2019/NĐ-CP` |
| đi vào | `van_ban_bi_bai_bo` | 1 | bị bãi bỏ bởi `336/2025/NĐ-CP` |
| đi vào | `can_cu_ban_hanh` | 3 | 3 văn bản sau viện dẫn nó làm căn cứ |
| đi vào | `sua_doi_bo_sung` | 1 | bị sửa đổi bởi `238/2026/NĐ-CP` |

Toàn bộ từ vựng loại (cả hai hướng): `van_ban_bi_bai_bo, ban_dich, can_cu_ban_hanh, dan_chieu, dinh_chi_thi_hanh, dinh_chinh, hop_nhat, huong_dan_ap_dung, quy_dinh_chi_tiet_huong_dan_thi_hanh, sua_doi_bo_sung, tam_ngung_hieu_luc, thay_the, bo_sung, giai_thich, cong_bo`.

**THỰC TẾ — hai hướng bất đối xứng về payload.** Các entry đi ra mang `doc_id, doc_num, title, issue_date, eff_from, eff_to, status`; các entry đi vào **chỉ** mang `doc_id, title`. **SUY LUẬN:** một bảng cạnh được điền từ phía đi vào không thể được làm giàu bằng ngày hay `doc_num` — văn bản được tham chiếu phải được crawl riêng trước khi biết metadata của nó. Vì vậy thiết kế ingestion cần một **queue khám phá**: mọi đích quan hệ trở thành một văn bản ứng viên để crawl. Đó là một thiết kế crawler-frontier, và nó không tồn tại.

**THỰC TẾ — sửa đổi chỉ được ghi ở mức độ văn bản.** `luoc_do.json` nói `238/2026/NĐ-CP` sửa đổi nghị định này; nó **không** nói Điều hay Khoản nào bị sửa. **SUY LUẬN:** để biết rằng "khoản 3 Điều 6 đã bị sửa đổi", bạn phải parse chính văn bản sửa đổi (nó nói những thứ như *"sửa đổi điểm m khoản 3 Điều 6"* — và lưu ý chính Điều 53 của `van_ban.md` chứa đúng cấu trúc này ở cấp văn bản). Vì vậy việc theo dõi sửa đổi ở cấp Điều là một artifact *dẫn xuất* đòi hỏi trích xuất tham chiếu, không phải thứ crawler cung cấp. Bất kỳ thiết kế nào hứa hẹn lịch sử sửa đổi ở cấp điều khoản đều phải tính chi phí cho parser đó.

**THỰC TẾ — không có danh tính version.** Không có field `version`, `revision`, hay `as_of` trong bất kỳ artifact nào. Lần crawl chụp văn bản *như đang được hiển thị*, và `crawled_at` (`schema.sql:24`) là mốc thời gian duy nhất. **SUY LUẬN:** corpus là một kho snapshot, không phải một kho version. Các câu hỏi pháp lý theo thời điểm ("mức phạt vào ngày 2025-06-01 là bao nhiêu?") không thể trả lời được từ nó. Nếu đó là một yêu cầu sản phẩm, việc versioning phải được thiết kế vào (BƯỚC 7/8) — và câu trả lời trung thực hôm nay là nó không được hỗ trợ.

### Metadata và tệp đính kèm

**THỰC TẾ.** `signers` là một array `{name, title}` (một entry ở đây: `Trần Hồng Hà / "Phó  Thủ tướng"` — lưu ý **hai dấu cách**, thêm dữ liệu bẩn). `majors` rỗng `[]`; `fields` là `["Chưa phân loại"]`. **SUY LUẬN:** metadata phân loại thường xuyên vắng mặt hoặc chỉ là placeholder, nên mọi filter truy hồi hay facet dựng trên `fields`/`majors` sẽ thưa thớt. Đừng làm chúng bắt buộc, và đừng dựng chiến lược routing theo category trên chúng mà không đo tỉ lệ điền trên một corpus thật.

**THỰC TẾ — không có tệp đính kèm nào được biểu diễn trong mẫu NĐ 168.** `van_ban.md` chứa **0** dòng bảng Markdown và không có marker phụ lục; không artifact nào có file đính kèm. **ĐỀ XUẤT thiết kế (hướng sản phẩm):** vẫn mở rộng từ vựng level cho `Appendix` (Phụ lục / PL0) và `Group` (Nhóm / N1) trong Postgres `ltree` + Neo4j, để ingestion không phải redesign khi P0-4 crawl được văn bản có phụ lục. **CHƯA RÕ:** vbpl để lộ phụ lục/mẫu biểu như thế nào trên API — cần mẫu thật trước khi gắn content.

### Payload nghiệp vụ: dữ liệu chưa trích xuất có giá trị cao nhất

**THỰC TẾ (đo được).**

| Mẫu | Số lần xuất hiện |
|---|---|
| `[Pp]hạt tiền từ` (khoảng tiền phạt) | 186 |
| Số tiền (`\d[\d.]{5,}\s*đồng`) | 472 |
| `trừ điểm giấy phép lái xe` | 103 |

**SUY LUẬN.** Nghị định này không phải văn xuôi — nó là một **bảng xử phạt có cấu trúc cao được serialize thành text**. Mỗi Điểm thường mã hoá (mô tả hành vi, loại xe, mức phạt tối thiểu, mức phạt tối đa, số điểm bị trừ, hình thức xử phạt bổ sung). Không có gì trong số đó được trích xuất vào bất kỳ cột nào trong `schema.sql`, nên cách duy nhất để trả lời *"mức phạt cho X là bao nhiêu?"* là truy hồi ngữ nghĩa cộng một LLM đọc lại các con số — cơ chế kém tin cậy nhất có thể cho một tra cứu số liệu thực tế, và chính xác là loại câu hỏi mà `PROGRESS_REPORT.md:87` ghi lại chatbot đang *chủ động từ chối* trả lời.

**ĐỀ XUẤT.** Thêm một bảng phóng chiếu chuyên biệt theo domain `legal_penalties` (BƯỚC 8, bảng 12). Trích xuất 186 khoảng tiền phạt bằng một regex tất định + một lượt validation sẽ biến loại câu trả lời yếu nhất của sản phẩm thành mạnh nhất, và làm được điều đó *mà không* cần LLM trên đường trả lời. Xét theo công sức bỏ ra, đây là hạng mục có tỉ lệ hoàn vốn cao nhất trong toàn bộ bản rà soát, và nó không nằm trong lộ trình hiện có nào.

### Thống kê dung lượng văn bản (đo được)

```
Số đoạn phân cách theo Khoản: 333
trung bình 779 ký tự · p90 1.749 · tối đa 8.704 · tổng văn bản 277.961 ký tự
```
Được dùng trong I-13 (cắt embedding) và BƯỚC 13 (sizing).

---

# BƯỚC 6 — Đánh giá phản biện: PostgreSQL + pgvector + ltree + Neo4j

**Cập nhật hướng kiến trúc (quyết định sản phẩm).** Stack mục tiêu là **GraphRAG hai tầng**: Postgres/pgvector là nguồn sự thật cho dữ liệu nền, embedding, audit và transaction; Neo4j là phóng chiếu graph cho quan hệ điều khoản / sửa đổi / dẫn chiếu và mở rộng ngữ cảnh sâu sau khi vector retrieval đã chọn seed. FAISS bị **loại bỏ hẳn** và mọi vector được re-embed vào pgvector.

Tôi đã đánh giá từng công nghệ dựa trên dữ liệu đã đo và mẫu query. Kết luận cập nhật: **bốn thành phần đều được chọn**, với ranh giới trách nhiệm tường minh — Neo4j không thay Postgres, và không nhân bản full text / embedding.

**Tổng hợp phán quyết**

| Công nghệ | Phán quyết | Lý do một dòng |
|---|---|---|
| PostgreSQL | **Chọn (source of truth)** | Metadata, section/chunk, embedding, hiệu lực, audit, transaction — một store có thẩm quyền |
| pgvector | **Chọn — ưu tiên cắt FAISS** | Hybrid HNSW + FTS (RRF); thay thế nguyên nhân gốc của I-1/I-4/I-5/I-8/I-15 |
| ltree | **Chọn — cây trong Postgres** | Subtree / tổ tiên / đích tham chiếu nội bộ văn bản; bổ sung cho graph, không bị Neo4j thay thế |
| Neo4j | **Chọn — SoT quan hệ** | `luoc_do` + PARENT/NEXT/REFERS_TO; map Postgres chỉ qua `doc_id`/`section_id` |

---

## 6.1 PostgreSQL

**Vì sao nó nên tồn tại?** Nó là hệ thống lưu trữ chính thức cho hợp đồng của người dùng, cache phân tích, checkpoint LangGraph, và corpus pháp luật. **Mục tiêu vận hành:** PostgreSQL chạy trong **Docker Compose** (image có sẵn `pgvector`, bật `ltree`/`unaccent`/`pg_trgm`), không dùng Supabase managed DB.

**Nó giải quyết vấn đề gì?** Lưu trữ quan hệ bền vững, có transaction, backup/PITR tự quản (volume + `pg_basebackup`/WAL), và khả năng đặt vector, phân cấp, full text, metadata quan hệ **trong một transaction**.

**Nếu bỏ đi?** Viết lại toàn bộ. Không phải câu hỏi thực tế.

**Hiệu năng.** Dư sức với biên độ rộng cho workload metadata. Rủi ro hiệu năng nằm ở vector index (BƯỚC 13), không phải truy cập quan hệ.

**Chi phí bảo trì / độ phức tạp vận hành.** Trung bình — nhóm tự vận hành container: volume, backup, upgrade image, tuning `shared_buffers`/`max_connections`. **Đổi lại:** pin được version extension (`pgvector`, `ltree`), không bị giới hạn pooler/RLS của SaaS, không phụ thuộc PostgREST/`auth.uid()`. Phân quyền ownership hợp đồng vẫn cưỡng chế trong application (`_assert_owns_contract`) — đúng với Postgres thuần trong Docker.

**Lưu trữ / học / mở rộng / migration / rủi ro.** Lưu trữ chủ yếu do vector. Mở rộng: dọc trên một node Docker/VM trước, rồi read replica, rồi partition. Rủi ro chính: quên backup volume và cấu hình `max_connections` quá thấp khi API+worker+checkpointer cùng mở nhiều connection không pool (I-12).

**Các phương án đã xét.** MySQL (thiếu pgvector/ltree); SQLite (không concurrency); MongoDB (mất toàn vẹn quan hệ); **Supabase managed — bị từ chối theo quyết định sản phẩm** (vendor lock-in Auth/DB/Storage; hướng Docker tự host).

**Khuyến nghị cuối: giữ PostgreSQL trên Docker.** Sửa cách dùng (Alembic, pooling, repository, index, constraint), không đổi engine.

---

## 6.2 pgvector

**Vì sao nó nên tồn tại?** Truy hồi ngữ nghĩa là cơ chế cốt lõi của cả hai tính năng sản phẩm (xét tuân thủ và chat). Hôm nay việc đó chạy trên FAISS, và FAISS là nguyên nhân trực tiếp của **I-1** (filtered recall hỏng), **I-4** (không scale ngang), **I-5** (ghi O(N) mỗi lần upload), **I-6** (dựng lại văn bản bằng quét toàn bộ), **I-8** (RCE qua pickle), và **I-15** (đọc không đồng bộ hoá). Đó là năm vấn đề Nghiêm trọng và một vấn đề Cao từ một lựa chọn kiến trúc duy nhất.

**Nó giải quyết vấn đề gì?** (a) **Tìm kiếm tiền lọc đúng đắn** — `WHERE contract_id = $1 ORDER BY embedding <=> $2 LIMIT 5` có ngữ nghĩa filter chính xác, loại bỏ hẳn I-1 thay vì che nó bằng một `fetch_k` lớn hơn. (b) **State dùng chung** — bất kỳ số lượng instance ứng dụng nào cũng query một index. (c) **Nhất quán theo transaction** — dòng chunk và vector của nó commit cùng dòng hợp đồng, loại bỏ chế độ lỗi vector mồ côi. (d) **Hợp nhất vận hành** — một backup, một restore, một dòng thời gian PITR bao trùm cả metadata *và* vector. (e) **Hybrid search** — BM25/`tsvector` và similarity vector có thể kết hợp trong một câu SQL, điều không thể làm khi hai thứ sống ở hai hệ thống khác nhau.

**Nếu bỏ đi (tức là giữ FAISS hoặc chuyển sang một vector DB chuyên dụng)?** Giữ FAISS nghĩa là giữ cả sáu vấn đề trên và chấp nhận một đường ghi chạy một node — không tương thích với mục tiêu scale đã nêu. Chuyển sang Qdrant/Milvus/Weaviate sửa được filter nhưng thêm một store vector thứ ba bên cạnh Postgres và Neo4j — chi phí nhất quán không đáng ở mức 10M vector khi embedding đã sống trong Postgres. **ĐỀ XUẤT:** pgvector cho vector; Neo4j chỉ cho graph quan hệ (BƯỚC 6.4), không cho embedding.

**Lợi ích hiệu năng.** Filtered recall đi từ "hỏng khi scale" thành chính xác. Độ trễ tuyệt đối: HNSW ở 10M vector với index nằm trong RAM thường là vài đến vài chục milli giây cho top-10 — chậm hơn FAISS trong process trên một index nhỏ (không có network hop, không parse SQL), nhưng *đúng*, điều mà cấu hình hiện tại không đạt được. Với budget latency của sản phẩm này, so sánh đó không liên quan: truy hồi mất vài chục milli giây bên trong một request tiêu 30–60 giây cho các lệnh gọi LLM.

**Chi phí bảo trì.** Có thật nhưng vừa phải: việc build index HNSW chậm và ngốn bộ nhớ (`maintenance_work_mem` phải được nâng, và build 10M vector mất nhiều giờ), và `REINDEX`/rebuild cần một kế hoạch bảo trì. Được bù lại bằng việc xoá toàn bộ bộ máy persistence, locking, và reset của `faiss_store.py`.

**Độ phức tạp vận hành.** **Thấp hơn hiện tại về mặt ứng dụng** (một store vector thay FAISS file). Image Docker Postgres chọn sẵn có `pgvector` (ví dụ `pgvector/pgvector:pg16`) — version extension **pin được**, không phụ thuộc SaaS.

**Chi phí lưu trữ.** Là chi phí chủ đạo của toàn bộ thiết kế. `vector(768)` = 3.072 byte payload; HNSW gần như nhân đôi con số đó. Xem BƯỚC 13 cho số liệu và cách giảm nhẹ (`halfvec`, giảm chiều, chỉ embed ở cấp Khoản) — đây là chỗ kiến trúc thực sự căng.

**Chi phí học.** Thấp. Các khái niệm (HNSW `m`/`ef_construction`/`ef_search`, operator class, `<=>` vs `<->`) là một ngày đọc. `hnsw.iterative_scan` và hành vi filtered-recall là hai điểm tinh tế quan trọng (BƯỚC 9).

**Ảnh hưởng tới mở rộng.** Tốt tới ~10M vector trên một node lớn; vượt qua đó cần partition cộng lượng tử hoá (BƯỚC 13). Read replica scale truy hồi theo chiều ngang.

**Độ phức tạp migration.** Thấp–Trung bình. Cả hai collection đều rebuild được từ nguồn: chunk hợp đồng từ `full_text` đã lưu (sau khi I-6 được sửa), và collection pháp luật từ `legal_document_sections`. Re-embedding là một batch job, không phải một migration bảo toàn dữ liệu, nên không có bước cutover nguy hiểm — chạy song song cả hai, so sánh output truy hồi, rồi chuyển.

**Rủi ro.** Filtered recall của HNSW phải thiết kế (partial index và/hoặc `hnsw.iterative_scan` với pgvector ≥ 0.8). Với Docker, **pin image** và kiểm `SELECT extversion FROM pg_extension WHERE extname='vector'` trong smoke test Compose — không còn “CHƯA RÕ version trên SaaS”.

**Phương án thay thế.** Qdrant/Milvus/Weaviate — hiệu năng vector thô tốt hơn và filter phong phú hơn, với giá là một datastore thứ hai, ghi kép, và một câu chuyện backup thứ hai. Elasticsearch/OpenSearch — hybrid search tốt nhưng dấu chân vận hành nặng. FAISS như một service riêng — bạn sẽ đang tự xây Qdrant. **Không cái nào biện minh được chi phí biên của nó ở mức 10M vector khi dữ liệu đã sống trong Postgres.**

**Khuyến nghị cuối: chọn pgvector, làm đầu tiên, trước mọi việc DB khác.** Nó loại bỏ nhiều vấn đề Nghiêm trọng hơn bất kỳ thay đổi đơn lẻ nào khác trong tài liệu này.

---

## 6.3 ltree

**Vì sao nó nên tồn tại?** Corpus bản chất là một cây có độ sâu đo được là 5, và — quan trọng — cú pháp tham chiếu đã đo nhắm vào *path*: 119 lần xuất hiện `điểm a khoản 3 Điều 6` trong một văn bản duy nhất. Một đích tham chiếu tự nhiên là `173920.dieu_6.khoan_3.diem_a`, đúng là một path ltree.

**Nó giải quyết vấn đề gì?** Bốn nhu cầu query cụ thể mà chỉ `parent_id` phục vụ kém:

1. **Lấy subtree để lắp ghép context RAG** — "cho tôi Điều 6 và mọi thứ dưới nó, theo thứ tự". Với `parent_id` đây là một recursive CTE (5 cấp, một index lookup mỗi cấp mỗi node); với ltree nó là `WHERE path <@ '173920.dieu_6'` trên một index GiST duy nhất. Đây là query nóng nhất trên đường truy hồi, vì câu trả lời pháp lý tốt cần *các điều khoản lân cận và cha* của một điều khoản để làm ngữ cảnh, không chỉ điều khoản đó.
2. **Chuỗi tổ tiên để render trích dẫn** — "Chương I > Mục 2 > Điều 6 > Khoản 3". Hôm nay `schema.sql:49` giải quyết bằng cách phi chuẩn hoá một `breadcrumb` dạng text tự do, không query được và phải sinh lại mỗi khi cấu trúc đổi. `path @> other.path` cho nó một cách có cấu trúc.
3. **Query theo mẫu cấp** — "mọi Khoản trên toàn corpus có Điểm con" qua mẫu `lquery`.
4. **Giải tham chiếu** — một tham chiếu đã parse trở thành một chuỗi path và giải bằng một index lookup, thay vì một lượt đi xuống phân cấp qua nhiều join.

**Nếu bỏ đi?** Mọi thứ vẫn *khả thi* qua `parent_id` + recursive CTE — không gì trở thành bất khả. Bạn mất hiệu năng query subtree và một khoá tự nhiên cho đích tham chiếu; bạn giữ lại một `breadcrumb` text tự do phải bảo trì bằng tay. **SUY LUẬN:** ltree là một phi chuẩn hoá về hiệu năng và khả năng biểu đạt, không phải một mở khoá năng lực. Đó chính là vì sao nó rẻ để chọn và rẻ để từ bỏ.

**Lợi ích hiệu năng.** Đáng kể cho query subtree/tổ tiên: một lần probe index GiST so với một recursive CTE 5 cấp. Lưu ý phản luận trung thực — vì `order_index` là một **chuỗi DFS pre-order dày đặc** (sự thật đã đo), bạn có thể thay vào đó lưu `(order_index, subtree_size)` và có query subtree thành một `BETWEEN` trên btree, *còn nhanh hơn nữa*. Điểm bắt là khoảng nested-set phải được đánh số lại khi có chèn, điều không chấp nhận được khi các sửa đổi bắt đầu chèn `Điều 6a`. Path ltree ổn định dưới việc chèn nếu nhãn ổn định. **ĐỀ XUẤT:** dùng ltree, chính bởi vì nó sống sót qua việc chèn do sửa đổi.

**Chi phí bảo trì.** Thấp, với một cái bẫy thật: path phải được sinh lại cho một subtree mỗi khi cấu trúc thay đổi, và một sửa đổi *đánh số lại* ("Điều 7 thành Điều 8") làm mọi path đã lưu và mọi tham chiếu đã lưu tới nó trở nên vô hiệu. **Đây là quyết định thiết kế ltree lớn nhất**, và BƯỚC 10 xử lý nó bằng cách dẫn xuất nhãn từ **id node ổn định**, không từ số hiển thị.

**Độ phức tạp vận hành.** Gần bằng không trong Docker: `CREATE EXTENSION ltree;` trên image Postgres chính thức/contrib. Không process mới ngoài container Postgres đã có.

**Chi phí lưu trữ.** Không đáng kể. Một path độ sâu 5 với lược đồ nhãn ở BƯỚC 10 là ~40–60 byte; index GiST là một phần nhỏ của bảng. So với ~3 KB mỗi dòng cho embedding, con số này làm tròn về 0.

**Chi phí học.** Thấp nhưng khác 0, và có hai cạnh sắc mà nhóm phải biết trước khi viết một path nào: **nhãn bị hạn chế trong `[A-Za-z0-9_]`**, nên dấu tiếng Việt và dấu cách là bất hợp pháp — `Điều 6` không thể là một nhãn và phải được chuyển tự; và `.` là dấu phân cách, nên nó không được xuất hiện trong một nhãn. Làm sai điều này sẽ sinh lỗi runtime lúc ingestion, đó là vì sao BƯỚC 10 đặc tả một bộ chữ nhãn tường minh, có assert.

**Ảnh hưởng tới mở rộng.** Tốt. GiST trên ltree scale tới hàng chục triệu dòng. Ở mức 1M văn bản × 1.308 node = 1,3 tỉ dòng, *bảng* cần partition từ rất lâu trước khi bản thân ltree trở thành ràng buộc.

**Độ phức tạp migration.** Thấp. Thêm một cột `path ltree` nullable, backfill bằng một recursive CTE, thêm index GiST, rồi cưỡng chế `NOT NULL`. Hoàn toàn đảo ngược được; không mất dữ liệu nếu từ bỏ.

**Rủi ro.** Thấp. Xấu nhất là cột này dư thừa và bạn drop nó. Rủi ro thật duy nhất — path bất ổn khi đánh số lại — là một rủi ro *thiết kế*, được giảm nhẹ bằng lược đồ nhãn theo id ổn định.

**Phương án thay thế.** `parent_id` + recursive CTE (đã có; giữ nó làm xương sống toàn vẹn). Materialised path dạng `TEXT` + `LIKE 'prefix%'` (chạy được, btree-index được, nhưng không có toán tử tổ tiên, không có mẫu cấp, và phải tự xử lý xung đột prefix giữa `dieu_6` và `dieu_60` — biên nhãn của ltree xử lý miễn phí). Nested set (đọc nhanh nhất, chi phí chèn không chấp nhận được). Closure table (nhanh cho query tổ tiên/hậu duệ tuỳ ý, nhưng O(độ sâu) dòng mỗi node — nhân ~5× số dòng cho một mẫu query mà ltree đã phủ).

**Khuyến nghị cuối: chọn ltree, như một bổ sung cho `parent_id`, không phải thay thế.** Giữ `parent_id` cho toàn vẹn tham chiếu và ngữ nghĩa cascade; thêm `path ltree` làm bề mặt query; **xoá `breadcrumb`** và dẫn xuất chuỗi hiển thị từ path. Áp dụng nó *cùng lúc* với pipeline ingestion, vì backfill về sau tốn công hơn là sinh path lúc ghi.

---

## 6.4 Neo4j — SoT của **quan hệ**, không phải bản sao Postgres

**Bạn đúng khi hỏi:** nếu quan hệ cũng nằm SoT trong Postgres rồi sync sang Neo4j thì Neo4j gần như thừa. Bản trước đã lệch sang “projection/outbox”. **Chốt lại đúng hướng sản phẩm:**

| | PostgreSQL | Neo4j |
|---|---|---|
| Vai trò | Dữ liệu nền, nội dung, embedding, audit, transaction | Mô hình quan hệ + traversal GraphRAG |
| SoT cho | `thuoc_tinh`, content `van_ban`, chunk/vector, user/hợp đồng, log | `luoc_do`, cây traversal, dẫn chiếu điều khoản |
| **Điểm chung duy nhất để map** | `doc_id`, `section_id` (cùng giá trị id vbpl / muc_luc) | cùng `doc_id`, `section_id` trên node |

**Không** lưu bảng cạnh quan hệ đầy đủ trong Postgres rồi chiếu sang Neo4j. **Không** lưu `content` / `embedding` trong Neo4j.

### Vì sao vẫn cần Neo4j (khi đã tách đúng)

Postgres giỏi: transaction, HNSW, FTS, audit.  
Neo4j giỏi: đa hop `AMENDS|REPEALS|BASED_ON|REFERS_TO|PARENT_OF|NEXT` xuyên văn bản — đúng chỗ GraphRAG mở rộng ngữ cảnh sau khi vector đã chọn **seed id**.

Luồng:

```
hybrid HNSW+FTS (Postgres) → section_id[]
     → Cypher expand (Neo4j) bằng cùng section_id / doc_id
     → hydrate content (Postgres) WHERE id IN (...)
```

Chỉ cần **một khóa map** ở mỗi bước — không join schema phức tạp giữa hai store.

### Phân bổ 4 file crawler (tách thật)

| Artifact | Đi đâu | Không đi đâu |
|---|---|---|
| `thuoc_tinh.json` | **Postgres** `legal_documents` | Neo4j chỉ nhận node `:Document {doc_id}` + vài nhãn nhẹ (`doc_num`, `doc_type`) để traversal |
| `van_ban.md` (nội dung cắt theo muc_luc) | **Postgres** `sections.content` + `legal_section_chunks` + embedding | Neo4j **không** giữ text |
| `muc_luc.json` | **Postgres**: dòng section (id, level, label, path ltree — phục vụ filter/FTS) | **Neo4j**: `:PARENT_OF`, `:NEXT` (cạnh cấu trúc để expand) |
| `luoc_do.json` | **Neo4j only** — `AMENDS`, `REPEALS`, `SUPERSEDES`, `BASED_ON`, `CITES`, … | **Không** bảng `legal_document_relations` SoT trong Postgres |

Tham chiếu điều khoản extract từ text → cạnh `:REFERS_TO` **trên Neo4j** (source/target = `section_id`).

### Cột dẫn xuất (không phải graph SoT)

Job đọc Neo4j (bãi bỏ/thay thế) có thể ghi **một cờ** `is_effective` xuống Postgres để filter HNSW — đó là cache phục vụ retrieval, không phải lưu lại toàn bộ cạnh.

### Rủi ro khi tách SoT hai bên

Hai store = hai chỗ ghi lúc ingest. Giảm rủi ro bằng:
1. Cùng `doc_id` / `section_id` làm khóa bất biến.
2. Ingest **một job**: ghi PG (nền) + ghi Neo4j (cạnh) theo cùng id; fail một bên → retry idempotent theo id (không outbox “copy relations từ PG”).
3. Đối chiếu định kỳ: mọi `section_id` trong Neo4j phải tồn tại trong Postgres và ngược lại (cho node đã ingest).

**Khuyến nghị cuối:** Neo4j là **SoT quan hệ / traversal**; Postgres là **SoT nền + vector**. Chỉ map bằng `doc_id` và `section_id`.

---

## 6.5 Stack được khuyến nghị

```
Docker Compose (không Supabase)
  ├── postgres   pgvector/pgvector:pg16 (+ ltree, unaccent, pg_trgm)
  ├── neo4j      neo4j:5
  ├── minio      S3-compatible
  └── api/worker + JWT tự host

PostgreSQL = SoT NỀN
  thuoc_tinh → legal_documents
  muc_luc    → legal_document_sections (id, path, content…)
  van_ban    → content + legal_section_chunks + HNSW/FTS
  audit, jobs, hợp đồng, is_effective (cờ dẫn xuất)
  ─ KHÔNG chứa SoT cạnh luoc_do / REFERS_TO

Neo4j = SoT QUAN HỆ
  node :Document / :Section   {doc_id | section_id}   ← điểm map duy nhất
  cạnh PARENT_OF, NEXT        ← từ muc_luc
  cạnh AMENDS, REPEALS, …     ← từ luoc_do
  cạnh REFERS_TO              ← extract từ van_ban
  ─ KHÔNG chứa full text / embedding

Điểm map: doc_id, section_id
─ FAISS / Supabase: loại bỏ
```

**Pipeline GraphRAG:**
```
query → hybrid HNSW+FTS (Postgres) → seed section_id[]
     → Neo4j expand bằng section_id / doc_id
     → Postgres hydrate content theo cùng id → prompt
```

**Vì sao `unaccent` + `pg_trgm` vẫn bắt buộc trên Postgres.** Nửa lexical của hybrid search; không liên quan Neo4j.

---

# BƯỚC 7 — Kiến trúc mục tiêu

Thiết kế cho stack GraphRAG trên **Docker Compose**: **PostgreSQL + pgvector + ltree** (SoT), **Neo4j** (projection), **MinIO** (object), **JWT tự host**; **FAISS và Supabase bị loại bỏ**.

## 7.0 Topology Docker Compose (mục tiêu)

```yaml
# phác thảo — chưa có trong repo; P6-1 / P0 sẽ commit
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: contractlens
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d contractlens"]

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4jdata:/data
    ports: ["7474:7474", "7687:7687"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes:
      - miniodata:/data
    ports: ["9000:9000", "9001:9001"]

  # api / worker: DATABASE_URL=postgresql://app:***@postgres:5432/contractlens
  # NEO4J_URI=bolt://neo4j:7687  S3_ENDPOINT=http://minio:9000  JWT_SECRET=...
```

**Quy ước env:** `DATABASE_URL`, `NEO4J_*`, `S3_*`, `JWT_SECRET`. **Không** còn `SUPABASE_URL` / `SUPABASE_SECRET_KEY` / `SUPABASE_ANON_KEY`.

## 7.1 Kiến trúc logic

```mermaid
graph TB
    subgraph Client
      SPA[React SPA<br/>router + TanStack Query]
    end
    subgraph Edge
      LB[Ingress<br/>TLS · rate limit · trần kích thước body · allowlist CORS]
    end
    subgraph API["Tầng API — không state, N replica"]
      RT[Router<br/>mỏng, chỉ validate]
      AUTH[Auth JWT tự host<br/>verify local]
      APP[Service ứng dụng<br/>command + query]
      REPO[Repository<br/>biên SQL]
      RET[Service truy hồi<br/>hybrid RRF + GraphRAG expand]
    end
    subgraph Workers["Tầng worker — không state, M replica"]
      W1[ingest.contract<br/>parse → chunk → embed]
      W2[analyze.contract<br/>extract → judge fan-out]
      W3[ingest.legal<br/>4 file crawl → PG → outbox]
      W4[graph.reconcile<br/>đối chiếu doc_id/section_id]
      W5[maintain<br/>reindex · retention · effectivity]
    end
    subgraph Embed["Service embedding — không state"]
      EMB[SentenceTransformer<br/>theo batch · GPU tuỳ chọn]
    end
    subgraph Compose["Docker Compose"]
      PG[(PostgreSQL + pgvector<br/>ltree · FTS · outbox)]
      NJ[(Neo4j)]
      OBJ[(MinIO S3-compatible)]
      Q[(Job queue<br/>PG SKIP LOCKED)]
    end
    subgraph Ext
      LLM[Gemini]
      VBPL[vbpl.vn]
    end
    SPA -->|Bearer JWT| LB --> RT --> AUTH --> APP --> REPO --> PG
    APP --> RET
    RET --> PG
    RET --> NJ
    APP --> Q --> W1 & W2 & W3 & W4 & W5
    W1 & W2 & W3 --> REPO
    W1 & W3 --> EMB
    RET --> EMB
    W2 --> LLM
    W3 --> VBPL
    W3 --> OBJ
    W4 --> NJ
    W4 --> PG
    APP --> OBJ
    W1 --> OBJ
```

**Những khác biệt then chốt so với hiện tại**

| # | Thay đổi | Sửa được |
|---|---|---|
| 1 | Vector FAISS → pgvector trên Postgres Docker (re-embed) | I-1, I-4, I-5, I-8, I-15 |
| 2 | Neo4j Docker + outbox một chiều cho GraphRAG | mở rộng ngữ cảnh xuyên luật |
| 3 | **Bỏ Supabase** — JWT tự host + MinIO + Postgres/Neo4j Compose | I-11, vendor lock-in |
| 4 | Tầng API không state → N replica | I-4 |
| 5 | LLM sang worker phía sau queue | I-24, I-28, I-29 |
| 6 | Embedding service riêng | I-28 |
| 7 | Repository là chỗ duy nhất SQL tồn tại | I-22 |
| 8 | Upload + snapshot crawl → MinIO | I-41 |
| 9 | Ingestion 4 file crawler | I-2, I-10 |
| 10 | Alembic thay DDL lúc startup | I-3, I-9 |

**Đề xuất về queue.** Queue trên nền Postgres (`jobs` + `SKIP LOCKED`). Job `ingest.legal` ghi PG + Neo4j theo cùng `doc_id`/`section_id` (idempotent).

## 7.2 Kiến trúc vật lý (topology production ban đầu)

| Thành phần | Kích cỡ | Ghi chú |
|---|---|---|
| Ingress | LB / reverse proxy | TLS, rate limit theo IP + theo user, trần body 25 MB |
| API | 3 × (2 vCPU, 4 GB) hoặc service Compose | không state; JWT verify local |
| Worker | 2 × (4 vCPU, 8 GB), scale theo queue | `ingest.legal` ghi PG + Neo4j |
| Embedding | 2 × (4 vCPU, 8 GB) CPU, hoặc 1 × GPU | batch size 32 |
| PostgreSQL Docker | 8 vCPU, 32 GB, volume NVMe — tăng theo BƯỚC 13 | image `pgvector/pgvector:pg16`; `shared_buffers` 25%, `maintenance_work_mem` ≥ 2 GB |
| PG read replica | ×1 (tuỳ chọn) | hybrid retrieval + `GET` |
| Neo4j Docker | 1 × (4 vCPU, 16 GB) | volume riêng; không giữ vector |
| MinIO | 1 × + volume | upload + snapshot 4 file crawl; SSE |

**Các thiết lập Postgres quan trọng:** `maintenance_work_mem` ≥ 2 GB, `max_parallel_maintenance_workers` ≥ 4, `shared_buffers` đủ để HNSW nằm trong RAM, `ALTER TABLE … ALTER COLUMN embedding SET STORAGE PLAIN` trên mọi cột vector. Backup: `pg_dump`/WAL archive từ volume Docker — không dựa SaaS.

## 7.3 Luồng dữ liệu — đường hợp đồng

```
POST /contracts (multipart, stream, có trần kích thước)
  → PUT lên MinIO (S3)                              (I-7, I-41)
  → INSERT uploaded_contracts (status='received')
  → INSERT jobs (type='ingest.contract')      cùng một transaction
  → 202 Accepted {contract_id, status_url}

worker ingest.contract:
  lấy object → parse (docx|pdf|OCR ảnh)
  → INSERT contract_documents(full_text)      (I-6: văn bản lưu một lần, có thẩm quyền)
  → chia chunk theo điều khoản, nhận biết token  (I-13, I-19)
  → service embedding, theo batch
  → INSERT contract_chunks (content, embedding) — MỘT transaction
  → UPDATE status='ready', chunk_count
  → khi lỗi: status='failed', failure_code    (I-26)

POST /contracts/{id}/analysis-runs            (I-24)
  → INSERT analysis_runs(status='queued') + jobs(type='analyze.contract')
  → 202 {run_id}

worker analyze.contract:
  đọc contract_documents.full_text (theo PK)
  → extract (extractor do profile chọn)       (I-21)
  → mỗi điều khoản: truy hồi hybrid → judge (LLM), concurrency có giới hạn, có retry (I-29)
  → INSERT contract_analyses + contract_risks (dòng có kiểu, không phải blob JSONB)
  → UPDATE analysis_runs(status, cost, tokens, duration, model_version)

GET /contracts/{id}/analysis  → rẻ, cache được, replica phục vụ
```

## 7.4 Luồng dữ liệu — ingestion (tách store, một khóa map)

**Nguyên tắc:** mỗi artifact ghi **đúng một SoT**; hai store chỉ gặp nhau ở `doc_id` / `section_id`.

| Artifact | Postgres (nền) | Neo4j (quan hệ) |
|---|---|---|
| `thuoc_tinh.json` | UPSERT `legal_documents` | `MERGE (:Document {doc_id})` + nhãn nhẹ |
| `muc_luc.json` | UPSERT `legal_document_sections` (id, level, label, path, …) | `MERGE` Section + `:PARENT_OF` + `:NEXT` |
| `van_ban.md` | gắn `content`/`title` + chunk + embed | *(không)* |
| `luoc_do.json` | *(không lưu cạnh SoT)* | `MERGE` `AMENDS`/`REPEALS`/… giữa Document |
| extract dẫn chiếu | tuỳ chọn log lỗi extract | `:REFERS_TO` Section→Section |

```
worker ingest.legal (mỗi văn bản), cùng doc_id:
0. snapshot 4 file → MinIO
1. chuẩn hoá NFC / khoảng trắng
2. PG: UPSERT legal_documents ← thuoc_tinh
3. PG: UPSERT legal_document_sections ← muc_luc (giữ path ltree cho filter retrieval)
4. PG: cắt van_ban theo muc_luc → content + chunks + HNSW
5. Neo4j: MERGE Document/Section bằng cùng doc_id/section_id
         + PARENT_OF/NEXT từ muc_luc
         + AMENDS/REPEALS/… từ luoc_do          ← SoT quan hệ ở đây
6. Neo4j: REFERS_TO từ extract (khi có)
7. PG: cập nhật cờ is_effective (dẫn xuất từ Neo4j, không lưu lại toàn bộ cạnh)
8. frontier: enqueue doc_id đích chưa có trong PG
```

**Không** còn `graph_outbox` kiểu “Postgres relations → Neo4j”. Ingest ghi thẳng Neo4j cho phần quan hệ; nếu Neo4j fail → retry job theo `doc_id` (idempotent `MERGE`).

## 7.4b Luồng GraphRAG (đường đọc)

```
hybrid HNSW + FTS (Postgres) → section_id[]
  → Cypher expand (Neo4j) WHERE section_id IN $seeds
  → SELECT content FROM legal_document_sections / chunks WHERE id IN (...)
  → prompt
```

Khóa map duy nhất xuyên suốt: **`section_id`** (và **`doc_id`** ở cấp văn bản).

## 7.5 Luồng lập chỉ mục

| Kích hoạt | Hành động |
|---|---|
| Nội dung section mới/đã đổi | tính lại hash → chia chunk lại → embed lại → thay các dòng chunk trong một transaction |
| Đổi model embedding | `embedding_model_id` mới; ghi các dòng chunk mới song song với cũ; chuyển đường đọc bằng config; drop cái cũ sau khi kiểm chứng (ghi kép, không downtime) |
| Backfill hàng loạt | drop HNSW → `COPY` các dòng → `CREATE INDEX CONCURRENTLY` với `maintenance_work_mem` đã nâng (nhanh hơn 10–100× so với insert từng phần) |
| Bảo trì định kỳ | theo dõi index bloat và dead tuple; `REINDEX CONCURRENTLY` định kỳ; kiểm chứng `autovacuum` theo kịp trên các bảng chunk biến động cao |

## 7.6 Job nền và job theo lịch

| Job | Loại | Lịch | Mục đích |
|---|---|---|---|
| `ingest.contract` | queue | theo yêu cầu | parse/chunk/embed các file upload |
| `analyze.contract` | queue | theo yêu cầu | extraction + xét từng điều khoản |
| `ingest.legal` | queue | theo yêu cầu + frontier | ghi PG (nền) + Neo4j (quan hệ) theo cùng id |
| `effectivity.refresh` | cron | hằng ngày | đọc cạnh Neo4j → cập nhật cờ `is_effective` trên PG |
| `graph.reconcile` | cron | hằng ngày | đối chiếu `doc_id`/`section_id` giữa hai store |
| `frontier.enqueue` | cron | hằng ngày | đưa các đích quan hệ đã khám phá lên hàng đợi |
| `recrawl.stale` | cron | hằng tuần | crawl lại văn bản có quan hệ đến thay đổi, hoặc cũ hơn N ngày |
| `effectivity.refresh` | cron | hằng ngày | tính lại hiệu lực pháp lý dẫn xuất (**I-10**) |
| `analysis.invalidate` | queue | khi pháp luật đổi | đánh dấu các phân tích viện dẫn luật đã đổi là cũ |
| `retention.checkpoints` | cron | hằng ngày | prune các thread chat không hoạt động (**I-14**) |
| `retention.uploads` | cron | hằng ngày | cưỡng chế lifecycle của object storage (**I-41**) |
| `index.maintain` | cron | hằng tuần | kiểm bloat, `REINDEX CONCURRENTLY` khi cần |
| `metrics.rollup` | cron | mỗi giờ | tỉ lệ hit truy hồi, tỉ lệ từ chối, chi phí mỗi lượt chạy |

## 7.7 Phục hồi khi lỗi

| Lỗi | Phát hiện | Phục hồi |
|---|---|---|
| Worker chết giữa job | heartbeat / lease hết hạn | lease timeout đưa job về `queued`; job phải **idempotent** (`ON CONFLICT DO UPDATE` khoá theo `(contract_id, chunk_index)` / `(section_id, chunk_index)`) |
| LLM rate limit | 429 từ provider | exponential backoff + jitter; sau N lần thử đánh dấu *điều khoản* là `skipped_rate_limited` và lượt chạy là `partial` — **không bao giờ âm thầm bỏ** (I-29) |
| Service embedding chết | health check | job nằm lại trong queue; alert theo độ sâu queue; truy hồi suy thoái về chỉ-lexical thay vì fail |
| Trang crawl đổi hình dạng | parser assertion fail | fail job, giữ snapshot thô, alert; parse lại từ snapshot sau khi sửa parser — không fetch lại |
| Index HNSW hỏng/phình | monitor recall và độ trễ | `REINDEX CONCURRENTLY`; vector nằm trong heap nên không mất gì |
| Mất Postgres primary | restore volume Docker / promote replica | các job đang chạy replay từ lease của chúng |
| Deploy tệ | alert theo tỉ lệ lỗi | roll back app; migration phải tương thích ngược trong một release (expand/contract) |
| Dữ liệu bị nhiễm (crawl xấu) | counter validation | chạy lại ingestion từ snapshot bất biến; `legal_documents.crawled_at` giới hạn bán kính ảnh hưởng |

## 7.8 Chiến lược backup

| Tài sản | Phương pháp | RPO / RTO |
|---|---|---|
| PostgreSQL (Docker volume) | `pg_dump` hằng ngày + WAL archive (hoặc snapshot volume) | RPO ≈ vài phút–vài giờ tuỳ cấu hình; RTO ≈ 1 h |
| MinIO (upload) | versioning bucket + replicate volume | RPO ≈ vài phút |
| MinIO (snapshot crawl) | versioning; nguồn parse lại corpus | dữ liệu dẫn xuất |
| Embedding | **không backup riêng** — dẫn xuất, tái tạo được | chỉ tốn chi phí tính lại |
| Neo4j (Docker volume) | dump định kỳ + **rebuild từ Postgres** (đường chính) | RPO theo outbox SLO; restore dual-store phải đối chiếu |
| Diễn tập restore | mỗi quý: PG volume + MinIO + rebuild Neo4j từ SoT | — |

**ĐỀ XUẤT.** Hãy coi embedding là dữ liệu dẫn xuất, không bao giờ là quý giá. Việc chúng nằm trong database chính là một tiện lợi cho tính nhất quán, không phải một lý do để bảo vệ chúng: phải luôn rẻ hơn khi re-embed so với khi restore. Chính tính chất đó làm luồng "drop index, bulk load, rebuild" ở §7.5 trở nên an toàn.

## 7.9 Chiến lược migration

Expand/contract, mỗi release một quan tâm, luôn tương thích ngược trong một version:

1. **P0** — dump schema thực đang deploy; đối chiếu với `database.py`, `schema.sql`, `loader.py`. Không gì khác bắt đầu cho tới khi biết baseline thật.
2. Đưa Alembic vào; ghi lại trạng thái đã đối chiếu thành revision `0001` với **không** thay đổi DDL nào.
3. Thêm bảng và cột mới ở dạng nullable/có default. Deploy code ghi cả đường cũ và mới.
4. Backfill theo batch; kiểm chứng số lượng và kiểm mẫu nội dung.
5. Chuyển đường đọc sang đường mới sau một config flag; so sánh output (shadow-read).
6. Ngừng ghi đường cũ.
7. Contract: drop cột/bảng cũ ở một release sau.

Riêng cutover vector: build chunk pgvector *song song* với FAISS, chạy cả hai retriever ở chế độ shadow, log cả hai tập kết quả vào `search_logs`, so sánh độ trùng và độ trễ, rồi bật flag. Không bước phá huỷ nào cho tới khi việc so sánh đạt yêu cầu.

## 7.10 Chiến lược nhất quán

- **Mạnh (Postgres):** hợp đồng + chunk + vector; section content + path; phân tích / rủi ro.
- **Mạnh theo id (Neo4j):** cạnh `luoc_do` + `PARENT_OF`/`NEXT`/`REFERS_TO` — SoT quan hệ; `MERGE` idempotent.
- **Ingest dual-write:** cùng `doc_id`/`section_id`; fail Neo4j → retry job, không copy cạnh từ bảng Postgres.
- **Cờ `is_effective`:** dẫn xuất từ Neo4j xuống Postgres để filter HNSW (cache, không phải SoT cạnh).
- **Đối chiếu:** mọi `section_id` đã ingest phải có mặt ở cả hai store.

## 7.11 Chiến lược versioning

**THỰC TẾ (từ BƯỚC 5):** crawler không cung cấp danh tính version; corpus là một kho snapshot.

**ĐỀ XUẤT — ba lớp, áp dụng theo thứ tự này:**

1. **Lớp snapshot (làm ngay, rẻ).** `legal_document_snapshots(doc_id, crawled_at, content_hash, storage_key)` — mỗi lần crawl giữ artifact thô một cách bất biến. Chỉ riêng điều này làm cho "chúng ta tin điều gì vào ngày D?" trả lời được và làm mọi bug parser sửa được hồi tố.
2. **Lớp hiệu lực dẫn xuất (làm ngay, sửa I-10).** `legal_document_effectivity(doc_id, valid_from, valid_to, status, derived_from)` tính từ `eff_from`/`eff_to` **cộng** các cạnh đến `van_ban_bi_bai_bo` / `thay_the` / `tam_ngung_hieu_luc`. Mọi truy hồi lọc theo cái này, tính theo mốc thời gian của query — không bao giờ theo một scalar đã lưu.
3. **Lớp thời gian ở cấp section (hoãn tới khi thật cần).** `legal_document_sections` có thêm `valid_from`/`valid_to` và trở thành append-only, nên một section có lịch sử các bản sửa. **Cái này đắt** — nó nhân số dòng lên, làm phức tạp mọi query và mọi path ltree, và (theo BƯỚC 5) đòi phải parse các văn bản sửa đổi để biết section *nào* đã đổi. Đừng xây nó cho tới khi một stakeholder yêu cầu tường minh câu trả lời theo thời điểm.

**Versioning API:** giữ tiền tố `/api/v1`; thêm `/v2` cho các thay đổi response phá vỡ tương thích ở I-24, I-25, I-30 thay vì biến đổi `v1` dưới chân các client hiện có.

**Versioning phân tích:** lưu `prompt_version`, `model_version`, `embedding_model_id`, và `kb_snapshot_at` trên mỗi dòng `analysis_runs`. Không có những cái này thì không kết quả phân tích nào tái lập hay giải thích được — một tính chất không thể chấp nhận với một dấu vết audit tư vấn pháp lý.

## 7.12 Monitoring

| Tầng | Tín hiệu |
|---|---|
| API | RPS, p50/p95/p99 theo route, 4xx/5xx theo mã, số lần auth thất bại |
| Queue | độ sâu theo loại, tuổi job cũ nhất, tỉ lệ retry, kích thước DLQ |
| Truy hồi | **tỉ lệ hit** (số query có kết quả / tổng query), **tỉ lệ từ chối**, tỉ lệ `insufficient_evidence`, điểm top-1 trung bình, tỉ lệ thắng của hybrid so với chỉ-vector, phân tách độ trễ (embed vs search) |
| LLM | số lệnh gọi/phút, token vào/ra, chi phí mỗi lượt chạy, độ trễ p95, tỉ lệ 429, tỉ lệ JSON không parse được, tỉ lệ retry |
| Database | connection so với giới hạn, tỉ lệ cache hit, query chậm, index bloat, dead tuple, replication lag, probe recall HNSW |
| Corpus | số văn bản theo trạng thái hiệu lực, section không có content, section không có embedding, tham chiếu chưa giải được, độ sâu crawl frontier, `crawled_at` cũ nhất |
| Chất lượng | tỉ lệ feedback 👍/👎, tỉ lệ trích dẫn bị loại, tỉ lệ người dùng ghi đè |

**Ba tín hiệu quan trọng nhất và hiện chưa được theo dõi** — mỗi cái map trực tiếp vào một vấn đề Nghiêm trọng/Cao:
1. **Tỉ lệ hit truy hồi** — sẽ phơi bày I-1 ngay lập tức, vì nó suy giảm đơn điệu theo mức tăng trưởng corpus.
2. **Tỉ lệ `insufficient_evidence`** — phân biệt "không có luật liên quan nào tồn tại" với "kho tri thức thiếu/rỗng" (H-7), hai thứ hiện không phân biệt được với cả người dùng lẫn người vận hành.
3. **Phân bố hiệu lực của corpus** — phơi bày I-10 bằng cách làm cho số văn bản cũ/đã bãi bỏ trong KB đang hoạt động trở nên đếm được.

---

# BƯỚC 8 — Thiết kế schema PostgreSQL

Quy ước: `TIMESTAMPTZ` ở mọi nơi (`TIMESTAMP` hiện tại ở `database.py:41` làm mất thông tin múi giờ); `UUID` cho id nội bộ; `TEXT` cho id bên ngoài (được biện minh bởi các định dạng `doc_id` lẫn lộn đã đo); mọi cột kiểu enum đều có một `CHECK`; mọi bảng có `created_at`/`updated_at` với một trigger; extension `pg_trgm`, `unaccent`, `ltree`, `vector`.

Các ước lượng tăng trưởng giả định theo văn bản đã đo (1.308 section, 387 có nội dung, 278k ký tự) và được gắn cờ là **ngoại suy từ mẫu đơn**.

## Extension và hạ tầng dùng chung

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Cấu hình tìm kiếm text tiếng Việt không phân biệt dấu. schema.sql:34,59 dùng 'simple',
-- vốn không bỏ dấu, nên "lao dong" không thể khớp "lao động".
CREATE TEXT SEARCH CONFIGURATION vi (COPY = simple);
ALTER TEXT SEARCH CONFIGURATION vi
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$ LANGUAGE plpgsql;
```

---

### 1. `legal_documents` — một dòng cho mỗi văn bản pháp luật

**Vì sao tồn tại.** Gốc của corpus. Map 1:1 lên `thuoc_tinh.json` của crawler (13 khoá, đã kiểm chứng).

```sql
CREATE TABLE legal_documents (
    doc_id          TEXT PRIMARY KEY,
    doc_num         TEXT NOT NULL,
    doc_num_norm    TEXT NOT NULL,           -- chữ thường, bỏ dấu, bỏ dấu câu: "1682024ndcp"
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL REFERENCES legal_document_types(code),
    agency          TEXT,
    majors          TEXT[] NOT NULL DEFAULT '{}',
    fields          TEXT[] NOT NULL DEFAULT '{}',
    issue_date      DATE,
    eff_from        DATE,
    eff_to          DATE,
    eff_status      TEXT,                    -- giá trị THÔ từ crawler; không bao giờ dùng để lọc (I-10)
    eff_status_code TEXT,                    -- giá trị THÔ từ crawler; không bao giờ dùng để lọc (I-10)
    signers         JSONB NOT NULL DEFAULT '[]',
    source_url      TEXT,
    preamble        TEXT,
    closing         TEXT,
    content_hash    TEXT,                    -- hash của toàn văn đã chuẩn hoá; quyết định việc re-embed
    section_count   INTEGER NOT NULL DEFAULT 0,
    crawled_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ld_eff_window CHECK (eff_to IS NULL OR eff_from IS NULL OR eff_to >= eff_from),
    CONSTRAINT ck_ld_doc_id_shape CHECK (doc_id ~ '^[0-9]+$' OR doc_id ~ '^[0-9a-f-]{36}$')
);
```

**Các quyết định thiết kế và lý do.**
- `doc_id TEXT` — **bắt buộc**: các giá trị `doc_id` đã đo bao gồm cả `"173920"` và `"b043c150-7924-11f1-85a7-e1f385e447d3"`. `CHECK` ghi lại cả hai hình dạng được chấp nhận để một định dạng thứ ba sẽ fail ồn ào thay vì âm thầm.
- `doc_num_norm` — được thêm vì người dùng tìm `"168/2024"`, `"168-2024-NĐ-CP"`, và `"1682024ndcp"` thay thế cho nhau. Thú vị là `helpers/text_normalizer.py:24-29` đã hiện thực đúng hàm này và đang là code chết — nên hồi sinh nó cho cột này thay vì xoá.
- `eff_status` / `eff_status_code` được giữ **chỉ như xuất xứ thô**, tường minh không bao giờ dùng trong một mệnh đề `WHERE`. Đây là việc cưỡng chế cách sửa I-10 ở cấp schema.
- **`full_text` bị cố tình bỏ.** `schema.sql:21` lưu nó; ở mức 278 KB/văn bản đó là 28 GB cho mỗi 100k văn bản nhân bản nội dung đã có trong `legal_document_sections`. Hãy dựng lại khi cần bằng `string_agg(content ORDER BY order_index)`, hoặc phục vụ snapshot crawl bất biến từ object storage. Nếu một đường hiển thị thực sự cần nó, hãy thêm một materialised view thay vì một cột.

**Index**
```sql
CREATE UNIQUE INDEX uq_ld_doc_num_norm  ON legal_documents (doc_num_norm);
CREATE INDEX idx_ld_type_issue          ON legal_documents (doc_type, issue_date DESC);
CREATE INDEX idx_ld_issue               ON legal_documents (issue_date DESC);
CREATE INDEX idx_ld_title_fts           ON legal_documents USING gin (to_tsvector('vi', title));
CREATE INDEX idx_ld_title_trgm          ON legal_documents USING gin (title gin_trgm_ops);
CREATE INDEX idx_ld_majors              ON legal_documents USING gin (majors);
CREATE INDEX idx_ld_fields              ON legal_documents USING gin (fields);
CREATE INDEX idx_ld_stale               ON legal_documents (crawled_at) WHERE crawled_at IS NOT NULL;
```
Composite `(doc_type, issue_date DESC)` thay hai btree một cột riêng của `schema.sql`, vốn không thể phục vụ đồng thời mẫu filter-and-sort. `gin_trgm_ops` trên `title` hỗ trợ tra cứu tiêu đề mờ; index FTS dùng configuration `vi` có bỏ dấu. **Lưu ý:** `unaccent` không phải `IMMUTABLE` mặc định trong một số thiết lập; nếu expression index bị từ chối, hãy bọc nó trong một hàm SQL `IMMUTABLE` hoặc duy trì một cột `tsvector` generated.

**Chuẩn hoá:** 3NF, với hai phi chuẩn hoá array có lý do (`majors`, `fields` — từ vựng nhỏ và đóng, có GIN index) và `signers` là JSONB (đã đo 1 entry; về nguyên tắc không giới hạn, không bao giờ query theo cấu trúc). **Partition:** không cần — 1M dòng là chuyện nhỏ. **Kích thước:** ~2 KB/dòng → 200 MB ở 100k, 2 GB ở 1M văn bản.

---

### 2. `legal_document_types` — bảng tham chiếu

**Vì sao tồn tại.** `doc_type` hiện là text tự do; từ vựng đã đo là nhỏ và đóng (`Nghị định`, `Luật`, `Bộ luật`, `Thông tư`, `Nghị quyết`, `Quyết định`, …). Một bảng tham chiếu cho toàn vẹn tham chiếu cộng với một chỗ để lưu **thứ bậc hiệu lực pháp lý**, thứ mà truy hồi cần: khi một Luật và một Nghị định xung đột, Luật thắng, và một cột xếp hạng cho phép retriever ưu tiên nguồn có thẩm quyền cao hơn.

```sql
CREATE TABLE legal_document_types (
    code        TEXT PRIMARY KEY,          -- 'nghi_dinh'
    label_vi    TEXT NOT NULL,             -- 'Nghị định'
    authority_rank SMALLINT NOT NULL,      -- 1 = Hiến pháp … 7 = Quyết định; số nhỏ thắng khi xung đột
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
Kích thước: < 50 dòng. Không partition. Bảng này là **mới** — hiện không có gì tương đương, và không có nó thì retriever không có cách nào biểu đạt thứ bậc pháp lý.

---

### 3. `legal_document_sections` — cây phân cấp

**Vì sao tồn tại.** Cây cấu trúc, và là đơn vị mà trích dẫn trỏ tới. Dẫn xuất trực tiếp từ `muc_luc.json`.

```sql
CREATE TABLE legal_document_sections (
    id              TEXT PRIMARY KEY,                    -- id node vbpl (đã đo: id == key)
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    parent_id       TEXT REFERENCES legal_document_sections(id) ON DELETE CASCADE,
    path            LTREE NOT NULL,                      -- BƯỚC 10
    depth           SMALLINT NOT NULL,                   -- = nlevel(path); đã đo tối đa 5
    level           TEXT NOT NULL,
    order_index     INTEGER NOT NULL,                    -- DFS pre-order dày đặc 1..N (đã đo)
    subtree_size    INTEGER NOT NULL DEFAULT 1,          -- cho phép quét khoảng [order_index, +subtree_size)
    label           TEXT NOT NULL,                       -- 'Điều 1'  (từ muc_luc, đã chuẩn hoá khoảng trắng)
    ordinal         TEXT,                                -- '1' | 'a' | 'I'  (parse từ label)
    rubric          TEXT,                                -- 'Phạm vi điều chỉnh' (từ H2 trong thân — đã đo: nguồn duy nhất)
    content         TEXT,                                -- NULL với Chương/Mục (heading nhóm)
    content_source  TEXT NOT NULL DEFAULT 'none',        -- 'anchor' | 'segmented' | 'none'  ← nhu cầu đã đo
    content_hash    TEXT,
    char_count      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_lds_level CHECK (level IN ('Chapter','Section','Article','Clause','Point','Appendix','Group')),
    CONSTRAINT ck_lds_content_source CHECK (content_source IN ('anchor','segmented','none')),
    CONSTRAINT ck_lds_depth CHECK (depth = nlevel(path)),
    CONSTRAINT ck_lds_no_self_parent CHECK (parent_id IS DISTINCT FROM id),
    CONSTRAINT uq_lds_doc_order UNIQUE (doc_id, order_index)
);
```

**Các quyết định thiết kế.**
- **Bỏ `ptype`.** Đã đo là 1:1 với `level` (2↔Chapter, 3↔Section, 5↔Article, 6↔Clause, 7↔Point). Giữ cả hai là mời gọi sự phân kỳ; nếu muốn xuất xứ thô, hãy đặt nó trong snapshot, không phải trong bề mặt query.
- **Bỏ `breadcrumb`.** `schema.sql:49` lưu một path dạng text tự do; `path` thay thế nó và query được. Hãy render breadcrumb từ các tổ tiên sắp theo `nlevel(path)`.
- **Thêm `content_source` — đây là cột mới quan trọng nhất.** Đã đo: chỉ 387 trên 1.308 node có anchor nội dung. Cột này ghi lại *bằng cách nào* nội dung được lấy, nên chất lượng truy hồi có thể đo theo xuất xứ và nội dung Điểm `segmented` (đến từ một parser, không từ nguồn) là kiểm toán được và phân biệt được với nội dung `anchor` có thẩm quyền. Không có nó, các bug parser là vô hình.
- **Tách `label` / `ordinal` / `rubric`.** Đã đo: `muc_luc.json` chỉ cho `"Điều 1"`; tên điều `"Phạm vi điều chỉnh"` chỉ tồn tại như một H2 trong thân. Giữ chúng riêng làm cho phép join trở nên tường minh và cho phép `rubric IS NULL` gắn cờ một lần ingestion chưa hoàn chỉnh.
- **Thêm `subtree_size`.** Vì `order_index` là một chuỗi pre-order dày đặc đã đo, `WHERE doc_id = $1 AND order_index BETWEEN o AND o + subtree_size - 1` là một lượt quét subtree trên btree — rẻ hơn ltree cho trường hợp phổ biến trong một văn bản. Có cả hai cho planner một lựa chọn: khoảng btree cho trong-văn-bản, GiST cho query mẫu xuyên văn bản.
- **`level` hết ở `Point` (+ `Appendix`/`Group` cho PL).** Không `SubPoint` — văn bản VN quy phạm dừng ở Điểm.

**Index**
```sql
CREATE INDEX idx_lds_doc_order   ON legal_document_sections (doc_id, order_index);
CREATE INDEX idx_lds_parent      ON legal_document_sections (parent_id);
CREATE INDEX idx_lds_path_gist   ON legal_document_sections USING gist (path);
CREATE INDEX idx_lds_doc_level   ON legal_document_sections (doc_id, level)
    WHERE level IN ('Article','Clause');
CREATE INDEX idx_lds_content_fts ON legal_document_sections USING gin (to_tsvector('vi', content))
    WHERE content IS NOT NULL;
CREATE INDEX idx_lds_missing_content ON legal_document_sections (doc_id)
    WHERE content IS NULL AND level IN ('Article','Clause','Point');   -- monitor mức đầy đủ của ingestion
```
Index cuối là một công cụ vận hành, không phải tối ưu query: nó làm cho "bao nhiêu phần corpus không lấy được nội dung?" trở thành một phép đếm nhanh, chính là khoảng trống monitoring cho phép các vấn đề kiểu I-10 ẩn mình.

**Partition.** Không cần dưới ~200M dòng. Ở 1M văn bản (1,3 tỉ dòng) hãy partition `BY HASH (doc_id)` thành 32–64 partition — hash thay vì range vì truy cập luôn theo `doc_id` và không có tính cục bộ theo thời gian. Lưu ý index GiST ltree sẽ thành từng-partition, nên các mẫu `lquery` xuyên văn bản suy thoái thành quét theo partition; điều đó chấp nhận được vì các query như vậy là phân tích, không phải tương tác.

**Kích thước:** trung bình ~400 byte/dòng (phần lớn dòng là Điểm với nội dung ngắn). 100k văn bản → 131M dòng → **~52 GB**. 1M văn bản → 1,3 tỉ dòng → ~520 GB, có partition. Bảng này, không phải metadata, là áp lực scale thật đầu tiên sau vector.

---

### 4. `legal_section_chunks` — embedding cho corpus

**Vì sao tồn tại — và vì sao nó tách khỏi section.** Độ dài khoản đã đo (trung bình 779, p90 1.749, tối đa 8.704 ký tự) vượt cửa sổ 256 token của model embedding (I-13), nên **một section map thành N chunk**. `schema.sql:50` đặt `embedding` trực tiếp trên dòng section, điều về mặt cấu trúc không thể biểu diễn được việc đó và âm thầm cắt bớt. Một bảng riêng không phải một sở thích về phong cách; nó là yêu cầu do dữ liệu đã đo.

```sql
CREATE TABLE legal_section_chunks (
    id              BIGSERIAL PRIMARY KEY,
    section_id      TEXT NOT NULL REFERENCES legal_document_sections(id) ON DELETE CASCADE,
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,  -- phi chuẩn hoá để lọc
    path            LTREE NOT NULL,                      -- phi chuẩn hoá: cho phép vector search giới hạn theo subtree
    chunk_index     SMALLINT NOT NULL,
    token_count     SMALLINT NOT NULL,
    content         TEXT NOT NULL,
    context_prefix  TEXT,                                -- 'Chương I > Điều 6 > Khoản 3' được nối vào trước khi embed
    embedding       vector(768) NOT NULL,
    embedding_model_id SMALLINT NOT NULL REFERENCES embedding_models(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lsc UNIQUE (section_id, chunk_index, embedding_model_id),
    CONSTRAINT ck_lsc_tokens CHECK (token_count > 0 AND token_count <= 512)
);
ALTER TABLE legal_section_chunks ALTER COLUMN embedding SET STORAGE PLAIN;
```

**Các quyết định thiết kế.**
- `doc_id` và `path` được **cố tình phi chuẩn hoá** để tránh một join bên trong query vector. Filter phải nằm trên cùng bảng với vector để planner kết hợp chúng tốt với một lượt scan HNSW.
- `embedding_model_id` cho phép **migration model không downtime**: ghi các dòng model mới song song với cũ, chuyển đường đọc bằng config, drop cái cũ sau khi kiểm chứng. Không có nó, đổi model embedding nghĩa là downtime hoặc một bảng thứ hai.
- `context_prefix` — embed một `"a) Phù hiệu cấp cho xe ô tô…"` trơ trọi làm mất toàn bộ ngữ cảnh. Nối chuỗi tổ tiên vào trước (có miễn phí từ `path`) cải thiện truy hồi một cách đo được với các Điểm ngắn. Được lưu lại để kiểm toán và tái lập được.
- **`SET STORAGE PLAIN` không phải tuỳ chọn.** Một `vector(768)` là 3.076 byte, vượt ngưỡng TOAST ~2 KB, nên Postgres sẽ nén và đưa nó ra ngoài dòng — thêm một lần detoast cho *mỗi* phép tính khoảng cách và làm chậm việc build HNSW đáng kể. Đây là bước cấu hình pgvector bị bỏ sót nhiều nhất.

**Index**
```sql
CREATE INDEX idx_lsc_hnsw ON legal_section_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_lsc_section ON legal_section_chunks (section_id, chunk_index);
CREATE INDEX idx_lsc_doc     ON legal_section_chunks (doc_id);
CREATE INDEX idx_lsc_path    ON legal_section_chunks USING gist (path);
CREATE INDEX idx_lsc_fts     ON legal_section_chunks USING gin (to_tsvector('vi', content));  -- hybrid search
```
**Partition.** `BY LIST (embedding_model_id)` rất hấp dẫn: mỗi model có index HNSW riêng, query luôn lọc theo một model nên việc prune partition là chính xác, và loại bỏ một model là `DROP PARTITION`. Vượt ~50M dòng mỗi model, hãy sub-partition `BY HASH (doc_id)`.

**Kích thước:** ~4,1 KB/dòng heap + ~3,5 KB/dòng HNSW (xem BƯỚC 13). Tốc độ theo văn bản đã đo ≈ 500 chunk/văn bản → 100k văn bản = 50M chunk ≈ **205 GB heap + 175 GB index**. **Đây là chi phí chủ đạo trong toàn bộ thiết kế** và là lý do BƯỚC 13 khuyến nghị dùng `halfvec` sớm.

---

### 5. `embedding_models` — bảng tham chiếu

**Vì sao tồn tại.** Kết quả truy hồi chỉ so sánh được trong cùng một model+số chiều+cách chuẩn hoá. Không có một registry, một lần đổi model sẽ âm thầm làm hỏng không gian vector, và không có ghi chép nào về vector nào đến từ đâu.

```sql
CREATE TABLE embedding_models (
    id           SMALLSERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,          -- 'dangvantuan/vietnamese-embedding'
    dimensions   SMALLINT NOT NULL,             -- 768 (đã đo: khớp schema.sql)
    max_tokens   SMALLINT NOT NULL,             -- 256 (đã đo: embeddings.py:26)
    normalised   BOOLEAN NOT NULL DEFAULT TRUE,
    distance     TEXT NOT NULL DEFAULT 'cosine',
    is_active    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_em_distance CHECK (distance IN ('cosine','l2','ip'))
);
```
Kích thước: < 10 dòng. **Một điều CHƯA RÕ đáng ghi lại ở đây:** `dangvantuan/vietnamese-embedding` dựa trên PhoBERT, và các model họ PhoBERT thường được huấn luyện trên đầu vào tiếng Việt **đã tách từ**. Không có gì trong `embeddings.py` thực hiện tách từ. Việc model card của nó có yêu cầu điều đó — và do đó chất lượng truy hồi hiện tại có đang bị bỏ lỡ hay không — phải được kiểm chứng với tài liệu model và đo bằng một test truy hồi A/B. Tôi gắn cờ điều này thay vì khẳng định. `max_tokens` nằm ở đây để chunker đọc giới hạn của nó từ registry thay vì từ hằng số `256` hard-code ở `embeddings.py:26`.

---

### 6. `legal_document_effectivity` — hiệu lực thời gian dẫn xuất (sửa I-10)

**Vì sao tồn tại.** Đã đo: `thuoc_tinh.json` nói nghị định còn hiệu lực và không có ngày kết thúc, trong khi `luoc_do.json` cho thấy nó bị bãi bỏ bởi `336/2025/NĐ-CP` và sửa đổi bởi `238/2026/NĐ-CP`. Một field trạng thái đơn lẻ đã lưu là không đáng tin cậy một cách chứng minh được, và `loader.py:18` lọc theo đúng loại field đó.

```sql
CREATE TABLE legal_document_effectivity (
    doc_id       TEXT PRIMARY KEY REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    valid_from   DATE,
    valid_to     DATE,                     -- dẫn xuất: MIN(eff_to, eff_from của văn bản bãi bỏ)
    status       TEXT NOT NULL,            -- 'effective' | 'expired' | 'repealed' | 'partially_repealed'
                                           -- | 'suspended' | 'not_yet_effective' | 'unknown'
    repealed_by  TEXT REFERENCES legal_documents(doc_id),
    superseded_by TEXT REFERENCES legal_documents(doc_id),
    amended_by   TEXT[] NOT NULL DEFAULT '{}',
    derivation   JSONB NOT NULL,           -- dấu vết audit: cạnh/ngày nào tạo ra phán quyết này
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_lde_status CHECK (status IN
      ('effective','expired','repealed','partially_repealed','suspended','not_yet_effective','unknown'))
);
CREATE INDEX idx_lde_status   ON legal_document_effectivity (status);
CREATE INDEX idx_lde_window   ON legal_document_effectivity (valid_from, valid_to);
CREATE INDEX idx_lde_active   ON legal_document_effectivity (doc_id) WHERE status = 'effective';
CREATE INDEX idx_lde_stale    ON legal_document_effectivity (computed_at);
```
**`derivation` là cột quan trọng.** Với một sản phẩm pháp lý, câu hỏi "vì sao hệ thống tin rằng văn bản này còn hiệu lực?" phải trả lời được. Nó ghi lại các cạnh và ngày tạo ra phán quyết, và `'unknown'` là một trạng thái hạng nhất — thà có một unknown tường minh hơn là một `'effective'` sai một cách tự tin. Được refresh bởi job `effectivity.refresh` (§7.6) và mỗi khi có thay đổi quan hệ. Kích thước: một dòng cho mỗi văn bản, ~500 B → 50 MB ở 100k.

---

### 7. `legal_document_snapshots` — xuất xứ crawl bất biến

**Vì sao tồn tại.** Cho phép parse lại mà không crawl lại (nhờ đó bug parser sửa được hồi tố), cho một câu trả lời dựa trên sự thật cho "chúng ta tin điều gì vào ngày D?", và giới hạn bán kính ảnh hưởng của một lần crawl xấu.

```sql
CREATE TABLE legal_document_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    crawled_at   TIMESTAMPTZ NOT NULL,
    content_hash TEXT NOT NULL,
    storage_key  TEXT NOT NULL,             -- prefix object storage giữ cả 4 artifact thô
    artifact_bytes INTEGER,
    parser_version TEXT NOT NULL,
    CONSTRAINT uq_lds_snap UNIQUE (doc_id, content_hash)
);
CREATE INDEX idx_ldsnap_doc ON legal_document_snapshots (doc_id, crawled_at DESC);
```
`UNIQUE (doc_id, content_hash)` nghĩa là một lần crawl lại không thay đổi gì sẽ là no-op — cách rẻ để việc crawl lại hằng tuần trở nên chi trả được. Kích thước: ~200 B/dòng + object storage (~845 KB mỗi văn bản đã đo, nén được xuống ~150 KB).

---

### 8. Quan hệ văn bản — **không** còn bảng SoT trong Postgres

**Chốt hướng sản phẩm:** `luoc_do.json` và cạnh dẫn chiếu sống trên **Neo4j**. Postgres chỉ giữ khóa map `doc_id` / `section_id` và bảng mỏng `legal_document_effectivity` dẫn xuất từ Neo4j để filter HNSW.

Traversal = Cypher trên Neo4j → hydrate content từ Postgres theo cùng id. **Không** nhân bản bảng cạnh trong Postgres.

---

### 8b. `legal_document_effectivity` — cờ dẫn xuất (Postgres)

```sql
CREATE TABLE legal_document_effectivity (
    doc_id       TEXT PRIMARY KEY REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    status       TEXT NOT NULL,
    valid_from   DATE,
    valid_to     DATE,
    derived_from JSONB DEFAULT '[]',  -- tóm tắt cạnh Neo4j đã dùng
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 9. Catalogue nhãn quan hệ (tuỳ chọn)

Chỉ phục vụ UI/label (`sua_doi_bo_sung` → "Sửa đổi, bổ sung"). Có thể là config app hoặc bảng mã mỏng. **Cạnh thật nằm trên Neo4j**, không phải bảng Postgres.

---

### 10. Dẫn chiếu điều khoản — SoT trên Neo4j (`:REFERS_TO`)

Đã đo ~731 tham chiếu/văn bản. Extract xong ghi cạnh Neo4j `(:Section)-[:REFERS_TO]->(:Section)` với `section_id` map sang Postgres. **Không** cần bảng `legal_references` SoT trong Postgres (tránh nhân bản graph).

Tuỳ chọn: bảng log lỗi extract trên Postgres (raw_text, resolution=failed) — không phải SoT cạnh.

---

### 11. `legal_keywords`, `legal_aliases`, `legal_topics`, `legal_section_topics`

**Vì sao tồn tại.** Đã đo: `majors` là `[]` và `fields` là `["Chưa phân loại"]` — phân loại do crawler cung cấp trên thực tế là không có, nên mọi việc faceting hay routing query phải được xây tại chỗ. Alias quan trọng vì người dùng nói `"Nghị định 168"`, `"NĐ 168"`, `"168/2024"`, và `"luật giao thông mới"` để chỉ cùng một văn bản.

```sql
CREATE TABLE legal_keywords (
    id          BIGSERIAL PRIMARY KEY,
    section_id  TEXT NOT NULL REFERENCES legal_document_sections(id) ON DELETE CASCADE,
    keyword     TEXT NOT NULL,
    keyword_norm TEXT NOT NULL,             -- chữ thường không dấu
    weight      REAL NOT NULL DEFAULT 1.0,
    source      TEXT NOT NULL,              -- 'tfidf' | 'llm' | 'manual'
    CONSTRAINT uq_lk UNIQUE (section_id, keyword_norm, source)
);
CREATE INDEX idx_lk_norm ON legal_keywords (keyword_norm);

CREATE TABLE legal_aliases (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    alias_norm  TEXT NOT NULL,
    source      TEXT NOT NULL,              -- 'derived' | 'manual' | 'query_log'
    CONSTRAINT uq_la UNIQUE (doc_id, alias_norm)
);
CREATE INDEX idx_la_norm ON legal_aliases USING gin (alias_norm gin_trgm_ops);

CREATE TABLE legal_topics (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    label_vi    TEXT NOT NULL,
    parent_id   INTEGER REFERENCES legal_topics(id),
    path        LTREE NOT NULL
);
CREATE INDEX idx_lt_path ON legal_topics USING gist (path);

CREATE TABLE legal_section_topics (
    section_id  TEXT NOT NULL REFERENCES legal_document_sections(id) ON DELETE CASCADE,
    topic_id    INTEGER NOT NULL REFERENCES legal_topics(id) ON DELETE CASCADE,
    confidence  REAL NOT NULL DEFAULT 1.0,
    source      TEXT NOT NULL,
    PRIMARY KEY (section_id, topic_id)
);
```
`source = 'query_log'` trên alias đóng một vòng hữu ích: `search_logs` (bảng 17) cho thấy người dùng thực sự gọi tên văn bản thế nào, và những cách gọi đó trở thành alias truy hồi được. **Kích thước:** keyword ~10/section trên các section có nội dung → ~4M dòng mỗi 100k văn bản; alias ~5/văn bản → 500k; topic vài trăm. Tất cả đều nhỏ so với vector.

---

### 12. `legal_penalties` — phóng chiếu nghiệp vụ (bảng có ROI cao nhất trong thiết kế này)

**Vì sao tồn tại.** Đã đo trong một văn bản duy nhất: **186** khoảng `phạt tiền từ`, **472** số tiền, **103** lần trừ điểm giấy phép. Đây là một bảng xử phạt có cấu trúc được serialize thành văn xuôi. Trích xuất nó biến "mức phạt cho X là bao nhiêu?" từ việc một LLM đọc số ra khỏi văn bản đã truy hồi — cơ chế kém tin cậy nhất có thể, và là loại câu hỏi mà `PROGRESS_REPORT.md:87` ghi lại sản phẩm đang *chủ động từ chối* — thành một tra cứu số có index, không có LLM nào trên đường trả lời.

```sql
CREATE TABLE legal_penalties (
    id              BIGSERIAL PRIMARY KEY,
    section_id      TEXT NOT NULL REFERENCES legal_document_sections(id) ON DELETE CASCADE,
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    path            LTREE NOT NULL,
    subject_type    TEXT,                    -- 'individual' | 'organization' | NULL
    vehicle_class   TEXT,                    -- 'xe ô tô' | 'xe mô tô' | ...
    offence_summary TEXT NOT NULL,
    fine_min        NUMERIC(14,0),           -- VND
    fine_max        NUMERIC(14,0),
    licence_points  SMALLINT,                -- trừ điểm GPLX
    suspension_min_months SMALLINT,
    suspension_max_months SMALLINT,
    extra_sanctions TEXT[],
    extractor_version TEXT NOT NULL,
    confidence      REAL NOT NULL,
    verified_by     TEXT,                    -- người rà soát; NULL cho tới khi được kiểm chứng
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_lp_fine CHECK (fine_max IS NULL OR fine_min IS NULL OR fine_max >= fine_min),
    CONSTRAINT ck_lp_points CHECK (licence_points IS NULL OR licence_points BETWEEN 1 AND 12)
);
CREATE INDEX idx_lp_section ON legal_penalties (section_id);
CREATE INDEX idx_lp_fine    ON legal_penalties (fine_min, fine_max);
CREATE INDEX idx_lp_path    ON legal_penalties USING gist (path);
CREATE INDEX idx_lp_offence_fts ON legal_penalties USING gin (to_tsvector('vi', offence_summary));
CREATE INDEX idx_lp_unverified ON legal_penalties (doc_id) WHERE verified_by IS NULL;
```
`confidence` + `verified_by` làm cho đây trở thành một phóng chiếu *rà soát được* một cách tường minh: được trích xuất tự động, được nâng thành có thẩm quyền bởi con người. Với các con số pháp lý, cửa rà soát đó là không tuỳ chọn. **Ghi chú phạm vi:** bảng này riêng cho domain xử phạt hành chính. Các domain khác (lao động, thuế, thương mại) cần phóng chiếu riêng; điều đó là ổn — các phóng chiếu domain nên hẹp và nhiều thay vì một bảng key-value tổng quát mà không query được gì.

**Kích thước:** ~200 dòng cho mỗi văn bản loại xử phạt, ~300 B/dòng → nhỏ (~6 GB ở 100k văn bản xử phạt, ít hơn nhiều nếu phần lớn văn bản không phải văn bản xử phạt).

---

### 13. `uploaded_contracts` — văn bản của người dùng

```sql
CREATE TABLE uploaded_contracts (
    contract_id     UUID PRIMARY KEY,                    -- trước là surrogate TEXT + PK BIGSERIAL (I-3)
    user_id         UUID NOT NULL,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    byte_size       BIGINT NOT NULL,
    storage_key     TEXT NOT NULL,                       -- object storage, không phải đường dẫn local (I-41)
    content_sha256  TEXT NOT NULL,                       -- chống trùng: cùng một file upload hai lần
    status          TEXT NOT NULL DEFAULT 'received',
    failure_code    TEXT,                                -- có kiểu, không phải một thông báo thô (I-16, I-26)
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,                         -- soft delete, cho luồng xoá kiểu GDPR
    CONSTRAINT ck_uc_status CHECK (status IN ('received','parsing','ready','failed')),
    CONSTRAINT ck_uc_type CHECK (file_type IN ('.docx','.doc','.pdf','.png','.jpg','.jpeg'))
);
CREATE INDEX idx_uc_user_created ON uploaded_contracts (user_id, created_at DESC)
    WHERE deleted_at IS NULL;                            -- sửa I-23 + keyset pagination I-25
CREATE INDEX idx_uc_sha          ON uploaded_contracts (user_id, content_sha256)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_uc_status       ON uploaded_contracts (status) WHERE status IN ('received','parsing');
```
Thay đổi so với `database.py:31-43`: `contract_id` trở thành primary key `UUID` thật (`BIGSERIAL id` chưa từng được tham chiếu ở đâu); `message` trở thành `failure_code` có kiểu; `analysis`/`risks` JSONB chuyển sang bảng riêng (14, 15); `file_path` trở thành `storage_key`; `TIMESTAMP` trở thành `TIMESTAMPTZ`; mọi cột kiểu enum có thêm một `CHECK`; soft delete cộng `content_sha256` hỗ trợ yêu cầu xoá và chống trùng upload. **Kích thước:** ~500 B/dòng → 500 MB ở 1M hợp đồng. Không cần partition; nếu có bao giờ cần thì `BY HASH (user_id)`.

---

### 14. `contract_documents` — văn bản đã parse, lưu một lần

**Vì sao tồn tại.** Sửa I-6 trực tiếp: hôm nay đầu vào của extractor được lắp lại từ các chunk chồng lấp theo thứ tự dictionary, vừa O(corpus) vừa mất mát.

```sql
CREATE TABLE contract_documents (
    contract_id  UUID PRIMARY KEY REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    full_text    TEXT NOT NULL,
    char_count   INTEGER NOT NULL,
    parser       TEXT NOT NULL,          -- 'python-docx' | 'pdfplumber' | 'gemini-ocr'
    parser_version TEXT NOT NULL,
    ocr_used     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
Ghi lại `parser`/`ocr_used` quan trọng cho phân tích chất lượng: các hợp đồng qua OCR nên được kỳ vọng cho extraction kém hơn, và không có cột này thì tương quan đó không đo được. **Kích thước:** ~30 KB/hợp đồng → 30 GB ở 1M. Đặt `STORAGE EXTENDED` (mặc định) để `full_text` được nén TOAST — khác với các cột vector, ở đây việc nén là mong muốn.

---

### 15. `contract_chunks` — embedding của văn bản người dùng

**Vì sao tồn tại.** Thay thế collection FAISS `contracts`; đây là bảng loại bỏ I-1.

```sql
CREATE TABLE contract_chunks (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     UUID NOT NULL REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    article_no      TEXT,                    -- số 'Điều', có cấu trúc (sửa việc trộn namespace ở I-36)
    clause_no       TEXT,                    -- số 'Khoản', riêng biệt — không bao giờ lẫn
    is_preamble     BOOLEAN NOT NULL DEFAULT FALSE,
    content         TEXT NOT NULL,
    token_count     SMALLINT NOT NULL,
    embedding       vector(768) NOT NULL,
    embedding_model_id SMALLINT NOT NULL REFERENCES embedding_models(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cc UNIQUE (contract_id, chunk_index, embedding_model_id)
);
ALTER TABLE contract_chunks ALTER COLUMN embedding SET STORAGE PLAIN;

CREATE INDEX idx_cc_contract ON contract_chunks (contract_id, chunk_index);
CREATE INDEX idx_cc_hnsw ON contract_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_cc_fts ON contract_chunks USING gin (to_tsvector('vi', content));
```
Tách `article_no` khỏi `clause_no` sửa I-36 ở cấp schema: hôm nay một field metadata `clause_number` giữ hoặc số Điều hoặc số Khoản tuỳ regex nào khớp, và `qa_agent.py:136` so sánh trích dẫn xuyên qua sự nhập nhằng đó. **Query sửa I-1:**
```sql
SELECT id, article_no, clause_no, content, 1 - (embedding <=> $2) AS score
FROM contract_chunks
WHERE contract_id = $1 AND embedding_model_id = $3
ORDER BY embedding <=> $2
LIMIT $4;
```
Ngữ nghĩa filter chính xác — không `fetch_k`, không hậu lọc. **Partition:** `BY HASH (contract_id)`, 32 partition, trên ~50M dòng; điều này cũng làm lượt scan HNSW theo hợp đồng chọn lọc hơn. **Kích thước:** ~50 chunk/hợp đồng → 50M chunk ở 1M hợp đồng ≈ 205 GB heap + 175 GB HNSW. Chunk hợp đồng là ứng viên mạnh cho `halfvec` trước tiên, vì recall chính xác trên văn bản của một người dùng ít quan trọng hơn so với trên corpus pháp luật.

---

### 16. `analysis_runs`, `contract_analyses`, `contract_risks`

**Vì sao tồn tại.** Thay các blob JSONB `analysis`/`risks` (`database.py:45-46`), vốn không query được (`SELECT` các hợp đồng có rủi ro chấm dứt nghiêm trọng đòi quét toàn bộ JSONB), không validate được (I-30), và không mang xuất xứ nào.

```sql
CREATE TABLE analysis_runs (
    run_id          UUID PRIMARY KEY,
    contract_id     UUID NOT NULL REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    requested_by    UUID NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    completeness    TEXT,                    -- 'complete' | 'partial'  ← phơi bày việc âm thầm bỏ ở I-29
    clauses_total   INTEGER,
    clauses_judged  INTEGER,
    clauses_skipped INTEGER,
    prompt_version  TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    embedding_model_id SMALLINT REFERENCES embedding_models(id),
    kb_snapshot_at  TIMESTAMPTZ,             -- trạng thái corpus nào sinh ra phán quyết này
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(10,4),
    duration_ms     INTEGER,
    error_code      TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ar_status CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    CONSTRAINT ck_ar_completeness CHECK (completeness IS NULL OR completeness IN ('complete','partial'))
);
CREATE INDEX idx_ar_contract ON analysis_runs (contract_id, created_at DESC);
CREATE INDEX idx_ar_active   ON analysis_runs (status) WHERE status IN ('queued','running');

CREATE TABLE contract_analyses (
    contract_id     UUID PRIMARY KEY REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES analysis_runs(run_id),
    contract_type   TEXT,
    execution_date  TEXT,                    -- TEXT: ngày trong nguồn là tiếng Việt tự do, chưa parse
    start_date      TEXT,
    end_date        TEXT,
    duration        TEXT,
    contract_value  TEXT,
    fields          JSONB NOT NULL,          -- ~12 field tự sự còn lại, cố tình bán cấu trúc
    parties         JSONB NOT NULL DEFAULT '[]',
    clauses         JSONB NOT NULL DEFAULT '[]',
    schema_version  SMALLINT NOT NULL,       -- sửa nửa "bất tương thích âm thầm" của I-30
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE contract_risks (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     UUID NOT NULL REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES analysis_runs(run_id),
    article_no      TEXT NOT NULL,
    severity        TEXT NOT NULL,
    issue           TEXT NOT NULL,
    recommendation  TEXT,
    legal_basis_text TEXT,
    legal_basis_section_id TEXT REFERENCES legal_document_sections(id) ON DELETE SET NULL,
    grounding_status TEXT NOT NULL,          -- 'grounded' | 'insufficient_evidence' | 'skipped_error'
    retrieved_top_score REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_cr_sev CHECK (severity IN ('critical','warning','ok')),
    CONSTRAINT ck_cr_ground CHECK (grounding_status IN ('grounded','insufficient_evidence','skipped_error'))
);
CREATE INDEX idx_cr_contract ON contract_risks (contract_id, severity);
CREATE INDEX idx_cr_severity ON contract_risks (severity) WHERE severity = 'critical';
CREATE INDEX idx_cr_basis    ON contract_risks (legal_basis_section_id)
    WHERE legal_basis_section_id IS NOT NULL;
```

**Ba quyết định đáng bảo vệ.**
- `contract_analyses.fields` giữ JSONB cho ~12 field tự sự (`force_majeure`, `severability`, …). Chúng là text tự do dài, không bao giờ được filter, và thường xuyên vắng mặt — mỗi cái một cột sẽ thành 12 cột TEXT phần lớn NULL. Những field *được* query thì có cột thật. Đây là một sự lai có chủ ý, không phải sự do dự.
- `contract_risks.legal_basis_section_id` là bổ sung then chốt: nó biến một chuỗi trích dẫn text tự do (`RiskItem.legal_basis`, `schemas/contract.py:23`) thành một **khoá ngoại kiểm chứng được**. Kết hợp với `idx_cr_basis` nó trả lời "phân tích nào đã viện dẫn luật mà nay đã thay đổi?" — chính là query làm cho job invalidation ở §7.6 khả thi. Không có nó, cách sửa I-10 không thể lan tới các phân tích đã giao.
- `grounding_status` và `retrieved_top_score` làm đường từ chối trở nên đo được. Hôm nay một cảnh báo `insufficient_evidence` không phân biệt được với một kho tri thức rỗng (H-7); hai cột này biến điều đó thành một tỉ lệ theo dõi được.

**Kích thước:** run ~1 KB/dòng; analyses ~5 KB/dòng; risks ~1 KB/dòng × ~20/hợp đồng. Ở 1M hợp đồng ≈ 25 GB tổng.

---

### 17. `search_logs` — telemetry truy hồi

**Vì sao tồn tại.** Không metric nào có thể bắt được I-1, I-10, hay I-13 tính được hôm nay, bởi vì truy hồi không để lại dấu vết. Bảng này là dụng cụ đo.

```sql
CREATE TABLE search_logs (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         UUID,
    contract_id     UUID,
    correlation_id  UUID NOT NULL,
    surface         TEXT NOT NULL,           -- 'chat' | 'clause_judge' | 'api_search'
    query_text      TEXT NOT NULL,
    query_norm      TEXT NOT NULL,
    strategy        TEXT NOT NULL,           -- 'vector' | 'lexical' | 'hybrid'
    embedding_model_id SMALLINT REFERENCES embedding_models(id),
    top_k           SMALLINT NOT NULL,
    result_count    SMALLINT NOT NULL,       -- giá trị 0 ở đây là tín hiệu của I-1 / H-7
    top_score       REAL,
    threshold_used  REAL,
    result_ids      BIGINT[] NOT NULL DEFAULT '{}',
    embed_ms        INTEGER,
    search_ms       INTEGER,
    rerank_ms       INTEGER,
    refused         BOOLEAN NOT NULL DEFAULT FALSE
) PARTITION BY RANGE (occurred_at);
CREATE INDEX idx_sl_time    ON search_logs (occurred_at DESC);
CREATE INDEX idx_sl_zero    ON search_logs (surface, occurred_at DESC) WHERE result_count = 0;
CREATE INDEX idx_sl_norm    ON search_logs USING gin (query_norm gin_trgm_ops);
```
**Partition theo tháng từ ngày đầu** — đây là bảng dung lượng cao duy nhất cần partition ngay lập tức, vì retention chính là mục đích (`DROP PARTITION` thắng `DELETE`). `result_count = 0` với một partial index làm cho metric sức khoẻ quan trọng nhất trở thành một phép đếm nhanh. `idx_sl_norm` đồng thời là nguồn cho `legal_aliases(source='query_log')`. **Kích thước:** ~500 B/dòng; ở 100 lượt tìm/giây đó là ~250M dòng/tháng ≈ 125 GB/tháng — giữ 3 tháng nóng, chuyển phần còn lại sang cold storage dưới dạng tổng hợp.

---

### 18. `user_feedback`

**Vì sao tồn tại.** `PROGRESS_REPORT.md:98` liệt kê 👍/👎 là một tính năng còn thiếu. Nó không chỉ là một tính năng: không có nhãn kết quả thì không có cách nào đo xem một thay đổi prompt hay truy hồi có giúp gì không, làm cho mọi quyết định chất lượng tương lai thành một ý kiến.

```sql
CREATE TABLE user_feedback (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL,
    contract_id     UUID REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL,           -- 'chat_answer' | 'risk_item' | 'analysis'
    target_id       TEXT NOT NULL,
    correlation_id  UUID,                    -- join tới search_logs để lấy đúng lượt truy hồi đã sinh ra nó
    rating          SMALLINT NOT NULL,       -- -1 | +1
    reason_code     TEXT,                    -- 'wrong_law' | 'hallucinated' | 'incomplete' | 'unclear'
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_uf_rating CHECK (rating IN (-1, 1)),
    CONSTRAINT ck_uf_target CHECK (target_type IN ('chat_answer','risk_item','analysis'))
);
CREATE INDEX idx_uf_target   ON user_feedback (target_type, target_id);
CREATE INDEX idx_uf_negative ON user_feedback (created_at DESC) WHERE rating = -1;
```
`correlation_id` là thứ làm bảng này có giá trị thay vì chỉ để trang trí: một 👎 join tới đúng lượt truy hồi đã sinh ra câu trả lời, nên feedback tiêu cực trở thành một tập dữ liệu lỗi truy hồi có nhãn — corpus mầm cho benchmark mà `PROGRESS_REPORT.md:88` xác định là ưu tiên số một. **Kích thước:** nhỏ.

---

### 19. `jobs` — queue

```sql
CREATE TABLE jobs (
    id              BIGSERIAL PRIMARY KEY,
    job_type        TEXT NOT NULL,
    payload         JSONB NOT NULL,
    idempotency_key TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    priority        SMALLINT NOT NULL DEFAULT 100,
    attempts        SMALLINT NOT NULL DEFAULT 0,
    max_attempts    SMALLINT NOT NULL DEFAULT 5,
    lease_expires_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error      TEXT,
    correlation_id  UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_jobs_idem UNIQUE (job_type, idempotency_key),
    CONSTRAINT ck_jobs_status CHECK (status IN ('queued','running','succeeded','failed','dead'))
);
CREATE INDEX idx_jobs_claim ON jobs (job_type, priority, next_attempt_at)
    WHERE status = 'queued';
CREATE INDEX idx_jobs_stuck ON jobs (lease_expires_at) WHERE status = 'running';
```
Mẫu nhận job:
```sql
UPDATE jobs SET status='running', attempts=attempts+1,
       lease_expires_at = NOW() + INTERVAL '10 minutes', updated_at=NOW()
WHERE id = (SELECT id FROM jobs
            WHERE status='queued' AND job_type = $1 AND next_attempt_at <= NOW()
            ORDER BY priority, next_attempt_at
            FOR UPDATE SKIP LOCKED LIMIT 1)
RETURNING *;
```
`UNIQUE (job_type, idempotency_key)` làm việc enqueue trở nên idempotent; `idx_jobs_stuck` điều khiển việc thu hồi lease cho các worker đã crash. **Partition:** không cần — job đã hoàn thành được prune bởi job retention. **Kích thước:** bị giới hạn bởi retention.

---

### 20. `crawl_frontier`

**Vì sao tồn tại.** Đã đo: quan hệ đi vào chỉ nêu tên văn bản bằng `doc_id` + `title`, không có ngày và không có `doc_num`. Vì vậy việc làm corpus lớn lên *đòi hỏi* một frontier khám phá; không có nó corpus chỉ có thể chứa các văn bản chọn tay.

```sql
CREATE TABLE crawl_frontier (
    doc_id          TEXT PRIMARY KEY,
    discovered_via  TEXT,                    -- loại quan hệ đã làm nó hiện ra
    discovered_from TEXT,                    -- văn bản mà luoc_do của nó nêu tên nó
    hint_title      TEXT,                    -- payload duy nhất mà quan hệ đi vào cung cấp
    priority        SMALLINT NOT NULL DEFAULT 100,
    state           TEXT NOT NULL DEFAULT 'pending',
    attempts        SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error      TEXT,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    CONSTRAINT ck_cf_state CHECK (state IN ('pending','crawling','done','failed','skipped'))
);
CREATE INDEX idx_cf_ready ON crawl_frontier (priority, next_attempt_at) WHERE state = 'pending';
```
**ĐỀ XUẤT về priority.** Xếp hạng theo thẩm quyền pháp lý và số lần được viện dẫn, không theo thứ tự khám phá: một `Luật` được 500 nghị định viện dẫn có giá trị với chất lượng truy hồi cao hơn nhiều so với một `Quyết định` cấp tỉnh vô danh. `legal_document_types.authority_rank` (bảng 2) cộng số cạnh đi vào từ bảng 8 cho đúng thứ hạng đó.

---

## Tổng hợp schema

| # | Bảng | Mục đích | Số dòng @100k văn bản / 1M hợp đồng | Kích thước ước tính | Partition |
|---|---|---|---|---|---|
| 1 | `legal_documents` | gốc corpus | 100k | 200 MB | — |
| 2 | `legal_document_types` | tham chiếu + thứ bậc thẩm quyền | <50 | — | — |
| 3 | `legal_document_sections` | phân cấp + ltree | 131M | 52 GB | hash(doc_id) @1M văn bản |
| 4 | `legal_section_chunks` | embedding corpus | 50M | **380 GB** | list(model)+hash(doc) |
| 5 | `embedding_models` | registry model | <10 | — | — |
| 6 | `legal_document_effectivity` | hiệu lực dẫn xuất (I-10) | 100k | 50 MB | — |
| 7 | `legal_document_snapshots` | xuất xứ crawl | 300k | 60 MB + object | — |
| 8 | *(quan hệ)* | **Neo4j SoT** — không bảng cạnh PG | — | — | — |
| 9 | `legal_relation_types` | tham chiếu | 15 | — | — |
| 10 | `legal_references` | trích dẫn đã giải | 73M | 19 GB | hash(doc_id) |
| 11 | keyword/alias/topic | phân loại | ~5M | 2 GB | — |
| 12 | `legal_penalties` | phóng chiếu nghiệp vụ | ~20M | 6 GB | — |
| 13 | `uploaded_contracts` | văn bản người dùng | 1M | 500 MB | — |
| 14 | `contract_documents` | văn bản đã parse | 1M | 30 GB | — |
| 15 | `contract_chunks` | embedding hợp đồng | 50M | **380 GB** | hash(contract_id) |
| 16 | run/analyses/risks | kết quả | 21M | 25 GB | — |
| 17 | `search_logs` | telemetry | theo retention | 125 GB/tháng | **range(tháng)** |
| 18 | `user_feedback` | nhãn chất lượng | nhỏ | — | — |
| 19 | `jobs` | queue | theo retention | — | — |
| 20 | `crawl_frontier` | khám phá | ~1M | 200 MB | — |

**Vector chiếm ~76% tổng dung lượng.** Mọi bảng khác cộng lại là số làm tròn bên cạnh bảng 4 và 15 — đó là vì sao BƯỚC 9 và BƯỚC 13 tập trung vào đó.

---

# BƯỚC 9 — Chiến lược pgvector

## 9.1 Số chiều embedding

**THỰC TẾ.** Model hiện tại `dangvantuan/vietnamese-embedding` (`.env.example:3`), dựa trên PhoBERT, **768** chiều, `max_seq_length` bị buộc thành **256** token (`embeddings.py:26`). `schema.sql:50,74` dùng `vector(768)` — nhất quán.

**ĐỀ XUẤT.** Giữ 768 hiện tại (không có chi phí re-embed, schema đã khớp), nhưng coi số chiều như một **cần điều khiển chi phí với ba mức**, chọn theo dung lượng:

| Dung lượng | Cấu hình | Byte/vector | Lý do |
|---|---|---|---|
| < 10M chunk | `vector(768)` | 3.072 | Đơn giản nhất; index vừa RAM |
| 10–50M chunk | `halfvec(768)` | 1.536 | Tiết kiệm ~50%; mất recall thường < 1% với embedding đã chuẩn hoá |
| > 50M chunk | `halfvec(768)` + tiền lọc `bit(768)` | 1.536 + 96 | Tầng nhị phân trước, rerank chính xác trên các ứng viên |

`halfvec` cần pgvector ≥ 0.7. Với Docker, **pin** image `pgvector/pgvector:pg16` (hoặc mới hơn) và assert trong smoke test: `SELECT extversion FROM pg_extension WHERE extname='vector'`.

## 9.2 Độ đo khoảng cách

**THỰC TẾ.** Hiện tại: embedding đã chuẩn hoá (`embeddings.py:22`) + `MAX_INNER_PRODUCT` (`faiss_store.py:55`) = cosine. `schema.sql:61,81` dùng `vector_cosine_ops`. Nhất quán.

**ĐỀ XUẤT.** Giữ cosine (`<=>`, `vector_cosine_ops`). Vì vector đã được chuẩn hoá L2, inner product (`<#>`, `vector_ip_ops`) tương đương về mặt toán học và nhẹ hơn một chút — nhưng cosine tự giải thích và mức tiết kiệm không đáng kể bên cạnh độ trễ LLM. **Đừng trộn** operator class: một index build với `vector_cosine_ops` đơn giản là không được dùng bởi một query viết bằng `<->`, và kết quả là một lượt quét tuần tự âm thầm. Hãy assert điều này trong một test.

## 9.3 HNSW so với IVFFlat

| | HNSW | IVFFlat |
|---|---|---|
| Thời gian build | chậm (nhiều giờ ở 10M) | nhanh |
| Bộ nhớ build | cao — cần `maintenance_work_mem` | thấp |
| Độ trễ query | thấp hơn, ổn định | cao hơn, điều chỉnh được qua `probes` |
| Recall ở cùng độ trễ | tốt hơn | tệ hơn |
| Insert từng phần | tốt, không cần train lại | suy thoái khi centroid lệch |
| Cần dữ liệu train | không | **có** — phải build trên một bảng đã có dữ liệu |
| Kích thước index | lớn hơn (lưu graph) | nhỏ hơn |

**ĐỀ XUẤT: HNSW, với `m = 16, ef_construction = 64`** — khớp với mặc định ngầm của `schema.sql:60-62` nhưng được nêu tường minh.

**Lập luận, riêng cho workload này:** (a) IVFFlat cần một index đã train, không phù hợp với một corpus lớn lên liên tục qua crawl frontier — bạn sẽ phải rebuild định kỳ khi centroid lệch; (b) insert là liên tục (mỗi lần upload, mỗi lần crawl lại) và HNSW xử lý chúng mà không cần train lại; (c) recall quan trọng hơn thời gian build trong một sản phẩm pháp lý, nơi một quy định bị bỏ sót là một câu trả lời sai; (d) ở mức < 50M vector, chi phí build là một lần tính theo giờ, không phải một ràng buộc thường xuyên.

**Điều chỉnh:** bắt đầu với `hnsw.ef_search = 40`; nâng lên 100 nếu một probe recall cho thấy < 0,95 so với tìm kiếm chính xác; `m = 24` chỉ khi cần recall cao hơn ở 768 chiều và chấp nhận được ~30% index lớn hơn.

## 9.4 Chiến lược chunk — bài toán Điều / Khoản / Điểm với cửa sổ 256 token

**Bài toán thật (Điều 13 NĐ 168).** Query: *"Xe ô tô không có gương chiếu hậu thì phạt sao?"*

| Tầng | Mang thông tin gì trong ví dụ | Nếu thiếu khi embed |
|---|---|---|
| **Điều 13** | Đối tượng: người điều khiển **xe ô tô** (và loại xe tương tự) | Khớp nhầm xe máy / không biết áp dụng ai |
| **Khoản 2** | **Mức phạt** 400.000–600.000 đồng | Biết hành vi nhưng không trả lời được "phạt sao" |
| **Điểm a** | Hành vi: thiếu **gương chiếu hậu** (cùng cụm đèn, còi…) | Không bắt được query "gương chiếu hậu" |

Một Khoản gồm nhiều Điểm dài ~500–700 từ → **không thể** nhét cả khoản vào một vector 256 token. Cắt chỉ mỗi Điểm trơ (không kèm Điều/Khoản) cũng **hỏng RAG**.

**ĐỀ XUẤT — embed nhỏ, lắp đủ (small-to-big):**

1. **Đơn vị cắt / embed = 1 Điểm** (dao `muc_luc`), không embed cả Khoản.
2. **`embed_text` (≤ 256 token) luôn ghép 3 mảnh:**
   ```
   Điều 13. [rubric rút gọn: xử phạt người điều khiển xe ô tô…]
   Khoản 2. Phạt tiền từ 400.000 đồng đến 600.000 đồng đối với một trong các hành vi…
   Điểm a) … gương chiếu hậu …
   ```
   → một vector bắt được đối tượng + mức phạt + hành vi.
3. Nếu ghép vượt 256: **ưu tiên giữ nguyên `clause_lead` (câu phạt) + `point_body`**; rút `article_rubric` (giữ cụm đối tượng: "xe ô tô", "GPLX"…).
4. **Sau retrieval (bắt buộc):** hydrate prompt từ Postgres/Neo4j đủ **Điều + cả Khoản cha + Điểm** (và anh em Điểm nếu cần) — LLM không chỉ thấy chuỗi đã cắt 256 token.
5. Hybrid FTS trên `embed_text` giúp khớp số tiền và cụm "gương chiếu hậu" cùng lúc.
6. Khoản không có Điểm: embed theo Khoản + prefix Điều; vẫn hydrate đủ Điều khi trả lời.

`muc_luc` chỉ là dao cắt. Store retrieval = `legal_section_chunks`. Liên kết bộ ba = cột `article_*`/`clause_*`/`point_*` + `PARENT_OF` trên Neo4j + bước hydrate — không dựa vào việc nhét cả khoản vào một embedding.

## 9.5 Lọc metadata — cái bẫy của pgvector và cách sửa

**Đây là điểm tinh tế quyết định việc migration có thực sự sửa I-1 hay không.** HNSW trong pgvector lọc *trong lúc* scan index, nên một `WHERE` chọn lọc cao có thể làm cạn lượt traversal graph trước khi thu đủ `LIMIT` dòng — trả về ít kết quả hơn yêu cầu. Đó là một người họ hàng nhẹ hơn của vấn đề `fetch_k` ở FAISS, và nó phải được thiết kế thay vì được cho là tự khỏi.

**Ba cách giảm nhẹ, theo thứ tự ưu tiên:**

1. **Partial index cho các predicate ổn định, lực lượng thấp.** `schema.sql:60-62` đã làm đúng điều này:
   ```sql
   CREATE INDEX idx_lsc_hnsw_active ON legal_section_chunks
       USING hnsw (embedding vector_cosine_ops)
       WHERE embedding_model_id = 1;
   ```
   **Cảnh báo then chốt:** một partial index chỉ được dùng nếu query lặp lại predicate *đúng theo nghĩa văn tự*. `WHERE embedding_model_id = 1` dùng được nó; `WHERE embedding_model_id = $1` có thể không. Cái này phải được kiểm chứng bằng `EXPLAIN`, không phải giả định — và đó là cách phổ biến nhất khiến một partial HNSW index được dựng cẩn thận lại không được dùng.

2. **Iterative scan (pgvector ≥ 0.8).**
   ```sql
   SET LOCAL hnsw.iterative_scan = relaxed_order;
   SET LOCAL hnsw.max_scan_tuples = 20000;
   ```
   Cho pgvector tiếp tục scan tới khi thoả `LIMIT`. Đây là câu trả lời tổng quát đúng cho các filter có tính chọn lọc cao.

3. **Partition rồi tìm, cho các predicate lực lượng cao.** `contract_id` có hàng triệu giá trị phân biệt, nên không partial index nào giúp được. Hash-partition `contract_chunks` theo `contract_id` nghĩa là planner prune về một partition và tìm trên một index nhỏ hơn nhiều. Kết hợp với việc một hợp đồng chỉ có ~50 chunk, **một lượt quét tuần tự với khoảng cách chính xác thường là plan tối ưu** — và planner sẽ chọn nó. Riêng với `contract_chunks`, khuyến nghị trung thực là: hãy tạo index HNSW, rồi đo xem nó có được dùng chút nào không; một lượt quét chính xác 50 dòng thắng mọi index xấp xỉ.

**Các filter mà thiết kế phải hỗ trợ:** `embedding_model_id` (luôn luôn), `doc_id`, `path <@ subtree`, `level`, trạng thái hiệu lực (join tới bảng 6), `doc_type`/`authority_rank`, khoảng `issue_date`, `contract_id`.

**Lọc theo hiệu lực** — cách sửa I-10 tại thời điểm query:
```sql
SELECT c.section_id, c.content, 1 - (c.embedding <=> $1) AS score
FROM legal_section_chunks c
JOIN legal_document_effectivity e ON e.doc_id = c.doc_id
WHERE c.embedding_model_id = 1
  AND e.status = 'effective'
  AND (e.valid_from IS NULL OR e.valid_from <= $2)
  AND (e.valid_to   IS NULL OR e.valid_to   >= $2)
ORDER BY c.embedding <=> $1
LIMIT 20;
```
Vì join này có tính chọn lọc, đây chính xác là trường hợp cần iterative scan hoặc một partial index trên một boolean `is_effective` phi chuẩn hoá. **ĐỀ XUẤT:** phi chuẩn hoá `is_effective BOOLEAN` xuống `legal_section_chunks`, được duy trì bởi job hiệu lực, và build index HNSW partial trên `WHERE is_effective`. Nó trao đổi một job bảo trì lấy một plan nhanh và đáng tin cậy — một trao đổi tốt, vì filter này nằm trên đường quan trọng của mọi lượt truy hồi pháp luật.

## 9.6 Hybrid search

**Vì sao nó cần thiết ở đây, không chỉ là "có thì tốt".** Vector search thất bại đúng ở những query mà domain này sinh ra nhiều nhất: số hiệu văn bản chính xác (`"168/2024/NĐ-CP"`), trích dẫn chính xác (`"khoản 3 Điều 6"`), và thuật ngữ chuyên ngành hiếm (`"phù hiệu"`). Bằng chứng đã đo: 472 số tiền và 193 trích dẫn phân cấp trong một văn bản — nội dung nặng về số và định danh là chỗ embedding yếu nhất và BM25 mạnh nhất.

```sql
WITH vec AS (
    SELECT id, section_id, content,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS rank
    FROM legal_section_chunks
    WHERE embedding_model_id = 1 AND is_effective
    ORDER BY embedding <=> $1 LIMIT 50
),
lex AS (
    SELECT id, section_id, content,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('vi', content),
                                                  websearch_to_tsquery('vi', $2)) DESC) AS rank
    FROM legal_section_chunks
    WHERE embedding_model_id = 1 AND is_effective
      AND to_tsvector('vi', content) @@ websearch_to_tsquery('vi', $2)
    LIMIT 50
)
SELECT COALESCE(v.id, l.id) AS id,
       COALESCE(v.content, l.content) AS content,
       COALESCE(1.0 / (60 + v.rank), 0) + COALESCE(1.0 / (60 + l.rank), 0) AS rrf_score
FROM vec v FULL OUTER JOIN lex l USING (id)
ORDER BY rrf_score DESC
LIMIT 10;
```
Dùng **Reciprocal Rank Fusion** (k=60) thay vì trộn điểm có trọng số, vì cosine similarity và `ts_rank_cd` ở hai thang không so sánh được, và mọi trọng số cố định sẽ sai với một nửa phân bố query. RRF không cần hiệu chuẩn.

**Điều kiện tiên quyết:** cấu hình tìm kiếm text `vi` với `unaccent` (§extension của BƯỚC 8). Với `'simple'` như đang dùng ở `schema.sql:34,59`, nhánh lexical không thể khớp query không dấu và hybrid search hỏng một nửa từ đầu.

## 9.7 Reranking

**Trạng thái hiện tại: không có.** `retrieve_legal` trả top-3 theo cosine trực tiếp vào prompt (`risk_flagger.py:18`).

**ĐỀ XUẤT — một phễu ba tầng:**

| Tầng | Phương pháp | Vào → ra | Độ trễ |
|---|---|---|---|
| 1 Recall | hybrid RRF | corpus → 50 | ~20–50 ms |
| 2 Rerank | cross-encoder (đa ngôn ngữ, hỗ trợ tiếng Việt) | 50 → 10 | ~50–150 ms CPU |
| 3 Chính sách | thứ bậc thẩm quyền, hiệu lực, đa dạng theo `doc_id`, MMR | 10 → 3–5 | < 1 ms |

Tầng 2 thường tạo ra mức tăng chất lượng đơn lẻ lớn nhất trong một pipeline RAG, vì cosine của bi-encoder là một tín hiệu liên quan yếu với văn bản pháp lý dài. Tầng 3 rẻ và riêng cho domain này: ưu tiên một `Luật` hơn một `Nghị định` khi xung đột (`authority_rank`, bảng 2), không bao giờ trả về một quy định đã bị bãi bỏ, và giới hạn số kết quả mỗi văn bản để một nghị định dài dòng không chiếm cả 5 slot — một rủi ro thực, vì một văn bản đã đo chứa 332 khoản.

**Tầng 3 cũng sửa một vấn đề đang tồn tại.** `SIMILARITY_THRESHOLD = 0.6` (`config.py:20`) là một hằng số toàn cục duy nhất quyết định việc toàn bộ phán quyết tuân thủ được tạo ra hay bị từ chối (`risk_flagger.py:20-30`). Không có bằng chứng nào trong repository cho thấy 0.6 đã được hiệu chuẩn. **ĐỀ XUẤT:** thay ngưỡng tuyệt đối bằng một ngưỡng trên điểm rerank được hiệu chuẩn theo một tập có nhãn, và log `top_score` trong `search_logs` để phân bố quan sát được trước khi chọn một điểm cắt.

## 9.8 Pipeline truy hồi (mục tiêu — GraphRAG)

```
câu hỏi / văn bản điều khoản
  → chuẩn hoá (NFC, khoảng trắng kể cả \xa0, biến thể không dấu cho lexical)
  → phát hiện trích dẫn tường minh ("khoản 3 Điều 6", "168/2024") → tra cứu ltree/doc_num trực tiếp, ĐI TẮT
  → embed query (theo batch; cache theo hash của text đã chuẩn hoá)
  → recall hybrid RRF trên Postgres/pgvector, k=50, lọc model + hiệu lực (+ contract_id)
  → rerank cross-encoder → 10 seed
  → filter chính sách: thẩm quyền, đa dạng, MMR → seed section_id[]
  → Neo4j expand: PARENT_OF|NEXT|REFERS_TO + AMENDS|REPEALS|BASED_ON|CITES…
  → hydrate content từ Postgres theo section_id; bỏ seed/hàng xóm không còn hiệu lực
  → mở rộng bổ sung trong-cây bằng ltree path <@ / @> nếu expand graph tắt/lệch
  → lắp prompt với nhãn nguồn tường minh
  → log search_logs (correlation_id, thời gian, điểm, result_count, graph_hops)
```
Việc đi tắt theo trích dẫn vẫn ưu tiên: *"khoản 3 Điều 6 nói gì?"* → path ltree, không semantic search. Graph expand thêm giá trị khi cần ngữ cảnh xuyên luật (sửa đổi/bãi bỏ/căn cứ/dẫn chiếu).

## 9.9 Top-k

**THỰC TẾ.** Hiện tại: `TOP_K_RETRIEVAL = 5` cho hợp đồng, `k=3` hard-code cho pháp luật (`retriever.py:18`, `risk_flagger.py:18`, `qa_agent.py:61`).

**ĐỀ XUẤT.** Recall 50 → rerank 10 → cuối cùng 3–5, với số cuối được điều khiển bởi một **budget token** thay vì một số cố định: các đoạn pháp luật hiện bị cắt ở 4.000 ký tự (`risk_flagger.py:37`) và 3.000 (`qa_agent.py:71`) *sau khi* đã chọn, điều có thể cắt đôi đoạn liên quan nhất. Hãy chọn theo budget, đừng cắt sau khi chọn.

## 9.10 Bảo trì index

| Việc | Tần suất | Ghi chú |
|---|---|---|
| `maintenance_work_mem` ≥ 2 GB trước khi build | mỗi lần build | nếu không HNSW sẽ spill và thời gian build nhân lên |
| `CREATE INDEX CONCURRENTLY` | mọi lần build production | tránh lock `ACCESS EXCLUSIVE` (đối lập với `database.py:47-48`) |
| Bulk load: drop index → `COPY` → rebuild | mỗi lần backfill | nhanh hơn 10–100× so với insert từng phần |
| Probe recall so với tìm kiếm chính xác | hằng ngày, lấy mẫu | cách **duy nhất** để phát hiện sự suy thoái của index xấp xỉ; hiện không có gì như vậy |
| Kiểm bloat + `REINDEX CONCURRENTLY` | hằng tuần / khi cần | HNSW không thu hồi tốt không gian của node đã xoá |
| Điều chỉnh `autovacuum` trên bảng chunk | liên tục | bảng biến động cao cần scale factor thấp hơn |
| `ANALYZE` sau thay đổi hàng loạt | mỗi lần backfill | planner cần thống kê hiện thời để chọn partial index |

**Probe recall hằng ngày là hạng mục quan trọng nhất và bị bỏ sót phổ biến nhất.** Lấy mẫu 200 query, chạy mỗi cái trên index HNSW và trên tìm kiếm chính xác (`SET enable_indexscan = off`), và ghi lại overlap@10. Sự suy thoái của index xấp xỉ nếu không thì hoàn toàn vô hình — mà đó chính là chế độ lỗi của I-1: chất lượng truy hồi suy giảm âm thầm khi dữ liệu lớn lên, và không có gì đo nó.

---

# BƯỚC 10 — Thiết kế ltree

## 10.1 Cây phân cấp thực sự là gì (đo được, không giả định)

Đề bài hỏi liệu ltree có nên biểu diễn `Văn bản → Chương → Mục → Điều → Khoản → Điểm → Tiểu điểm`. Câu trả lời đã đo là **gần đúng, với hai điều chỉnh**:

```
Văn bản (gốc, = doc_id)
 ├─ Chương            đo được 4
 │   ├─ Mục           đo được 8  ──┐
 │   └─ Điều          đo được 9  ← con TRỰC TIẾP của Chương trong 9 trên 55 trường hợp
 │                                 │
 └─────── Mục ────────────────────┘
              └─ Điều  đo được 46
                   └─ Khoản  đo được 332
                        └─ Điểm  đo được 909
                             └─ Tiểu điểm — KHÔNG QUAN SÁT ĐƯỢC trong văn bản này
```

**Điều chỉnh 1 — cây không đồng nhất theo cấp.** 9 Điều là con trực tiếp của một Chương; 46 Điều nằm dưới một Mục. **Vì vậy một path phải mã hoá *cấp*, không phải *độ sâu*.** Một lược đồ như `173920.1.2.3` là sai: vị trí thứ 2 nghĩa là "Mục" với một Điều và "Khoản" với một Điều khác.

**Điều chỉnh 2 — không Subpoint.** Theo hướng sản phẩm VN: hết ở Điểm. Bỏ Tiểu điểm khỏi schema/CHECK. Nhánh phụ: Phụ lục (PL) → Nhóm.

## 10.2 Lược đồ nhãn

**THỰC TẾ — các ràng buộc cứng của ltree.** Nhãn phải khớp `[A-Za-z0-9_]+`; `.` là dấu phân cách. Vì vậy `"Điều 6"` **không thể** là một nhãn — cả dấu tiếng Việt và dấu cách đều bất hợp pháp. `"Điều \xa02"` (đã đo, lưu ý non-breaking space) sẽ gây lỗi runtime nếu chuyển tự một cách ngây thơ.

**ĐỀ XUẤT — nhãn có tiền tố cấp, hậu tố số thứ tự:**

| Cấp | Tiền tố | Nguồn ví dụ | Nhãn |
|---|---|---|---|
| Văn bản | `d` | `doc_id = "173920"` | `d173920` |
| Văn bản (dạng UUID) | `d` | `doc_id = "b043c150-7924-…"` | `db043c15079241…` (bỏ dấu gạch) |
| Chương | `ch` | `Chương I` | `ch1` (La Mã → Ả Rập) |
| Mục | `mu` | `Mục 2` | `mu2` |
| Điều | `di` | `Điều 6` | `di6` |
| Điều (có chữ) | `di` | `Điều 6a` | `di6a` |
| Khoản | `kh` | `Khoản 3` | `kh3` |
| Điểm | `dm` | `Điểm a` | `dma` |
| Điểm (`đ`) | `dm` | `Điểm đ` | `dmdd` (`đ` → `dd`) |
| Tiểu điểm | — | **bỏ** | không dùng trong schema VN |

**Ví dụ path từ văn bản đã đo:**
```
d173920                              -- nghị định
d173920.ch1                          -- Chương I
d173920.ch1.di1                      -- Điều 1 (con trực tiếp của Chương — đã đo 9 trường hợp)
d173920.ch1.di1.kh1                  -- Khoản 1
d173920.ch1.di1.kh1.dma              -- Điểm a
d173920.ch2.mu1.di6                  -- Điều 6 (dưới một Mục — đã đo 46 trường hợp)
d173920.ch2.mu1.di6.kh3.dmm          -- điểm m khoản 3 Điều 6  ← xuất hiện nguyên văn trong Điều 53
```
Path cuối cùng là phần đền đáp. Văn bản đã đo của Điều 53 nói *"Quy định tại điểm m khoản 3 Điều 6 … có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026"* — một tham chiếu có đích chính xác là `d173920.ch2.mu1.di6.kh3.dmm`. Giải tham chiếu trở thành một lần index lookup.

**Vì sao tiền tố cấp là không thể thương lượng, dựa trên các phép đo:**
1. Chúng xử lý được độ sâu không đồng nhất — `d173920.ch1.di1` và `d173920.ch2.mu1.di6` đều không nhập nhằng.
2. Chúng làm mẫu `lquery` trở nên có ngữ nghĩa: `*.di*` khớp Điều ở mọi độ sâu, điều không thể làm với số thứ tự trần.
3. Chúng loại bỏ xung đột prefix — `di6` và `di60` là hai nhãn phân biệt, trong khi một lược đồ materialised path với `LIKE 'prefix%'` sẽ cần xử lý dấu phân cách bằng tay.
4. Dấu được loại bỏ một cách tất định (`đ` → `dd`, La Mã → Ả Rập), và phép biến đổi có thể assert được.

**Các bảo vệ ingestion bắt buộc, mỗi cái được biện minh bởi dữ liệu bẩn đã quan sát:**
```python
LABEL_RE = re.compile(r'^[A-Za-z0-9_]+$')

def make_label(level: str, ordinal: str) -> str:
    # \xa0 đã đo trong "Điều \xa02"; hai dấu cách đã đo trong chức danh người ký "Phó  Thủ tướng"
    o = unicodedata.normalize('NFKC', ordinal)
    o = re.sub(r'\s+', '', o)
    o = o.replace('đ', 'dd').replace('Đ', 'dd')
    o = unicodedata.normalize('NFD', o)
    o = ''.join(c for c in o if unicodedata.category(c) != 'Mn')
    label = f"{LEVEL_PREFIX[level]}{o.lower()}"
    if not LABEL_RE.match(label):                      # fail ồn ào, không bao giờ ghi một path hỏng
        raise IngestionError(f"illegal ltree label {label!r} from ({level!r}, {ordinal!r})")
    return label
```

## 10.3 Vấn đề ổn định — và vì sao lược đồ nhãn không được dùng số hiển thị

**Đây là quyết định ltree quan trọng nhất, và là cái dễ làm sai nhất.**

Các sửa đổi đánh số lại quy định. Nếu `238/2026/NĐ-CP` chèn một Điều mới giữa 6 và 7, thì dưới một lược đồ theo số hiển thị, mọi path từ `di7` trở đi đều thay đổi, **và mọi tham chiếu đã lưu trong `legal_references.target_path` âm thầm trở nên sai** — trỏ vào một quy định thật nhưng *khác*. Điều đó tệ hơn một con trỏ treo: nó là một trích dẫn pháp lý sai mà vẫn giải được.

**ĐỀ XUẤT — danh tính hai đường:**

1. **`path` (ltree) được dẫn xuất từ *thứ tự node id ổn định của vbpl*, không từ số hiển thị.** Các sự thật đã đo làm điều này khả thi: `id` của node là ổn định và bất biến (`id == key`, cả 1.308 đều duy nhất), và `orderIndex` là một chuỗi pre-order dày đặc. Vậy `path` được dựng từ *cấu trúc* cây, và số hiển thị sống trong `label`/`ordinal` như dữ liệu trình bày.
2. **Số hiển thị được render từ `label`/`ordinal`, không bao giờ từ `path`.** Nếu một sửa đổi đánh số lại Điều 7 → Điều 8, `label` đổi và `path` không đổi. Các tham chiếu đã có vẫn đúng.

Ở chỗ node id của vbpl thực sự thay đổi (một lần crawl lại phát hành lại id — **CHƯA RÕ** liệu điều này có xảy ra, và đáng kiểm chứng bằng cách crawl lại cùng một văn bản), cần một lượt viết lại path. Hãy xử lý nó tường minh:
- giữ `legal_section_aliases(old_path, new_path, changed_at)` để các tham chiếu cũ vẫn giải được;
- cập nhật `path` cho một subtree trong một transaction: `UPDATE … SET path = $new || subpath(path, nlevel($old)) WHERE path <@ $old;`
- giải lại các dòng `legal_references` bị ảnh hưởng và chạy lại monitor mức đầy đủ.

**Trade-off trung thực:** một path theo id ổn định thì khó đọc hơn `d173920.ch2.mu1.di6`. Dễ đọc là một tiện lợi khi debug; trích dẫn đúng là một yêu cầu sản phẩm. Nếu tính dễ đọc đủ quan trọng, hãy giữ path theo số hiển thị như một cột `display_path` *thứ hai*, không có thẩm quyền, và không bao giờ lưu tham chiếu theo nó.

## 10.4 Index

```sql
CREATE INDEX idx_lds_path_gist ON legal_document_sections USING gist (path);
CREATE INDEX idx_lds_path_btree ON legal_document_sections (path);   -- so bằng + sắp xếp
CREATE INDEX idx_lsc_path_gist ON legal_section_chunks USING gist (path);
CREATE INDEX idx_lref_tpath_gist ON legal_references USING gist (target_path);
```
GiST hỗ trợ `@>`, `<@`, `~` (lquery), `?`. Btree hỗ trợ `=` và `ORDER BY path`, điều GiST không làm được — cả hai đều được mong muốn. GiST trên ltree rất gọn; ở 131M dòng dự kiến vài GB, không đáng kể bên cạnh các index vector.

## 10.5 Các query

```sql
-- 1. Toàn bộ subtree của Điều 6, theo thứ tự đọc — query context RAG nóng nhất
SELECT label, rubric, content
FROM legal_document_sections
WHERE path <@ 'd173920.ch2.mu1.di6'
ORDER BY order_index;

-- 1b. Cùng việc đó qua tính chất pre-order dày đặc đã đo — thường nhanh hơn (khoảng btree)
SELECT s2.label, s2.content
FROM legal_document_sections s1
JOIN legal_document_sections s2
  ON s2.doc_id = s1.doc_id
 AND s2.order_index BETWEEN s1.order_index AND s1.order_index + s1.subtree_size - 1
WHERE s1.path = 'd173920.ch2.mu1.di6'
ORDER BY s2.order_index;

-- 2. Chuỗi tổ tiên cho breadcrumb trích dẫn (thay cột `breadcrumb` dạng text tự do)
SELECT label, rubric
FROM legal_document_sections
WHERE path @> 'd173920.ch2.mu1.di6.kh3.dmm'
ORDER BY nlevel(path);
-- → Chương II > Mục 1 > Điều 6 > Khoản 3 > Điểm m

-- 3. Mọi Điều trong corpus, ở bất kỳ độ sâu (chạy được bất chấp độ sâu không đồng nhất)
SELECT doc_id, label, rubric
FROM legal_document_sections
WHERE path ~ '*.di*'::lquery AND level = 'Article';

-- 4. Chỉ con trực tiếp (xuống một cấp)
SELECT label FROM legal_document_sections
WHERE path ~ 'd173920.ch2.mu1.di6.*{1}'::lquery
ORDER BY order_index;

-- 5. Vector search giới hạn trong một subtree — kết hợp ltree và pgvector trong MỘT query.
--    Không biểu đạt được trong kiến trúc tách Postgres+Neo4j.
SELECT c.section_id, c.content, 1 - (c.embedding <=> $1) AS score
FROM legal_section_chunks c
WHERE c.path <@ 'd173920.ch2' AND c.embedding_model_id = 1
ORDER BY c.embedding <=> $1
LIMIT 5;

-- 6. Cái gì tham chiếu tới đúng quy định này? (query "phân tích tác động")
SELECT s.doc_id, s.label, r.raw_text
FROM legal_references r
JOIN legal_document_sections s ON s.id = r.source_section_id
WHERE r.target_path <@ 'd173920.ch2.mu1.di6.kh3';

-- 7. Mức đầy đủ của ingestion: các Khoản mà Điểm chưa từng được phân đoạn
SELECT s.doc_id, s.path, s.label
FROM legal_document_sections s
WHERE s.level = 'Clause'
  AND EXISTS (SELECT 1 FROM legal_document_sections p
              WHERE p.parent_id = s.id AND p.content IS NULL);
```
**Query 5 là luận cứ đơn lẻ mạnh nhất cho việc giữ phân cấp và vector trong cùng một database.** "Tìm theo ngữ nghĩa, nhưng chỉ trong Chương II" là một câu lệnh trong Postgres; trên Postgres + Neo4j đó là hai vòng round trip và một join ở phía ứng dụng, với hai chế độ lỗi và không có transaction chung.

## 10.6 Ưu điểm, hạn chế, phương án thay thế

**Ưu điểm.** Query subtree và tổ tiên trong một phép toán có index; khớp mẫu theo ngữ nghĩa cấp qua `lquery`; một khoá tự nhiên cho đích tham chiếu (119 trích dẫn `điểm..khoản..Điều` đã đo map 1:1 lên path); kết hợp được với pgvector trong một query; là extension đi kèm không có dấu chân vận hành; dung lượng không đáng kể; và nó loại bỏ được `breadcrumb` text tự do không query được ở `schema.sql:49`.

**Hạn chế, nêu một cách trung thực.**
1. **Path bất ổn khi cấu trúc thay đổi** — rủi ro trung tâm, được giảm nhẹ bởi §10.3. Không bị loại bỏ.
2. **Hạn chế bộ chữ của nhãn** — không dấu, không dấu cách, không dấu chấm. Cần tầng chuyển tự ở §10.2, mà bản thân nó cũng là một nguồn bug (dữ liệu bẩn đã đo: `\xa0`, hai dấu cách, `đ`).
3. **Phi chuẩn hoá** — `path` nhân bản thông tin trong `parent_id` và phải được giữ nhất quán. Giảm nhẹ bằng một trigger hoặc bằng cách ghi cả hai trong một transaction ingestion. Giữ `parent_id` làm xương sống toàn vẹn; `path` là bề mặt query, không phải nguồn sự thật.
4. **Tương tác với partition** — ở 1M văn bản, hash partition làm index ltree thành từng-partition, nên `lquery` xuyên văn bản quét mọi partition. Chấp nhận được: các query đó là phân tích, không phải tương tác.
5. **Không có path xuyên văn bản** — ltree mô hình một cây. Quan hệ giữa các văn bản cần bảng cạnh (bảng 8). ltree dứt khoát *không phải* một thứ thay thế graph.

**Phương án thay thế, với lý do mỗi cái thua.**

| Phương án | Phán quyết |
|---|---|
| Chỉ `parent_id` + recursive CTE | Đã có; giữ nó. Query subtree tốn một index lookup mỗi node mỗi cấp, và không có khoá đích tham chiếu tự nhiên. **Không đủ nếu đứng một mình, cần thiết khi đi cùng.** |
| Materialised path dạng `TEXT` + `LIKE 'pfx%'` | Chạy được và btree-index được, nhưng không có toán tử tổ tiên, không có mẫu cấp, và phải xử lý xung đột prefix bằng tay (`di6` vs `di60`). ltree hoàn toàn tốt hơn với cùng dung lượng. |
| Nested set (`lft`/`rgt`) | Đọc nhanh nhất. **Bị từ chối:** mọi lần chèn đánh số lại một phần lớn của bảng, và các sửa đổi thì chèn. Lưu ý `subtree_size` + `order_index` pre-order dày đặc đã đo đã cho lợi ích đọc đó *trong một văn bản*, không kèm chi phí ghi — đó là vì sao bảng 3 có cả hai. |
| Closure table | Tuyệt vời cho query tổ tiên/hậu duệ tuỳ ý, với giá O(độ sâu) dòng mỗi node (~5× số dòng) cho một mẫu mà ltree đã phủ. Chỉ xét lại nếu độ sâu tăng vượt xa 5. |
| Cây JSONB lồng nhau mỗi văn bản | Khớp chính xác hình dạng `muc_luc.json` của crawler và là một lần fetch một dòng để hiển thị. **Bị từ chối:** từng section không thể được khoá ngoại, không thể mang vector, và không thể được trích dẫn — điều đó phá bỏ mục đích. |

**Khuyến nghị cuối:** `parent_id` (toàn vẹn) + `path ltree` (query) + `order_index`/`subtree_size` (khoảng nhanh trong một văn bản). Cả ba, mỗi cái đều xứng chỗ. Bỏ `breadcrumb` và `ptype`.

---

# BƯỚC 11 — Thiết kế Neo4j (SoT quan hệ / GraphRAG)

Neo4j **sở hữu** cạnh quan hệ và cấu trúc traversal — không phải bản sao chỉ-đọc của Postgres. Postgres sở hữu nội dung + vector. **Điểm map duy nhất:** `doc_id`, `section_id`.

**Cấm trong Neo4j:** `content` dài, `embedding`, checkpoint, audit, hợp đồng người dùng.

## 11.1 Nhãn node

| Node | Thuộc tính (nhẹ) | Khóa map | Ghi chú |
|---|---|---|---|
| `:Document` | `doc_id` (unique), `doc_num`, `doc_type` | `doc_id` | Nội dung đầy đủ nằm Postgres |
| `:Section` | `section_id` (unique), `doc_id`, `level`, `label`, `path`, `order_index` | `section_id` | Text/embed nằm Postgres |
| `:Agency` / `:Person` | tuỳ chọn | — | Có thể bỏ nếu chưa cần |

**Từ chối làm node:** `:Case`, `:Regulation`, `:Reference` (dùng relationship).

## 11.2 Relationship (SoT trên Neo4j)

| Rel | Nguồn | Ý nghĩa |
|---|---|---|
| `:PARENT_OF` / `:NEXT` | `muc_luc.json` | Cây + anh em — expand ngữ cảnh |
| `:BELONGS_TO` | suy từ `doc_id` | Section → Document |
| `:AMENDS` `:REPEALS` `:SUPERSEDES` `:SUSPENDS` `:BASED_ON` `:DETAILS` `:GUIDES` `:CORRECTS` `:CONSOLIDATES` `:CITES` `:EXPLAINS` `:ANNOUNCES` `:TRANSLATES` `:ADDS` | **`luoc_do.json` only** | Quan hệ cấp văn bản |
| `:REFERS_TO` | extract từ `van_ban.md` | Section → Section |
| `:RELATED_TO` từ kNN | **Cấm** | Để pgvector |

## 11.3 Constraint

```cypher
CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;
CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (s:Section) REQUIRE s.section_id IS UNIQUE;
CREATE INDEX section_doc IF NOT EXISTS FOR (s:Section) ON (s.doc_id);
```

## 11.4 Cypher GraphRAG (sau hybrid Postgres)

```cypher
MATCH (s:Section) WHERE s.section_id IN $seed_ids
OPTIONAL MATCH (s)-[:PARENT_OF|NEXT*0..2]-(near:Section)
OPTIONAL MATCH (s)-[:REFERS_TO]->(ref:Section)
OPTIONAL MATCH (s)-[:BELONGS_TO]->(d:Document)
OPTIONAL MATCH (d)-[:AMENDS|SUPERSEDES|BASED_ON|CITES|REPEALS*1..2]-(rel:Document)
RETURN DISTINCT near.section_id AS id, ref.section_id AS ref_id, rel.doc_id AS rel_doc
LIMIT 80;
```

App lấy danh sách `section_id`/`doc_id` → `SELECT` content từ Postgres. **Chỉ cần khóa map.**

## 11.5 Map hai store

| Postgres | Neo4j |
|---|---|
| `legal_documents.doc_id` | `:Document.doc_id` |
| `legal_document_sections.id` | `:Section.section_id` |
| *(không có bảng cạnh luoc_do)* | `AMENDS` / `REPEALS` / … |
| *(không SoT REFERS_TO)* | `:REFERS_TO` |
| `legal_section_chunks` | *(không sync)* |

---

# BƯỚC 12 — Nhất quán khi đã tách SoT

## 12.1 Hai SoT, một khóa map — không outbox copy quan hệ

| Dữ liệu | SoT | Nhất quán |
|---|---|---|
| metadata + content + chunk + vector | Postgres | transaction PG |
| cạnh `luoc_do` + `PARENT_OF`/`NEXT` + `REFERS_TO` | **Neo4j** | ghi lúc ingest; `MERGE` idempotent theo id |
| cờ `is_effective` trên chunk | Postgres (dẫn xuất) | job đọc Neo4j → cập nhật cờ |
| hợp đồng / audit / jobs | Postgres | — |

**Không** dùng `graph_outbox` để nhân bản `legal_document_relations` từ PG → Neo4j (mô hình đó làm Neo4j thừa).

## 12.2 Ingest dual-write theo id

```
BEGIN/ghi Postgres (document, sections, chunks)
MERGE Neo4j (Document, Section, PARENT_OF, NEXT, AMENDS…)  // cùng doc_id/section_id
nếu Neo4j fail → đánh dấu job retry; MERGE an toàn khi chạy lại
```

Đối chiếu định kỳ: `section_id` Neo4j ⊆ Postgres và ngược lại (sau ingest thành công).

## 12.3 Hiệu lực (I-10)

1. Đọc cạnh `REPEALS`/`SUPERSEDES`/`SUSPENDS` trên **Neo4j**.
2. Ghi cờ / bảng mỏng `legal_document_effectivity` trên **Postgres** để filter HNSW.
3. Không lưu lại toàn bộ 15 loại quan hệ trong Postgres.

## 12.4 Khi Neo4j chết

Hybrid retrieval Postgres vẫn chạy (thiếu expand). Không suy diễn quan hệ từ PG vì PG **không** giữ SoT cạnh. Alert + retry ingest graph.

---

# BƯỚC 13 — Ước lượng khả năng mở rộng

## 13.1 Cơ sở (đo được, mẫu đơn)

| Đại lượng | Giá trị đã đo |
|---|---|
| Số section mỗi văn bản | 1.308 |
| Section có nội dung (Điều + Khoản) | 387 (29,6%) |
| Văn bản dạng text | 277.961 ký tự |
| Độ dài khoản trung bình | 779 ký tự |
| Độ dài khoản p90 | 1.749 ký tự |
| Tham chiếu trong văn bản | ~731 |
| Cạnh quan hệ cấp văn bản | ~11 |
| Artifact crawl thô | ~845 KB |

**Cảnh báo mẫu đơn, nói thẳng.** `168/2024/NĐ-CP` là một văn bản **lớn** (55 Điều, 909 Điểm). Một Thông tư hay Quyết định điển hình thì nhỏ hơn nhiều. Vì vậy tôi mô hình hai profile:

- **Profile A (hỗn hợp điển hình):** ~150 chunk/văn bản — giả định phần lớn văn bản nhỏ hơn mẫu nhiều.
- **Profile B (đã đo):** ~500 chunk/văn bản — tốc độ của chính mẫu, một giới hạn trên.

Cách suy ra số chunk cho Profile B: 332 khoản × ~1,4 chunk (trung bình 779 ký tự ở ~220 token với 40 overlap) ≈ 465, cộng 55 chunk tóm tắt Điều ≈ **520**, làm tròn thành 500.

## 13.2 Dung lượng mỗi dòng

| Hạng mục | Byte | Ghi chú |
|---|---|---|
| `vector(768)` float32 | 3.076 | **phải là `STORAGE PLAIN`** — vượt ngưỡng TOAST |
| `halfvec(768)` | 1.540 | pgvector ≥ 0.7 |
| `bit(768)` | 100 | lượng tử hoá nhị phân, chỉ dùng cho recall tầng một |
| Nội dung chunk (~700 ký tự tiếng Việt) | ~1.000 | UTF-8, ~1,4 B/ký tự |
| Dòng + id + overhead | ~60 | |
| **Dòng heap của chunk, float32** | **~4.140** | |
| **Dòng heap của chunk, halfvec** | **~2.600** | |
| HNSW mỗi phần tử, float32 (m=16) | ~3.500 | index lưu vector cộng danh sách láng giềng |
| HNSW mỗi phần tử, halfvec | ~1.800 | |
| Dòng section | ~400 | phần lớn là Điểm ngắn |
| Dòng tham chiếu | ~150 | |
| Dòng quan hệ | ~80 | |

## 13.3 Các tình huống dung lượng

### 100k văn bản

| | Profile A (150 chunk/vb) | Profile B (500 chunk/vb) |
|---|---|---|
| Chunk | 15M | 50M |
| Heap chunk (f32) | 62 GB | 207 GB |
| HNSW (f32) | 53 GB | 175 GB |
| Section (131M dòng) | 52 GB | 52 GB |
| Tham chiếu (73M dòng) | 11 GB | 11 GB |
| Quan hệ (1,1M) | 0,1 GB | 0,1 GB |
| Bảng khác | ~10 GB | ~10 GB |
| **Tổng (f32)** | **~188 GB** | **~455 GB** |
| **Tổng (halfvec)** | **~140 GB** | **~300 GB** |
| RAM cho index thường trú | 53 GB → **node 128 GB** | 175 GB → **node 256 GB**, hoặc halfvec → 90 GB |
| Truy hồi p95 (index thường trú) | 5–15 ms | 10–25 ms |

**Phán quyết: thoải mái trên một node lớn**, đặc biệt với `halfvec`. Đây là mục tiêu thực tế 12–18 tháng và nó không làm căng kiến trúc.

### 1M văn bản

| | Profile A | Profile B |
|---|---|---|
| Chunk | 150M | 500M |
| Heap chunk (halfvec) | 390 GB | 1,3 TB |
| HNSW (halfvec) | 270 GB | 900 GB |
| Section (1,3 tỉ dòng) | 520 GB | 520 GB |
| Tham chiếu (730M dòng) | 110 GB | 110 GB |
| **Tổng** | **~1,3 TB** | **~2,9 TB** |

**Phán quyết: HNSW một node không còn khả thi.** Các thay đổi bắt buộc: hash-partition `legal_section_chunks` và `legal_document_sections` theo `doc_id` (32–64 partition); `halfvec` bắt buộc; thêm một tầng đầu `bit(768)` (150M × 100 B = **15 GB**, vừa RAM dễ dàng) với rerank chính xác trên ~1.000 ứng viên; chuyển truy hồi sang read replica. Xét việc giảm chiều xuống 384 (giảm một nửa nữa) sau khi đo chi phí recall.

### 10M chunk (mục tiêu tường minh trong đề bài)

| | float32 | halfvec |
|---|---|---|
| Heap chunk | 41 GB | 26 GB |
| HNSW | 35 GB | 18 GB |
| **Tổng vector** | **76 GB** | **44 GB** |
| Node | 128 GB RAM | 64 GB RAM |
| Thời gian build (`CREATE INDEX CONCURRENTLY`, 8 worker, 4 GB `maintenance_work_mem`) | ~2–6 h | ~1–3 h |
| Truy hồi p95 (`ef_search=40`) | 5–15 ms | 5–15 ms |

**Phán quyết: hỗ trợ đầy đủ, một node, không cần kỹ thuật đặc biệt nào.** Tương ứng ~65k văn bản ở Profile A hoặc ~20k ở Profile B.

### 100M chunk (mục tiêu vươn xa trong đề bài)

| Chiến lược | Heap | Index | RAM cần | Phán quyết |
|---|---|---|---|---|
| `vector(768)` + HNSW | 414 GB | 350 GB | 350 GB+ | **Không khả thi** trên hardware phổ thông |
| `halfvec(768)` + HNSW | 260 GB | 180 GB | 180 GB | Khả thi trên một node rất lớn; đắt |
| `halfvec(768)`, hash-partition ×64 | 260 GB | 180 GB | ~3 GB/partition | **Khả thi** — planner prune về một partition |
| Tầng đầu `bit(768)` + rerank chính xác | +10 GB | 10 GB | 10 GB | **Được khuyến nghị** — index nhị phân thường trú, rerank top-1000 chính xác |
| 384 chiều + `halfvec` + partition | 130 GB | 100 GB | ~1,5 GB/partition | Rẻ nhất; cần re-embed và một lần kiểm recall có đo lường |

**Phán quyết ở 100M chunk: chỉ khả thi với lượng tử hoá cộng partition.** Cấu hình được khuyến nghị là recall nhị phân `bit(768)` (10 GB, thường trú hoàn toàn) → 1.000 ứng viên → rerank `halfvec` chính xác → 50 → cross-encoder → 5. Kỳ vọng p95 30–80 ms. **Đây là điểm mà một vector store chuyên dụng xứng đáng được đánh giá lại một cách thực sự** — không phải vì Postgres không làm được, mà vì công sức tuning bắt đầu ngang với chi phí vận hành một hệ thống thứ hai. Đó là biên trung thực của kiến trúc này, và 100M chunk tương ứng ~650k văn bản ở Profile A, tức là một corpus pháp luật quốc gia rất lớn.

## 13.4 Sizing Neo4j, để ghi lại

Nếu được áp dụng ở 100k văn bản: 1,1M relationship `:Document` (không đáng kể, < 1 GB) cộng 73M relationship `:REFERENCES`. Overhead của Neo4j vào khoảng 34 B/relationship cộng property store và index → **~15–30 GB**. Các bảng Postgres tương đương: 0,2 GB + 19 GB = **~19 GB**. Postgres tương đương hoặc tốt hơn về dung lượng, và nó không cần máy thứ hai, backup thứ hai, hay pipeline đồng bộ. **Phép đo này là một phần của việc từ chối ở BƯỚC 6.4.**

## 13.5 Budget độ trễ kỳ vọng

| Thành phần | Độ trễ | Ghi chú |
|---|---|---|
| Auth (hiện tại: introspection từ xa) | **50–200 ms** | I-11 — thường là thành phần lớn nhất ngoài LLM |
| Auth (JWT tự host, verify local) | < 1 ms | sau khi bỏ Supabase / sửa I-11 |
| Kết nối DB (hiện tại: không pool) | **5–50 ms × 3** | I-12 |
| Query DB (có pool) | < 1 ms | |
| Embed query, CPU | **15–40 ms** | *chiếm ưu thế* so với vector search ở các dung lượng này |
| Embed query, GPU theo batch | 3–8 ms | |
| Tìm HNSW, 10M, thường trú | 5–15 ms | |
| Tìm HNSW, cache lạnh | **50–500 ms** | vì sao việc index thường trú là một yêu cầu sizing |
| Hybrid (vector + FTS + RRF) | 20–50 ms | |
| Rerank cross-encoder, 50 tài liệu, CPU | 50–150 ms | |
| **Tổng phụ truy hồi** | **~100–250 ms** | |
| Một lệnh gọi Gemini | **1–5 s** | |
| Phân tích đầy đủ, 20 điều khoản, 4 song song | **30–60 s** | khớp `docs/user-flow.md:123` |

**SUY LUẬN — kết luận về mở rộng quan trọng nhất.** Độ trễ LLM lớn hơn mọi thứ khác 100–1000×. Vector search *không* phải điểm nghẽn ở bất kỳ mức dung lượng nào được thảo luận ở đây, và tối ưu nó cho độ trễ là công sức đặt sai chỗ; hãy tối ưu nó cho **recall**, vì recall quyết định chất lượng câu trả lời trong khi độ trễ của nó là vô hình bên cạnh LLM. Ngược lại, I-11 và I-12 cộng lại thêm 65–350 ms vào *mọi* request kể cả những cái nhẹ — điều đó làm chúng thành các cách sửa độ trễ có đòn bẩy cao nhất trong hệ thống, và cả hai đều Dễ/Trung bình.

## 13.6 Các điểm nghẽn, xếp hạng

| Hạng | Điểm nghẽn | Dung lượng mà nó bắt đầu cắn | Cách sửa |
|---|---|---|---|
| 1 | Lệnh gọi LLM: 30–60 s inline, giữ một connection HTTP | **ngay bây giờ** | I-24 — queue + async |
| 2 | Filtered recall `fetch_k=20` của FAISS | **ngay bây giờ**, tệ dần đơn điệu | I-1 — pgvector |
| 3 | Trạng thái vector một process | **ngay bây giờ** — chặn mọi việc scale ngang | I-4 — pgvector |
| 4 | Ghi lại toàn bộ index mỗi lần upload | ~100k chunk | I-5 |
| 5 | 3 connection DB không pool mỗi request | ~50 người dùng đồng thời | I-12 |
| 6 | Vòng auth từ xa mỗi request | ~100 RPS | I-11 |
| 7 | Dựng lại văn bản bằng quét toàn bộ | ~500k chunk | I-6 |
| 8 | Embedding chạy trên process API | ~20 upload đồng thời | service embedding riêng |
| 9 | HNSW vượt RAM | ~50M chunk (f32) | halfvec, partition |
| 10 | Kích thước bảng section | ~500M dòng | hash partition |
| 11 | Tăng trưởng blob checkpoint | ~100k cuộc hội thoại | I-14 + retention |
| 12 | Dung lượng `search_logs` | ~1 tháng ở 100 QPS | partition theo tháng + rollup |

**Điểm nghẽn 1–3 đang bó buộc ở dung lượng hôm nay**, không phải ở một mức tương lai nào. Chúng là lý do Pha 1 của bản rà soát này có nội dung như vậy.

## 13.7 Mở rộng ngang so với dọc

| Thành phần | Chiến lược | Trần |
|---|---|---|
| Tầng API | **Ngang** — dễ dàng, khi đã không state (I-4) | thực tế không có |
| Worker | **Ngang** — autoscale theo độ sâu queue | rate limit của provider LLM |
| Service embedding | **Ngang**, không state; GPU cho throughput batch | chi phí |
| Ghi Postgres | **Chỉ dọc** — một primary | ~10–20k write/s; vượt xa nhu cầu |
| Đọc Postgres | **Ngang** — read replica cho truy hồi và `GET` | replica lag (giảm nhẹ bằng ghim read-your-writes) |
| Vector index | **Dọc** (RAM) rồi **partition** | xem §13.3 |
| Object storage | MinIO trong Compose (S3 API); scale volume / cluster sau | — |

**Quan sát quan trọng.** Sau khi migration sang pgvector, **mọi thứ có state đều là Postgres và mọi thứ không state đều scale ngang.** Đó là một mô hình vận hành đơn giản, được hiểu rõ, với một ràng buộc scale duy nhất phải lý giải — so với hôm nay, khi *bản thân process ứng dụng* có state và do đó không scale được. Giá trị kiến trúc của việc migration sang pgvector không phải chủ yếu là hiệu năng; nó là việc biến một hệ thống không scale được thành một hệ thống scale được theo cách thông thường.

---

# BƯỚC 14 — Lộ trình refactor

Mỗi task liệt kê **Lý do · Tác động · Công sức · Rủi ro · Phụ thuộc · Ưu tiên**. Công sức tính theo ngày-người cho một engineer có kinh nghiệm. Các pha được sắp theo phụ thuộc; task trong một pha được sắp theo giá trị.

## Pha 0 — Xác lập sự thật nền (2 ngày, chặn mọi thứ)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P0-1** | `pg_dump --schema-only` database đang deploy; đối chiếu với `database.py`, `schema.sql`, `loader.py`; công bố schema hiện tại có thẩm quyền | Ba nguồn không khớp (I-2, I-3) và `PROGRESS_REPORT.md:108` nêu bốn bảng khác không giải thích được. Mọi task sau đều phụ thuộc vào việc biết baseline thật | Mở khoá mọi việc DB; giải quyết điều CHƯA RÕ lớn nhất trong bản rà soát này | 0,5 | Không | quyền truy cập DB | **Nghiêm trọng** |
| **P0-2** | Đứng Postgres Docker (`pgvector/pgvector:pg16`); `CREATE EXTENSION` vector/ltree/unaccent/pg_trgm; assert version (≥0.7 halfvec, ≥0.8 iterative scan) | BƯỚC 9–10 phụ thuộc extension; với Docker thì **pin được**, không còn phụ thuộc SaaS | Chốt chiến lược pgvector | 0,5 | Không | P0-1 / compose skeleton | **Nghiêm trọng** |
| **P0-3** | Commit `schema.sql`, `docs/*`, và skeleton `docker-compose.yml` (postgres/neo4j/minio) vào git | Artifact thiết kế + hạ tầng Docker chưa track thì không review/version được | Làm thiết kế và stack review được | 0,5 | Không | Không | **Cao** |
| **P0-4** | Crawl 3–5 văn bản *khác loại* (Luật, Thông tư, Quyết định) **kể cả một cái có Phụ lục** | Mọi kết luận cấu trúc dựa trên một mẫu. Tệp đính kèm hoàn toàn không được biểu diễn (BƯỚC 5) | Xác nhận hoặc sửa thiết kế BƯỚC 8/10 trước khi xây | 1 | Phát hiện có thể làm thay đổi schema — mà đó chính là lý do làm việc này trước | quyền truy cập crawler | **Nghiêm trọng** |
| **P0-5** | Kiểm chứng liệu `dangvantuan/vietnamese-embedding` có cần tách từ; đo truy hồi có và không có | Đã gắn cờ CHƯA RÕ ở BƯỚC 8 bảng 5; có thể là một mức tăng chất lượng lớn và miễn phí | Có thể cải thiện recall đáng kể với chi phí gần bằng 0 | 0,5 | Không | Không | **Cao** |

## Pha 1 — Sửa các vấn đề Nghiêm trọng (3–4 tuần)

Sắp xếp để công việc mức độ nghiêm trọng cao nhất, ít phụ thuộc nhất, hạ cánh trước.

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P1-1** | Test hồi quy chứng minh I-1: 500 chunk trên 50 hợp đồng; khẳng định `retrieve_contract` trả về chunk của hợp đồng đích | Không thể sửa cái không đo được; test này **fail hôm nay** và là bằng chứng của khiếm khuyết | Chốt cách sửa; ngăn hồi quy | 1 | Không | Không | **Nghiêm trọng** |
| **P1-2** | Giảm nhẹ tạm thời cho I-1: `fetch_k = max(200, k*40)` | Thay đổi 1 dòng mua được dư địa trong lúc pgvector hạ cánh | Khôi phục truy hồi dùng được ngay lập tức | 0,25 | Tìm chậm hơn; không đáng kể so với độ trễ LLM | P1-1 | **Nghiêm trọng** |
| **P1-3** | Giới hạn kích thước upload + ghi theo stream (I-7) | OOM ở mức không xác thực từ một người dùng đã xác thực | Loại bỏ một DoS khai thác dễ dàng | 0,5 | Không | Không | **Nghiêm trọng** |
| **P1-4** | Response lỗi chung chung + correlation id; loại bỏ mọi rò rỉ `str(e)` (I-16) | SQL, đường dẫn, URL nội bộ hiện đang được trả về cho client | Đóng tiết lộ thông tin; cải thiện khả năng hỗ trợ | 1,5 | Client dựa vào text lỗi — không biết có ai | Không | **Nghiêm trọng** |
| **P1-5** | Allowlist CORS; bỏ wildcard+credentials (I-17) | Tổ hợp không hợp lệ và không an toàn | Đóng lỗ cross-origin | 0,25 | Phải liệt kê các origin thật | Không | **Nghiêm trọng** |
| **P1-6** | **Bỏ Supabase Auth**: JWT tự host + verify local; frontend bỏ `supabase-js` (I-11) | Latency + SPOF + vendor lock-in trên **mọi** request | Auth độc lập trên Docker stack | 3 | Migration `user_id` nếu đã có user production | Không | **Nghiêm trọng** |
| **P1-7** | Pool connection async; một driver (`psycopg` 3); bỏ `psycopg2-binary` (I-12, I-31) | 3 connection không pool mỗi request, chặn event loop | Thắng lớn về độ trễ và throughput; loại một driver trùng | 3 | Viết lại mọi truy cập DB; cần lưới test của P1-13 | P1-13 | **Nghiêm trọng** |
| **P1-8** | Alembic; revision `0001` = thực tế đã đối chiếu; xoá DDL khỏi `init_db()` (I-9) | Không có version schema; `CREATE INDEX` lock lúc boot | Làm mọi task schema sau này an toàn | 2 | Baseline phải khớp chính xác production nếu không migration đầu tiên sẽ fail | P0-1 | **Nghiêm trọng** |
| **P1-9** | Lưu văn bản đã parse vào `contract_documents`; ngừng dựng lại từ chunk (I-6) | Bộ nhớ O(corpus) mỗi lần analyse, và việc dựng lại là mất mát và sai thứ tự | Loại một bom bộ nhớ; **cải thiện tính đúng đắn của extraction** | 1,5 | Backfill cho các hợp đồng đã có | P1-8 | **Nghiêm trọng** |
| **P1-10** | Hiệu lực dẫn xuất: đọc `REPEALS`/`SUPERSEDES` trên **Neo4j** → ghi cờ/`legal_document_effectivity` trên **Postgres**; lọc retrieval theo cờ (I-10) | `thuoc_tinh` vs `luoc_do` trái ngược; không nhân bản cạnh vào PG | Sửa bug hiệu lực | 4 | Quy tắc pháp lý cần rà soát | P1-8, Neo4j ingest | **Nghiêm trọng** |
| **P1-11** | Migration pgvector: `contract_chunks` + `legal_section_chunks`; xoá `faiss_store.py` (I-1, I-4, I-5, I-8, I-15) | Một thay đổi đóng năm vấn đề Nghiêm trọng và mở khoá việc scale ngang | Thay đổi bản lề của toàn bộ lộ trình | 8 | Chất lượng truy hồi phải được kiểm chứng — chạy shadow mode và so sánh trước khi chuyển | P0-2, P1-1, P1-7, P1-8 | **Nghiêm trọng** |
| **P1-12** | Chia chunk nhận biết token; log việc cắt bớt; đọc giới hạn từ `embedding_models` (I-13, I-19) | Đã đo: khoản trung bình ở ngay giới hạn, p90 vượt 2×, tối đa 9× — nội dung đang bị âm thầm loại bỏ | Mức tăng chất lượng truy hồi trực tiếp, đo được | 2 | Cần re-embed toàn bộ | P1-11 | **Nghiêm trọng** |
| **P1-13** | Hạ tầng test: marker, embedder giả, store double trong RAM, Postgres tạm, CI (I-27) | Mọi task Pha 1 rủi ro hơn nếu không có nó; bộ test hiện tại cần một database thật | Cho phép làm mọi thứ khác một cách an toàn | 3 | Không | Không | **Nghiêm trọng** |
| **P1-14** | Timeout, backoff, và retry có kiểu cho Gemini; trạng thái từng điều khoản trong kết quả (I-29) | Một lỗi 429 hiện đang **âm thầm** làm mất điều khoản khỏi một báo cáo pháp lý | Loại bỏ kết quả thiếu một cách âm thầm | 2 | Không | Không | **Cao** |
| **P1-15** | Sửa index: composite `(user_id, created_at DESC)`; drop `idx_contracts_id` dư thừa (I-23) | Sort ở mọi lần load danh sách; khuếch đại ghi vô ích | Màn hình chính nhanh hơn | 0,25 | Không | P1-8 | **Cao** |

**Tiêu chí hoàn thành Pha 1:** P1-1 pass; không vấn đề Nghiêm trọng nào còn mở; bộ test hermetic và xanh trong CI; tỉ lệ hit truy hồi và tỉ lệ từ chối đã lên dashboard.

## Pha 2 — Dọn dẹp kiến trúc (3–4 tuần)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P2-1** | Tầng repository; loại mọi SQL khỏi service (I-22) | Business logic bị hợp nhất với SQL; giải nén dòng theo vị trí là mong manh một cách âm thầm | Khả năng test và bảo trì | 3 | Rộng nhưng cơ học | P1-7, P1-13 | **Cao** |
| **P2-2** | Job queue + worker; tách `POST /analyze` thành endpoint đọc/chạy (I-24, I-28) | Request inline 30–60 s sẽ đụng timeout của proxy; không tiến trình, không huỷ, không retry | Loại bỏ điểm nghẽn scale số 1 | 6 | Chế độ lỗi mới; cần kỷ luật idempotency | P2-1 | **Cao** |
| **P2-3** | Config `pydantic-settings` với biên và field bắt buộc (I-33) | Cấu hình sai hiện nổi lên muộn (`SIMILARITY_THRESHOLD=5.0` âm thầm vô hiệu hoá truy hồi) | Config fail-fast, test được | 1 | Không | Không | **Cao** |
| **P2-4** | DI qua protocol + `app.state`; loại các singleton cấp module (I-34) | Không có đường ráp test; tuổi thọ singleton chặn việc scale | Khả năng test; mở khoá worker gọn gàng | 3 | Refactor rộng | P2-1 | **Cao** |
| **P2-5** | API có kiểu: `AnalyzeResponse`, `schema_version`, validate JSONB đã cache (I-30) | `Any` ở biên quan trọng nhất; hai đường response không bao giờ validate giống nhau | Ngăn lệch client/server | 1 | Entry cache cũ có thể fail validation — hãy tái tạo chúng | P1-8 | **Cao** |
| **P2-6** | Registry extractor + profile theo từng loại (I-21) | Module god 485 dòng hard-code cho hợp đồng lao động chặn lộ trình hiển nhiên | Khả năng mở rộng; khả năng test | 5 | Hành vi thay đổi — cần golden test trước | P1-13 | **Cao** |
| **P2-7** | Hợp nhất danh tính điều khoản; `ClauseRef` có cấu trúc (I-36) | Hai regex khác nhau tạo hai không gian trích dẫn mà `qa_agent.py:136` so sánh xuyên qua | Trích dẫn đúng | 2 | Thay đổi output trích dẫn | P2-6 | **Cao** |
| **P2-8** | MinIO (Docker) cho upload; soft delete; luồng xoá (I-41) | Hợp đồng trên đĩa local tạm thời, không mã hoá, không xoá được; bỏ Supabase Storage | Tuân thủ; stack Docker thống nhất | 3 | Migrate file đã có | P2-1, P6-1 | **Cao** |
| **P2-9** | `lifespan` thay `on_event`; chuyển `init_db` ra ngoài (I-32) | Đã deprecated; startup không test được | Gọn gàng; startup test được | 0,5 | Không | P1-8 | **Trung bình** |
| **P2-10** | Giải quyết `provider`: làm cho nó thật hoặc xoá nó (I-20) | Trừu tượng no-op 5 tầng, còn chiếm cả state được checkpoint | API trung thực; ít state hơn | 1 | Đổi hình dạng request/response | Không | **Trung bình** |
| **P2-11** | Xoá code chết: `text_normalizer` (hồi sinh `normalize_doc_number` cho `doc_num_norm`), `flag_risks`, `ON CONFLICT` không tới được, `DataError` catch không tới được | Code chết hàm ý một hành vi được bảo trì mà thực ra không tồn tại | Rõ ràng | 0,5 | Không | P2-6 | **Trung bình** |
| **P2-12** | Logging có cấu trúc, mức đúng, lan truyền correlation, metric (I-35) | ERROR đang dùng cho các thành công, nên không thể alert trên lỗi thật | Khả năng vận hành | 2 | Không | P1-4 | **Cao** |
| **P2-13** | Keyset pagination cho `GET /contracts` (I-25) | Response không giới hạn | Độ trễ dự đoán được | 1 | Thay đổi frontend | P2-1 | **Trung bình** |
| **P2-14** | Kiểm file theo magic byte; từ chối `.doc` legacy tường minh (I-18) | Kiểm chỉ theo đuôi file đưa byte chưa kiểm chứng vào hai parser lớn | Bảo mật; lỗi tốt hơn | 1 | Từ chối các file trước đây chạy nửa vời | Không | **Cao** |
| **P2-15** | Lỗi upload có kiểu; frontend rẽ nhánh theo status (I-26) | HTTP 200 khi parse fail, rồi một 404 gây nhầm lẫn | UX; khả năng hỗ trợ | 1 | Thay đổi frontend | P2-2 | **Cao** |
| **P2-16** | Tái cấu trúc thư mục: `infrastructure/llm/`, `document/extraction/`, `repositories/`, `workers/`; xoá `helpers/` | `agents/` trộn agent với hạ tầng và xử lý văn bản thuần | Rõ ràng về biên module | 1 | Xáo trộn import | P2-4, P2-6 | **Trung bình** |

## Pha 3 — Thiết kế lại database (4–6 tuần)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P3-1** | Toàn bộ schema BƯỚC 8 qua Alembic, expand/contract | Schema hiện tại không thể biểu diễn dữ liệu đã đo (section nhiều chunk, phân cấp không đồng nhất, quan hệ, tham chiếu) | Nền tảng cho mọi tính năng chất lượng | 5 | Lớn; hãy hạ cánh từng phần | P1-8, P0-4 | **Cao** |
| **P3-2** | Path ltree + GiST; bỏ `breadcrumb` và `ptype` (BƯỚC 10) | Đích tham chiếu là path (đã đo 119 `điểm..khoản..Điều`); `breadcrumb` không query được | Query subtree/tổ tiên nhanh; một khoá đích tham chiếu thật | 3 | Bug chuyển tự nhãn — hãy assert bộ chữ | P3-1 | **Cao** |
| **P3-3** | Pipeline ingestion 4 file (§7.4): `thuoc_tinh`→PG, `muc_luc`+cắt `van_ban`, `luoc_do`→relations+outbox; phân đoạn Điểm + join tên điều | Đã đo: chỉ 387/1308 node có anchor; tên điều chỉ ở H2 thân. Không có chúng thì content/title trống | Corpus thật; bỏ `loader.py` FAISS | 8 | Parser correctness — dùng `content_source` | P3-1, P3-2 | **Cao** |
| **P3-4** | Extract dẫn chiếu → Neo4j `:REFERS_TO` (map `section_id`) | 731 tham chiếu/văn bản; GraphRAG xuyên điều khoản | Mở khoá KB | 5 | Nhập nhằng nội bộ/bên ngoài | P3-2, P3-3, P3-12 | **Cao** |
| **P3-5** | Crawl frontier + khám phá + crawl lại theo lịch | Quan hệ đi vào chỉ mang `doc_id`+`title`; corpus không lớn lên được nếu không có nó | Tăng trưởng corpus | 3 | Sự lịch sự/rate limit với vbpl.vn | P3-3 | **Cao** |
| **P3-6** | Snapshot lên object storage; phát hiện thay đổi bằng content hash | Cho phép parse lại mà không crawl lại; làm việc crawl lại hằng tuần trở nên rẻ | Khả năng chống chịu vận hành | 2 | Chi phí lưu trữ | P3-3 | **Trung bình** |
| **P3-7** | Constraint và trigger: mọi `CHECK`, `updated_at`, tính duy nhất | Hiện không có một `CHECK` nào; mọi bất biến nằm trong code ứng dụng | Toàn vẹn dữ liệu trên nhiều writer | 2 | Dữ liệu hiện có có thể vi phạm — hãy audit trước | P3-1 | **Cao** |
| **P3-8** | `analysis_runs` / `contract_analyses` / `contract_risks`; loại bỏ các blob JSONB | JSONB không query được và không mang xuất xứ; hiện không phân tích nào tái lập được | Kết quả query được; dấu vết audit | 3 | Migrate JSONB đã có | P3-1, P2-2 | **Cao** |
| **P3-9** | Phóng chiếu `legal_penalties` + extractor + UI rà soát | Đã đo 186 khoảng tiền phạt, 472 số tiền. Biến loại câu trả lời yếu nhất của sản phẩm thành mạnh nhất, **không có LLM trên đường trả lời** | **ROI cao nhất trong lộ trình** | 5 | Độ chính xác trích xuất — chặn bằng `verified_by` | P3-3 | **Cao** |
| **P3-10** | Cấu hình tìm kiếm text `vi` với `unaccent`; thay `'simple'` | `'simple'` không thể khớp tiếng Việt không dấu; một nửa hybrid search hỏng trước cả khi được xây | Điều kiện tiên quyết cho hybrid search | 1 | Tính immutable của `unaccent` cho expression index | P3-1 | **Cao** |
| **P3-11** | Partition ở những chỗ BƯỚC 8 chỉ định (`search_logs` theo tháng từ ngày đầu) | Retention bằng `DROP PARTITION`, không phải `DELETE` | Telemetry bền vững | 2 | Không | P3-1 | **Trung bình** |
| **P3-12** | Neo4j SoT quan hệ: ingest `luoc_do`+`PARENT_OF`/`NEXT`/`REFERS_TO` + expand GraphRAG bằng `section_id` | Tách store đúng hướng; không outbox copy từ PG | GraphRAG xuyên luật | 5 | Dual-write theo id + reconcile | P3-3, BƯỚC 11–12 | **Cao** |

## Pha 4 — Tối ưu hiệu năng (2–3 tuần)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P4-1** | Tách service embedding; batching; GPU tuỳ chọn | Embedding trên process API chặn loop; embed query mất 15–40 ms, thành phần truy hồi chiếm ưu thế | Throughput; độ trễ | 3 | Một service mới phải vận hành | P2-2 | **Cao** |
| **P4-2** | Cache embedding query theo hash của text đã chuẩn hoá | Cùng một đoạn điều khoản được embed lại mỗi lần chạy; hiện không có cache | Chi phí và độ trễ | 1 | Invalidate khi đổi model | P4-1 | **Trung bình** |
| **P4-3** | Tuning HNSW; probe recall hằng ngày so với tìm kiếm chính xác | Sự suy thoái xấp xỉ nếu không thì **vô hình** — đúng chế độ lỗi của I-1 | Bảo vệ chất lượng truy hồi lâu dài | 2 | Không | P1-11 | **Cao** |
| **P4-4** | Migration `halfvec` khi vượt 10M chunk | Giảm một nửa chi phí lưu trữ chủ đạo | Chi phí; dư địa RAM | 2 | Kiểm chứng mất recall < 1% | P0-2, P1-11 | **Trung bình** |
| **P4-5** | Read replica cho truy hồi; ghim read-your-writes | Scale đọc theo chiều ngang | Throughput | 2 | UX do replica lag | P1-7 | **Trung bình** |
| **P4-6** | Làm gọn checkpoint (bỏ context khỏi state) + retention (I-14) | ~11 KB văn bản tái tạo được bị checkpoint mỗi lượt; ~20 GB ở 100k×20 | Lưu trữ; thời gian backup; độ trễ đọc lịch sử | 2 | Migrate checkpoint đã có | P2-2 | **Cao** |
| **P4-7** | Rate limit, quota theo user, trần concurrency LLM toàn cục (I-38) | `force=true` trong một vòng lặp là một tấn công denial-of-wallet | Kiểm soát chi phí; công bằng | 2 | Điều chỉnh các giới hạn | P2-2 | **Cao** |
| **P4-8** | Response chat theo stream (SSE) | 1–5 s im lặng mỗi câu trả lời; hiện không có gì stream | Độ trễ cảm nhận | 2 | Thay đổi frontend | P2-2 | **Trung bình** |

## Pha 5 — Chất lượng tìm kiếm (3–4 tuần)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P5-1** | Tập benchmark có nhãn (truy hồi + phán quyết rủi ro), được luật sư rà soát | `PROGRESS_REPORT.md:88` nêu đây là ưu tiên số một. **Không gì sau điểm này đo được nếu không có nó** | Biến việc cải thiện chất lượng từ ý kiến thành đo lường | 5 | Cần chuyên môn nghiệp vụ | Không | **Nghiêm trọng** |
| **P5-2** | Hybrid search với RRF (BƯỚC 9.6) | Đã đo 472 số tiền và 193 trích dẫn — loại nội dung mà vector search xử lý tệ nhất | Mức tăng recall lớn | 3 | Không | P3-10, P5-1 | **Cao** |
| **P5-3** | Rerank cross-encoder | Thường là mức tăng chất lượng RAG đơn lẻ lớn nhất; hiện không có | Độ chính xác | 3 | +50–150 ms | P5-1, P5-2 | **Cao** |
| **P5-4** | Đi tắt theo trích dẫn cho các tham chiếu tường minh | `"khoản 3 Điều 6"` nên là một lần tra path, không phải tìm kiếm ngữ nghĩa — chính xác hoàn hảo, không LLM | Độ chính xác trên một hình dạng query đã đo là phổ biến | 2 | Không | P3-2, P3-4 | **Cao** |
| **P5-5** | `context_prefix` trên embedding; mở rộng ngữ cảnh tổ tiên/anh em | Một Điểm trơ trọi gần như vô nghĩa; `path` làm prefix miễn phí | Recall và chất lượng câu trả lời | 2 | Cần re-embed | P3-2, P1-12 | **Cao** |
| **P5-6** | Hiệu chuẩn `SIMILARITY_THRESHOLD`; thay điểm cắt tuyệt đối bằng điểm cắt sau rerank | 0.6 quyết định toàn bộ phán quyết được tạo hay bị từ chối, mà không có bằng chứng nào rằng nó đã được hiệu chuẩn | Ít từ chối sai và phán quyết sai hơn | 1 | Thay đổi tỉ lệ từ chối | P5-1, P5-3 | **Cao** |
| **P5-7** | Filter chính sách theo thẩm quyền + đa dạng (BƯỚC 9.7 tầng 3) | Một `Luật` nên xếp trên một `Nghị định`; một nghị định 332 khoản không nên chiếm cả 5 slot | Chất lượng câu trả lời | 2 | Không | P5-3 | **Trung bình** |
| **P5-8** | Vòng feedback: `user_feedback` + `search_logs` → tập dữ liệu lỗi | Biến 👎 thành các lỗi truy hồi có nhãn được join với đúng lượt truy hồi | Cải tiến liên tục | 2 | Không | P3-11, P5-1 | **Trung bình** |
| **P5-9** | Agent tính toán cho tiền phạt, dựa trên `legal_penalties` | `PROGRESS_REPORT.md:87` ghi chatbot tránh việc tính toán. Với bảng 12 các con số là **dữ liệu**, không phải output LLM | Cho phép loại câu trả lời được mong muốn nhất, một cách đáng tin cậy | 3 | Tính đúng đắn — phải trích dẫn dòng nguồn | P3-9 | **Cao** |

## Pha 6 — Bảo trì dài hạn (liên tục)

| ID | Task | Lý do | Tác động | Công sức | Rủi ro | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|---|
| **P6-1** | `Dockerfile` + `docker-compose.yml` (postgres/pgvector, neo4j, minio, api/worker) + CI/CD + cổng Alembic | Không có container hoá; quyết định bỏ Supabase | Dev/prod tái lập được trên Docker | 4 | Không | P1-13, P1-6 | **Cao** |
| **P6-2** | Pin dependency; lockfile; torch chỉ-CPU; cập nhật theo lịch (I-31) | Không pin nào, và code phụ thuộc vào attribute **private** của hai thư viện | Khả năng tái lập; image nhỏ hơn | 1 | Việc pin có thể phơi bày các bất tương thích tiềm ẩn | Không | **Cao** |
| **P6-3** | Observability: dashboard, alert, SLO, tracing | Ba tín hiệu quan trọng nhất (tỉ lệ hit truy hồi, tỉ lệ `insufficient_evidence`, phân bố hiệu lực) hiện không được đo | Phát hiện suy thoái trước người dùng | 3 | Không | P2-12 | **Cao** |
| **P6-4** | Kiểm chứng backup: diễn tập restore hằng quý | Backup chưa test thì không phải backup | Khả năng phục hồi | 1/quý | Không | P6-1 | **Cao** |
| **P6-5** | Lifecycle dữ liệu: retention, yêu cầu xoá, audit log | Hợp đồng khách hàng tích tụ mãi mãi mà không có đường xoá | Tuân thủ | 3 | Cần rà soát pháp lý | P2-8 | **Cao** |
| **P6-6** | Crawl lại theo lịch + refresh hiệu lực + invalidate phân tích | Corpus pháp luật sẽ cũ đi; đã có bằng chứng đo được rằng `eff_status` đã cũ | Tính đúng đắn của câu trả lời theo thời gian | 2 | Không | P3-5, P1-10 | **Cao** |
| **P6-7** | Frontend: router, TanStack Query, trạng thái lỗi (I-37) | Không deep link; refresh mất việc; lỗi hiện ra như trạng thái rỗng | UX; tính đúng đắn của state được hiển thị | 4 | Không | P2-13 | **Trung bình** |
| **P6-8** | Danh tính chat nhiều hội thoại `(user, contract, conversation)` (I-40) | Rẻ bây giờ, đau đớn sau khi tính năng chia sẻ ra mắt | Ngăn một lớp rò rỉ dữ liệu trong tương lai | 1 | Migrate các thread đã có | P2-2 | **Trung bình** |
| **P6-9** | Versioning theo thời gian ở cấp section (§7.11 lớp 3) | **Chỉ khi** câu trả lời theo thời điểm là yêu cầu. Đắt và cần parse văn bản sửa đổi | Độ chính xác pháp lý theo thời điểm | 8 | Độ phức tạp cao | P3-4 | **Thấp — hoãn** |
| **P6-10** | Vận hành Neo4j GraphRAG: SLO outbox, reconcile, diễn tập rebuild từ Postgres | Neo4j đã chọn; rủi ro còn lại là nhất quán hai store | Tránh tư vấn sai do graph lệch | 3 | Không | P3-4, P6-3, BƯỚC 12 | **Cao** |

## Tổng hợp công sức

| Pha | Công sức (ngày-người) | Thời lượng (1 engineer) |
|---|---|---|
| 0 — Sự thật nền | 2,5 | ~3 ngày |
| 1 — Sửa vấn đề Nghiêm trọng | 31 | 6–7 tuần |
| 2 — Dọn dẹp kiến trúc | 26 | 5–6 tuần |
| 3 — Thiết kế lại database | 39 | 8 tuần |
| 4 — Hiệu năng | 16 | 3–4 tuần |
| 5 — Chất lượng tìm kiếm | 23 | 5 tuần |
| 6 — Bảo trì | 26 (+8 hoãn) | liên tục |
| **Tổng** | **~164 ngày** | **~8 tháng một người, ~4 tháng hai người** |

## Đường tới hạn (critical path)

```
P0-1 (schema thật) → P0-2 (extension) → P1-8 (Alembic) → P1-11 (pgvector) → P3-1 (schema) → P3-3 (ingestion) → P3-4 (tham chiếu) → P5-2/P5-3 (chất lượng)
                                                             ↑
P1-13 (hạ tầng test) → P1-7 (pool) ──────────────────────────┘
P0-4 (crawl nhiều loại) ─────────────────→ P3-1
P5-1 (benchmark) ────────────────────────→ toàn bộ Pha 5
```

**Nếu chỉ có hai tuần**, theo thứ tự này: **P0-1** (biết schema thật), **P1-1 + P1-2** (chứng minh và giảm nhẹ truy hồi bị hỏng), **P1-3, P1-4, P1-5** (ba cách sửa bảo mật, tổng ~2 ngày), **P1-6** (độ trễ auth và SPOF), **P1-15** (sửa index). Đó là khoảng 6 ngày công việc loại bỏ bug tính đúng đắn nguy hiểm nhất, ba lỗ bảo mật, và thành phần độ trễ lớn nhất — và mua thời gian để việc migration pgvector được làm đúng thay vì làm gấp.

**Nếu chỉ làm được một việc: P1-11 (pgvector).** Nó đóng I-1, I-4, I-5, I-8, và I-15 — năm trong mười hai vấn đề Nghiêm trọng — và biến một ứng dụng một process không scale được thành một ứng dụng scale được theo cách thông thường. Mọi thứ trong Pha 3 và Pha 5 đều phụ thuộc vào nó.

---

# Phụ lục A — Chỉ mục Thực tế / Suy luận / Đề xuất

**Các THỰC TẾ chọn lọc kèm dẫn chứng** (đã kiểm chứng trong code, SQL, config, hoặc bằng cách chạy script đo lường trên output crawler):

| # | Sự thật | Dẫn chứng |
|---|---|---|
| F1 | Lọc metadata của FAISS hậu lọc trên top-`fetch_k`=20 toàn cục | source `langchain_community 0.4.1`, kiểm chứng bằng `inspect.getsource`; `faiss_store.py:73-77` không bao giờ truyền `fetch_k` |
| F2 | SQL của `loader.py` tham chiếu 1 bảng + 7 cột không có trong `schema.sql` | `loader.py:6-18` vs `schema.sql:8,17,40,44,46,48` |
| F3 | `schema.sql:71` khai báo một FK `UUID` tới một cột `TEXT` | `schema.sql:71` vs `database.py:33` |
| F4 | Mục lục đã crawl: 1.308 node; Chương 4 / Mục 8 / Điều 55 / Khoản 332 / Điểm 909; độ sâu tối đa 5 | đo trên `muc_luc.json` |
| F5 | Cây không đồng nhất theo cấp: 9 Điều là con trực tiếp của Chương, 46 nằm dưới Mục | đo trên `muc_luc.json` |
| F6 | `orderIndex` là một chuỗi pre-order dày đặc 1…1308; `id == key` với mọi node | đo trên `muc_luc.json` |
| F7 | `van_ban.md` neo đúng 55 Điều + 332 Khoản; **0** Điểm, Chương, hay Mục — 387/1308 = 29,6% | đo trên `van_ban.md` × `muc_luc.json` |
| F8 | Tương ứng anchor↔mục lục là chính xác theo cả hai hướng với Điều và Khoản | đo được: 0 node mồ côi ở cả hai chiều |
| F9 | Tiêu đề mục lục là nhãn trần (`"Điều 1"`); tên điều chỉ tồn tại như heading H2 trong thân (55 cái) | đo trên cả hai file |
| F10 | Độ dài đoạn theo Khoản: trung bình 779, p90 1.749, tối đa 8.704 ký tự so với giới hạn model 256 token | đo được; `embeddings.py:26` |
| F11 | Tham chiếu trong văn bản: 419 `Điều N`, 193 `khoản N Điều N`, 119 `điểm..khoản..Điều`, 24 bên ngoài — nội bộ:bên ngoài ≈ 17:1 | đo trên `van_ban.md` |
| F12 | Payload nghiệp vụ: 186 `phạt tiền từ`, 472 số tiền, 103 lần trừ điểm giấy phép | đo trên `van_ban.md` |
| F13 | `thuoc_tinh.json` nói "Còn hiệu lực", `eff_to = null`; `luoc_do.json` cho thấy bị bãi bỏ bởi 336/2025 và sửa đổi bởi 238/2026 | đo trên cả hai file |
| F14 | `luoc_do.json` để lộ 15 loại quan hệ theo cả hai hướng; entry đi vào chỉ mang `doc_id`+`title` | đo được |
| F15 | `doc_id` xuất hiện ở hai định dạng: chuỗi số và UUID | đo trong `luoc_do.json` |
| F16 | 0 dòng bảng Markdown; không có biểu diễn phụ lục hay đính kèm trong bất kỳ artifact nào | đo được |
| F17 | `get_chat_model` bỏ qua tham số `provider` của nó, thứ được xuyên qua 5 tầng | `llm_client.py:12-20` + 9 chỗ gọi |
| F18 | `helpers/text_normalizer.py` và `risk_flagger.flag_risks` không có nơi nào import | grep khắp `app/`, `scripts/`, `tests/` |
| F19 | `idx_contracts_id` trùng lặp với index do `contract_id … UNIQUE` tạo ra | `database.py:33,47` |
| F20 | Không có Dockerfile, CI, migration, `pyproject.toml`, hay dependency được pin | `git ls-files`; `requirements.txt` |
| F21 | 11 test; không cái nào phủ `risk_flagger`, `qa_agent`, `workflow`, `retriever`, `faiss_store`, `loader`, `auth`, hay `clause_parser` | `tests/` |
| F22 | Dữ liệu bẩn: `"Điều \xa02"` (NBSP) trong một tiêu đề mục lục; `"Phó  Thủ tướng"` (hai dấu cách) trong chức danh người ký | đo được |

**Các SUY LUẬN chính** (lập luận được trình bày tại mỗi chỗ sử dụng): repository là hai hệ thống con ở hai mức trưởng thành khác nhau (BƯỚC 1); lỗi thiếu KB của H-7 không phân biệt được với một lần từ chối chính đáng (BƯỚC 3.3); `eff_status` là một snapshot đã cũ và phải được dẫn xuất (I-10); GraphRAG cần **hai tầng** — ltree/Postgres cho cây nội bộ + Neo4j cho quan hệ xuyên văn bản (BƯỚC 6.4); độ trễ LLM chiếm ưu thế 100–1000× nên vector search tối ưu cho recall (BƯỚC 13.5).

**Các ĐỀ XUẤT chính:** Docker Compose (Postgres/pgvector + Neo4j + MinIO), bỏ Supabase; **tách SoT** — Postgres = nền/content/vector, Neo4j = quan hệ; **chỉ map `doc_id`/`section_id`**; JWT tự host; xóa FAISS; ingestion 4 file đúng store; `legal_penalties` (ROI cao).

# Phụ lục B — Các câu hỏi mở cần thông tin ngoài repository này

| # | Câu hỏi | Vì sao quan trọng | Cách giải quyết |
|---|---|---|---|
| Q1 | Schema thực tế đang deploy là gì? | Ba nguồn không khớp; `PROGRESS_REPORT.md:108` nêu 4 bảng không giải thích được | `pg_dump --schema-only` (**P0-1**) |
| Q2 | Version pgvector trên image Docker nào? | Quyết định `halfvec` / iterative scan | Pin `pgvector/pgvector:pg16`+ và `SELECT extversion` (**P0-2**) |
| Q3 | Các loại văn bản khác có lồng sâu hơn Điểm không? | Từ vựng nhãn ltree và constraint `CHECK` | Crawl một Bộ luật và một Luật (**P0-4**) |
| Q4 | Tệp đính kèm (`Phụ lục`) được để lộ ra sao? | Cần mẫu thật để điền content cho level Appendix/Group đã dự phòng | Crawl một văn bản có phụ lục (**P0-4**) |
| Q5 | Node id của vbpl có ổn định qua các lần crawl lại không? | Quyết định liệu path ltree có cần một đường viết lại | Crawl lại cùng một văn bản và diff các id |
| Q6 | `dangvantuan/vietnamese-embedding` có cần tách từ không? | Có thể là mức tăng truy hồi lớn và miễn phí | Model card + test truy hồi A/B (**P0-5**) |
| Q7 | Source code của crawler ở đâu? | Không có trong repository này; ingestion không thể hoàn thiện mà không có nó | Tìm nó hoặc lập kế hoạch viết lại |
| Q8 | Mục tiêu thực về tính khả dụng, độ trễ, và dung lượng là gì? | Không có NFR nào trong bất kỳ tài liệu nào; việc sizing hiện là suy luận của tôi | Quyết định của stakeholder |
| Q9 | Độ chính xác pháp lý theo thời điểm có bắt buộc không? | Quyết định lớp 3 của §7.11 (P6-9, 8 ngày) có nằm trong phạm vi hay không | Quyết định của stakeholder |
| Q10 | Ngữ nghĩa pháp lý đúng của 15 loại quan hệ cho việc dẫn xuất hiệu lực là gì? | Cách sửa I-10 không được mã hoá một quy tắc pháp lý sai | Rà soát pháp lý |
| Q11 | Có ai có kinh nghiệm Neo4j production không? | Bắt buộc cho vận hành GraphRAG (P6-10), không còn điều kiện trì hoãn | Đánh giá nhóm + spike |
| Q12 | Hệ thống hiện có đang xử lý hợp đồng khách hàng thật không? | Nâng I-41 từ Trung bình lên Cao | Xác nhận của stakeholder |





