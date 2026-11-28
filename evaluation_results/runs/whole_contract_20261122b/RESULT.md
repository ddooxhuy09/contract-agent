# Câu hỏi toàn hợp đồng (T3): đọc mọi Điều thay vì top-k vector — kết quả trước/sau

Protocol chốt trước khi chạy: `PROTOCOL.json`. Số liệu: `metrics.json`. Lần chạy a bị hủy vì lỗi (xem `../whole_contract_20261122/ABORTED.md`).

| | Dev (32 câu, 16 ca) trước → sau | Validation injection_v3 (48 câu) trước → sau |
|---|---:|---:|
| Điều gold có trong ngữ cảnh (ca vi phạm) | 0,19 → 1,00 | 0,50 → 1,00 |
| Kết luận đúng trên ca vi phạm | 0,25 → 1,00 | 0,71 → 1,00 |
| Kết luận đúng trên ca hợp lệ | 0,81 → 0,25 | 0,50 → 0,21 |
| Kết luận khớp nhãn (chung) | 0,53 → 0,63 | 0,60 → 0,60 |
| Correctness (0–1) | 0,52 → 0,59, CI95 chênh [−0,31; +0,48] | 0,50 → 0,56, CI95 chênh [−0,14; +0,25] |
| Faithfulness | 0,77 → 0,48 | 0,62 → 0,49 |
| Token / độ trễ p50 | 3.495 → 4.761 / 3,1 → 5,6 s | 3.667 → 5.391 / 3,5 → 6,8 s |

Kết luận: sửa được phần truy xuất (Điều có lỗi luôn nằm trong ngữ cảnh, không còn bỏ sót vi phạm), nhưng mô hình chuyển sang báo nhầm trên hợp đồng hợp lệ:
31 câu trả lời hợp lệ bị kết luận vi phạm, 15 câu nhắm vào chính Điều near-miss (bỏ qua ngoại lệ của luật, ví dụ NLĐ hưởng lương hưu),
16 câu nhắm vào Điều khác của hợp đồng nền (ví dụ coi «kéo dài thời hạn nâng lương» là trái luật, trong khi đó là hình thức kỷ luật hợp pháp).
Ngữ cảnh luật vẫn là truy xuất chung từ câu hỏi, không có văn bản luật cho từng Điều, nên faithfulness giảm.
Chênh lệch correctness không có ý nghĩa thống kê; kết luận chung trên validation không đổi. Chưa nên phát hành ở dạng này.
