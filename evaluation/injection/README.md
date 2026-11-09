# Bộ bơm lỗi hợp đồng lao động (nhãn biết trước do cấu tạo)

Đo khả năng phát hiện từng luật đỏ trong `app/agents/labor_red_flags.py`. Nhãn có được do cách viết ca: ca `violation` được viết để vi phạm điều luật nêu trong `legal_basis`; ca `compliant` (near-miss) được viết gần giống nhưng hợp lệ. Không cần chuyên gia để gán nhãn, nhưng **chưa có luật sư/chuyên gia xác nhận** từng ca.

## Lưu ý về số luật
Yêu cầu ban đầu nói 7 luật đỏ, nhưng `_FLAGS` trong code có **8**: `ot_unpaid`, `no_bhxh`, `retain_id_papers`, `forfeit_wage_quit`, `training_cost_flat`, `fine_deduct_wage`, `terminate_pregnancy`, `ban_lawsuit`. Bộ này gồm cả 8 luật: 8 × (5 vi phạm + 5 hợp lệ) = **80 ca**.

## Cấu trúc
| File | Nội dung |
|---|---|
| `base_contract.txt` | Hợp đồng nền sạch (11 Điều). Điều 2, 4, 5, 6, 7, 8, 9, 10 là các "slot" ứng với 8 luật |
| `cases.jsonl` | 80 ca: `case_id, rule_id, label, slot, clause_text, legal_basis, phrasing, regex_expected, note` |
| `contracts/<case_id>.txt` | Hợp đồng đã chèn: nền với đúng một Điều (slot) bị thay bằng `clause_text` |
| `manifest.json` | SHA-256 của nền, của `cases.jsonl` và từng hợp đồng |
| `run.py` | `build`, `check`, `rule-only`, `full`, `report` |

Ghi chú: `data/demo_contracts` chỉ có một hợp đồng chứa nhiều vi phạm (`..._SAI.md`), không có hợp đồng sạch, nên nền được soạn mới.

## Thiết kế ca
- Mỗi luật: 5 ca vi phạm + 5 ca hợp lệ. Cột `phrasing`: `formulaic` (mẫu quen thuộc), `paraphrase`, `number_words` (số bằng chữ), `abbreviation` (viết tắt), `long_sentence`, `negation_trap` (cụm từ khoá xuất hiện trong câu phủ định hợp lệ), `lawful_variant`, `boundary`.
- Cột `regex_expected` là dự đoán của tác giả: vi phạm `hit`/`miss` (regex hiện tại trúng/không trúng), hợp lệ `trap` (regex hiện tại có thể trúng nhầm)/`clean`.
- Mỗi luật có 3/5 ca vi phạm viết khác mẫu regex (yêu cầu tối thiểu 2/5). `run.py check` kiểm điều này và kiểm hợp đồng nền không kích hoạt luật nào. Lần chạy `check` trước khi đóng băng in ra cả số near-miss mà regex trúng; **không ca nào được sửa sau lần kiểm đó**.
- Căn cứ pháp lý đối chiếu với văn bản BLLĐ 2019 (45/2019/QH14) trong DB: Điều 17, 40, 48, 62, 94, 98, 102, 107, 124, 127, 137, 138, 168, 179, 187.

## Cách chấm (khai báo trước khi chạy hệ thống)
**(a) Rule-only** (không LLM): `check_labor_red_flags(text, None)` trên cả 80 hợp đồng. Luật `r` được coi là "kích hoạt" ở một ca nếu có `RiskFinding.key == r`.
- Dương tính thật của luật `r` = ca `violation` có `rule_id == r`. Mọi ca khác là âm tính với `r` (kể cả ca vi phạm của luật khác và mọi near-miss).
- TP/FP/FN tính cho từng luật trên cả 80 ca; precision, recall, F1 từng luật; tổng là micro (cộng TP, FP, FN của 8 luật). Báo thêm: số near-miss của luật `r` bị chính luật `r` kích hoạt, và số ca hợp lệ bị luật bất kỳ kích hoạt.
- CI95: bootstrap 1000 lần, seed 20261109, lấy lại mẫu theo ca (chỉ cho chỉ số tổng; mỗi luật chỉ có 10 ca nên chỉ số từng luật rất thô).

**(b) Pipeline đầy đủ** (Gemini judge, `run_analysis_workflow`): đơn vị là ca. Dương tính khi có rủi ro `critical`/`warning` tại **Điều đã bơm**. Điều chưa kiểm (`unchecked`) được tính là âm tính và báo riêng; ca có Điều bơm chưa kiểm do hết quota **không được lưu** và chạy lại ở lần sau.
- Chạy theo **mẫu**: 3 vi phạm + 3 hợp lệ mỗi luật (48 ca), seed 20261109, xếp xen kẽ để dừng giữa chừng vẫn cân bằng. Lý do dùng mẫu và chạy nhiều ngày: một hợp đồng 11 Điều cần khoảng 12 lượt gọi Gemini, hạn mức khoảng 40 lượt/ngày.
- Báo thêm: số ca mà Điều khác ngoài Điều bơm bị gắn cờ (nền sạch bị gắn cờ).
- Báo cáo ghi rõ số ca đã hoàn tất trên tổng mẫu; chỉ số trên mẫu chưa hoàn tất là chỉ số của phần đã chạy.

## Giới hạn
- Ca do chính nhóm tác giả viết (và viết bởi một mô hình hỗ trợ), nên có thể thiên về cách diễn đạt quen thuộc dù đã cố ý đa dạng hoá; đây là **kiểm tra khả năng phát hiện, không phải tỷ lệ đúng trên hợp đồng thực tế**.
- Chưa có luật sư xác nhận nhãn. Một số ca near-miss phụ thuộc diễn giải luật (ví dụ NLĐ đang hưởng lương hưu; hoà giải nội bộ).
- Mỗi hợp đồng chỉ có một Điều sai; không đo tương tác giữa nhiều vi phạm.
- Hợp đồng ở dạng văn bản thuần, không qua bước đọc DOCX.
- Mỗi luật chỉ 10 ca: CI theo từng luật rất rộng.

## Đóng băng
Commit chứa các file này được gắn tag `injection-frozen` **trước** khi chạy bất kỳ hệ thống nào trên bộ này. Sau tag không sửa `cases.jsonl`, `base_contract.txt`, `contracts/` hay cách chấm.
