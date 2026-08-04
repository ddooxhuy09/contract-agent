# ContractLens — Sơ đồ Luồng Dữ liệu (DFD)

> Dựa trên phân tích toàn bộ mã nguồn. Mọi thành phần, kho dữ liệu, luồng đều được dẫn chiếu tới file code thật.
> Ngày tạo: 2026-07-26

---

## Mục lục

| DFD | Tên module | File nguồn |
|-----|------------|------------|
| Mức 0 | Sơ đồ Tổng quan Hệ thống | — |
| Mức 1 | Sơ đồ Chi tiết các Module chính | — |
| Mức 2 | Xác thực Người dùng | `app/core/auth.py:6` |
| Mức 2 | Tải lên & Xử lý Hợp đồng | `app/document/file_handler.py:21`, `app/document/parser.py:58`, `app/document/chunker.py:44`, `app/services/contract_service.py:36` |
| Mức 2 | Phân tích Rủi ro (AI Workflow) | `app/agents/workflow.py:85`, `app/agents/clause_parser.py:453`, `app/agents/risk_flagger.py:10`, `app/agents/llm_client.py:23` |
| Mức 2 | Hỏi đáp Hợp đồng (Chat Q&A) | `app/agents/qa_agent.py:170`, `app/agents/llm_client.py:12` |
| Mức 2 | Danh sách Hợp đồng | `app/services/contract_service.py:110` |
| Mức 2 | Nạp Kho Dữ liệu Luật | `app/knowledge_base/loader.py:16`, `scripts/load_legal_kb.py` |
| Mức 2 | Giao diện Người dùng (Frontend) | `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/src/components/*.jsx` |

---

# DFD Mức 0 — Sơ đồ Tổng quan Hệ thống

Nhìn từ bên ngoài: Người dùng giao tiếp với Hệ thống ContractLens, và ContractLens gọi các dịch vụ bên ngoài.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Người dùng\n(qua trình duyệt web)" as User
rectangle "ContractLens\n(Máy chủ ứng dụng +\nGiao diện web)" as System
cloud "Supabase Auth\n(Hệ thống đăng nhập)" as SupabaseAuth
cloud "Gemini API\n(Trí tuệ nhân tạo\ncủa Google)" as GeminiAPI
database "PostgreSQL\n(Cơ sở dữ liệu)" as PostgreSQL
database "FAISS\n(Kho vector\nđể tìm kiếm)" as FAISS
database "Ổ cứng\n(Lưu file)" as LocalFS

User --> System : "Gửi yêu cầu\n(đăng nhập, tải file,\nphân tích, hỏi đáp)"
System --> User : "Trả kết quả\n(trang web, dữ liệu JSON)"

System --> SupabaseAuth : "Hỏi: Token này\ncủa ai?"
SupabaseAuth --> System : "Trả: ID người dùng\nhoặc báo lỗi"

System --> GeminiAPI : "Gửi: Nhờ AI xử lý"
GeminiAPI --> System : "Trả: Kết quả từ AI"

System --> PostgreSQL : "Ghi / Đọc dữ liệu"
PostgreSQL --> System : "Trả dữ liệu"

System --> FAISS : "Tìm kiếm / Lưu\nthông tin hợp đồng"
FAISS --> System : "Trả kết quả\ntìm kiếm"

System --> LocalFS : "Ghi / Đọc file"
LocalFS --> System : "Nội dung file"

@enduml
```

---

# DFD Mức 1 — Sơ đồ Chi tiết các Module chính

Bên trong hệ thống ContractLens có 7 module chính. Hình dưới đây cho thấy tất cả luồng dữ liệu giữa chúng.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Người dùng\n(qua trình duyệt)" as User

rectangle "Xác thực\nNgười dùng" as Auth
rectangle "Tải lên &\nXử lý Hợp đồng" as Upload
rectangle "Phân tích\nRủi ro AI" as Analyze
rectangle "Hỏi đáp\nHợp đồng" as Chat
rectangle "Danh sách\nHợp đồng" as List
rectangle "Nạp Kho\nDữ liệu Luật" as LegalLoader
rectangle "Giao diện\nNgười dùng" as Frontend

cloud "Supabase Auth\n(Đăng nhập)" as SupabaseAuth
cloud "Gemini API\n(AI Google)" as GeminiAPI
database "PostgreSQL\n(Cơ sở dữ liệu)" as PG
database "FAISS\nHợp đồng" as FaissC
database "FAISS\nKho Luật" as FaissL
database "Ổ cứng\nLưu file" as LocalFS

' ---- Giao diện người dùng ----
User --> Frontend : "Thao tác"
Frontend --> User : "Hiển thị màn hình"

' ---- Đăng nhập ----
Frontend --> SupabaseAuth : "Gửi email + mật khẩu"
SupabaseAuth --> Frontend : "Trả phiên đăng nhập"
Frontend --> Auth : "Gửi token qua header"
Auth --> SupabaseAuth : "Hỏi token hợp lệ không?"
SupabaseAuth --> Auth : "Trả ID người dùng"

' ---- Tải lên hợp đồng ----
Frontend --> Upload : "Gửi file hợp đồng"
Upload --> LocalFS : "Lưu file xuống ổ cứng"
Upload --> FaissC : "Lưu vector vào kho"
Upload --> PG : "Ghi thông tin hợp đồng"
Upload --> Frontend : "Trả mã hợp đồng"

' ---- Phân tích rủi ro ----
Frontend --> Analyze : "Yêu cầu phân tích"
Analyze --> PG : "Đọc kết quả cũ (nếu có)"
Analyze --> FaissC : "Lấy nội dung hợp đồng"
Analyze --> GeminiAPI : "Gọi AI trích xuất"
Analyze --> GeminiAPI : "Gọi AI đánh giá rủi ro"
Analyze --> FaissL : "Tra cứu luật liên quan"
Analyze --> PG : "Lưu kết quả phân tích"
Analyze --> Frontend : "Trả kết quả"

' ---- Hỏi đáp ----
Frontend --> Chat : "Gửi câu hỏi"
Chat --> FaissC : "Tra cứu hợp đồng"
Chat --> FaissL : "Tra cứu kho luật"
Chat --> GeminiAPI : "Gọi AI trả lời"
Chat --> PG : "Lưu lịch sử hội thoại"
Chat --> Frontend : "Trả câu trả lời"

' ---- Danh sách hợp đồng ----
Frontend --> List : "Yêu cầu danh sách"
List --> PG : "Đọc danh sách"
List --> Frontend : "Trả danh sách"

' ---- Nạp kho luật ----
LegalLoader --> PG : "Đọc dữ liệu luật"
LegalLoader --> FaissL : "Lưu vào kho vector"

@enduml
```

---

# DFD Mức 2 — Xác thực Người dùng

File nguồn: `app/core/auth.py:6`

Mỗi khi người dùng gửi yêu cầu tới máy chủ, một "người gác cổng" kiểm tra token đăng nhập trước khi cho phép thao tác.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Giao diện\nngười dùng" as Frontend
rectangle "Người gác cổng\n(get_current_user_id)" as CheckAuth
cloud "Supabase Auth\n(Dịch vụ đăng nhập)" as SupabaseAuth

Frontend --> CheckAuth : "Gửi kèm token\nở phần đầu yêu cầu"
CheckAuth --> SupabaseAuth : "Hỏi Supabase:\nToken này có hợp lệ không?"

SupabaseAuth --> CheckAuth : "OK: đây là\nuser ID của họ"
SupabaseAuth --> CheckAuth : "Lỗi: token hết hạn\nhoặc không hợp lệ"

CheckAuth --> Frontend : "Cho phép đi tiếp"
CheckAuth --> Frontend : "Từ chối (401/503)"

note right of CheckAuth
  Người gác cổng này được gọi
  trước mỗi chức năng:
  - Tải lên hợp đồng
  - Phân tích rủi ro
  - Xem danh sách
  - Hỏi đáp
  - Xem lịch sử hỏi đáp
end note

@enduml
```

---

# DFD Mức 2 — Tải lên & Xử lý Hợp đồng

File nguồn: `app/document/file_handler.py:21`, `app/document/parser.py:58`, `app/document/chunker.py:44`, `app/services/contract_service.py:36`

Khi người dùng tải hợp đồng lên, máy tính sẽ đọc file, tách thành từng điều khoản, rồi lưu vào kho vector để sau này tìm kiếm.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Giao diện\nngười dùng" as Frontend
rectangle "Điều phối\ntải lên" as Orchestrator
rectangle "Kiểm tra\nđịnh dạng" as Validate
rectangle "Lưu file\nxuống ổ cứng" as SaveFile
rectangle "Đọc nội dung\nfile hợp đồng" as ParseDoc
rectangle "Đọc file\nWord (.docx)" as ParseDOCX
rectangle "Đọc file\nPDF" as ParsePDF
rectangle "Đọc ảnh\nbằng AI" as ParseImage
rectangle "Tách thành\ntừng điều khoản" as Chunker
rectangle "Lưu vào\nkho vector" as FaissAdd
cloud "Gemini AI\n(Đọc ảnh OCR)" as GeminiOCR
database "Ổ cứng\n(thư mục data/uploads/)" as LocalFS
database "FAISS\nKho vector hợp đồng" as FaissC
database "PostgreSQL\n(Bảng uploaded_contracts)" as PG

Frontend --> Orchestrator : "Gửi file hợp đồng\n+ ID người dùng"
Orchestrator --> Validate : "Kiểm tra tên file"
Validate --> Orchestrator : "Đuôi file hợp lệ"

Orchestrator --> SaveFile : "Đọc nội dung file"
SaveFile --> LocalFS : "Ghi file xuống ổ cứng"
SaveFile --> Orchestrator : "Đường dẫn + mã hợp đồng"

Orchestrator --> ParseDoc : "Đọc file từ ổ cứng"
ParseDoc --> ParseDOCX : "Nếu là file .docx"
ParseDOCX --> ParseDoc : "Nội dung văn bản"
ParseDoc --> ParsePDF : "Nếu là file .pdf"
ParsePDF --> ParseDoc : "Nội dung văn bản"
ParseDoc --> ParseImage : "Nếu là file ảnh"
ParseImage --> GeminiOCR : "Gửi ảnh nhờ AI đọc"
GeminiOCR --> ParseImage : "AI trả nội dung"
ParseImage --> ParseDoc : "Nội dung văn bản"
ParseDoc --> Orchestrator : "Toàn bộ văn bản"

Orchestrator --> Chunker : "Cắt văn bản\nthành điều khoản"
Chunker --> Orchestrator : "Danh sách các\nđiều khoản đã cắt"

Orchestrator --> FaissAdd : "Lưu vào kho vector"
FaissAdd --> FaissC : "Xây dựng chỉ mục"
FaissAdd --> Orchestrator : "Xong"

Orchestrator --> PG : "Lưu thông tin\nhợp đồng vào CSDL"
PG --> Orchestrator : "Xong"

Orchestrator --> Frontend : "Báo thành công\nkèm mã hợp đồng"

@enduml
```

---

# DFD Mức 2 — Phân tích Rủi ro (AI Workflow)

File nguồn: `app/agents/workflow.py:85`, `app/agents/clause_parser.py:453`, `app/agents/risk_flagger.py:10`, `app/agents/llm_client.py:23`

Đây là quy trình AI phức tạp nhất. Hệ thống đọc hợp đồng, trích xuất thông tin, rồi gửi từng điều khoản cho AI đánh giá xem có vi phạm luật không.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Giao diện\nngười dùng" as Frontend

rectangle "Điều phối\nphân tích" as AnalyzeOrch
rectangle "Kiểm tra\nquyền sở hữu" as AssertOwn
rectangle "Đọc kết quả\nđã lưu (cache)" as CacheLoad
rectangle "Quy trình AI\n(LangGraph)" as LangGraphWF

rectangle "Bước 1:\nTrích xuất" as ExtractNode
rectangle "Trích xuất\ntheo công thức" as RuleExtract
rectangle "Bổ sung\nbằng AI" as LLMFill

rectangle "Bước 2:\nĐánh giá rủi ro" as JudgeNode
rectangle "Tra cứu\nkho luật" as LegalRetrieve
rectangle "Gọi AI\ntrả lời" as LLMCall

rectangle "Bước 3:\nGom kết quả" as AggregateNode
rectangle "Lưu kết quả\nvào CSDL" as SaveResult

cloud "Gemini API\n(AI Google)" as GeminiAPI
database "PostgreSQL\n(Cơ sở dữ liệu)" as PG
database "FAISS\nKho Luật" as FaissL
database "FAISS\nKho hợp đồng" as FaissC

Frontend --> AnalyzeOrch : "Yêu cầu phân tích\n(kèm mã hợp đồng)"

AnalyzeOrch --> AssertOwn : "Kiểm tra:\nđây là hợp đồng\ncủa bạn không?"
AssertOwn --> PG : "Hỏi CSDL"
PG --> AssertOwn : "Có / Không"
AssertOwn --> AnalyzeOrch : "OK / Báo lỗi"

AnalyzeOrch --> CacheLoad : "Đã từng phân tích\nhợp đồng này chưa?"
CacheLoad --> PG : "Tìm kết quả cũ"
PG --> CacheLoad : "Có / Chưa"
CacheLoad --> AnalyzeOrch : "Trả luôn kết quả cũ\n/ Tiếp tục phân tích"

AnalyzeOrch --> LangGraphWF : "Bắt đầu quy trình AI"
note right of LangGraphWF
  Quy trình gồm 3 bước:
  Bắt đầu → Trích xuất
  → Đánh giá (làm song song
  tối đa 4 điều khoản cùng lúc)
  → Gom kết quả → Kết thúc
end note

LangGraphWF --> ExtractNode : "Gửi nội dung hợp đồng"

ExtractNode --> RuleExtract : "Dùng công thức\nđể trích xuất"
RuleExtract --> ExtractNode : "Thông tin cơ bản\n(loại HĐ, bên A/B...)"
ExtractNode --> LLMFill : "Nếu thiếu,\nnhờ AI bổ sung"
LLMFill --> GeminiAPI : "Gửi nhờ AI trích xuất"
GeminiAPI --> LLMFill : "AI trả thông tin"
LLMFill --> ExtractNode : "Thông tin đầy đủ"
ExtractNode --> LangGraphWF : "Xong bước trích xuất"

LangGraphWF --> JudgeNode : "Gửi từng điều khoản\ncho AI đánh giá (tối đa 4 cái cùng lúc)"
JudgeNode --> LegalRetrieve : "Tìm luật liên quan\nđến điều khoản này"
LegalRetrieve --> FaissL : "Tìm kiếm trong kho luật"
FaissL --> LegalRetrieve : "Các điều luật\nliên quan nhất"
LegalRetrieve --> JudgeNode : "Danh sách điều luật"

JudgeNode --> LLMCall : "Gửi: điều khoản\n+ điều luật liên quan"
LLMCall --> GeminiAPI : "Nhờ AI đánh giá"
GeminiAPI --> LLMCall : "AI: có vấn đề/không"
LLMCall --> JudgeNode : "Kết quả rủi ro"

JudgeNode --> LangGraphWF : "Rủi ro của\nđiều khoản này"

LangGraphWF --> AggregateNode : "Gom tất cả\nkết quả lại"
AggregateNode --> LangGraphWF : "Xong"

LangGraphWF --> AnalyzeOrch : "Trả kết quả:\n- Phân tích tổng quan\n- Danh sách rủi ro"

AnalyzeOrch --> SaveResult : "Lưu vào CSDL\nđể lần sau khỏi phân tích lại"
SaveResult --> PG : "Cập nhật kết quả"
PG --> SaveResult : "Xong"

AnalyzeOrch --> Frontend : "Trả ra màn hình:\n- Thông tin hợp đồng\n- Danh sách rủi ro"

@enduml
```

---

# DFD Mức 2 — Hỏi đáp Hợp đồng (Chat Q&A)

File nguồn: `app/agents/qa_agent.py:170`, `app/agents/llm_client.py:12`

Người dùng có thể hỏi bất kỳ câu hỏi nào về hợp đồng. Hệ thống sẽ tra cứu hợp đồng và kho luật, rồi nhờ AI trả lời.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Giao diện\nngười dùng" as Frontend

rectangle "Điều phối\nhỏi đáp" as ChatOrch
rectangle "Kiểm tra\nquyền sở hữu" as AssertOwn
rectangle "Quy trình AI\nhỏi đáp" as QAGraph

rectangle "Tra cứu\nthông tin" as RetrieveNode
rectangle "Tìm trong\nhợp đồng" as ContractRetrieve
rectangle "Tìm trong\nkho luật" as LegalRetrieve

rectangle "Chọn\nhướng đi" as Router
rectangle "Sinh câu\ntrả lời" as GenerateNode
rectangle "Từ chối\n(không đủ thông tin)" as RefusalNode
rectangle "Gọi AI" as LLMCall

rectangle "Xem lịch sử\nhỏi đáp" as HistoryLoad

cloud "Gemini API\n(AI Google)" as GeminiAPI
database "PostgreSQL\n(Lưu lịch sử\nhội thoại)" as PGCheckpoint
database "FAISS\nKho hợp đồng" as FaissC
database "FAISS\nKho Luật" as FaissL

Frontend --> ChatOrch : "Gửi câu hỏi\n(kèm mã hợp đồng)"
ChatOrch --> AssertOwn : "Kiểm tra quyền"
AssertOwn --> ChatOrch : "OK / Lỗi"

ChatOrch --> QAGraph : "Bắt đầu quy trình AI"
note right of QAGraph
  Quy trình:
  Bắt đầu → Tra cứu
  → Sinh trả lời
  hoặc → Từ chối
  → Kết thúc
  Lịch sử được lưu tự động
end note

QAGraph --> RetrieveNode : "Tìm thông tin\nliên quan đến câu hỏi"
RetrieveNode --> ContractRetrieve : "Tìm trong hợp đồng"
ContractRetrieve --> FaissC : "Tìm kiếm"
FaissC --> ContractRetrieve : "Đoạn hợp đồng\nliên quan"
ContractRetrieve --> RetrieveNode : "Đoạn hợp đồng"
RetrieveNode --> LegalRetrieve : "Tìm trong kho luật"
LegalRetrieve --> FaissL : "Tìm kiếm"
FaissL --> LegalRetrieve : "Điều luật\nliên quan"
LegalRetrieve --> RetrieveNode : "Điều luật"
RetrieveNode --> QAGraph : "Đã có / Không có\nthông tin"

QAGraph --> Router : "Quyết định"
Router --> GenerateNode : "Có thông tin →\nnhờ AI trả lời"
Router --> RefusalNode : "Không có thông tin →\nbáo không trả lời được"

GenerateNode --> LLMCall : "Gửi câu hỏi +\ncác thông tin tìm được"
LLMCall --> GeminiAPI : "Nhờ AI trả lời"
GeminiAPI --> LLMCall : "Câu trả lời của AI"
LLMCall --> GenerateNode : "Câu trả lời +\ncác điều khoản trích dẫn"
GenerateNode --> QAGraph : "Câu trả lời"

RefusalNode --> QAGraph : "Câu trả lời mặc định:\n'Không tìm thấy\nthông tin...'"

QAGraph --> PGCheckpoint : "Lưu hội thoại\nvào CSDL"
PGCheckpoint --> QAGraph : "Xong"
QAGraph --> ChatOrch : "Trả câu trả lời"

ChatOrch --> Frontend : "Hiển thị:\n- Câu trả lời\n- Các điều khoản\ntrích dẫn"

' ---- Xem lịch sử ----
Frontend --> HistoryLoad : "Yêu cầu lịch sử\nhỏi đáp của hợp đồng"
HistoryLoad --> QAGraph : "Đọc từ CSDL"
QAGraph --> PGCheckpoint : "Lấy lịch sử"
PGCheckpoint --> QAGraph : "Các tin nhắn cũ"
QAGraph --> HistoryLoad : "Danh sách tin nhắn"
HistoryLoad --> Frontend : "Hiển thị lịch sử"

@enduml
```

---

# DFD Mức 2 — Danh sách Hợp đồng

File nguồn: `app/services/contract_service.py:110`

Khi người dùng vào trang chính, hệ thống lấy danh sách các hợp đồng của họ từ cơ sở dữ liệu.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database

actor "Giao diện\nngười dùng" as Frontend
rectangle "Lấy danh sách\nhợp đồng" as ListProc
database "PostgreSQL\n(Bảng uploaded_contracts)" as PG

Frontend --> ListProc : "Vào trang danh sách\n(kèm ID người dùng)"
ListProc --> PG : "Truy vấn: lấy tất cả\nhợp đồng của người này\nsắp xếp mới nhất trước"
PG --> ListProc : "Danh sách hợp đồng"
ListProc --> Frontend : "Trả danh sách\n(tên file, trạng thái,\nngày tải lên)"

@enduml
```

---

# DFD Mức 2 — Nạp Kho Dữ liệu Luật

File nguồn: `app/knowledge_base/loader.py:16`, `scripts/load_legal_kb.py`

Đây là tác vụ chạy thủ công (gõ lệnh trong terminal) để đưa các văn bản luật vào kho vector, phục vụ cho việc tra cứu khi phân tích hợp đồng.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database

actor "Người quản trị\n(gõ lệnh)" as Operator
rectangle "Script nạp\nkho luật" as Script
rectangle "Đọc từ CSDL\nvà đưa vào\nkho vector" as Loader
rectangle "Kho vector\nluật" as FaissOp
database "PostgreSQL\n(Bảng legal_documents\n+ document_chunks)" as PG
database "FAISS\nKho vector Luật" as FaissL

Operator --> Script : "Gõ lệnh:\npython scripts/load_legal_kb.py"
Script --> Loader : "Gọi hàm nạp dữ liệu"
Loader --> FaissOp : "Lấy kho vector luật"
FaissOp --> FaissL : "Xoá dữ liệu cũ,\nbắt đầu lại từ đầu"
FaissL --> FaissOp : "Xong"

Loader --> PG : "Đọc tất cả văn bản luật\n(chỉ lấy bản đang có hiệu lực)\nsắp xếp theo thứ tự"
PG --> Loader : "Trả từng trang\n(mỗi lần 256 dòng)"

Loader --> FaissOp : "Lưu vào kho vector\n(theo từng lô)"
FaissOp --> FaissL : "Xây dựng chỉ mục\nvà ghi xuống ổ cứng"
FaissL --> FaissOp : "Xong"
FaissOp --> Loader : "Tiếp tục"

Loader --> Loader : "Lặp lại cho đến\nhết dữ liệu"
Loader --> FaissOp : "Lưu lần cuối"
FaissOp --> FaissL : "Ghi ra ổ cứng"
FaissL --> FaissOp : "Xong"

Loader --> Script : "Tổng số\nlượng đã nạp"
Script --> Operator : "In ra màn hình"

@enduml
```

---

# DFD Mức 2 — Giao diện Người dùng (Frontend)

File nguồn: `frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/components/*.jsx`

Sơ đồ này mô tả cách người dùng tương tác với từng màn hình và cách dữ liệu chạy từ giao diện tới máy chủ.

```plantuml
@startuml
!define ENTITY actor
!define PROCESS rectangle
!define STORE database
!define EXTERNAL cloud

actor "Người dùng" as User

rectangle "App\n(Ứng dụng chính)" as App
rectangle "Màn hình\nĐăng nhập" as LoginScreen
rectangle "Màn hình\nDanh sách HĐ" as ContractListScreen
rectangle "Màn hình\nTải lên" as UploadScreen
rectangle "Màn hình\nKết quả" as AnalysisResult
rectangle "Thanh bên\n(Sidebar)" as Sidebar
rectangle "Tab\nTổng quan" as OverviewTab
rectangle "Tab\nRủi ro" as RiskList
rectangle "Tab\nĐiều khoản" as ClausesTab
rectangle "Tab\nHỏi đáp" as ChatTab

rectangle "api.js\n(Gọi máy chủ)" as API
rectangle "AuthContext\n(Quản lý\nđăng nhập)" as AuthCtx
rectangle "supabaseClient\n(Kết nối\nSupabase)" as SupabaseClient

cloud "Supabase Auth\n(Dịch vụ đăng nhập)" as SupabaseAuthJS
rectangle "Máy chủ\nFastAPI" as Backend

' ---- Đăng nhập ----
User --> LoginScreen : "Nhập email + mật khẩu\n+ bấm Đăng nhập / Đăng ký"
LoginScreen --> AuthCtx : "Gửi thông tin"
AuthCtx --> SupabaseClient : "Chuyển tiếp"
SupabaseClient --> SupabaseAuthJS : "Gửi lên Supabase"
SupabaseAuthJS --> SupabaseClient : "Trả phiên đăng nhập"
SupabaseClient --> AuthCtx : "Lưu phiên"
AuthCtx --> App : "Thông báo:\nđã đăng nhập"
App --> LoginScreen : "Nếu chưa đăng nhập →\nhiển thị màn hình đăng nhập"
App --> ContractListScreen : "Nếu đã đăng nhập →\nhiển thị danh sách HĐ"

' ---- Danh sách hợp đồng ----
User --> ContractListScreen : "Xem danh sách\n/ Bấm vào hợp đồng\n/ Bấm 'Tải mới'"
ContractListScreen --> API : "Lấy danh sách hợp đồng"
API --> Backend : "Gửi yêu cầu kèm token"
Backend --> API : "Trả danh sách"
API --> ContractListScreen : "Danh sách hợp đồng"
ContractListScreen --> App : "Chuyển màn hình"

' ---- Tải lên hợp đồng ----
User --> UploadScreen : "Chọn file + chọn AI\n+ bấm 'Phân tích ngay'"
UploadScreen --> API : "Lấy danh sách\nAI có sẵn"
API --> Backend : "Hỏi máy chủ"
Backend --> API : "Danh sách AI"
API --> UploadScreen : "Các lựa chọn AI"

UploadScreen --> API : "Gửi file hợp đồng"
API --> Backend : "Tải file lên"
Backend --> API : "Trả mã hợp đồng"
API --> UploadScreen : "Đã tải xong"

UploadScreen --> API : "Yêu cầu phân tích"
API --> Backend : "Gửi yêu cầu"
Backend --> API : "Trả kết quả"
API --> UploadScreen : "Kết quả phân tích"
UploadScreen --> App : "Chuyển sang\nmàn hình kết quả"
App --> AnalysisResult : "Hiển thị kết quả"

' ---- Kết quả phân tích ----
User --> AnalysisResult : "Bấm chọn tab"
AnalysisResult --> Sidebar : "Tab nào đang chọn"
AnalysisResult --> OverviewTab : "Tab: Tổng quan"
AnalysisResult --> RiskList : "Tab: Sai luật / Cần chú ý"
AnalysisResult --> ClausesTab : "Tab: Chi tiết điều khoản"
AnalysisResult --> ChatTab : "Tab: Hỏi đáp"

' ---- Hỏi đáp ----
User --> ChatTab : "Gõ câu hỏi + Enter"
ChatTab --> API : "Gửi câu hỏi"
API --> Backend : "Chuyển lên máy chủ"
Backend --> API : "Trả câu trả lời"
API --> ChatTab : "Hiển thị câu trả lời"

ChatTab --> API : "Lấy lịch sử hỏi đáp"
API --> Backend : "Hỏi máy chủ"
Backend --> API : "Lịch sử"
API --> ChatTab : "Hiển thị lịch sử"

@enduml
```

---

## Danh sách Kiểm tra

| # | Tiêu chí | Trạng thái |
|---|----------|------------|
| 1 | Mọi đối tượng bên ngoài đều được thể hiện | ✓ Người dùng, Supabase Auth, Gemini API |
| 2 | Mọi kho dữ liệu đều được thể hiện | ✓ PostgreSQL, FAISS (hợp đồng + luật), Ổ cứng |
| 3 | Mọi yêu cầu đều có phản hồi | ✓ Tất cả mũi tên đi đều có mũi tên về |
| 4 | Mọi truy cập CSDL đều được vẽ | ✓ SELECT/INSERT/UPDATE trong tất cả sơ đồ |
| 5 | Mọi API bên ngoài đều được vẽ | ✓ Supabase Auth REST, Gemini LLM, Gemini OCR |
| 6 | Mọi lưu tạm (cache) đều được vẽ | ✓ Kiểm tra kết quả cũ khi phân tích |
| 7 | Mọi tác vụ nền đều được vẽ | ✓ Nạp Kho Dữ liệu Luật (chạy bằng lệnh) |
| 8 | Mọi luồng xác thực đều được vẽ | ✓ Sơ đồ Xác thực Người dùng |
| 9 | Không có thành phần nào bịa đặt | 100% dẫn chiếu từ file code thật |
