# Phạm vi đề tài

ContractLens rà soát **hợp đồng lao động tiếng Việt** và đối chiếu với quy định pháp luật lao động đã nạp vào hệ thống.

## Hệ thống làm gì
- Đọc hợp đồng `.docx`, `.pdf` (có lớp chữ) hoặc ảnh, tách điều khoản và thông tin các bên.
- Phát hiện rủi ro theo 7 quy tắc "luật đỏ" (làm thêm giờ không trả lương, không đóng BHXH, giữ giấy tờ gốc, mất lương khi nghỉ việc, phạt trừ lương, chấm dứt hợp đồng với lao động nữ mang thai, cấm khởi kiện), kiểm tra nội dung bắt buộc và căn cứ pháp lý ở phần mở đầu.
- Để mô hình ngôn ngữ đánh giá từng điều khoản dựa trên điều luật truy xuất được, kèm trích dẫn.
- Trả lời câu hỏi về hợp đồng đã tải lên, có nguồn là điều khoản và điều luật.
- Báo cáo **độ phủ**: bao nhiêu điều khoản đã được kiểm và bao nhiêu chưa kiểm được (xem `analysis.coverage`).

## Hệ thống không làm gì
- Không phải tư vấn pháp lý và không thay thế luật sư.
- Không xử lý hợp đồng dân sự hay thương mại.
- Không đảm bảo độ chính xác của kết quả; kết quả đo được ghi ở `evaluation_results/RESULTS_TUAN.md`, kèm cỡ mẫu và khoảng tin cậy.
- Không hỗ trợ tệp `.doc` (cần chuyển sang `.docx`) và PDF dạng ảnh quét không có lớp chữ.
- Chỉ dùng một nhà cung cấp mô hình ngôn ngữ (Gemini).
- Giao diện chưa có bước duyệt thủ công; cơ chế duyệt (`review_mode`, `/analyze/resume`) chỉ có ở API.
