# ContractLens — Luồng thao tác người dùng trên UI

## 1. Sequence Diagram (UML) — Luồng chính

```
┌──────┐          ┌──────────────┐          ┌──────────────┐          ┌─────────────┐          ┌───────────────┐
│ User │          │  LoginScreen │          │ ContractList │          │ UploadScreen │          │ AnalysisResult│
│      │          │              │          │   Screen     │          │              │          │ (5 tabs)      │
└──┬───┘          └──────┬───────┘          └──────┬───────┘          └──────┬───────┘          └───────┬───────┘
   │                     │                         │                         │                          │
   │  Nhập email + pass  │                         │                         │                          │
   │────────────────────>│                         │                         │                          │
   │                     │──► POST /auth/v1/signin│                         │                          │
   │                     │    (Supabase Auth)      │                         │                          │
   │  ◄─── token/session │                         │                         │                          │
   │<────────────────────│                         │                         │                          │
   │                     │                         │                         │                          │
   │                     │         ┌───────────────┐                         │                          │
   │                     │         │  state: list  │                         │                          │
   │                     │         └───────┬───────┘                         │                          │
   │   Hiển thị danh     │                 │                                 │                          │
   │   sách hợp đồng     │                 │ GET /api/v1/contracts          │                          │
   │<────────────────────┼─────────────────│ (Bearer JWT)                    │                          │
   │                     │                 │                                 │                          │
   │  ◄─── [ {filename, date, status}, ... ]                                │                          │
   │                     │                 │                                 │                          │
   │                     │                 │                                 │                          │
   │  Click "Tải mới"    │                 │                                 │                          │
   │─────────────────────────────────────> │  state: upload                  │                          │
   │                                       │────────────────────────────────>│                          │
   │                                       │                                 │                          │
   │  Chọn file (docx/pdf/png) + chọn model│                                 │                          │
   │───────────────────────────────────────────────────────────────────────>│                          │
   │                                       │                                 │ POST /api/v1/upload      │
   │                                       │                                 │──► FastAPI               │
   │  ◄─── { contract_id, filename, status }                                │                          │
   │                                       │                                 │                          │
   │  Click "Phân tích ngay"              │                                 │                          │
   │───────────────────────────────────────────────────────────────────────>│ POST /api/v1/analyze     │
   │                                       │                                 │──► LangGraph Workflow    │
   │                                       │                                 │    (extract→judge→agg)  │
   │                                       │                                 │                          │
   │  ◄─── analysis + risks               │                                 │                          │
   │                                       │  state: result                  │                          │
   │                                       │─────────────────────────────────────────────────────────>│
   │                                       │                                 │                          │
   │  Hiển thị Dashboard 5 tabs           │                                 │                          │
   │<─────────────────────────────────────────────────────────────────────────────────────────────────│
   │                                       │                                 │                          │
   │  ┌── Tab "Tổng quan" ───────────────────────────────────────────────────────────────────────────│
   │  │ Nhận: Loại HĐ, giá trị, thời hạn, bên A/B, luật áp dụng, giải quyết tranh chấp,   │
   │  │       risk score (số critical + warning)                                                  │
   │  │                                                                                          │
   │  ├── Tab "Sai luật" ────────────────────────────────────────────────────────────────────────│
   │  │ Nhận: Danh sách điều khoản vi phạm pháp luật (severity=critical), mỗi card gồm:        │
   │  │       vấn đề + căn cứ pháp lý + đề xuất AI                                              │
   │  │                                                                                          │
   │  ├── Tab "Điểm cần chú ý" ──────────────────────────────────────────────────────────────────│
   │  │ Nhận: Danh sách điều khoản bất lợi/không rõ (severity=warning), mỗi card gồm:           │
   │  │       vấn đề + căn cứ pháp lý + đề xuất AI                                              │
   │  │                                                                                          │
   │  ├── Tab "Chi tiết điều khoản" ─────────────────────────────────────────────────────────────│
   │  │ Nhận: Toàn bộ điều khoản đã trích xuất (số điều, tiêu đề, nội dung tóm tắt)             │
   │  │                                                                                          │
   │  └── Tab "Hỏi đáp" ─────────────────────────────────────────────────────────────────────────│
   │      User: gõ câu hỏi tự nhiên về hợp đồng                                                  │
   │                      ───────────────────────────────────────────────────────────────────────│
   │                      POST /api/v1/chat ──► LangGraph QA Agent                               │
   │                           (RAG: FAISS contract + legal KB → Gemini)                         │
   │      Nhận: Câu trả lời tiếng Việt + cited_clauses (số điều khoản được dẫn nguồn)            │
   │                                                                                             │
```

---

## 2. Activity Diagram — User Journey

```
                         ┌─────────────────┐
                         │   Mở Ứng Dụng   │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Login Screen   │
                         │  Nhập: email,   │
                         │  password       │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │ Đăng nhập   │ Đăng ký     │
                    │ (signIn)    │ (signUp)    │
                    └──────┬──────┴──────┬──────┘
                           │             │
                           └──────┬──────┘
                                  │
                                  ▼
                    ┌──────────────────────┐
                    │ Contract List Screen │
                    │ Nhận: danh sách HĐ   │
                    │ [{name,date,status}] │
                    └──────────┬───────────┘
                               │
               ┌───────────────┼────────────────┐
               │               │                │
               ▼               ▼                │
    ┌──────────────────┐  ┌─────────────┐       │
    │ Click "Tải mới"  │  │ Click 1 HĐ  │       │
    │ (state: upload)  │  │ đã phân tích│       │
    └────────┬─────────┘  └──────┬──────┘       │
             │                   │               │
             ▼                   │               │
    ┌──────────────────┐         │               │
    │ Upload Screen    │         │               │
    │ Input: file      │         │               │
    │ (.docx/.pdf/img) │         │               │
    │ + chọn model AI  │         │               │
    │ Nhận: contract_id│         │               │
    └────────┬─────────┘         │               │
             │                   │               │
             │ Click "Phân tích" │               │
             │ POST /analyze    │               │
             │ (đợi ~30-60s)    │               │
             │                   │               │
             └─────────┬─────────┘               │
                       │                         │
                       ▼                         ▼
              ┌─────────────────────────────────────┐
              │      Analysis Result Screen         │
              │  ┌─────────────────────────────┐    │
              │  │ Sidebar navigation          │    │
              │  │ ☰ Tổng quan                 │    │
              │  │ ⚠ Sai luật (N)              │    │
              │  │ ⚡ Điểm cần chú ý (N)       │    │
              │  │ 📋 Chi tiết điều khoản      │    │
              │  │ 💬 Hỏi đáp                  │    │
              │  │ ◀  Quay lại danh sách       │    │
              │  └─────────────────────────────┘    │
              └─────────────────────────────────────┘
```

---

## 3. State Machine — Các màn hình UI

```
                     ┌──────────┐
                     │  LOADING │
                     └────┬─────┘
                          │
              ┌───────────┴───────────┐
              │ checkSupabaseSession  │
              └───────────┬───────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
          có session              không session
              │                       │
              ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │ CONTRACT_LIST    │    │    LOGIN         │
    │ screen           │◄───│    screen        │
    └────────┬─────────┘    └──────────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        │
┌────────┐ ┌──────────────────┐
│ UPLOAD │ │ ANALYSIS_RESULT  │
│ screen │ │ screen (5 tabs)  │
└───┬────┘ └──────────────────┘
    │              ▲
    │              │
    └──────────────┘
    (sau khi phân tích xong)
```

---

## 4. Tổng hợp Input / Output của User

| # | Bước | User thao tác gì? | User nhận được gì? |
|---|------|-------------------|---------------------|
| 1 | **Đăng nhập** | Nhập email + password, click Sign In | Session token → chuyển sang danh sách hợp đồng |
| 2 | **Danh sách HĐ** | Xem danh sách, chọn HĐ cũ hoặc click "Tải hợp đồng mới" | Cards hiển thị: tên file, ngày upload, trạng thái (analyzed / parsed / uploaded) |
| 3 | **Upload** | Kéo/thả hoặc chọn file (.docx / .pdf / .png / .jpg) + chọn model AI | `contract_id` + filename + trạng thái "parsed" |
| 4 | **Phân tích** | Click nút "Phân tích ngay" | Hiển thị loading → chuyển sang dashboard kết quả |
| 5 | **Tab: Tổng quan** | Click tab "Tổng quan" | Card tổng hợp: loại hợp đồng, giá trị, thời hạn, bên A/B (tên, MST, địa chỉ, đại diện), luật áp dụng, cơ quan giải quyết tranh chấp, risk score (số lượng critical + warning) |
| 6 | **Tab: Sai luật** | Click tab "Sai luật" | Danh sách cards **đỏ**: các điều khoản vi phạm pháp luật. Mỗi card hiển thị: vấn đề vi phạm, căn cứ pháp lý, đề xuất từ AI |
| 7 | **Tab: Điểm cần chú ý** | Click tab "Điểm cần chú ý" | Danh sách cards **vàng**: các điều khoản bất lợi/không rõ ràng. Mỗi card hiển thị: vấn đề, căn cứ pháp lý, đề xuất từ AI |
| 8 | **Tab: Chi tiết điều khoản** | Click tab "Chi tiết điều khoản" | Toàn bộ điều khoản đã trích xuất: số điều + tiêu đề + nội dung |
| 9 | **Tab: Hỏi đáp** | Gõ câu hỏi tự nhiên bằng tiếng Việt (vd: "Điều khoản phạt vi phạm là gì?") | AI trả lời + dẫn nguồn cụ thể số điều khoản trong hợp đồng. Lịch sử chat được lưu và hiển thị lại khi mở lại HĐ |

---

## 5. Backend API — Giao tiếp Frontend ↔ Backend

| Method | Endpoint | Auth | Input | Output |
|--------|----------|------|-------|--------|
| `POST` | `/auth/v1/signin` | Không | `{email, password}` | `{access_token, user}` |
| `GET` | `/api/v1/contracts` | Bearer JWT | — | `[{contract_id, filename, upload_date, status}]` |
| `POST` | `/api/v1/upload` | Bearer JWT | `FormData { file, model }` | `{contract_id, filename, status}` |
| `POST` | `/api/v1/analyze` | Bearer JWT | `{contract_id, model}` | `{analysis: ContractAnalysis, risks: RiskItem[]}` |
| `POST` | `/api/v1/chat` | Bearer JWT | `{contract_id, message}` | `{answer, cited_clauses, needs_clarification?}` |
| `GET` | `/api/v1/chat/{contract_id}/history` | Bearer JWT | — | `[{role, content, cited_clauses}]` |

---

## 6. Luồng xử lý AI phía Backend

```
User upload file
      │
      ▼
┌─────────────────┐
│ 1. Trích xuất   │  DOCX → python-docx
│    văn bản       │  PDF  → pdfplumber
│                  │  Ảnh  → Gemini OCR
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Chunk theo   │  Regex "Điều N" / "Khoản N"
│    điều khoản   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Lưu FAISS    │  Embeddings → SBERT Vietnamese
│    vector store │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 4. LangGraph Workflow (song song)       │
│                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────┐│
│  │ EXTRACT   │───▶│  JUDGE   │───▶│ AGG  ││
│  │ (rule)    │    │ (LLM+RAG)│    │      ││
│  │           │    │ x4 concurrency│      ││
│  │ Tách:     │    │          │    │ Gộp  ││
│  │ - loại HĐ │    │ Per clause:│   │ kết  ││
│  │ - bên A/B │    │ 1. search  │   │ quả  ││
│  │ - ngày    │    │    legal KB│      ││
│  │ - tiền    │    │ 2. Gemini  │      ││
│  │ - clauses │    │    judge   │      ││
│  │ - ...     │    │ 3. return  │      ││
│  └──────────┘    │    RiskItem│      ││
│                   └──────────┘    └──────┘│
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 5. Cache vào PG │  analysis + risks (JSONB)
└─────────────────┘
```
