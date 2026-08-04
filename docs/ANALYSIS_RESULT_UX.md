# UX Redesign — Legal Consultant Report (ContractLens)

*Vai trò: Senior UX / Product Design / Legal AI Experience. Phạm vi: hiển thị kết quả phân tích — không đổi logic pháp lý backend.*  
*SoT UI hiện tại: `AnalysisResult.jsx`, `OverviewTab.jsx`, `RiskList.jsx`, `ClausesTab.jsx`, `Sidebar.jsx`.*

---

## 1. Review UX/UI hiện tại (khắt khe)

### Cách mắt người dùng đọc hôm nay

```
[Sidebar trái cố định]
  Tổng quan | Sai luật (n) | Cần chú ý (n) | Điều khoản | Chat
        ↓
[Header: tên file]
        ↓
Tab "Tổng quan": banner "100% Hoàn tất" → lưới metadata → vòng tròn đếm risk → thẻ parties
        ↓
Tab "Sai luật" / "Cần chú ý": lưới 2 cột thẻ risk — mỗi thẻ: badge → Điều → khối "Vấn đề" (đoạn văn) → căn cứ italic → "Phương án xử lý AI"
```

**First 5 giây:** user thấy “đã phân tích / 100%” và metadata — **chưa thấy kết luận rủi ro chính**.  
**Muốn biết “có sao không?”** phải đọc sidebar count hoặc chuyển tab.  
**Muốn hành động:** phải mở từng thẻ, đọc đoạn `issue` dài (monospace legal dump).

### Vì sao mệt

| Nguyên nhân | Hậu quả |
|-------------|---------|
| Executive conclusion **không** ở first viewport | User không biết nên lo hay yên trong 5s |
| Risk tách 2 tab + Overview không list top issues | Phải click nhiều; mất mental model “một báo cáo” |
| `issue` render 1 `<p>` monospace | Không scan được “Kết luận / Lý do” dù prompt đã bullet |
| Grid 2 cột risk cards | Desktop: so sánh ngang 2 lỗi khó; Mobile: vẫn OK nhưng thiếu collapse |
| Label “Phương án xử lý AI” | Giảm trust (nghe như tip AI, không phải khuyến nghị luật sư) |
| “100% Hoàn tất” | Signal vô nghĩa; chiếm hierarchy của kết luận |
| Clauses tab = list phẳng mọi Điều | Scale xấu với 100+ Điều; không gắn risk |
| Không progressive disclosure | Mọi field luôn mở → cognitive load tăng tuyến tính theo số lỗi |
| Không deep-link Điều ↔ Risk | User không nhảy từ lỗi → ngữ cảnh Điều |

### Dư thừa / lặp / cần rút

| Nội dung | Đánh giá |
|----------|----------|
| Banner “Đã phân tích + 100%” | **Dư** — trạng thái process, không phải insight |
| “Phát hiện N mục trong hợp đồng này” dưới H1 risk | **Lặp** với badge sidebar |
| Badge + border + banner cùng severity | **Lặp visual** — giữ 1 tín hiệu màu |
| `issue` paragraph dài không parse cấu trúc | **Cần rút + bullet** (UI parse dòng `Kết luận:` / `Lý do:`) |
| Italic toàn bộ `legal_basis` | **Giảm readability** — citation nên mono/short + title |
| Parties + full metadata trên overview trước risk | **Đẩy xuống** — secondary sau Executive Summary |

### Default vs “Xem chi tiết”

| Luôn hiện | Collapse / “Xem chi tiết” |
|-----------|---------------------------|
| Executive Summary (mức độ tổng + 3 vấn đề nóng) | Toàn văn Điều liên quan |
| Mỗi lỗi: tiêu đề Điều + severity + 1 dòng kết luận | Lý do đầy đủ, ảnh hưởng, đề xuất câu thay thế |
| Căn cứ: doc_number / chunk_ref (1 dòng) | Trích đoạn luật dài (nếu API bổ sung sau) |
| CTA khuyến nghị ngắn (1–2 bullet) | Toàn bộ recommendation dài + copy draft |

---

## 2. Vấn đề theo mức độ nghiêm trọng

### Critical

| ID | Vấn đề | Ảnh hưởng |
|----|--------|-----------|
| U1 | Không có Executive Summary kết luận | Không đạt “hiểu trong 5–10s”; trust thấp |
| U2 | Risk bị chôn trong tab phụ | User bỏ lỡ critical nếu ở Overview |
| U3 | Issue dump không scannable | Cognitive overload; bỏ cuộc trước khi đọc recommendation |

### High

| ID | Vấn đề | Ảnh hưởng |
|----|--------|-----------|
| U4 | Không progressive disclosure | 50–100 lỗi = trang không dùng được |
| U5 | Không liên kết Risk ↔ Điều | Không “hành động ngay” trên đúng chỗ HĐ |
| U6 | Copy “AI” trong recommendation | Giảm cảm giác LegalTech chuyên nghiệp |
| U7 | Mobile: sidebar `ml-64` chiếm / không drawer | First-run mobile kém (layout desktop-first) |

### Medium

| ID | Vấn đề | Ảnh hưởng |
|----|--------|-----------|
| U8 | Terminology lệch (Sai luật / Cần chú ý / Rủi ro cao) | Consistency kém |
| U9 | Clauses tab không filter theo risk | Scalability kém |
| U10 | Empty states OK nhưng không hướng CTA | Dead-end UX |
| U11 | Accessibility: màu severity chỉ màu, thiếu text/icon pattern ổn định | WCAG risk |

### Low

| ID | Vấn đề | Ảnh hưởng |
|----|--------|-----------|
| U12 | Emoji trong badge | Phong cách không đồng nhất Legal report |
| U13 | Shadow/hover card nặng | Noise visual |

---

## 3. Information Architecture mới

```
Báo cáo rà soát hợp đồng
├── 1. Executive Summary          ← default land
│     ├── Verdict (1 dòng)
│     ├── Score strip: Critical | Warning | OK clauses
│     ├── Top 3 vấn đề ưu tiên (click → scroll/open card)
│     └── CTA: Xuất PDF (future) / Hỏi AI
├── 2. Danh sách vấn đề           ← primary work area
│     ├── Filter: Tất cả | Nghiêm trọng | Cần chú ý | Theo Điều
│     ├── Sort: Severity → Số Điều
│     └── Issue Card[] (accordion)
│           ├── Header (always): Điều · Severity · Kết luận 1 dòng
│           └── Body (expand): Lý do · Căn cứ · Ảnh hưởng · Khuyến nghị · Đề xuất sửa
├── 3. Hồ sơ hợp đồng             ← secondary / collapse
│     ├── Loại · Giá trị · Thời hạn · Luật · Tranh chấp
│     └── Các bên
├── 4. Mục lục điều khoản         ← progressive
│     └── Điều N + chip risk (nếu có) → expand summary
└── 5. Chat tư vấn                ← giữ tab/drawer
```

**Nguyên tắc mắt đọc (F-pattern Legal Report):**

1. Verdict  
2. Numbers  
3. Top issues  
4. Scan headers của Issue Cards  
5. Expand chỉ card cần xử lý  

---

## 4. Wireframe (Desktop)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Danh sách    HĐ: ten_file.docx              [Hỏi AI] [Tải lại phân tích]│
├──────────────────────────────────────────────────────────────────────────┤
│ EXECUTIVE SUMMARY                                                        │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ Kết luận: Hợp đồng có 3 vấn đề nghiêm trọng, cần xử lý trước khi ký. │ │
│ │  ● 03 Nghiêm trọng   ● 05 Cần chú ý   ● 12 Điều không ghi nhận lỗi   │ │
│ │ Ưu tiên:                                                             │ │
│ │  1. Điều 8 — Đơn phương chấm dứt không báo trước          [Mở →]   │ │
│ │  2. Điều 12 — Phạt vượt khung                                     │ │
│ │  3. Điều 3 — Thời hạn HĐ không rõ loại                            │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ VẤN ĐỀ CẦN XỬ LÝ                    [Tất cả ▾] [Nghiêm trọng] [Cần chú ý]│
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ ▼ Điều 8 · Nghiêm trọng                                              │ │
│ │   Kết luận: Cho phép chấm dứt không báo trước — trái quy định…     │ │
│ │   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │ │
│ │   Lý do                                                              │ │
│ │   • …                                                                │ │
│ │   Căn cứ pháp lý                                                     │ │
│ │   45/2019/QH14 · C3.D35.K1                                           │ │
│ │   Ảnh hưởng                                                          │ │
│ │   • Rủi ro bồi thường / vô hiệu một phần khi tranh chấp              │ │
│ │   Khuyến nghị                                                        │ │
│ │   • Bổ sung nghĩa vụ báo trước…                                      │ │
│ │   Đề xuất sửa  [Sao chép]                                            │ │
│ │   ┌────────────────────────────────────────────────────────────┐     │ │
│ │   │ «Bên A chỉ được đơn phương chấm dứt khi…»                  │     │ │
│ │   └────────────────────────────────────────────────────────────┘     │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ ▶ Điều 12 · Cần chú ý · Phạt có thể vượt khung hợp lý          │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ▸ Hồ sơ hợp đồng (đã thu gọn)                                            │
│ ▸ Mục lục điều khoản (24)                                                │
└──────────────────────────────────────────────────────────────────────────┘
```

### Wireframe (Mobile)

```
┌─────────────────────────┐
│ ☰  Báo cáo HĐ        ⋯  │
├─────────────────────────┤
│ KẾT LUẬN                │
│ Cần xử lý trước khi ký  │
│ [03 nghiêm] [05 chú ý]  │
│ 1. Điều 8 …        ›    │
│ 2. Điều 12 …       ›    │
├─────────────────────────┤
│ VẤN ĐỀ                 │
│ [Filter chips scroll →] │
│ ┌─────────────────────┐ │
│ │ Điều 8 · Nghiêm trọng│ │
│ │ Kết luận một dòng…  │ │
│ │ [Chi tiết]          │ │
│ └─────────────────────┘ │
│ � Kết luận một dòng…  │ │
│ │ [Chi tiết]          │ │
│ └─────────────────────┘ │
│ ┌─────────────────────┐ │
│ │ Điều 12 · Cần chú ý │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ [Tổng quan] [Chat]      │  ← bottom nav, không sidebar cố định
└─────────────────────────┘
```

Bottom sheet khi bấm Chi tiết: Lý do / Căn cứ / Khuyến nghị / Đề xuất sửa.

---

## 5. Quy chuẩn từng block

### B1 — Executive Summary

| Rule | Spec |
|------|------|
| Vị trí | Top, luôn default |
| Verdict | 1 câu, ≤ 140 ký tự, không jargon AI |
| Counts | 3 chip: Nghiêm trọng / Cần chú ý / Ổn |
| Top N | Max 3; sort severity rồi số Điều |
| Empty | “Không phát hiện vấn đề trọng yếu trong phạm vi đã rà soát.” |

### B2 — Issue Card (một lỗi = một khối)

| Zone | Default | Collapse |
|------|---------|----------|
| Header: `Điều X` + severity pill + kết luận 1 dòng | **Mở** | — |
| Lý do (bullets từ `issue`) | Đóng nếu > 2 bullet | Mở khi expand |
| Căn cứ (`legal_basis`) | 1 dòng citation | Expand nếu có quote dài |
| Ảnh hưởng | Optional; 1–2 bullet (derive từ issue hoặc field mới sau) | Trong chi tiết |
| Khuyến nghị | 1–2 bullet đầu | Còn lại trong chi tiết |
| Đề xuất sửa `«…»` | Trong chi tiết + nút Copy | — |

**Severity pills (consistent):**

- `critical` → “Nghiêm trọng” (không “Sai luật” / không emoji)  
- `warning` → “Cần chú ý”  
- `ok` → không tạo card  

### B3 — Hồ sơ hợp đồng

Metadata + parties; **collapsed by default** sau khi có Executive Summary.

### B4 — Mục lục Điều

Row: `Điều N · Title · [chip risk|—]`; expand = summary; tap chip = mở Issue Card.

---

## 6. Quy tắc UX Writing (cho UI + AI text đã sinh)

1. **Kết luận ≤ 1 dòng** trên header card (UI cắt từ dòng `Kết luận:` của `issue`).  
2. Không hiển thị nguyên khối monospace; **parse** thành:
   - dòng bắt đầu `Kết luận:`
   - các dòng sau `Lý do:` / `- `  
3. Căn cứ: ưu tiên hiển thị `doc_number` đậm + `chunk_ref` nhỏ; bỏ italic toàn đoạn.  
4. Khuyến nghị: mỗi bullet một hành động động từ (“Bổ sung…”, “Xóa cụm…”, “Thay bằng…”).  
5. Cấm trong UI labels: “Phương án xử lý AI”, “AI reasoning”, “Dựa trên phân tích toàn diện”.  
6. Dùng: “Khuyến nghị”, “Căn cứ pháp lý”, “Đề xuất sửa điều khoản”.  
7. Không lặp verdict Executive Summary bên trong mọi card.  
8. Số liệu luôn chữ số (`3`) không chữ (`ba`) trên chip.  

**Parser UI gợi ý (pseudo):**

```
parseIssue(issue):
  conclusion = line after "Kết luận:" or first line
  reasons = bullets under "Lý do" or remaining "-" lines
parseRecommendation(rec):
  actions = bullets
  draft = text inside « » if any
```

---

## 7. Scalability (hàng chục Điều / hàng trăm lỗi)

| Kỹ thuật | Áp dụng |
|----------|---------|
| Virtualized list | Issue list khi > 30 card |
| Default collapse | Chỉ auto-expand Top 1 critical |
| Filter + search | Theo severity, số Điều, keyword |
| Group by Điều | Optional toggle khi > 50 issues |
| Summary sticky | Executive Summary sticky dưới header khi scroll |
| Pagination / “Xem thêm 20” | Mobile |
| Không render full clauses | Mục lục ảo hóa; summary on demand |

---

## 8. Before → After (cùng Điều 8)

### Trước (UI hiện tại — cảm nhận)

```
[Tab Cần chú ý / Sai luật]
┌──────── card ────────┐  ┌──── card khác ────┐
│ ⚠️ SAI LUẬT          │  │ ...               │
│ Điều 8               │  │                   │
│ Vấn đề:              │  │                   │
│ (đoạn văn monospace  │  │                   │
│  dài, khó scan)      │  │                   │
│ Căn cứ (italic)…     │  │                   │
│ Phương án xử lý AI…  │  │                   │
└──────────────────────┘  └───────────────────┘
```

User: không biết đây có phải ưu tiên #1; đọc mệt; không copy được câu sửa.

### Sau (Legal Consultant Report)

```
Kết luận: Có 3 vấn đề nghiêm trọng — xử lý trước khi ký.
Ưu tiên #1 → Điều 8

▼ Điều 8 · Nghiêm trọng
  Kết luận: Đơn phương chấm dứt không báo trước — trái quy định bắt buộc trong ngữ cảnh luật.
  [Chi tiết mở]
  Lý do
  • Trao quyền tuyệt đối cho một bên
  Căn cứ: 45/2019/QH14 · C3.D35.K1
  Khuyến nghị
  • Bổ sung nghĩa vụ báo trước theo luật
  Đề xuất sửa  [Sao chép]
  «Bên A chỉ được đơn phương chấm dứt khi đúng lý do luật định và đã báo trước…»
```

---

## 9. Mapping triển khai frontend (gợi ý, chưa bắt buộc code ngay)

| Component hiện tại | Hướng |
|--------------------|--------|
| `OverviewTab` | Thay bằng `ExecutiveSummary` + collapsed `ContractProfile` |
| `RiskList` × 2 tab | Gộp `IssueList` + filter chips; bỏ split tab critical/warning |
| `Sidebar` counts | Desktop: nav rút gọn (Báo cáo / Điều khoản / Chat); Mobile: bottom nav |
| `ClausesTab` | `ClauseIndex` với risk chips |
| `AnalysisResult` | Single scroll report thay multi-tab primary |

**Không đổi API** trong phase UX: parse `issue` / `recommendation` phía client.  
Field `impact` có thể thêm sau ở prompt/JSON — tạm derive 1 dòng từ kết luận nếu thiếu.

---

## 10. Success metrics (product)

- Time-to-first-understanding < 10s (task: “HĐ này ký được không?”).  
- % user expand < 30% cards (đủ thông tin ở header).  
- Với fixture 50 issues: scroll performance 60fps; không “wall of text”.  
- Label trust: 0 lần dùng chữ “AI” trên recommendation blocks.

---

## 11. Implementation status (2026-08-03)

Đã implement trên frontend:

- `ExecutiveSummary.jsx` — verdict + chips + Top 3
- `IssueCard.jsx` / `IssueList.jsx` — accordion + filter
- `ContractProfile.jsx` — hồ sơ HĐ collapse
- `ClauseIndex.jsx` — mục lục + chip risk
- `AnalysisResult.jsx` — single report flow (Báo cáo / Điều khoản / Chat)
- `lib/riskDisplay.js` — parse `Kết luận` / `Lý do` / `«draft»`
- Sidebar desktop + bottom nav mobile

Đã gỡ: `OverviewTab.jsx`, `RiskList.jsx`, `ClausesTab.jsx`.
