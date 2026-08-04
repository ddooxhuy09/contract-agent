# ContractLens — Giao diện Người dùng (Frontend)

> Tài liệu mô tả toàn bộ giao diện web ContractLens: kiến trúc, các màn hình, chức năng, cách sử dụng.
> Dựa trên mã nguồn tại thư mục `frontend/`.

---

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Cách chạy thử](#2-cách-chạy-thử)
3. [Cấu trúc thư mục & file](#3-cấu-trúc-thư-mục--file)
4. [Luồng điều hướng (State Machine)](#4-luồng-điều-hướng-state-machine)
5. [Màn hình Đăng nhập (LoginScreen)](#5-màn-hình-đăng-nhập-loginscreen)
6. [Màn hình Danh sách Hợp đồng (ContractListScreen)](#6-màn-hình-danh-sách-hợp-đồng-contractlistscreen)
7. [Màn hình Tải lên (UploadScreen)](#7-màn-hình-tải-lên-uploadscreen)
8. [Màn hình Kết quả (AnalysisResult)](#8-màn-hình-kết-quả-analysisresult)
9. [Thanh bên (Sidebar)](#9-thanh-bên-sidebar)
10. [Tab Tổng quan (OverviewTab)](#10-tab-tổng-quan-overviewtab)
11. [Tab Rủi ro (RiskList)](#11-tab-rủi-ro-risklistsai-luật--cần-chú-ý)
12. [Tab Chi tiết Điều khoản (ClausesTab)](#12-tab-chi-tiết-điều-khoản-clausestab)
13. [Tab Hỏi đáp (ChatTab)](#13-tab-hỏi-đáp-chattab)
14. [Xác thực & API](#14-xác-thực--api)
15. [Tổng kết các chức năng](#15-tổng-kết-các-chức-năng)

---

## 1. Tổng quan

ContractLens là một **ứng dụng web đơn trang (SPA - Single Page Application)** dùng để:

- **Tải lên hợp đồng** (file .docx, .pdf, ảnh chụp)
- **AI tự động phân tích rủi ro pháp lý**
- **Hỏi đáp về hợp đồng và luật liên quan**
- **Xem báo cáo trực quan** (rủi ro, điều khoản, thông tin các bên)

### Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Ngôn ngữ | JavaScript (JSX) |
| Framework UI | React 19 |
| Build tool | Vite 8 |
| CSS | Tailwind CSS 3 |
| Xác thực | Supabase Auth (@supabase/supabase-js) |
| Biểu tượng | Material Symbols (Google Icons) |
| Font | Inter (Google Fonts) |

---

## 2. Cách chạy thử

### Yêu cầu
- Node.js 18+
- Backend ContractLens đang chạy (xem README gốc)

### Cài đặt

```bash
# Vào thư mục frontend
cd frontend

# Cài dependencies
npm install

# Tạo file .env từ mẫu (sửa thông tin Supabase + Backend URL)
cp .env.example .env

# Chạy dev server (cổng 5173 mặc định)
npm run dev
```

### Build cho production

```bash
npm run build
# Kết quả nằm trong thư mục dist/
# FastAPI tự động serve thư mục này nếu có
```

### File `.env.example`

```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-anon-key
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

---

## 3. Cấu trúc thư mục & file

```
frontend/
├── index.html                  # File HTML chính (gốc của SPA)
├── package.json                # Dependencies & scripts
├── vite.config.js              # Cấu hình Vite build
├── tailwind.config.js          # Cấu hình Tailwind (màu sắc, font, spacing)
├── postcss.config.js           # Cấu hình PostCSS
├── eslint.config.js            # Cấu hình ESLint
├── .env.example                # Mẫu biến môi trường
├── public/
│   └── favicon.svg             # Icon tab trình duyệt
└── src/
    ├── main.jsx                # Điểm vào của ứng dụng (render App)
    ├── App.jsx                 # Component chính, điều hướng các màn hình
    ├── index.css               # Style gốc + Tailwind directives
    ├── api.js                  # Tất cả hàm gọi API backend
    ├── useAuth.js              # Hook đọc thông tin đăng nhập
    ├── AuthContext.jsx          # Quản lý trạng thái đăng nhập toàn cục
    ├── authContextObject.js     # Tạo context object
    ├── supabaseClient.js       # Kết nối Supabase JS SDK
    └── components/
        ├── LoginScreen.jsx     # Màn hình đăng nhập / đăng ký
        ├── ContractListScreen.jsx  # Màn hình danh sách hợp đồng
        ├── UploadScreen.jsx    # Màn hình tải lên hợp đồng
        ├── AnalysisResult.jsx  # Màn hình kết quả phân tích
        ├── Sidebar.jsx         # Thanh bên điều hướng tab
        ├── OverviewTab.jsx     # Tab tổng quan hợp đồng
        ├── RiskList.jsx        # Tab danh sách rủi ro
        ├── ClausesTab.jsx      # Tab chi tiết điều khoản
        └── ChatTab.jsx         # Tab hỏi đáp AI
```

---

## 4. Luồng điều hướng (State Machine)

Ứng dụng hoạt động như một máy trạng thái đơn giản:

```
                    ┌────────────┐
                    │  LOADING   │  (kiểm tra session Supabase)
                    └─────┬──────┘
                          │
               ┌──────────┴──────────┐
               │                     │
          Có session            Không session
               │                     │
               ▼                     ▼
     ┌─────────────────┐   ┌──────────────────┐
     │ DANH SÁCH Hợp   │   │  ĐĂNG NHẬP       │
     │ đồng (List)     │◄──│  (LoginScreen)    │
     └────────┬────────┘   └──────────────────┘
              │
     ┌────────┼─────────┐
     │        │         │
     ▼        ▼         │
  ┌────────┐ ┌──────────────────┐
  │ TẢI    │ │ KẾT QUẢ          │
  │ LÊN    │ │ (AnalysisResult) │
  │(Upload)│ │ - Tổng quan      │
  └───┬────┘ │ - Sai luật       │
      │      │ - Cần chú ý      │
      │      │ - Điều khoản     │
      └──────│ - Hỏi đáp        │
      (sau   └──────────────────┘
      phân
      tích)
```

---

## 5. Màn hình Đăng nhập (LoginScreen)

**File:** `frontend/src/components/LoginScreen.jsx`

### Mô tả
Màn hình đầu tiên người dùng thấy khi chưa đăng nhập. Cho phép **Đăng nhập** hoặc **Đăng ký** tài khoản mới.

### Giao diện
- Logo **ContractLens** ở giữa trên
- Form nhập **Email** + **Mật khẩu**
- Nút **Đăng nhập** (màu xanh dương đậm)
- Link chuyển chế độ: "Chưa có tài khoản? **Đăng ký ngay**" / "Đã có tài khoản? **Đăng nhập**"
- Hiển thị lỗi (nếu có) bằng màu đỏ, thông báo thành công bằng màu xanh lá

### Chức năng
| Thao tác | Kết quả |
|----------|---------|
| Nhập email + password + bấm Đăng nhập | Gọi `supabase.auth.signInWithPassword()` → nhận session → chuyển sang danh sách hợp đồng |
| Nhập email + password + bấm Đăng ký | Gọi `supabase.auth.signUp()` → hiển thị "Vui lòng kiểm tra email để xác nhận" |

### Luồng dữ liệu
```
LoginScreen → AuthContext → supabaseClient → Supabase Auth API
                 ↑                                |
                 └──────── session ───────────────┘
```

---

## 6. Màn hình Danh sách Hợp đồng (ContractListScreen)

**File:** `frontend/src/components/ContractListScreen.jsx`

### Mô tả
Màn hình chính sau khi đăng nhập. Hiển thị tất cả hợp đồng của người dùng dưới dạng thẻ (card).

### Giao diện
- **Thanh navigation** phía trên: logo "ContractLens" bên trái, nút "Đăng xuất" bên phải
- **Tiêu đề:** "Hợp đồng của bạn" + mô tả phụ
- **Nút "Tải hợp đồng mới"** (xanh dương, có icon upload)
- **Danh sách các thẻ hợp đồng** (nếu có), mỗi thẻ gồm:
  - Icon file
  - Tên file (in đậm)
  - Ngày tải lên (theo định dạng Việt Nam)
  - Trạng thái (chip màu):
    - 🟢 **Đã phân tích** (xanh lá)
    - 🟡 **Chờ phân tích** (vàng)
    - 🔴 **Lỗi xử lý tệp** (đỏ)
  - Mũi tên "→" bên phải
- **Màn hình trống** nếu chưa có hợp đồng nào: icon cloud + "Chưa có hợp đồng nào" + hướng dẫn

### Chức năng
| Thao tác | Kết quả |
|----------|---------|
| Click vào thẻ hợp đồng | Gọi `analyzeContract()` (lấy kết quả cũ) → chuyển sang màn hình kết quả |
| Click "Tải hợp đồng mới" | Chuyển sang màn hình Upload |
| Click "Đăng xuất" | Gọi `supabase.auth.signOut()` → quay về màn hình đăng nhập |

### Luồng dữ liệu
```
ContractListScreen → api.listContracts() → GET /api/v1/contracts (Bearer JWT)
                  ← contracts[]
```

---

## 7. Màn hình Tải lên (UploadScreen)

**File:** `frontend/src/components/UploadScreen.jsx`

### Mô tả
Cho phép người dùng tải file hợp đồng lên và bắt đầu phân tích.

### Giao diện
- **Thanh navigation:** nút "← Danh sách hợp đồng", logo, nút "Đăng xuất"
- **Phần giới thiệu:** "Hệ thống AI tự động rà soát rủi ro Hợp đồng" + mô tả
- **Khu vực kéo-thả file (drag & drop zone):**
  - Icon cloud upload
  - "Tải hợp đồng của bạn lên" (nếu chưa chọn file)
  - Tên file đã chọn (nếu đã chọn)
  - Các định dạng hỗ trợ: `.DOCX / .DOC`, `.PDF`, `Ảnh chụp (OCR)`
- **Dropdown chọn model AI** (Gemini 2.5 Flash)
- **Nút "Phân tích ngay"** (chỉ active khi đã chọn file và không đang xử lý)
- **Overlay loading** khi đang xử lý: thanh progress chạy + text trạng thái
- **Hiển thị lỗi** (màu đỏ) nếu có

### Định dạng file hỗ trợ
| Loại | Đuôi file |
|------|-----------|
| Word | `.doc`, `.docx` |
| PDF | `.pdf` |
| Ảnh | `.png`, `.jpg`, `.jpeg` |

### Chức năng
| Thao tác | Kết quả |
|----------|---------|
| Kéo-thả file vào vùng upload | Kiểm tra định dạng → hiển thị tên file |
| Click vào vùng upload | Mở hộp thoại chọn file |
| Chọn model AI | Lưu lựa chọn provider |
| Click "Phân tích ngay" | 1. `uploadContract(file)` → POST /api/v1/upload → nhận `contract_id` |
| | 2. `analyzeContract(contract_id, provider)` → POST /api/v1/analyze → nhận kết quả |
| | 3. Lưu vào danh sách + chuyển sang màn hình kết quả |

### Trạng thái loading
Khi đang xử lý, màn hình hiển thị lần lượt:
1. "Đang tải file lên..." (upload)
2. "Đang chạy AI phân tích rủi ro & sai luật..." (analyze)

---

## 8. Màn hình Kết quả (AnalysisResult)

**File:** `frontend/src/components/AnalysisResult.jsx`

### Mô tả
Màn hình hiển thị kết quả phân tích hợp đồng, chia làm 5 tab. Đây là màn hình phức tạp và giàu thông tin nhất.

### Bố cục
```
┌──────────────────────────────────────────────────────────┐
│ ╔════════════════╗                                        │
│ ║   SIDEBAR      ║  Header: "Hợp đồng: <tên file>"      │
│ ║                ║                                        │
│ ║  ☰ Tổng quan  ║  ┌──────────────────────────────────┐  │
│ ║  ⚠ Sai luật   ║  │                                  │  │
│ ║  ⚡ Cần chú ý  ║  │   NỘI DUNG TAB HIỆN TẠI        │  │
│ ║  📋 Điều khoản ║  │                                  │  │
│ ║  💬 Hỏi đáp    ║  │                                  │  │
│ ║                ║  └──────────────────────────────────┘  │
│ ║  📤 Tải mới    ║                                        │
│ ║  🚪 Đăng xuất  ║                                        │
│ ╚════════════════╝                                        │
└──────────────────────────────────────────────────────────┘
```

### 5 Tab chức năng

| # | Tab | Hiển thị |
|---|-----|----------|
| 1 | **Tổng quan** (OverviewTab) | Thông tin cốt lõi: loại HĐ, giá trị, thời hạn, bên A/B, luật áp dụng, risk score |
| 2 | **Sai luật** (RiskList - variant:critical) | Các điều khoản vi phạm pháp luật (màu đỏ) |
| 3 | **Điểm cần chú ý** (RiskList - variant:warning) | Các điều khoản bất lợi, không rõ ràng (màu vàng) |
| 4 | **Chi tiết điều khoản** (ClausesTab) | Danh sách tất cả điều khoản đã trích xuất |
| 5 | **Hỏi đáp** (ChatTab) | Giao diện chat hỏi đáp về hợp đồng |

---

## 9. Thanh bên (Sidebar)

**File:** `frontend/src/components/Sidebar.jsx`

### Mô tả
Thanh điều hướng dọc bên trái, luôn cố định khi cuộn. Chứa các tab và nút chức năng.

### Giao diện
- **Logo + tiêu đề** "ContractLens AI" + "Trợ lý Pháp lý Số"
- **Nút "Tải hợp đồng mới"** (xanh dương, nổi bật)
- **5 tab điều hướng:**
  - ☰ **Tổng quan** (dashboard icon)
  - ⚠ **Sai luật** (gavel icon) + số lượng (nếu > 0)
  - ⚡ **Điểm cần chú ý** (warning icon) + số lượng (nếu > 0)
  - 📋 **Chi tiết điều khoản** (list icon)
  - 💬 **Hỏi đáp** (chat icon)
- **Nút "Đăng xuất"** (cuối cùng)

### Chức năng
| Thao tác | Kết quả |
|----------|---------|
| Click tab | Chuyển nội dung vùng chính |
| Click "Tải hợp đồng mới" | Về màn hình Upload |
| Click "Đăng xuất" | Đăng xuất khỏi ứng dụng |

---

## 10. Tab Tổng quan (OverviewTab)

**File:** `frontend/src/components/OverviewTab.jsx`

### Mô tả
Tab đầu tiên và quan trọng nhất, cung cấp cái nhìn tổng thể về hợp đồng.

### Giao diện

#### Phần 1: Banner trạng thái
- Icon xác nhận + "Đã phân tích: `<tên file>`"
- "Hệ thống đã rà soát N điều khoản pháp lý"
- "100% - Hoàn tất"

#### Phần 2: Thông tin cốt lõi (lưới 2 cột)
| Mục | Hiển thị |
|-----|----------|
| 📄 Loại hợp đồng | VD: "Hợp đồng lao động" |
| 💳 Giá trị | VD: "10,000,000 VND/tháng" |
| 📅 Thời hạn | VD: "01/07/2026 – 31/12/2026" |
| ⚖️ Luật áp dụng | VD: "Bộ luật Lao động 2019" |
| Giải quyết tranh chấp | VD: "Tòa án Nhân dân quận..." |

#### Phần 3: Risk Score (cột phải)
- Vòng tròn đỏ: số **rủi ro cao** (critical)
- "Cần xử lý ngay lập tức"
- Vòng tròn vàng: số **cần lưu ý** (warning)
- "Rủi ro trung bình"

#### Phần 4: Các bên tham gia
- Mỗi bên một thẻ riêng, hiển thị:
  - Vai trò: "Người sử dụng lao động" / "Người lao động"
  - Tên/Họ tên
  - MST/CMND
  - Đại diện pháp luật
  - Địa chỉ

---

## 11. Tab Rủi ro (RiskList)
### Sai luật & Cần chú ý

**File:** `frontend/src/components/RiskList.jsx`

### Mô tả
Hiển thị danh sách các vấn đề pháp lý được AI phát hiện, chia làm 2 cấp độ:

- **Sai luật** (critical) - màu đỏ: vi phạm pháp luật
- **Cần chú ý** (warning) - màu vàng: bất lợi, không rõ ràng

### Giao diện mỗi thẻ rủi ro

```
┌──┬────────────────────────────────┐
│  │  ⚠️ SAI LUẬT                    │
│  │  Điều 5                         │
│  ├────────────────────────────────┤
│  │  Vấn đề:                        │
│  │  "Thời giờ làm việc..."         │
│  │                                 │
│  │  📖 Căn cứ pháp lý              │
│  │  "Khoản 1 Điều 25 BLLĐ 2019"   │
│  │                                 │
│  │  ✨ Phương án xử lý AI           │
│  │  "Đề xuất sửa đổi..."           │
│  └────────────────────────────────┘
```

### Chức năng
- Lưới 2 cột (responsive)
- Card có viền trái màu đỏ/vàng tương ứng
- Mỗi card gồm:
  - **Badge**: "⚠️ SAI LUẬT" hoặc "🔔 CẦN CHÚ Ý"
  - **Điều khoản**: "Điều 5"
  - **Vấn đề:** mô tả chi tiết bằng tiếng Việt
  - **Căn cứ pháp lý** (nếu có): điều luật cụ thể
  - **Phương án xử lý AI** (nếu có): đề xuất sửa đổi

---

## 12. Tab Chi tiết Điều khoản (ClausesTab)

**File:** `frontend/src/components/ClausesTab.jsx`

### Mô tả
Hiển thị toàn bộ các điều khoản được AI trích xuất từ hợp đồng.

### Giao diện
- **Tiêu đề:** "Chi tiết điều khoản" + "Tóm tắt toàn bộ N điều khoản"
- **Danh sách các thẻ**, mỗi thẻ gồm:
  - Số điều khoản (trong vòng tròn xanh)
  - Tiêu đề (in đậm)
  - Nội dung tóm tắt

### Trường hợp không có điều khoản
Hiển thị thông báo: "Không trích xuất được điều khoản nào."

---

## 13. Tab Hỏi đáp (ChatTab)

**File:** `frontend/src/components/ChatTab.jsx`

### Mô tả
Giao diện chat cho phép người dùng hỏi AI bằng tiếng Việt về hợp đồng và luật liên quan.

### Giao diện
- **Header:** "💬 Hỏi đáp về hợp đồng & luật liên quan"
- **Vùng chat** (có thanh cuộn):
  - Tin nhắn người dùng (căn phải, nền xanh)
  - Tin nhắn AI (căn trái, nền trắng, viền xám)
  - AI có thể kèm **badge "Điều X"** (dẫn nguồn)
  - Nếu AI cần hỏi thêm → badge vàng "Cần làm rõ thêm"
  - Animation 3 chấm khi AI đang trả lời
- **Trạng thái rỗng:** icon + "Hỏi bất cứ điều gì về hợp đồng..."
- **Ô nhập** (textarea) + nút gửi
- **Hiển thị lỗi** (nếu có)

### Chức năng
| Thao tác | Kết quả |
|----------|---------|
| Gõ câu hỏi + Enter (hoặc click nút gửi) | 1. Hiển thị câu hỏi ngay lập tức |
| | 2. `chatWithContract()` → POST /api/v1/chat |
| | 3. Hiển thị câu trả lời từ AI (kèm trích dẫn điều khoản) |
| Mở tab | `fetchChatHistory()` → GET /api/v1/chat/{id}/history → hiển thị các tin nhắn cũ |

### Tính năng thông minh
- AI **chỉ trả lời dựa trên hợp đồng và kho luật**, không bịa thông tin
- Nếu thiếu thông tin, AI sẽ **hỏi lại người dùng** (cần làm rõ thêm)
- AI **trích dẫn số điều khoản** cụ thể trong câu trả lời
- Lịch sử chat được **lưu lại**, khi mở lại hợp đồng sẽ thấy các câu hỏi cũ

---

## 14. Xác thực & API

### Xác thực (Auth)

**File:** `frontend/src/AuthContext.jsx`, `frontend/src/authContextObject.js`, `frontend/src/useAuth.js`, `frontend/src/supabaseClient.js`

Cơ chế xác thực dùng **Supabase Auth** (bên thứ ba), quản lý email/password.

```
AuthContext (React Context toàn cục)
  ├── session: phiên đăng nhập hiện tại
  ├── user: thông tin người dùng
  ├── accessToken: token gửi kèm API
  ├── loading: đang kiểm tra session
  ├── signIn(email, password): đăng nhập
  ├── signUp(email, password): đăng ký
  └── signOut(): đăng xuất
```

**Luồng:**
1. Khi app khởi động: gọi `supabase.auth.getSession()` → nếu có session, chuyển thẳng vào danh sách
2. Lắng nghe sự kiện `onAuthStateChange` → cập nhật session tự động
3. Mỗi khi gọi API backend: lấy `access_token` từ session → gửi dưới dạng `Authorization: Bearer <token>`

### Gọi API

**File:** `frontend/src/api.js`

Tất cả giao tiếp với backend đều qua module `api.js`. Mỗi hàm:

1. Lấy token từ Supabase session
2. Gọi fetch() tới backend
3. Xử lý lỗi (nếu HTTP status không OK)
4. Trả JSON

| Hàm | Endpoint | Mục đích |
|-----|----------|----------|
| `uploadContract(file)` | `POST /api/v1/upload` | Tải file hợp đồng lên |
| `analyzeContract(contractId, provider, force)` | `POST /api/v1/analyze` | Yêu cầu AI phân tích |
| `listContracts()` | `GET /api/v1/contracts` | Lấy danh sách hợp đồng |
| `fetchModels()` | `GET /api/v1/models` | Lấy danh sách model AI có sẵn |
| `chatWithContract(contractId, question, provider)` | `POST /api/v1/chat` | Gửi câu hỏi chat |
| `fetchChatHistory(contractId)` | `GET /api/v1/chat/{id}/history` | Lấy lịch sử hỏi đáp |

---

## 15. Tổng kết các chức năng

| # | Chức năng | Màn hình | Ghi chú |
|---|-----------|----------|---------|
| 1 | Đăng nhập bằng email/password | LoginScreen | Dùng Supabase Auth |
| 2 | Đăng ký tài khoản mới | LoginScreen | Gửi email xác nhận nếu cần |
| 3 | Xem danh sách hợp đồng | ContractListScreen | Sắp xếp mới nhất trước |
| 4 | Tải file hợp đồng lên | UploadScreen | Kéo-thả hoặc chọn file |
| 5 | Chọn model AI | UploadScreen | Dropdown chọn Gemini |
| 6 | Phân tích rủi ro AI | UploadScreen → AnalysisResult | Chạy ngay sau upload |
| 7 | Xem tổng quan hợp đồng | OverviewTab | Loại HĐ, bên A/B, risk score |
| 8 | Xem danh sách sai luật | RiskList (critical) | Màu đỏ, có căn cứ pháp lý |
| 9 | Xem điểm cần chú ý | RiskList (warning) | Màu vàng, có đề xuất AI |
| 10 | Xem chi tiết điều khoản | ClausesTab | Tất cả điều khoản đã trích xuất |
| 11 | Hỏi đáp về hợp đồng | ChatTab | AI trả lời kèm trích dẫn |
| 12 | Xem lịch sử hỏi đáp | ChatTab | Tự động khi mở tab |
| 13 | Đăng xuất | Mọi màn hình | Nút ở thanh navigation/sidebar |
