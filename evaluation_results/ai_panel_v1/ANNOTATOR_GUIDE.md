# Hướng dẫn gán nhãn (hội đồng AI, mỗi phòng làm độc lập)

Bạn là một phòng thẩm định pháp lý độc lập (luật Việt Nam). Gán nhãn cho **từng** mục trong `packet.jsonl` (128 mục).

## Được và không được đọc
- CHỈ đọc: `evaluation_results/ai_panel_v1/packet.jsonl`, `evaluation_results/ai_panel_v1/law.json`, file hướng dẫn này.
- KHÔNG đọc bất kỳ file nào khác trong repo (đặc biệt `key.json`, `room_*.jsonl` của phòng khác, `merged.jsonl`, `evaluation/`, `evaluation_results/runs/`, `docs/`), không tìm kiếm (Grep/Glob) trong repo, không chạy code, không dùng web. Không đọc `.env`.
- Chỉ ghi đúng một file: `evaluation_results/ai_panel_v1/room_<PHÒNG>.jsonl`.

## Mỗi mục có
`pid`, `contract_type`, `as_of_date` (thời điểm đánh giá; null = hiện hành), `transaction_date` (ngày xác lập giao dịch, nếu có), `question`, `clause_ids`, `clause_text` (nguyên văn điều khoản; rỗng nếu câu hỏi là tình huống), `law_refs` (khoá vào `law.json`).
`law.json` là **tài liệu tham khảo**, không phải đáp án: có thể thiếu Điều cần thiết hoặc chứa Điều không liên quan. Dùng thêm hiểu biết của bạn về pháp luật Việt Nam, áp dụng văn bản có hiệu lực tại `as_of_date` (lưu ý quy định chuyển tiếp nếu có `transaction_date`).

## Nhãn (`label`)
- `violation`: nội dung điều khoản / tình huống **trái** quy định bắt buộc hoặc điều cấm, hoặc làm quyền của bên được luật bảo vệ (người lao động, người tiêu dùng…) thấp hơn mức luật định; hoặc câu hỏi hỏi "có được/có hợp pháp không" và câu trả lời đúng là "không được / trái luật".
- `compliant`: hợp pháp — kể cả biến thể hợp lệ, câu phủ định ("không được giữ giấy tờ"), dẫn chiếu "theo quy định pháp luật", hoặc thoả thuận có lợi hơn cho người lao động/người tiêu dùng.
- `n/a`: câu hỏi không yêu cầu kết luận hợp pháp/trái luật (hỏi nội dung, luật nào áp dụng, tình trạng hiệu lực, liệt kê…).
- `unclear`: thông tin không đủ để kết luận một cách có trách nhiệm.

Lưu ý: hợp đồng **không** bắt buộc chép lại luật; thiếu một nội dung chỉ là trái luật khi đó là nội dung bắt buộc (vd. Điều 21 BLLĐ 2019) hoặc khi chính câu chữ làm sai lệch quyền/nghĩa vụ luật định. Đánh giá đúng điều khoản được hỏi, không đánh giá các điều khoản khác.

## Định dạng đầu ra — mỗi dòng một JSON, đủ 128 dòng, mỗi `pid` đúng một lần
```json
{"pid": "P101", "label": "violation", "articles": [{"doc": "45/2019/QH14", "article": 62, "clause": 3}], "reason": "≤3 câu tiếng Việt, nêu căn cứ.", "confidence": 0.9}
```
- `articles`: căn cứ chính (số hiệu văn bản như `45/2019/QH14`, số Điều nguyên, `clause` số Khoản hoặc null); rỗng nếu `n/a`.
- `confidence`: 0–1.
Làm lần lượt theo thứ tự được giao, ghi nối dần vào file (mỗi lần một nhóm ~20 mục) để không mất việc. Xong thì đọc lại file, kiểm tra đủ 128 `pid` khác nhau và đúng định dạng.
