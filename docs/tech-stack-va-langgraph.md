# ContractLens — Công nghệ sử dụng & cách LangGraph được áp dụng

> Tài liệu mô tả chi tiết toàn bộ stack công nghệ của dự án **ContractLens** (hệ thống AI rà soát hợp đồng tiếng Việt), với phần chuyên sâu nhất về **LangGraph** — cách nó được tích hợp, vì sao được chọn, và từng node/edge/state được triển khai cụ thể ra sao trong code.

---

## 1. Tổng quan kiến trúc

ContractLens là một hệ thống "AI rà soát hợp đồng" theo mô hình **RAG (Retrieval-Augmented Generation) + Agent workflow**:

```
Người dùng
   │  upload hợp đồng (.docx/.pdf/.png...)
   ▼
FastAPI (Backend API)  ──────►  React 19 + Vite (Frontend)
   │
   ├─ Document pipeline: parse → chunk theo "Điều" → embedding → lưu pgvector
   ├─ Analysis workflow (LangGraph): extract → judge từng Điều → aggregate
   ├─ QA workflow (LangGraph): retrieve → generate/refusal, có checkpointer
   │
   ├─ PostgreSQL + pgvector : hợp đồng, chunks, kho luật, embeddings, checkpoint chat
   ├─ Neo4j : đồ thị văn bản pháp luật (GraphRAG expansion)
   └─ Gemini 2.5 Flash : LLM sinh nội dung (chat, JSON extraction, đánh giá rủi ro)
```

Luồng dữ liệu chính qua các API (`app/api/routes.py`):

| Endpoint | Use case | Pipeline |
|---|---|---|
| `POST /api/v1/upload` | `UploadContract` | parse → chunk → embed → lưu Postgres |
| `POST /api/v1/analyze` | `AnalyzeContract` | LangGraph **analysis graph** |
| `POST /api/v1/chat` | `ChatWithContract` | LangGraph **QA graph** |
| `GET /api/v1/chat/{id}/history` | `GetChatHistory` | đọc checkpoint từ Postgres |
| `POST /api/v1/auth/*` | `RegisterUser`/`LoginUser` | JWT + bcrypt |
| `GET /api/v1/contracts` | `ListContracts` | truy vấn Postgres |

---

## 2. Danh sách công nghệ

### 2.1 Backend — Python + FastAPI

- **FastAPI** + **uvicorn** — framework API async, khai báo schema bằng Pydantic (`requirements.txt:1-2`).
- **Kiến trúc phân lớp** (Clean/Hexagonal Architecture):
  - `app/domain/` — entities + ports (interfaces) — `domain/ports/repositories.py`, `domain/ports/services.py`
  - `app/application/use_cases/` — business logic độc lập framework (`contracts.py`, `auth.py`, `legal_ingest.py`)
  - `app/infrastructure/` — cài đặt cụ thể (Postgres, Neo4j, LLM, embeddings, vector search...)
  - `app/agents/` — các module LangGraph + helper LLM
  - `app/api/` — REST layer
  - DI container: `app/infrastructure/container.py` (`AppContainer`, `build_container()`)

### 2.2 LLM — Google Gemini

- **Gemini 2.5 Flash** (`gemini-2.5-flash`, `app/core/settings.py:15`), gọi qua **`langchain-google-genai`** (`ChatGoogleGenerativeAI`, `temperature=0`).
- Hai entry-points:
  - `app/agents/llm_client.py` — `get_chat_model()` (message-list invocation cho LangGraph node) và `chat_completion()` (single-string, cho extractor/risk_flagger).
  - `app/infrastructure/llm/gemini_chat.py` — `GeminiChatModel` theo interface `ChatModel` trong DI container.

### 2.3 Embeddings — BAAI/bge-m3

- **`BAAI/bge-m3`** — model embedding đa ngôn ngữ (tốt cho tiếng Việt), chiều vector **1024** (`settings.py:18-19`).
- Nạp qua **`langchain-huggingface`** (`HuggingFaceEmbeddings`) + **PyTorch** (`torch`), tự chọn device CUDA/CPU (`app/infrastructure/embeddings/hf_embedder.py:12-43`).
- Cache HF chia sẻ qua volume Docker `hf_cache`, warm-up lúc startup (`app/main.py:62-66`).

### 2.4 Database — PostgreSQL + pgvector + Neo4j

- **PostgreSQL 16 với pgvector** (image `pgvector/pgvector:pg16`) — lưu: người dùng, hợp đồng, `contract_chunks`, kho luật `legal_documents` + `legal_section_chunks`, và cả **checkpoint chat của LangGraph**.
- **Vector search**: operator `<=>` (cosine distance) trong `app/infrastructure/vector/pg_search.py`.
- **Hybrid search**: vector cosine + **Postgres Full-Text Search** (`tsv`, `ts_rank_cd`) → hợp nhất bằng **Reciprocal Rank Fusion** (`app/infrastructure/vector/rrf.py`).
- **Neo4j 5** — đồ thị các văn bản pháp luật: node `Document`/`Node`/`Chunk`, quan hệ `PARENT_OF`, `REPEALS`, `SUPERSEDES`, `AMENDS`, `BASED_ON`, `CITES`... (`app/infrastructure/neo4j/graph_repository.py:10-40`). Dùng cho **GraphRAG** — bung mở kết quả tìm kiếm theo quan hệ pháp lý.
- **psycopg / psycopg2** — driver Postgres sync; **psycopg async pool** cho LangGraph checkpointer (`app/agents/checkpointer.py`).

### 2.5 Retrieval — RAG / GraphRAG

- **`app/infrastructure/retrieval/legal_graph_rag.py`** — pipeline 3 bước:
  1. **Seed**: hybrid search Postgres lấy các điều luật liên quan.
  2. **Expand**: Neo4j bung các "sibling/ancestor/related" theo quan hệ đồ thị.
  3. **Hydrate**: lấy text từ Postgres, đánh hạng theo hiệu lực (`status_flag`, `eff_from/eff_to`) và vai trò (seed/sibling/ancestor/related).
- Query rewrite theo loại hợp đồng: `app/infrastructure/retrieval/query_rewrite.py`.

### 2.6 Auth — JWT + bcrypt

- **PyJWT** (HS256) — `app/infrastructure/auth/jwt_tokens.py`.
- **passlib[bcrypt]** — `app/infrastructure/auth/password.py`.
- Chặn khởi động nếu `JWT_SECRET` còn mặc định (`app/main.py:25-31`).

### 2.7 Document processing

- **pdfplumber** (PDF), **python-docx** (Word), OCR ảnh qua Gemini, cùng allowlist extension (`app/application/use_cases/contracts.py:29-31`).
- **Chunker theo "Điều"** — tách đúng mức điều khoản, giữ `clause_number` ổn định khi cắt nhỏ (`app/document/chunker.py:93-150`).

### 2.8 Frontend — React + Vite + Tailwind

- **React 19**, **Vite 8**, **Tailwind CSS 3**, ESLint (`frontend/package.json`).
- Serve trực tiếp bởi FastAPI ở production (`app/main.py:107-112`).

### 2.9 Deployment — Docker Compose

- 4 services: `postgres`, `neo4j`, `api`, `frontend` (`docker-compose.yml`), healthcheck + volume riêng.
- Script restore dump DB: `scripts/restore_db.ps1/.sh`, `restore_neo4j.ps1/.sh`.

---

## 3. LangGraph — phần chuyên sâu

> **LangGraph** là framework của LangChain để xây dựng **stateful, multi-agent workflows** dưới dạng đồ thị có chu kỳ (cyclic graph). Khác với chuỗi tuyến tính (chain), nó cho phép *rẽ nhánh điều kiện*, *chạy song song*, *lặp*, và *persist trạng thái* giữa các lần chạy (checkpoint). ContractLens dùng **2 đồ thị LangGraph riêng biệt** cho 2 pipeline: phân tích rủi ro và hỏi đáp.

```
requirements.txt
├── langgraph                        # core framework
├── langgraph-checkpoint-postgres    # lưu trạng thái graph vào Postgres
├── langchain / langchain-core       # messages, StateGraph types
└── langchain-google-genai           # ChatGoogleGenerativeAI (LLM node)
```

---

### 3.1 Đồ thị 1 — Analysis workflow (phân tích rủi ro hợp đồng)

**File:** `app/agents/workflow.py`

Đây là đồ thị **"map-reduce" (fan-out / fan-in)** trên các điều khoản. Sơ đồ:

```
                    ┌────────────────────┐
 START ──► extract  │  StateGraph        │
                    │  AnalysisState     │
                    └─────────┬──────────┘
                              │  có điều khoản?
                    ┌─────────┴─────────┐
               (có) │            (không)│
                    ▼                  │
         Send("judge_clause", ...)     │
         ┌───┬──────┬───┬───┬───┐      │
         ▼   ▼      ▼   ▼   ▼   ▼      │
      judge_clause (≤4 node chạy song song)│
         └───┴──────┴───┴───┴───┘      │
                    │                  │
                    └──────┬───────────┘
                           ▼
                       aggregate ──► END
```

#### 3.1.1 State — dùng `TypedDict` + Reducer

```python
class AnalysisState(TypedDict):
    contract_text: str
    contract_id: str
    provider: str
    analysis: ContractAnalysis
    risks: Annotated[List[RiskItem], operator.add]   # workflow.py:19-24
```

- Mỗi field là một phần trạng thái; các node trả về **dict các field cần cập nhật**, LangGraph merge vào state.
- **`risks` dùng reducer `operator.add`** — khi nhiều node `judge_clause` chạy song song cùng trả về list rủi ro, LangGraph **cộng dồn (reduce)** chúng vào một list duy nhất. Đây là cơ chế chính để "fan-in" dữ liệu từ nhiều nhánh song song.
- `ClauseState` (state riêng cho từng nhánh): `clause`, `contract_id`, `provider`, `contract_type` (workflow.py:27-31).

#### 3.1.2 Nodes

- **`_extract_node`** (workflow.py:34-41) — gọi `parse_contract()` (rule-based + LLM gap-fill) chạy trong thread pool qua `asyncio.to_thread` để không block event loop. Nếu lỗi, trả về `ContractAnalysis` rỗng thay vì crash.
- **`_fan_out_clauses`** (workflow.py:44-62) — đây **không phải node xử lý** mà là **conditional edge function**: nó quyết định rẽ nhánh. Nếu không có điều khoản → về thẳng `"aggregate"`. Nếu có → trả về list `Send("judge_clause", {...})`.
- **`_judge_clause_node`** (workflow.py:65-83) — đánh giá 1 điều khoản bằng `evaluate_clause()` (RAG pháp luật + LLM), trả `{"risks": [risk]}`. Bắt lỗi và trả `[]` để không làm hỏng graph.
- **`_aggregate_node`** (workflow.py:86-87) — điểm gom kết quả; reducer đã lo việc hợp nhất, nên node này chỉ cần trả `{}`.

#### 3.1.3 Graph building — `StateGraph`, `START`, `END`, conditional edges

```python
_graph = StateGraph(AnalysisState)                                # workflow.py:90
_graph.add_node("extract", _extract_node)                         # 91
_graph.add_node("judge_clause", _judge_clause_node)               # 92
_graph.add_node("aggregate", _aggregate_node)                     # 93
_graph.add_edge(START, "extract")                                 # 94
_graph.add_conditional_edges(                                     # 95
    "extract", _fan_out_clauses, ["judge_clause", "aggregate"]
)
_graph.add_edge("judge_clause", "aggregate")                      # 96
_graph.add_edge("aggregate", END)                                 # 97
_compiled_graph = _graph.compile()                                # 98
```

#### 3.1.4 Chạy với `ainvoke` + kiểm soát concurrency

```python
result = await _compiled_graph.ainvoke(                          # workflow.py:104-107
    {"contract_text": ..., "contract_id": ..., "provider": ..., "risks": []},
    config={"max_concurrency": _MAX_CONCURRENT_CLAUSE_CHECKS},    # = 4
)
```

- `_MAX_CONCURRENT_CLAUSE_CHECKS = 4` (workflow.py:16) — **giới hạn số LLM call đồng thời** để hợp đồng lớn (hàng chục điều khoản) không bùng nổ request tới provider và vượt rate limit.
- Mỗi lần `ainvoke` fan-out sẽ spawn các `Send` tới `judge_clause`; LangGraph tự lên lịch, tối đa 4 chạy cùng lúc.

#### 3.1.5 Vì sao dùng LangGraph ở đây?

Nếu viết tuần tự thì `extract → for clause: judge` mất `N` lần LLM gọi nối tiếp. LangGraph giúp:
1. **Song song hóa tự động** qua `Send` + `max_concurrency` — giảm thời gian phân tích từ tuyến tính xuống ~`N/4`.
2. **State quản lý tập trung** — mỗi node chỉ quan tâm field của mình, reducer lo merge.
3. **Chống chết graph** — mỗi node tự bắt lỗi; rủi ro từ 1 điều khoản không kéo sập cả phân tích.
4. **Khả năng mở rộng** — dễ thêm node (vd: pre-processing, summary) hay đổi rẽ nhánh điều kiện mà không đụng phần còn lại.

---

### 3.2 Đồ thị 2 — QA workflow (chat với hợp đồng)

**File:** `app/agents/qa_agent.py`

Đồ thị **RAG có điều kiện (conditional routing) + checkpoint**:

```
                ┌───────────────────┐
 START ──► retrieve                │ QAState (messages dùng add_messages reducer)
                │                   │
                └─────────┬─────────┘
                          │ _has_context?
                ┌─────────┴─────────┐
           (có) │            (không) │
                ▼                   ▼
            generate              refusal
                │                   │
                └─────────┬─────────┘
                          ▼
                         END
```

#### 3.2.1 State — `add_messages` reducer

```python
class QAState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]   # qa_agent.py:28-38
    contract_id: str
    provider: str
    source_clauses: List[str]
    needs_clarification: bool
    _has_context: bool
    _contract_context: str
    _legal_context: str
    _valid_clause_numbers: List[str]
```

- **`messages` dùng reducer `add_messages`** của `langgraph.graph.message` — mỗi node trả `{"messages": [AIMessage...]}` sẽ được **append** vào danh sách lịch sử, thay vì ghi đè. Đây là pattern chuẩn của LangGraph cho agent đối thoại.
- Các field `_has_context`, `_contract_context`... là "tạm" — chỉ tồn tại trong 1 lượt chạy.

#### 3.2.2 Các node

- **`_retrieve_node`** (qa_agent.py:58-73) — lấy câu hỏi cuối cùng trong `messages`, gọi `retrieve_contract()` (chunk hợp đồng theo câu hỏi) và `retrieve_legal()` (GraphRAG kho luật). Nếu **cả hai rỗng** → `{"_has_context": False}` (route đi từ chối), ngược lại nạp context + danh sách số điều hợp lệ.
- **`_generate_node`** (qa_agent.py:88-146):
  - Cắt lịch sử bằng **`trim_messages`** của LangChain (cửa sổ `_MAX_HISTORY_TOKENS = 2000`, giữ các tin **gần nhất**, loại tin hiện tại vì được chèn riêng) — đây chính là cơ chế *memory* của agent (bình luận trong code: tương đương `TokenWindowChatMemory`, qa_agent.py:22-25).
  - Build prompt: `SystemMessage(QA_SYSTEM_PROMPT) + history + HumanMessage(QA_HUMAN_TEMPLATE)` (qa_agent.py:101-107).
  - Gọi `get_chat_model()` qua `ainvoke`, parse JSON, **retry 1 lần** nếu parse lỗi.
  - **Kiểm chứng citation**: chỉ giữ số điều thực sự xuất hiện trong `_valid_clause_numbers` (từ retrieval), loại bỏ số điều "ảo" do LLM bịa (qa_agent.py:132-139).
  - Hỗ trợ chế độ `needs_clarification` — nếu model thấy câu hỏi mơ hồ, trả câu hỏi làm rõ.
- **`_refusal_node`** (qa_agent.py:80-85) — trả câu trả lời chuẩn "không tìm thấy thông tin" thay vì để LLM đoán bừa khi không có ngữ cảnh (anti-hallucination).

#### 3.2.3 Conditional routing

```python
_graph_builder.add_conditional_edges(
    "retrieve", _route_after_retrieve,
    {"generate": "generate", "refusal": "refusal"}               # qa_agent.py:154
)
```

Hàm `_route_after_retrieve` (qa_agent.py:76-77) đọc `_has_context` và trả key rẽ nhánh. Điểm hay: **quyết định route được làm trước khi gọi LLM**, dựa trên dữ liệu retrieval thực — giảm chi phí và chống ảo giác.

#### 3.2.4 Checkpointer — lưu trạng thái vào Postgres

**File:** `app/agents/checkpointer.py`

```python
_pool = AsyncConnectionPool(conninfo=get_settings().database_url, open=False, ...)
await _pool.open()                                              # checkpointer.py:21-26
_checkpointer = AsyncPostgresSaver(conn=_pool)                  # 27
await _checkpointer.setup()                                     # 28 (tạo bảng checkpoint)
```

- **`AsyncPostgresSaver`** từ `langgraph-checkpoint-postgres` — lưu toàn bộ state của graph sau mỗi node (messages, biến) vào bảng checkpoint trong Postgres.
- Compile graph kèm checkpointer (qa_agent.py:166):

```python
_compiled_graph = _graph_builder.compile(checkpointer=get_checkpointer())
```

- Mỗi cuộc hội thoại là một **`thread_id`** = `contract_id` (qa_agent.py:173-174):

```python
config={"configurable": {"thread_id": contract_id}}
```

- Nhờ checkpoint, khi người dùng hỏi tiếp, LangGraph **tự nạp lại toàn bộ lịch sử messages** của thread đó — không cần code SQL "lấy N dòng cuối". Đây là cơ chế *history* (đối lập với *memory* đã trim ở `_generate_node`).
- `get_conversation_history()` (qa_agent.py:184-207) đọc lại snapshot qua `graph.aget_state({"configurable": {"thread_id": contract_id}})` để dựng lịch sử hiển thị cho UI.

#### 3.2.5 Deferred compilation — khởi tạo đúng lúc

Graph QA **không compile lúc import** mà compile lười (lazy) trong `_get_graph()` (qa_agent.py:161-167). Lý do: `AsyncPostgresSaver` cần **event loop đang chạy** và pool được mở lúc app startup (`init_checkpointer()` trong `app/main.py:58`). Nếu compile ở import-time sẽ crash. Nhờ vậy module có thể import an toàn trong test hoặc script.

---

### 3.3 Cách các graph được cắm vào ứng dụng (wiring)

```
app/main.py (lifespan) ──► init_checkpointer()          # mở pool Postgres
                        ──► build_container()
                        ──► container.analyze_pipeline = LangGraphAnalyzePipeline()
                        ──► container.qa_pipeline      = LangGraphQaPipeline()
                        ──► bind_retrieval(...)         # gắn search/GraphRAG vào runtime holders
```

**File:** `app/infrastructure/agents/pipelines.py`

```python
class LangGraphAnalyzePipeline:                     # pipelines.py:8-13
    async def run(self, full_text, contract_id, provider):
        return await run_analysis_workflow(full_text, contract_id, provider)

class LangGraphQaPipeline:                          # pipelines.py:16-27
    async def answer(self, contract_id, question, provider):
        return await answer_question(question, contract_id, provider)
    async def history(self, contract_id):
        return await get_conversation_history(contract_id)
```

- Các pipeline này đáp ứng **port** `AnalyzePipeline` / `QaPipeline` trong `app/domain/ports/services.py`, nên `use_cases` (`AnalyzeContract`, `ChatWithContract`) chỉ gọi qua interface, không biết tới LangGraph — kiến trúc hexagonal hoạt động trơn tru.
- `bind_retrieval()` (`app/infrastructure/retrieval/context.py:15-31`) gắn các object search/graph vào module-level holders để các agent module truy cập không vòng import.

---

### 3.4 Human-in-the-loop (review gate) — Phase C

**File:** `app/agents/workflow.py`

Kể từ Phase C, analysis graph có thêm node `review` nằm sau `aggregate`:

```
aggregate ──► review ──► END
                │
                └─ nếu review_mode=True: interrupt() → pause, trả draft
```

- **`_review_node`** (workflow.py) — nếu `review_mode` không bật thì no-op (trả `{}`, đi thẳng `END`). Nếu bật, gọi `interrupt({"contract_id", "draft_analysis", "draft_risks"})`: graph **dừng**, state (gồm draft) được checkpoint lại, và `ainvoke` trả về `{'__interrupt__': [Interrupt(...)]}`.
- **Two-graph strategy**:
  - `_compiled_graph` (không checkpointer) — chạy path không review như trước, không cần DB, không đổi hành vi.
  - `_review_graph` (compile **deferred** trong `_get_review_graph()`, kèm `checkpointer=get_checkpointer()`) — chỉ build khi có review, vì checkpointer cần pool mở lúc startup (giống QA graph).
- **`run_analysis_workflow_review()`** — chạy `ainvoke` với `review_mode=True`, `thread_id = "analysis:{uuid}"`; trả `{review_id, draft_analysis, draft_risks}`. Chưa persist gì.
- **`resume_analysis_review()`** — gọi lại graph với `Command(resume={"approved": bool, "edits": [...]})` cùng thread_id. LangGraph tiếp tục từ điểm interrupt; payload `edits` (nếu là list **không rỗng**) thay thế danh sách rủi ro AI. Trả `{analysis, risks, approved}`.
- **Use case / API**: `AnalyzeContract(..., review_mode=True)` trả `status="awaiting_review"`; `POST /analyze/resume` → `ResumeAnalysisReview` — nếu `approved=True` mới `save_analysis()` (persist), nếu không thì trả draft mà không lưu.
- **Lưu ý threading**: thread_id của analysis-review dùng prefix `analysis:` tách khỏi QA (`chat:`), tránh xung đột checkpoint. Test: `tests/unit/test_analysis_review.py` dùng `InMemorySaver` thay Postgres.

---

### 3.5 Supervisor + subgraphs — Phase D

**File:** `app/agents/workflow.py`

Từ Phase D, analysis pipeline được tái cấu trúc thành **3 subgraph độc lập** + 1 **supervisor node** quyết định chạy subgraph nào kế tiếp:

```
                     ┌──────────────────────────────────────┐
  START ──► supervisor │                                      │
                     │  _extract_started?  -> "extract"      │
                     │  extract fail & retry budget -> "extract"
                     │  có clauses & chưa evaluate -> "evaluate"
                     │  review_mode -> "review" | còn lại -> END
                     └──────────────────────────────────────┘
                        │              │              │
              ┌─────────┘              │              └──────────┐
              ▼                        ▼                        ▼
    subgraph: extract         subgraph: evaluate      subgraph: review
    (extract node)           (judge_clause fan-out    (interrupt gate)
                             qua Send + aggregate)
              │                        │                        │
              └──────────► supervisor ◄┘                        END
```

- **`_supervisor_node`** — router trung tâm: đọc state (cờ `_extract_started`, `_extract_failed`/`attempts`, có clauses không, `_evaluated`, `review_mode`) rồi trả `_plan`. Conditional edge `_route_by_plan` map plan → subgraph node (hoặc `END`). Retry extract giờ do supervisor quyết định thay vì self-loop trong node.
- **Nested compiled graphs**: LangGraph cho phép dùng 1 compiled graph làm node của graph khác — subgraph đọc các channel **input** từ parent state và ghi các channel **output** về parent. Parent state phải chứa toàn bộ channel của mọi subgraph (`AnalysisState` là union), nên `_plan`/`_extract_started`/`_evaluated` nằm chung state.
- **Piège quan trọng — reducer + nested subgraph**: subgraph mặc định "echo" lại **mọi** channel nhận được. Channel có reducer `operator.add` (vd `risks`) bị **cộng dồn lại** khi subgraph chạy lại sau `Command(resume=...)` → risks nhân đôi. Fix: dùng `output_schema` (`_ExtractOutput`/`_EvaluateOutput`/`_ReviewOutput`) để mỗi subgraph chỉ ghi đúng channel nó sản sinh.
- Hành vi đã xác minh bằng experiment trước khi viết code: `Send` fan-out trong subgraph lồng giữ payload; `interrupt()` trong subgraph lồng được checkpoint bởi parent và resume qua `Command(resume=...)` hoạt động.
- Entry points giữ nguyên (`run_analysis_workflow`, `run_analysis_workflow_review`, `resume_analysis_review`) → pipeline, use case, route, tests không đổi. Đây là điểm mở rộng để sau này thêm routing tiết kiệm chi phí (vd bỏ qua judge các điều khoản boilerplate).

---

### 3.6 Long-term memory cross-thread — Phase E

**File:** `app/agents/memory.py` (store) + `app/agents/qa_agent.py` (tích hợp)

Phân biệt 3 loại "memory" trong QA graph:

| Loại | Cơ chế | Phạm vi | Sống tới khi |
|---|---|---|---|
| **History** | checkpointer (`thread_id`, toàn bộ messages) | 1 thread | khi bị trim |
| **Memory (short-term)** | `trim_messages` cấp prompt | 1 thread | bị `trim_messages` loại theo token |
| **Long-term memory** | `AsyncPostgresStore`, namespace theo `contract_id` | **mọi thread** của hợp đồng | tồn tại vĩnh viễn |

- **`app/agents/memory.py`** — dùng `AsyncPostgresStore` (cùng pool với checkpointer, `init_memory_store()` gọi trong `init_checkpointer()`). Namespace `("contracts", <contract_id>, "qa_memory")`, một tài liệu rolling `key="long_term"` chứa tối đa `_MAX_MEMORY_PAIRS = 5` cặp Hỏi/Trả lời gần nhất. Dùng 1 doc duy nhất để thứ tự xác định (không phụ thuộc ranking search của store).
- **QA graph**:
  - `_retrieve_node` gọi `load_qa_memory(contract_id)` → state `_long_term_memory`.
  - `_generate_node` nhúng `long_term_memory` vào `QA_HUMAN_TEMPLATE` (mục "Ký ức dài hạn từ các phiên hỏi trước").
  - Node mới `remember` chạy sau khi `generate` parse OK (route `generate → remember → END`), gọi `save_qa_memory()` — **không** lưu khi cần làm rõ (`needs_clarification`) hay khi refusal.
  - Từ đó, câu hỏi ở lượt sau (kể cả thread mới) đọc được kết luận các phiên trước dù thread history đã bị trim.
- **Resilient**: `save/load` bọc try/except — nếu store chưa init / lỗi thì chỉ log warning và trả rỗng, QA không bao giờ chết vì memory.
- **Test**: `tests/unit/test_qa_memory.py` dùng `InMemoryStore`; kiểm tra round-trip, rolling buffer, persist + inject sang lượt sau, và không lưu khi clarification/refusal.

---

### 3.7 Tổng kết LangGraph: các pattern được dùng| Pattern | Nơi dùng | Cơ chế |
|---|---|---|
| **Map-reduce (fan-out/fan-in)** | Analysis graph (`workflow.py`) | `Send` + reducer `operator.add` + `max_concurrency` |
| **Conditional routing** | Analysis (`_fan_out_clauses`), QA (`_route_after_retrieve`) | `add_conditional_edges` + hàm trả về tên node đích |
| **Checkpoint / persistence** | QA graph (`qa_agent.py`), review graph | `AsyncPostgresSaver` + `thread_id` |
| **Reducer `add_messages`** | QA graph | history messages append qua `langgraph.graph.message` |
| **Interrupt / resume (HITL)** | Analysis review (`workflow.py`) | `interrupt()` + `Command(resume=...)` + checkpointer |
| **Supervisor + subgraphs** | Analysis (`workflow.py`) | supervisor node route theo `_plan`; subgraph là compiled graph lồng nhau, `output_schema` giới hạn channel ghi lại |
| **Cross-thread memory (store)** | QA (`qa_agent.py` + `memory.py`) | `AsyncPostgresStore` namespace theo `contract_id`, rolling doc |

---

## 4. Bảng ánh xạ công nghệ → file mã nguồn

| Công nghệ | File chính |
|---|---|
| FastAPI | `app/main.py`, `app/api/routes.py` |
| LangGraph (analysis) | `app/agents/workflow.py` |
| LangGraph (QA) | `app/agents/qa_agent.py` |
| LangGraph checkpoint | `app/agents/checkpointer.py`, `langgraph-checkpoint-postgres` |
| Gemini | `app/agents/llm_client.py`, `app/infrastructure/llm/gemini_chat.py` |
| bge-m3 embeddings | `app/infrastructure/embeddings/hf_embedder.py` |
| pgvector | `app/infrastructure/vector/pg_search.py`, `schema.sql` |
| Hybrid search + RRF | `app/infrastructure/vector/rrf.py`, `pg_search.py` |
| GraphRAG / Neo4j | `app/infrastructure/retrieval/legal_graph_rag.py`, `app/infrastructure/neo4j/graph_repository.py` |
| JWT + bcrypt | `app/infrastructure/auth/*` |
| Doc parsing | `app/document/parser.py`, `chunker.py` |
| React/Vite/Tailwind | `frontend/` |
| Docker | `docker-compose.yml`, `Dockerfile` |
