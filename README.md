# ContractLens - Hệ thống AI rà soát hợp đồng tiếng Việt

## Yêu cầu
- Python 3.10+
- Gemini API Key (tại aistudio.google.com)

## Cài đặt & Chạy

```bash
pip install -r requirements.txt
cp .env.example .env  # Thêm GEMINI_API_KEY, DATABASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY của bạn
uvicorn app.main:app --reload --port 8000
```

## Cấu trúc mã nguồn

```
app/
  main.py            # Khởi tạo FastAPI app, mount static frontend
  api/routes.py       # Định nghĩa endpoint (/api/v1/...)
  core/               # config, database, auth, prompts
  schemas/            # Pydantic schema (contract.py)
  agents/             # clause_parser, risk_flagger, qa_agent, workflow, llm_client
  document/           # parser, chunker, file_handler
  vectorstore/        # FAISS store, embeddings, retriever
  knowledge_base/      # nạp dữ liệu luật vào vector store
  services/           # contract_service (orchestrator) + barrel export
  helpers/            # tiện ích dùng chung
scripts/              # script vận hành (nạp KB luật, ...)
tests/                # unit + integration test
```

Mở trình duyệt tại `http://localhost:8000`

## API Endpoints
- `POST /api/v1/upload` - Tải lên hợp đồng (.doc, .docx, .pdf)
- `POST /api/v1/analyze` - Phân tích rủi ro pháp lý
- `POST /api/v1/chat` - Hỏi đáp về hợp đồng
- `GET /health` - Kiểm tra trạng thái

## Công nghệ
- **FastAPI** - Backend framework
- **Gemini 2.5 Flash** (LangChain) - AI phân tích hợp đồng
- **LangGraph** - Điều phối multi-agent (Extractor → Judge theo từng điều khoản)
- **FAISS (LangChain) + Vietnamese-SBERT** - RAG và tìm kiếm ngữ nghĩa
- **PostgreSQL (Supabase)** - Lưu trữ dữ liệu
- **Supabase Auth** - Xác thực người dùng
