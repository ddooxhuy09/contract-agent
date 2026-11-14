# Phân tích lỗi theo từng bước pipeline (15/11/2026)

Chỉ đọc lại kết quả đã có, không chạy lại hệ thống, không sửa bộ test đóng băng.
Nguồn: `evaluation_results/injection/full/*.json` (48 ca, Groq gpt-oss-120b, commit `ed30fdd`/`f23ba86`),
`injection/rule_only.json`, `injection/BASE_CONTRACT_FLAGS.md`, `legal_qa/runs/{dev,test}_vector_*/predictions.jsonl`.

Lưu ý phương pháp: phân tích này làm **sau khi đã xem kết quả test**. Mọi cải tiến rút ra từ đây phải được đo trên **bộ ca mới đóng băng trước khi sửa code** (như đã làm với injection_v2), không đo lại trên bộ 48/80 ca rồi báo là cải thiện.

## 1. Pipeline đầy đủ: 15 báo nhầm (FP) đến từ bước nào?

Mỗi cờ có trường `keys`: khác rỗng là do **luật cố định (regex)**, rỗng là do **LLM judge**.

| Bước gây FP | Số ca | Ca | Kiểu câu |
|---|---:|---|---|
| Regex (luật cố định) | **6** | BH-09, DT-06, GT-09, KL-06, KL-10, OT-07 | 4 câu phủ định chứa từ khoá, 2 biến thể hợp pháp |
| LLM judge, cờ "thiếu / chưa đầy đủ" | **7** | DT-10, LU-07, LU-09, LU-10, OT-08, TS-07, TS-09 | Judge không nói điều khoản sai, mà nói *thiếu* nội dung |
| LLM judge, khẳng định vi phạm | **2** | TC-10, TS-10 | Kết luận sai thật |

Recall 24/24: 9 ca do regex, 15 ca do LLM (toàn bộ ca diễn đạt khác mẫu). Không bước nào bỏ sót.

### Nguyên nhân 1: regex critical bỏ qua LLM
`app/agents/workflow.py` (pre-pass, `skip_llm_clauses`): Điều bị regex gắn cờ `critical` không được gửi cho judge. Nên câu
"Công ty **không** áp dụng hình thức phạt tiền…" khớp regex `fine_deduct_wage` là ra cờ critical ngay, không ai kiểm lại.
Bản sửa bằng cửa sổ phủ định 30 ký tự (injection_v2) đã thử và thất bại (recall 1,00 → 0,50).

### Nguyên nhân 2: định nghĩa `warning` quá rộng
`app/core/prompts.py`, `GLOBAL_SEVERITY` và `_CLAUSE_RISK_TASK`:
- warning = "bất lợi / mơ hồ / mất cân bằng … **hoặc thiếu căn cứ để kết luận chắc**";
- "Thiếu luật liên quan hoặc không đủ để kết luận → severity=warning".

Nghĩa là mọi trường hợp "chưa hoàn hảo" đều thành warning, và chấm điểm tính warning là dương tính.
Prompt cũng không nói rằng **hợp đồng không bắt buộc chép lại luật**: dẫn chiếu "theo quy định của BLLĐ" là hợp lệ.

Bằng chứng trên toàn bộ 299 cờ của 48 lần chạy:

| Loại cờ | warning | critical |
|---|---:|---:|
| LLM "thiếu / chưa rõ" | 151 (51%) | 6 |
| LLM khẳng định vi phạm | 93 | 35 |
| Regex | 0 | 14 |

Cờ lặp lại nhiều nhất: "Hợp đồng (toàn văn): Thiếu địa chỉ…" 47/48 ca; "Điều 2: Thiếu quy định giới hạn giờ làm thêm" ~32/48;
"Điều 8: Thời hạn báo trước … không phù hợp" ~34/48 (sai số liệu: HĐ 24 tháng chỉ cần 30 ngày, Điều 35 khoản 1 điểm b).
Các Điều 2 và 8 bị cờ 42/48 ca bất kể ca bơm vào Điều nào, tức là cờ đến từ hợp đồng nền, không từ nội dung ca.

### Nguyên nhân 3: judge áp sai số liệu / văn bản (ít hơn nhưng nặng nhất)
- Điều 8: đòi 45 ngày thay vì 30 ngày (nhầm HĐ xác định thời hạn với không xác định thời hạn).
- Trích NĐ 27/2014 (chỉ cho lao động giúp việc gia đình) cho HĐ văn phòng.
- Khuyến nghị cho NSDLĐ giữ bản chính giấy tờ, trái Điều 17 khoản 1.
Đây là lỗi kết hợp retrieval (đưa đoạn luật sai phạm vi vào ngữ cảnh) và judge (không đối chiếu loại HĐ).

## 2. Luật cố định (80 ca): FN 24, FP 14

- FN 24 = toàn bộ ca viết khác mẫu (diễn đạt lại 10, số bằng chữ 5, viết tắt 5, câu dài 4). Đây là giới hạn bản chất của regex; LLM đã bù được (mục 1).
- FP 14 = 7 câu phủ định + 7 nội dung hợp pháp chứa từ khoá. Cùng nguyên nhân 1.

## 3. Truy xuất luật (vector, chỉ câu có Điều gold tìm được)

| Kết quả | dev (216) | test (556) |
|---|---:|---:|
| Đúng ở hạng 1 | 135 (62%) | 330 (59%) |
| Đúng ở hạng 2–5 | 36 | 112 |
| Đúng ở hạng 6–10 | 7 | 23 |
| Đúng văn bản, sai Điều | 13 | 16 |
| Đúng văn bản, top có đoạn không có Điều (PREAMBLE) | 9 | 25 |
| Sai văn bản hoàn toàn | 16 | 50 |

- Xếp hạng không phải điểm yếu chính: 135 câu test đã có đáp án trong top 10 nhưng chưa ở hạng 1, có thể cải thiện bằng rerank.
- Điểm yếu lớn nhất là **độ phủ kho**: chỉ 24% câu hỏi đánh giá được. Trong đó 679 câu (văn bản hết hiệu lực **một phần**, `status_flag=4`) bị ẩn toàn bộ vì cờ hiệu lực của văn bản bị sao xuống mọi đoạn. Đây là lỗi dữ liệu, không phải lỗi mô hình.

## 4. Đề xuất cải thiện, xếp theo tác động

| # | Sửa | Đánh vào | Chỗ sửa | Kỳ vọng / rủi ro |
|---|---|---|---|---|
| 1 | Tách loại phát hiện: judge trả thêm `loai` = `vi_pham` / `thieu_noi_dung` / `gop_y_soan_thao`; chỉ `vi_pham` được warning/critical, còn lại là `info` (vẫn hiện trên UI nhưng không tính rủi ro) | 7/15 FP + phần lớn cờ ở Điều khác | `GLOBAL_SEVERITY`, `_CLAUSE_RISK_TASK`, `_risk_from_judgement`, schema `RiskItem` (trường tuỳ chọn) | Giảm mạnh FP; rủi ro: judge xếp nhầm vi phạm thật thành "thiếu" |
| 2 | Thêm quy tắc vào prompt: HĐ không bắt buộc chép lại luật; dẫn chiếu "theo quy định pháp luật" là hợp lệ; "thiếu" chỉ tính khi thuộc Điều 21 khoản 1 | Cờ "thiếu giới hạn OT", "thiếu nội dung đào tạo" | `_CLAUSE_RISK_TASK` | Rẻ, ít rủi ro |
| 3 | Regex chuyển thành **ứng viên**: Điều khớp regex vẫn gửi judge kèm gợi ý "regex nghi `<rule>`"; judge xác nhận hoặc bác (bác thì hạ xuống `info`, giữ dấu vết) | 6/15 FP | `workflow.py` (`skip_llm_clauses`), prompt | Giữ recall vì judge đã bắt được cả ca khác mẫu; tốn thêm lượt gọi LLM |
| 4 | Đưa loại HĐ (xác định / không xác định thời hạn, ngành) vào prompt judge; lọc văn bản phạm vi hẹp (NĐ 27/2014) khỏi ngữ cảnh khi HĐ không thuộc phạm vi | Lỗi Điều 8, trích NĐ 27/2014 | `evaluate_clause`, `_retrieve_legal` | Sửa lỗi nặng nhất (critical sai) |
| 5 | Sửa cờ hiệu lực ở mức Điều cho văn bản `status_flag=4` | Độ phủ benchmark (679 câu) và chất lượng RAG thật | ingest / dữ liệu | Việc dữ liệu, tốn công, phải re-index |
| 6 | Rerank top 10 bằng cross-encoder | 135 câu đúng nhưng chưa hạng 1 | retrieval | Tăng độ trễ; xem `RAG_SCOPE_ABLATION.md` trước |

## 5. Cách đo cho trung thực
1. Viết bộ ca mới (gợi ý `injection_v3`): **nhiều hợp đồng nền** (≥3, đã kiểm sạch Điều 21), có cả ca phủ định, biến thể hợp pháp và ca viết khác mẫu; gắn tag đóng băng **trước** khi sửa code.
2. Ghi trước chỉ số chính và quy tắc chấp nhận vào `docs/NHAT_KY_THAY_DOI.md`, ví dụ: "precision tăng, recall không giảm quá 1 ca".
3. Chạy cấu hình cũ và mới trên cùng bộ, cùng judge; báo cả hai, kể cả khi kết quả xấu đi.
4. Đặt mỗi thay đổi sau cờ cấu hình (như `RED_FLAG_NEGATION_CHECK`) để hoàn tác được.
