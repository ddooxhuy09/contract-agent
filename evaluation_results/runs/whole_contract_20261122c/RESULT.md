# Lượt c: đọc mọi Điều + luật BLLĐ theo chủ đề từng Điều

Protocol: `PROTOCOL.json`. Câu hỏi, nhãn và hợp đồng giống hệt lượt b (cùng SHA-256 của `inputs.jsonl` và `gold.json`).
- baseline: top-k vector như cũ.
- candidate: đọc mọi Điều của hợp đồng đang hỏi; ngữ cảnh luật là các Điều BLLĐ 45/2019 theo chủ đề của từng Điều (`clause_legal_evidence`), cắt đều cho vừa 10000 ký tự, thay cho kết quả tìm luật theo câu hỏi.
- Model sinh: Groq `openai/gpt-oss-120b`. Judge: Groq `qwen/qwen3.8-27b`.
- 160 câu trả lời, 0 lỗi.

| Chỉ số | Dev (32) baseline → candidate | Validation (48) baseline → candidate |
|---|---:|---:|
| Điều gold có trong ngữ cảnh | 0,19 → 1,00 | 0,50 → 1,00 |
| Kết luận đúng, ca vi phạm | 0,19 → 1,00 | 0,54 → 1,00 |
| Kết luận đúng, ca hợp lệ | 0,94 → 0,13 | 0,54 → 0,21 |
| Kết luận khớp nhãn | 0,56 → 0,56 | 0,54 → 0,60 (CI95 chênh lệch [−0,15; +0,25]) |
| Correctness (0–1) | 0,55 → 0,42 (CI95 [−0,50; +0,27]) | 0,53 → 0,49 (CI95 [−0,24; +0,14]) |
| Token trung bình | 3514 → 14480 | 3761 → 15233 |
| Độ trễ p50 | 2,8 → 8,4 s | 2,6 → 7,9 s |

**Không dùng faithfulness của lượt này.** `judge_item` cắt ngữ cảnh còn 7000 ký tự, mà phần luật đứng trước và dài khoảng 10000 ký tự. Vì vậy judge không thấy hợp đồng của candidate và chấm "không có căn cứ" cả những câu trích đúng hợp đồng. Correctness và kết luận được chấm theo đáp án tham chiếu nên không bị ảnh hưởng. Không chấm lại để chọn điểm.

## Đọc kết quả

- Có luật cho từng Điều cũng không giảm báo nhầm trên hợp đồng hợp lệ: 0,21 ở validation, bằng lượt b (0,21). Correctness còn thấp hơn baseline, nhưng CI95 chứa 0.
- Câu trả lời trên hợp đồng hợp lệ chủ yếu chỉ ra *khoảng trống* ("không ghi giới hạn giờ làm thêm theo ngày", "chỉ ghi 'xét' nâng lương"), có khi viện dẫn chính Điều luật vừa được đưa vào. Câu T3 hỏi "điều khoản nào gây rủi ro", nên model luôn tìm ra rủi ro. Còn nhãn "compliant" chỉ có nghĩa là "không có lỗi bơm vào". Đây là lệch giữa câu hỏi và nhãn, không phải lỗi truy xuất.
- Chi phí tăng khoảng 4 lần token và 3 lần độ trễ.

Kết luận: không giữ cách gắn luật theo từng Điều. Ở cả hai lượt b và c, thay đổi định tuyến không cải thiện correctness một cách có ý nghĩa.
