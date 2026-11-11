# Hợp đồng nền có sạch không? Cờ của pipeline trên hợp đồng nền chưa bơm lỗi

**Phân loại dưới đây là của tác giả (không phải luật sư), chưa có chuyên gia xác nhận.** Căn cứ trích từ văn bản Bộ luật Lao động 45/2019/QH14 trong DB của dự án (`legal_documents`, doc_id 139264, đọc chỉ-đọc).

Cấu hình: pipeline đầy đủ `run_analysis_workflow`, judge Groq `openai/gpt-oss-120b` (nhiệt độ 0), cùng cấu hình lần 48 ca, commit `f23ba86` (đã chạy bằng `python -m evaluation.injection.base_flags`; dữ liệu thô ở `base_contract_flags.json`). Chỉ có **một** hợp đồng nền (`evaluation/injection/base_contract.txt`), nên chạy một lần; 11/11 Điều được kiểm, không Điều nào chưa kiểm. Chạy một lần, chưa đo độ lặp lại.

Kết quả: **8 cờ (7 warning, 1 critical) trên hợp đồng nền**. Chỉ Điều 1, 3, 4, 11 không bị gắn cờ.

| # | Vị trí | Mức | Cờ của pipeline (tóm tắt) | Phân loại | Nhận xét |
|---|---|---|---|---|---|
| 1 | Toàn văn | warning | Thiếu nội dung chủ yếu theo Điều 21 khoản 1: địa chỉ NSDLĐ, ngày sinh/giới tính/CCCD/nơi cư trú NLĐ, "thời hạn trả lương" | **(b)** cảnh báo thiếu có căn cứ, trừ một ý | Phần lớn đúng (xem căn cứ bên dưới). Riêng ý "thiếu thời hạn trả lương" sai: khoản 3.2 ghi "trả vào ngày 05 hằng tháng" |
| 2 | Điều 2 | warning | Thiếu giới hạn giờ làm thêm | **(a)** báo nhầm | Khoản 2.3 đã dẫn "theo quy định của Bộ luật Lao động"; hợp đồng không bắt buộc chép lại mức trần Điều 107 |
| 3 | Điều 5 | warning | Chưa quy định NSDLĐ giữ, bảo quản, trả giấy tờ bản chính | **(a)** báo nhầm, khuyến nghị đi ngược luật | Khoản 5.2 "NLĐ tự quản lý bản chính" chính là cách làm hợp pháp; đề nghị cho NSDLĐ giữ bản chính trái Điều 17 khoản 1 (sửa ngày 11/11/2026: bản trước ghi nhầm khoản 2) |
| 4 | Điều 6 | warning | 6.2 thiếu nội dung hợp đồng đào tạo nghề (Điều 62) và việc ký HĐLĐ sau đào tạo | **(a)** báo nhầm | 6.2 dẫn tới một hợp đồng đào tạo nghề riêng; các nội dung Điều 62 khoản 2 thuộc hợp đồng riêng đó, không phải hợp đồng lao động |
| 5 | Điều 7 | warning | 7.2 cho cách chức, sa thải "không điều kiện", trích Nghị định 27/2014 | **(a)** báo nhầm | 7.2 nêu đúng các hình thức của Điều 124 và "theo đúng trình tự pháp luật"; Nghị định 27/2014 chỉ áp dụng cho người giúp việc gia đình, không áp dụng ở đây |
| 6 | Điều 8 | **critical** | Báo trước 30 ngày không đáp ứng Điều 35 (cho rằng cần 45 ngày) | **(a)** báo nhầm rõ ràng | Hợp đồng xác định thời hạn 24 tháng: Điều 35 khoản 1 điểm b yêu cầu ít nhất 30 ngày. 45 ngày chỉ áp dụng cho hợp đồng không xác định thời hạn |
| 7 | Điều 9 | warning | 9.2 chỉ dẫn chung, chưa cấm chấm dứt hợp đồng với lao động nữ mang thai/nuôi con | **(c)** không chắc | Điều 137 khoản 3 đã cấm theo luật nên hợp đồng không bắt buộc nhắc lại; nhưng 9.2 mơ hồ về điểm này, đây là góp ý soạn thảo hơn là vi phạm |
| 8 | Điều 10 | warning | Thiếu thời hạn yêu cầu hòa giải và khởi kiện, trích Nghị định 27/2014 | **(a)** báo nhầm | Thời hiệu do Điều 190 quy định sẵn; hợp đồng không bắt buộc chép lại. Nghị định 27/2014 không áp dụng |

Tổng: **(a) 6, (b) 1, (c) 1.**

## Căn cứ cho nhóm (b) (cờ #1)
Bộ luật Lao động 2019, **Điều 21 khoản 1**: hợp đồng lao động phải có những nội dung chủ yếu, trong đó:
- điểm a: "Tên, địa chỉ của người sử dụng lao động và họ tên, chức danh của người giao kết hợp đồng lao động bên phía người sử dụng lao động";
- điểm b: "Họ tên, ngày tháng năm sinh, giới tính, nơi cư trú, số thẻ Căn cước công dân, Chứng minh nhân dân hoặc hộ chiếu của người giao kết hợp đồng lao động bên phía người lao động".

Hợp đồng nền chỉ ghi tên công ty và họ tên NLĐ. Không có địa chỉ công ty, ngày sinh, giới tính, nơi cư trú, số giấy tờ. Cờ này đúng về nội dung cho các điểm a, b.

Ngoài ra, hợp đồng nền còn thiếu điểm e (chế độ nâng bậc, nâng lương) và điểm h (trang bị bảo hộ lao động) của cùng khoản; pipeline **không** nêu hai điểm này, nghĩa là cờ #1 cũng chưa đầy đủ.

## Kết luận về độ sạch của hợp đồng nền
1. **Hợp đồng nền không hoàn toàn sạch**: thiếu thông tin định danh các bên (Điều 21), chưa theo mẫu hợp đồng thật. Lỗi này nằm ở cách soạn nền của tác giả, không phải ở hệ thống. Khung điều khoản chứa 8 luật đỏ thì không bị vi phạm theo đánh giá của tác giả, nhưng tác giả cũng không phải chuyên gia.
2. **Phần lớn cờ (6/8) là báo nhầm của judge** trên những Điều mà tác giả cho là hợp lệ; cờ critical ở Điều 8 sai về số liệu luật.
3. **Ảnh hưởng tới số 48 ca** (mô tả trên dữ liệu đã có, *không* tính lại chỉ số, *không* chạy lại): ở các ca hợp lệ (near-miss), Điều bơm trùng một Điều mà nền sạch cũng bị gắn cờ (Điều 2, 5, 6, 7, 8, 9, 10) bị gắn cờ **14/21**; ở Điều 4 (nền không bị cờ) là **1/3**. Do đó phần lớn "dương tính giả" 15/24 ở lần 48 ca có thể là xu hướng gắn cờ sẵn của judge trên các Điều đó, không nhất thiết do nội dung near-miss. Đây là quan sát *sau khi xem dữ liệu*, cỡ mẫu nhỏ, chỉ mang tính gợi ý. Chỉ số khai báo ban đầu (precision 0,62) giữ nguyên, không sửa.
4. Bộ 80 ca đã đóng băng (`injection-frozen`) không bị sửa. Nếu muốn bộ ca sạch hơn thì làm bộ mới, không sửa bộ này.
