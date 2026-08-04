# Prompt Architecture — ContractLens (Vietnam Legal AI)

*Ngày: 2026-08-03. SoT code: `app/core/prompts.py`.*

---

## 1. Đánh giá kiến trúc prompt hiện tại (trước refactor)

Bốn prompt độc lập (OCR / Extraction / Clause Risk / QA), viết chủ yếu bằng **tiếng Anh**, output field thì yêu cầu tiếng Việt.

| Thành phần | Có? | Nhận xét |
|------------|-----|----------|
| Role | Có, rời rạc | Mỗi prompt tự định nghĩa; không share taxonomy |
| Goal | Có | Rõ nhiệm vụ nhưng lẫn với constraints |
| Context | Có | Placeholders đủ cho code |
| Constraints | Có nhưng lặp | “DO NOT fabricate” copy giữa Risk & QA |
| Output Format | Có | JSON schema ổn với parser hiện tại |
| Reasoning Guidance | Yếu | Không ép “kết luận trước”; dễ sinh văn AI dài |
| Style Guide chung | **Không** | Thuật ngữ / severity / citation lệch nhẹ giữa agents |

**Kết luận:** Đủ cho prototype; **chưa production** về UX tư vấn VN, nhất quán, và khả năng bảo trì.

---

## 2–4. Điểm yếu · Mức độ · Nguyên nhân

| ID | Điểm yếu | Severity | Nguyên nhân / hậu quả |
|----|----------|----------|------------------------|
| P1 | Không có GLOBAL rules | **Critical** | Lặp instruction; sửa 1 chỗ phải sửa 4 prompt → lệch hành vi |
| P2 | Prompt tiếng Anh → output tiếng Việt | **High** | Dễ “dịch máy”, thuật ngữ pháp lý VN không tự nhiên |
| P3 | Không ép cấu trúc Kết luận→Lý do→Căn cứ→Khuyến nghị | **High** | UX nặng, giống AI reasoning |
| P4 | Recommendation cho phép chung chung | **High** | “Sửa cho phù hợp” = vô dụng với user |
| P5 | Severity mô tả dài, không taxonomy dùng chung | **Medium** | critical/warning/ok có thể lệch giữa Risk & messaging |
| P6 | QA “keep concise” quá mơ hồ | **Medium** | Model vẫn sinh đoạn 300–500 chữ |
| P7 | Extraction schema comment tiếng Anh trong JSON | **Low** | Nhiễu; tăng token không tạo giá trị UX |
| P8 | OCR lẫn “tool” narrative dài | **Low** | Đủ dùng; có thể gọn hơn |
| P9 | Không tách grounding vs style vs task | **High** | Khó scale khi thêm agent (calculator, verifier) |
| P10 | Human QA template không đánh dấu section rõ | **Medium** | Model dễ trộn contract/legal/question |

---

## 5. Hướng cải thiện

1. **Tiếng Việt làm ngôn ngữ instruction** cho mọi agent hướng user.  
2. **`GLOBAL_*` layers** + task prompt mỏng.  
3. **Style cứng:** kết luận trước, bullet, một ý/đoạn, cấm lặp.  
4. **Recommendation bắt buộc cụ thể** (+ gợi ý câu «…» khi được).  
5. **Giữ nguyên JSON field names** để không phá `risk_flagger` / `qa_agent` / `clause_parser`.  
6. OCR **không** gắn full legal GLOBAL (tránh nhiễu); chỉ nhiệm vụ phiên âm.

---

## 6. Kiến trúc mới (đã implement trong `prompts.py`)

```
GLOBAL_GROUNDING
GLOBAL_STYLE
GLOBAL_CITATION
GLOBAL_SEVERITY
        ↓ compose
OCR_PROMPT          (minimal — không full legal global)
EXTRACTION_PROMPT   (grounding + task)
CLAUSE_RISK_PROMPT  (full global + task)
QA_SYSTEM_PROMPT    (grounding + style + citation + task)
QA_HUMAN_TEMPLATE   (section headers rõ)
```

Export `GLOBAL_SYSTEM_RULES` = ghép 4 block global (để docs/agent khác tái sử dụng).

Placeholders **không đổi:**  
`{contract_text}` `{clause_number}` `{clause_title_suffix}` `{clause_text}` `{clause_summary}` `{legal_context}` `{contract_context}` `{legal_context}` `{question}`.

---

## 7. Vì sao prompt mới tốt hơn

| Trước | Sau |
|-------|-----|
| 4 silo tiếng Anh | 1 style guide + task mỏng tiếng Việt |
| “Keep concise” mơ hồ | Cấu trúc Kết luận / Lý do / Căn cứ / Khuyến nghị |
| Recommendation tùy nghi | Bắt buộc cụ thể + «câu đề xuất» |
| Severity lặp lại trong Risk | `GLOBAL_SEVERITY` một nguồn |
| Citation mô tả dài | Một block citation dùng chung Risk + QA |
| Sửa UX phải đụng 4 file logic | Sửa `GLOBAL_STYLE` một lần |

---

## 8. Ví dụ output cùng một điều khoản

**Giả định Điều 8 — Đơn phương chấm dứt:**  
*“Bên A được đơn phương chấm dứt hợp đồng bất kỳ lúc nào mà không cần báo trước và không bồi thường.”*  
Ngữ cảnh luật (rút gọn): `[45/2019/QH14 | C3.D35.K1]` quy định thời hạn báo trước khi đơn phương chấm dứt HĐLĐ.

### Output kiểu cũ (minh họa — dài, kết luận muộn)

> Sau khi phân tích kỹ lưỡng điều khoản trong mối liên hệ với các quy định pháp luật liên quan, có thể nhận thấy rằng việc cho phép một bên chấm dứt hợp đồng mà không cần thông báo trước có thể tiềm ẩn nhiều rủi ro pháp lý cũng như ảnh hưởng đến quyền lợi của bên còn lại. Theo tinh thần của pháp luật lao động Việt Nam, việc đơn phương chấm dứt thường gắn với nghĩa vụ báo trước… (tiếp tục dài)… Do đó khuyến nghị xem xét sửa đổi điều khoản cho phù hợp với quy định pháp luật hiện hành.

### Output kiểu mới (đúng schema + style)

```json
{
  "issue": "Kết luận: Điều khoản cho phép đơn phương chấm dứt không báo trước và không bồi thường — rủi ro/vi phạm cao so với quy định bắt buộc về báo trước trong ngữ cảnh luật.\nLý do:\n- HĐ trao quyền tuyệt đối cho một bên, mất cân bằng.\n- Ngữ cảnh luật yêu cầu thời hạn báo trước khi đơn phương chấm dứt.",
  "severity": "critical",
  "legal_basis": "45/2019/QH14 | C3.D35.K1 — thời hạn báo trước khi đơn phương chấm dứt HĐLĐ",
  "recommendation": "- Bổ sung nghĩa vụ báo trước đúng thời hạn luật định.\n- Xóa cụm «không bồi thường» nếu trái quy định bắt buộc trong ngữ cảnh.\n- Gợi ý sửa: «Bên A chỉ được đơn phương chấm dứt khi đúng lý do luật định và đã báo trước theo [thời hạn]; trường hợp trái luật phải bồi thường theo quy định.»"
}
```

**Khác biệt UX:** user đọc 5–10 giây là nắm kết luận + việc cần làm; có căn cứ trích dẫn kiểm chứng được.

---

## Production readiness

| Hạng mục | Trạng thái sau refactor |
|----------|-------------------------|
| Consistency terminology / severity / citation | Đạt (GLOBAL) |
| UX tư vấn VN | Đạt (style + tiếng Việt) |
| Schema tương thích code | Đạt (giữ field) |
| Structured output Gemini native | Chưa (vẫn parse JSON thủ công — backlog kỹ thuật, không phải prompt) |
| Delimiter chống prompt injection trong context | Một phần (section headers); nên bổ sung wrapper XML ở tầng agent |
| Versioning prompt trong DB | Chưa — ghi nhận backlog |

**Verdict:** Prompt layer **sẵn sàng dùng production nội bộ / demo mạnh**; còn thiếu kỹ thuật kèm (structured output, injection delimiters, prompt version) ở tầng agent/infra.

---

## Vận hành

- Sửa văn phong / grounding → chỉ sửa `GLOBAL_*` trong `prompts.py`.  
- Sửa schema JSON task → sửa `_…_TASK` tương ứng; cập nhật parser nếu đổi tên field.  
- Sau khi đổi: `docker compose restart api` (bind-mount `app/`).
