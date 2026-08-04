## 3.7.1 Xác thực người dùng qua mã thông báo JWT

### Figure

Hình 3.1 Quy trình xác thực người dùng qua mã thông báo JWT với Supabase Auth

### Source Files

- `app/core/auth.py`
- `frontend/src/AuthContext.jsx`
- `frontend/src/api.js`

### Code

```python
# app/core/auth.py — Server-side JWT validation
async def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_SECRET_KEY},
            )
    except httpx.HTTPError as e:
        logger.error(f"Supabase auth check failed: {e}")
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if res.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = res.json()
    return user["id"]
```

```jsx
// frontend/src/AuthContext.jsx — Client-side session management
export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  const value = {
    session, user: session?.user || null, accessToken: session?.access_token || null, loading,
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signUp: (email, password) => supabase.auth.signUp({ email, password }),
    signOut: () => supabase.auth.signOut(),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

```js
// frontend/src/api.js — Token attachment helper
async function authHeaders() {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
```

### Explanation

Xử lý xác thực được thực hiện qua hai lớp: phía giao diện quản lý phiên đăng nhập thông qua Supabase SDK, phía máy chủ xác thực mã thông báo JWT qua REST API. `AuthProvider` khởi tạo phiên từ bộ nhớ đệm khi ứng dụng khởi động và lắng nghe sự kiện thay đổi trạng thái xác thực. Mọi yêu cầu API từ giao diện đều được gắn mã thông báo truy cập vào header `Authorization` thông qua hàm `authHeaders`. Hàm `get_current_user_id` ở máy chủ kiểm tra mã thông báo bằng cách gọi endpoint `/auth/v1/user` của Supabase; nếu không hợp lệ hoặc hết hạn, trả về mã lỗi 401 hoặc 503 nếu dịch vụ xác thực không khả dụng. Quy trình này đại diện cho cơ chế bảo vệ tài nguyên xuyên suốt toàn bộ hệ thống.

---

## 3.7.2 Tải lên và lập chỉ mục tài liệu hợp đồng

### Figure

Hình 3.2 Quy trình tải lên, phân tích và lập chỉ mục tài liệu hợp đồng

### Source Files

- `app/document/file_handler.py`
- `app/document/parser.py`
- `app/document/chunker.py`
- `app/services/contract_service.py`

### Code

```python
# app/services/contract_service.py (upload_contract)
async def upload_contract(file: UploadFile, user_id: str) -> UploadResponse:
    contract_id, file_path, file_ext = await save_upload(file)
    filename = file.filename or "unknown"
    status, message, chunk_count = "uploaded", f"File uploaded successfully: {filename}", 0
    try:
        text = parse_document(file_path, file_ext)
        docs = chunk_by_clause(text, contract_id)
        get_contract_collection().add_documents(docs)
        chunk_count = len(docs)
        status, message = "parsed", f"{filename} parsed and indexed with {chunk_count} chunks"
    except Exception as e:
        logger.error(f"Upload parse failed: contract_id={contract_id} error={e}")
        message = f"File uploaded but parsing failed: {str(e)}"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO uploaded_contracts (contract_id, user_id, filename, file_type, file_path, status, message, chunk_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (contract_id) DO UPDATE SET status = EXCLUDED.status, message = EXCLUDED.message, chunk_count = EXCLUDED.chunk_count",
                (contract_id, user_id, filename, file_ext, file_path, status, message, chunk_count),
            )
    return UploadResponse(contract_id=contract_id, filename=filename, file_type=file_ext, status=status, message=message, chunk_count=chunk_count)
```

```python
# app/document/file_handler.py — File validation and persistence
def validate_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "unknown")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not supported.")
    return ext

async def save_upload(file: UploadFile) -> Tuple[str, str, str]:
    ext = validate_file(file)
    contract_id = str(uuid.uuid4())
    safe_filename = f"{contract_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return contract_id, file_path, ext
```

```python
# app/document/chunker.py — Clause-based document chunking
def chunk_by_clause(text: str, contract_id: str) -> List[Document]:
    text = unicodedata.normalize("NFC", text)
    clause_pattern = r"(?:(?:Điều|ĐIỀU|Khoản|KHOẢN)\s+\d+[\.:\-\)]\s*)"
    splits = re.split(f"({clause_pattern})", text)
    documents = []
    chunk_index = 0
    if splits and splits[0].strip():
        preamble = splits[0].strip()
        documents.append(Document(page_content=preamble,
            metadata={"contract_id": contract_id, "clause_number": "Preamble", "chunk_index": 1}))
        chunk_index = 1
    for i in range(1, len(splits), 2):
        header = splits[i]; content = splits[i + 1] if i + 1 < len(splits) else ""
        chunk_text = (header + content).strip()
        if not chunk_text: continue
        num = re.search(r"(\d+)", header)
        clause_number = num.group(1) if num else str(chunk_index)
        chunk_index += 1
        documents.append(Document(page_content=chunk_text,
            metadata={"contract_id": contract_id, "clause_number": clause_number, "chunk_index": chunk_index}))
    if not documents or (len(documents) == 1 and documents[0].metadata["clause_number"] == "Preamble"):
        documents = [Document(page_content=chunk.strip(),
            metadata={"contract_id": contract_id, "clause_number": str(idx + 1), "chunk_index": idx + 1})
            for idx, chunk in enumerate(_split_text(text, MAX_CHUNK_SIZE, CHUNK_OVERLAP)) if chunk.strip()]
    return documents
```

### Explanation

Quy trình tải lên bắt đầu bằng việc kiểm tra định dạng tệp và lưu tệp vào thư mục upload với định danh UUID. Nội dung văn bản được trích xuất thông qua `parse_document` tùy theo định dạng tệp (DOCX, PDF, hoặc ảnh dùng OCR qua Gemini Vision). Văn bản sau đó được chia thành các đoạn theo ranh giới điều khoản qua hàm `chunk_by_clause`, sử dụng biểu thức chính quy để tách các điều khoản và đánh nhãn metadata. Các đoạn văn bản được lập chỉ mục vào FAISS vector store và thông tin tài liệu được ghi vào cơ sở dữ liệu PostgreSQL. Quy trình này là bước đầu vào bắt buộc cho mọi hoạt động phân tích hợp đồng sau đó.

---

## 3.7.3 Trích xuất thông tin điều khoản hợp đồng

### Figure

Hình 3.3 Quy trình trích xuất thông tin hợp đồng kết hợp luật và mô hình ngôn ngữ

### Source Files

- `app/agents/clause_parser.py`
- `app/agents/json_parsing.py`
- `app/core/prompts.py`

### Code

```python
# app/agents/clause_parser.py — Main extraction entry point
def parse_contract(text: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> ContractAnalysis:
    text = unicodedata.normalize("NFC", text)
    dates = _extract_dates(text)
    finance = _extract_finance(text)
    penalty = _extract_penalty(text)
    analysis = ContractAnalysis(
        contract_id=contract_id,
        contract_type=_extract_contract_type(text),
        parties=_extract_parties(text),
        execution_date=dates.get("execution_date"),
        start_date=dates.get("start_date"),
        end_date=dates.get("end_date"),
        duration=None,
        contract_value=finance.get("contract_value"),
        payment_terms=finance.get("payment_terms"),
        payment_method=finance.get("payment_method"),
        termination_clause=_extract_termination(text),
        penalty_clause=penalty.get("penalty_clause"),
        indemnity=penalty.get("indemnity"),
        force_majeure=_extract_force_majeure(text),
        governing_law=_extract_governing_law(text),
        dispute_resolution=_extract_dispute(text),
        confidentiality=_extract_confidentiality(text),
        severability=_extract_severability(text),
        amendments=_extract_amendments(text),
        clauses=_extract_clauses(text),
    )
    return _fill_gaps_with_llm(analysis, text, contract_id, provider)
```

```python
# app/agents/clause_parser.py — LLM fallback for missing fields
def _fill_gaps_with_llm(analysis: ContractAnalysis, text: str, contract_id: str, provider: str) -> ContractAnalysis:
    try:
        llm_result = _extract_with_llm(text, contract_id, provider)
    except Exception as e:
        return analysis
    if not llm_result:
        return analysis
    data = analysis.model_dump()
    for field in _LLM_FILLABLE_FIELDS:
        if not data.get(field) and llm_result.get(field):
            data[field] = llm_result[field]
    if not data.get("parties") and llm_result.get("parties"):
        data["parties"] = llm_result["parties"]
    if not data.get("contract_type") and llm_result.get("contract_type"):
        data["contract_type"] = llm_result["contract_type"]
    return ContractAnalysis(**data)
```

```python
# app/agents/clause_parser.py — Regex-based clause splitting
_CLAUSE_SPLIT_RE = re.compile(r"(?:^|\n)\s*(Điều|ĐIỀU)\s+(\d+)\s*[\.:\)\-\–]\s*", re.MULTILINE)

def _extract_clauses(text: str) -> List[Clause]:
    clauses = []
    splits = list(_CLAUSE_SPLIT_RE.finditer(text))
    for i, match in enumerate(splits):
        number = match.group(2)
        header_end = match.end()
        next_start = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        content = text[header_end:next_start].strip()
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        title = lines[0][:150] if lines else None
        body = _normalize("\n".join(lines))
        clauses.append(Clause(clause_number=number, title=title, summary=body))
    return clauses
```

### Explanation

Quy trình trích xuất áp dụng chiến lược kết hợp: trước tiên, các hàm dựa trên biểu thức chính quy được thực thi để trích xuất tất cả các trường thông tin có cấu trúc (bên tham gia, ngày tháng, tài chính, loại hợp đồng, điều khoản phạt, v.v.) một cách xác định. Sau đó, nếu bất kỳ trường nào còn trống, mô hình ngôn ngữ Gemini được gọi để bổ sung thông tin còn thiếu, nhưng chỉ áp dụng cho các trường mà luật chưa phát hiện được. Các điều khoản hợp đồng được tách bằng biểu thức chính quy `_CLAUSE_SPLIT_RE` dựa trên mẫu "Điều" kèm số thứ tự, đồng thời trích xuất tiêu đề và nội dung tương ứng. Phương pháp này đảm bảo độ tin cậy cho dữ liệu có cấu trúc sẵn trong khi vẫn tận dụng khả năng của mô hình ngôn ngữ cho các trường hợp phức tạp.

---

## 3.7.4 Đánh giá rủi ro điều khoản với truy xuất pháp lý

### Figure

Hình 3.4 Quy trình đánh giá rủi ro từng điều khoản dựa trên truy xuất văn bản pháp luật

### Source Files

- `app/agents/risk_flagger.py`
- `app/vectorstore/retriever.py`
- `app/vectorstore/faiss_store.py`
- `app/core/prompts.py`

### Code

```python
# app/agents/risk_flagger.py — Per-clause evaluation with legal RAG
def evaluate_clause(clause: Clause, provider: str = DEFAULT_PROVIDER) -> Optional[RiskItem]:
    clause_ref = f"Điều {clause.clause_number}"
    query = f"{clause.title or ''} {clause.summary}".strip()
    legal_docs = retrieve_legal(query, k=3)

    if not legal_docs:
        return RiskItem(
            clause_ref=clause_ref,
            issue="Không tìm thấy căn cứ pháp luật đủ liên quan trong kho dữ liệu để đối chiếu điều khoản này.",
            severity="warning",
            legal_basis=None,
            recommendation="Cần luật sư rà soát thủ công do thiếu dữ liệu pháp luật tham chiếu cho điều khoản này.",
        )

    legal_context = "\n\n".join(d.page_content for d in legal_docs)
    prompt = CLAUSE_RISK_PROMPT.format(
        clause_number=clause.clause_number,
        clause_title_suffix=f" - {clause.title}" if clause.title else "",
        clause_text=clause.summary[:3000],
        legal_context=legal_context[:4000],
    )
    raw = chat_completion(prompt, provider=provider)
    result = parse_json_object(raw)
    if result is None:
        raw = chat_completion(prompt, provider=provider)
        result = parse_json_object(raw)
        if result is None:
            return None

    severity = result.get("severity", "ok")
    issue = (result.get("issue") or "").strip()
    if severity == "ok" and not issue:
        return None

    return RiskItem(clause_ref=clause_ref, issue=issue, severity=severity,
                    legal_basis=result.get("legal_basis"), recommendation=result.get("recommendation"))
```

```python
# app/vectorstore/retriever.py — Legal document retrieval
def retrieve_legal(query: str, k: int = 3) -> List[Document]:
    return get_legal_collection().similarity_search(query, k=k, min_score=SIMILARITY_THRESHOLD)
```

```python
# app/vectorstore/faiss_store.py — Similarity search with threshold
class FaissStore:
    def similarity_search(self, query: str, k: int = 5, where: dict | None = None, min_score: float | None = None) -> list[Document]:
        if self._store is None:
            return []
        kwargs = {"score_threshold": min_score} if min_score is not None else {}
        return self._store.similarity_search(query, k=k, filter=where, **kwargs)
```

### Explanation

Mỗi điều khoản được đánh giá riêng biệt thông qua cơ chế truy xuất tăng cường (RAG). Hàm `evaluate_clause` xây dựng truy vấn từ tiêu đề và nội dung tóm tắt của điều khoản, sau đó truy xuất tối đa ba văn bản pháp luật liên quan từ FAISS vector store với ngưỡng tương đồng tối thiểu 0,6. Nếu không tìm thấy văn bản pháp luật đủ liên quan, hệ thống trả về cảnh báo cần rà soát thủ công thay vì để mô hình ngôn ngữ tự phỏng đoán. Nếu có cơ sở pháp lý, prompt đánh giá rủi ro được định dạng và gửi đến Gemini; kết quả JSON được phân tích và đóng gói thành đối tượng `RiskItem` với mức độ nghiêm trọng, cơ sở pháp lý và đề xuất xử lý. Quy trình này đại diện cho cốt lõi của chức năng phân tích tuân thủ pháp luật của hệ thống.

---

## 3.7.5 Phối hợp đa tác tử phân tích hợp đồng

### Figure

Hình 3.5 Quy trình phối hợp đa tác tử phân tích hợp đồng với mô hình luồng rẽ nhánh

### Source Files

- `app/agents/workflow.py`
- `app/agents/checkpointer.py`

### Code

```python
# app/agents/workflow.py — LangGraph multi-agent orchestrator
class AnalysisState(TypedDict):
    contract_text: str
    contract_id: str
    provider: str
    analysis: ContractAnalysis
    risks: Annotated[List[RiskItem], operator.add]

class ClauseState(TypedDict):
    clause: Clause
    contract_id: str
    provider: str

async def _extract_node(state: AnalysisState) -> dict:
    try:
        analysis = await asyncio.to_thread(parse_contract, state["contract_text"], state["contract_id"], state["provider"])
    except Exception as e:
        analysis = ContractAnalysis(contract_id=state["contract_id"])
    return {"analysis": analysis}

def _fan_out_clauses(state: AnalysisState):
    clauses = state["analysis"].clauses
    if not clauses:
        return "aggregate"
    return [Send("judge_clause", {"clause": c, "contract_id": state["contract_id"], "provider": state["provider"]}) for c in clauses]

async def _judge_clause_node(state: ClauseState) -> dict:
    try:
        risk = await asyncio.to_thread(evaluate_clause, state["clause"], state["provider"])
        return {"risks": [risk] if risk else []}
    except Exception:
        return {"risks": []}

def _aggregate_node(state: AnalysisState) -> dict:
    return {}

_graph = StateGraph(AnalysisState)
_graph.add_node("extract", _extract_node)
_graph.add_node("judge_clause", _judge_clause_node)
_graph.add_node("aggregate", _aggregate_node)
_graph.add_edge(START, "extract")
_graph.add_conditional_edges("extract", _fan_out_clauses, ["judge_clause", "aggregate"])
_graph.add_edge("judge_clause", "aggregate")
_graph.add_edge("aggregate", END)
_compiled_graph = _graph.compile()

async def run_analysis_workflow(contract_text: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> Tuple[ContractAnalysis, List[RiskItem]]:
    result = await _compiled_graph.ainvoke(
        {"contract_text": contract_text, "contract_id": contract_id, "provider": provider, "risks": []},
        config={"max_concurrency": 4},
    )
    return result["analysis"], result["risks"]
```

### Explanation

Quy trình phối hợp đa tác tử được xây dựng trên nền tảng LangGraph với ba nút xử lý chính. Nút `extract` gọi hàm trích xuất thông tin hợp đồng; sau đó nút điều kiện `_fan_out_clauses` kiểm tra danh sách điều khoản và tạo các tác vụ `Send` riêng cho từng điều khoản đến nút `judge_clause`. Các nút `judge_clause` được thực thi song song với tối đa bốn luồng đồng thời nhằm tránh vượt quá giới hạn tốc độ của nhà cung cấp mô hình ngôn ngữ. Kết quả đánh giá rủi ro từ các nhánh được gộp vào danh sách `risks` thông qua toán tử `operator.add`. Kiến trúc rẽ nhánh này cho phép xử lý hợp đồng với số lượng điều khoản bất kỳ một cách hiệu quả và có khả năng mở rộng.

---

## 3.7.6 Hội thoại hỏi đáp về hợp đồng và pháp luật

### Figure

Hình 3.6 Quy trình hội thoại hỏi đáp với truy xuất ngữ cảnh và kiểm tra trích dẫn

### Source Files

- `app/agents/qa_agent.py`
- `app/vectorstore/retriever.py`
- `app/core/prompts.py`

### Code

```python
# app/agents/qa_agent.py — QA agent with retrieval, memory, and citation validation
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

async def _retrieve_node(state: QAState) -> dict:
    question = state["messages"][-1].content
    contract_docs = retrieve_contract(question, state["contract_id"])
    legal_docs = retrieve_legal(question, k=3)
    if not contract_docs and not legal_docs:
        return {"_has_context": False}
    return {
        "_has_context": True,
        "_contract_context": "\n\n".join(f"[Điều {d.metadata.get('clause_number', '?')}] {d.page_content}" for d in contract_docs)[:8000],
        "_legal_context": "\n\n".join(
            f"[{d.metadata.get('doc_number') or d.metadata.get('title') or 'Nguồn'}] {d.page_content}" for d in legal_docs)[:3000],
        "_valid_clause_numbers": [d.metadata.get("clause_number") for d in contract_docs],
    }

async def _generate_node(state: QAState) -> dict:
    question = state["messages"][-1].content
    history = trim_messages(state["messages"][:-1], max_tokens=2000, strategy="last")
    human_content = QA_HUMAN_TEMPLATE.format(
        contract_context=state["_contract_context"], legal_context=state["_legal_context"], question=question)
    prompt_messages = [SystemMessage(content=QA_SYSTEM_PROMPT), *history, HumanMessage(content=human_content)]
    chat_model = get_chat_model(state.get("provider", DEFAULT_PROVIDER))
    raw = (await chat_model.ainvoke(prompt_messages)).content
    result = parse_json_object(raw)
    if result is None:
        raw = (await chat_model.ainvoke(prompt_messages)).content
        result = parse_json_object(raw)
    if result is None:
        return {"messages": [AIMessage(content="Hệ thống gặp lỗi khi xử lý câu trả lời.")], "source_clauses": [], "needs_clarification": False}
    if result.get("needs_clarification"):
        return {"messages": [AIMessage(content=result.get("clarification_question"))], "source_clauses": [], "needs_clarification": True}
    valid_clause_numbers = set(state.get("_valid_clause_numbers") or [])
    cited_clauses = result.get("cited_clauses") or []
    verified_clauses = [c for c in cited_clauses if c in valid_clause_numbers]
    answer = (result.get("answer") or "").strip()
    ai_message = AIMessage(content=answer, additional_kwargs={"source_clauses": verified_clauses, "needs_clarification": False})
    return {"messages": [ai_message], "source_clauses": verified_clauses, "needs_clarification": False}

async def answer_question(question: str, contract_id: str, provider: str = DEFAULT_PROVIDER) -> ChatResponse:
    graph = _get_graph()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)], "contract_id": contract_id, "provider": provider},
        config={"configurable": {"thread_id": contract_id}},
    )
    return ChatResponse(answer=result["messages"][-1].content, source_clauses=result.get("source_clauses", []), contract_id=contract_id, needs_clarification=result.get("needs_clarification", False))
```

### Explanation

Tác tử hội thoại QA sử dụng LangGraph với ba nút: truy xuất, từ chối và sinh câu trả lời. Khi người dùng gửi câu hỏi, nút `_retrieve_node` truy xuất các đoạn hợp đồng và văn bản pháp luật liên quan từ FAISS vector store. Nếu không tìm thấy ngữ cảnh, luồng được chuyển đến nút từ chối trả lời. Nếu có ngữ cảnh, lịch sử hội thoại được cắt bớt theo ngưỡng token và kết hợp với ngữ cảnh truy xuất để tạo prompt cho Gemini. Kết quả trả về được phân tích JSON; nếu cần làm rõ thêm, tác tử trả về câu hỏi phụ. Các trích dẫn điều khoản do mô hình sinh ra được kiểm tra chéo với danh sách điều khoản thực tế từ kết quả truy xuất, loại bỏ các trích dẫn không hợp lệ để chống hiện tượng "ảo giác" của mô hình ngôn ngữ.

---

## 3.7.7 Tương tác API giữa giao diện và máy chủ

### Figure

Hình 3.7 Quy trình tương tác API giữa giao diện người dùng và máy chủ xử lý

### Source Files

- `frontend/src/api.js`
- `frontend/src/components/ChatTab.jsx`
- `app/api/routes.py`

### Code

```js
// frontend/src/api.js — API client layer
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try { const data = await res.json(); detail = data.detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadContract(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/upload`, {
    method: "POST", headers: await authHeaders(), body: formData,
  });
  return handleResponse(res);
}

export async function analyzeContract(contractId, provider, force = false) {
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ contract_id: contractId, provider, force }),
  });
  return handleResponse(res);
}

export async function chatWithContract(contractId, question, provider) {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ contract_id: contractId, question, provider }),
  });
  return handleResponse(res);
}
```

```python
# app/api/routes.py — Backend API routes
router = APIRouter(prefix="/api/v1")

class AnalyzeRequest(BaseModel):
    contract_id: str
    provider: str = DEFAULT_PROVIDER
    force: bool = False

class ChatRequest(BaseModel):
    contract_id: str
    question: str
    provider: str = DEFAULT_PROVIDER

@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    try:
        return await upload_contract(file, user_id)
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, user_id: str = Depends(get_current_user_id)):
    try:
        return await analyze_contract(req.contract_id, user_id, req.provider, req.force)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:
        return await chat_with_contract(req.contract_id, req.question, user_id, req.provider)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
```

### Explanation

Lớp tương tác API phía giao diện đóng gói tất cả các yêu cầu HTTP đến máy chủ FastAPI thông qua các hàm chuyên biệt. Mỗi hàm xây dựng request với phương thức, header và body tương ứng: `uploadContract` gửi tệp dưới dạng multipart/form-data, `analyzeContract` và `chatWithContract` gửi dữ liệu JSON. Hàm `authHeaders` tự động đính kèm mã thông báo JWT từ phiên Supabase vào mọi yêu cầu. Phản hồi được xử lý qua `handleResponse`, trích xuất thông báo lỗi chi tiết từ thân phản hồi nếu có. Phía máy chủ, các route API sử dụng dependency injection `Depends(get_current_user_id)` để bảo vệ endpoint; mọi ngoại lệ nghiệp vụ được chuyển đổi thành mã lỗi HTTP 404 hoặc 500 tương ứng. Kiến trúc này đảm bảo sự tách biệt rõ ràng giữa lớp giao diện, lớp API và lớp xử lý nghiệp vụ.
