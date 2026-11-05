# Nhật ký thay đổi theo kế hoạch 1 tuần

Ghi lại các quyết định và thay đổi so với kế hoạch gốc. Mốc đối chiếu: tag `baseline-tuan-0` (commit `dd1782f`).

## Ngày 1
- **Không dùng `git add -A`** để chụp snapshot: sẽ kéo cả các file riêng chưa theo dõi (ví dụ `.serena/`, `docs/presentations/`, `tests/fixtures/legal_qa.jsonl` 15 MB). Chỉ gắn tag lên HEAD đã sạch.
- **Môi trường kiểm thử sạch** là container api (Python 3.12), không phải venv 3.12 cục bộ (máy dùng 3.11). Kết quả: `docs/test_baseline.txt`.
- **Hiệu lực luật:** cờ sai, đã sửa dữ liệu cho 3 văn bản luật lao động, có bảng sao lưu. Chi tiết và giới hạn: `docs/kiem_tra_hieu_luc.md`.

## Ngày 2: lỗi nuốt âm thầm
- Điều khoản mà judge lỗi hoặc trả JSON hỏng không còn bị coi là sạch. `analysis.coverage` ghi `tong_so_dieu`, `da_kiem`, `chua_kiem`, `ty_le_da_kiem` và danh sách điều chưa kiểm kèm trạng thái `unchecked_error` hoặc `unparsable`.
- Judge trả JSON thiếu `severity` hoặc có `severity` ngoài `critical|warning|ok` cũng tính là không dùng được (trước đây thiếu `severity` bị coi là "ok").
- Không trích xuất được điều khoản nào: `/analyze` trả 502, không lưu kết quả (trước đây lưu một analysis rỗng rồi phục vụ từ cache).
- Cache chỉ phục vụ kết quả đầy đủ: analysis không có điều khoản hoặc có `chua_kiem > 0` sẽ được chạy lại.
- Giao diện: điều chưa kiểm tính riêng ("Chưa kiểm"), không tính vào "Ổn", và banner xanh không hiện khi còn điều chưa kiểm.
- Không thêm trường vào `RiskItem`; chỉ thêm `coverage` tùy chọn vào `ContractAnalysis`.

## Ngày 3: đầu vào
- `.doc` bị từ chối trước khi lưu (400, "chuyển sang .docx"). Trước đây `.doc` được nhận rồi python-docx thất bại.
- Tệp không đọc được (PDF ảnh quét không có lớp chữ, tệp hỏng) bị từ chối với 400 và xóa tệp đã lưu. Trước đây vẫn lưu hợp đồng trạng thái `uploaded` và giao diện đi tiếp sang bước phân tích rồi báo lỗi khó hiểu. Lỗi khi tạo chunk/embedding/ghi DB giờ lan ra (không nuốt), tệp đã lưu được xóa.
- Xóa `app/document/file_handler.py`: không nơi nào gọi.
- **Giới hạn 12.000 ký tự** (`clause_parser._LLM_GAPFILL_CHAR_LIMIT`): chỉ giới hạn đầu vào của LLM bù các trường mà regex bỏ sót; việc tách và đánh giá điều khoản chạy trên toàn văn. Báo cáo cũ nói điều khoản sau 12.000 ký tự không được kiểm là chưa đúng. Đã thêm cảnh báo log khi bị cắt. Chưa đo trên 5–10 hợp đồng: máy chỉ có 1 hợp đồng mẫu thật (3.605 ký tự, dưới ngưỡng) nên cần bạn cung cấp thêm file để đo.
