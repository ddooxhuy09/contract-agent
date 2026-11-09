# Bộ bơm lỗi hợp đồng: kết quả

Bộ đóng băng ở commit `e268fcb` (tag `injection-frozen`): 8 luật đỏ × (5 vi phạm + 5 hợp lệ) = 80 ca. Các ca do tác giả viết, chưa có luật sư xác nhận. Đây là **kiểm tra khả năng phát hiện, không phải tỷ lệ đúng trên hợp đồng thực tế**. Cách chấm đã khai báo trong `evaluation/injection/README.md` trước khi chạy hệ thống. Code `app/agents/labor_red_flags.py` không bị sửa.

Lưu ý: `_FLAGS` có **8** luật đỏ (yêu cầu ban đầu nói 7).

## (a) Rule-only, toàn bộ 80 ca (không LLM)
| Luật | TP | FP | FN | Precision | Recall | F1 | FP trên near-miss của chính nó |
|---|---:|---:|---:|---:|---:|---:|---:|
| ot_unpaid | 2 | 1 | 3 | 0,67 | 0,40 | 0,50 | 1/5 |
| no_bhxh | 2 | 3 | 3 | 0,40 | 0,40 | 0,40 | 3/5 |
| retain_id_papers | 2 | 3 | 3 | 0,40 | 0,40 | 0,40 | 3/5 |
| training_cost_flat | 2 | 1 | 3 | 0,67 | 0,40 | 0,50 | 1/5 |
| fine_deduct_wage | 2 | 2 | 3 | 0,50 | 0,40 | 0,44 | 2/5 |
| forfeit_wage_quit | 2 | 1 | 3 | 0,67 | 0,40 | 0,50 | 1/5 |
| terminate_pregnancy | 2 | 2 | 3 | 0,50 | 0,40 | 0,44 | 2/5 |
| ban_lawsuit | 2 | 1 | 3 | 0,67 | 0,40 | 0,50 | 1/5 |
| **Tổng (micro)** | 16 | 14 | 24 | 0,53 [0,36; 0,73] | 0,40 [0,25; 0,56] | 0,46 [0,30; 0,60] | 14/40 ca hợp lệ bị kích hoạt |

CI95 bootstrap theo ca (1000 lần, seed 20261109). Mỗi luật chỉ 10 ca nên chỉ số từng luật rất thô. Số `unchecked` ở chế độ này bằng 0 (không có bước LLM).

### Phân tích
- **Cách đọc recall 0,40 phải rất thận trọng.** Tôi cố ý viết 3/5 ca vi phạm mỗi luật bằng cách diễn đạt khác mẫu regex (yêu cầu của bài là tối thiểu 2/5), nên recall bị chặn trên ở 0,40 và con số này đo **thiết kế của bộ ca**, không phải recall kỳ vọng trên hợp đồng thật. Kết quả khớp tuyệt đối với dự đoán của tác giả về regex ở 77/80 ca; 3 ca lệch đều là near-miss mà tôi dự đoán là bẫy nhưng regex không trúng.
- **Bỏ sót (24 FN):** toàn bộ là ca không viết theo mẫu: paraphrase 10, số bằng chữ 5, viết tắt 5, câu dài 4. **Toàn bộ 16 ca viết theo mẫu quen thuộc đều bắt được (16/16).** Quy tắc xác định bắt đúng mẫu nhưng không khái quát hoá sang cách diễn đạt khác (ví dụ "giữ lại lương kỳ cuối", "tạm giữ thẻ Căn cước", "trừ 200.000 đồng vào lương", "có thai … đương nhiên hết hiệu lực").
- **Báo nhầm (14 FP trên 40 ca hợp lệ, 35%):** 7 ca là câu phủ định hợp lệ ("Công ty không áp dụng hình thức kỷ luật phạt tiền", "cam kết không giữ giấy tờ …") và 7 ca là nội dung hợp pháp có chứa từ khoá (NLĐ đang hưởng lương hưu, tháng nghỉ không lương trên 14 ngày không đóng BHXH, hoàn trả chi phí đào tạo theo hợp đồng đào tạo nghề có chứng từ, quyền NLĐ nữ mang thai tự chấm dứt theo Điều 138). Nguyên nhân: bước quét dùng `pattern.search` trên toàn văn và **không xét phủ định** (hàm `_violates` có xét phủ định nhưng chỉ dùng khi kiểm tra bản sửa). 23/40 ca hợp lệ không bị báo.
- Không có luật nào kích hoạt nhầm trên ca của luật khác (0 lần kích hoạt chéo). Mọi cờ đều ở mức `critical`.

## (b) Pipeline đầy đủ có Gemini: **chưa hoàn thành, chỉ 2/48 ca mẫu**
- Mẫu đã khai báo: 3 vi phạm + 3 hợp lệ mỗi luật (48 ca, seed 20261109), xen kẽ. Lý do dùng mẫu: mỗi hợp đồng 11 Điều cần khoảng 12 lượt gọi Gemini, hạn mức gói miễn phí là 20 lượt/ngày/khóa/mô hình, nên toàn bộ 80 ca cần khoảng 960 lượt (hàng tuần), mẫu 48 ca khoảng 580 lượt (khoảng 2 tuần).
- Đã chạy 2 ca (OT-02, OT-08); sau đó quota ngày cạn trên mọi khóa (HTTP 429, "limit: 20", thử lại sau khoảng 23 giờ 46 phút). Không có lượt gọi nào khác. Resume: `python -m evaluation.injection.run full` (các ca đã lưu được bỏ qua; ca mà Điều bơm chưa kiểm do quota không được lưu).
- Với n=2 **không đưa ra precision/recall**. Hai quan sát định tính, chỉ n=2:
  - OT-02 (vi phạm, regex bỏ sót): judge gắn `critical` đúng tại Điều bơm ("Vi phạm quy định về thanh toán tiền lương làm thêm giờ"). Tức là bước LLM bắt được ca mà quy tắc bỏ sót.
  - **Judge gắn cờ gần như mọi Điều của hợp đồng nền sạch** (cả hai hợp đồng: 10/10 và 8/10 Điều khác Điều bơm bị gắn `warning`/`critical`, phần lớn kiểu "thiếu nội dung…"). OT-08 là ca hợp lệ (đúng ngưỡng 40 giờ/tháng) nhưng bị gắn `critical` "Thiếu giới hạn thời giờ làm thêm" dù điều khoản đã nêu giới hạn. Nếu hiện tượng này đúng trên cả mẫu, định nghĩa chỉ số đã khai báo ("có cờ critical/warning tại Điều bơm") sẽ cho độ đặc hiệu rất thấp và precision gần tỷ lệ ca vi phạm; khi đó cần phân tích bổ sung (ví dụ chỉ tính `critical`, hoặc khớp theo luật qua `findings.key` đối với phần quy tắc) và phải ghi rõ đó là phân tích sau khi xem dữ liệu, không thay cho chỉ số đã khai báo.
- Cấu hình truy xuất khi chạy: mặc định mới `legal_retrieval_mode = vector`, commit `e268fcb`.

## Việc còn lại
1. Chạy tiếp (b) qua nhiều ngày bằng lệnh resume ở trên cho đến khi đủ 48 ca, hoặc chấp nhận mẫu nhỏ hơn và ghi rõ.
2. Quyết định cách xử lý FP của quy tắc (xét phủ định trước khi kích hoạt): thay đổi `app/`, không làm trong lượt này.
3. Nhờ luật sư xác nhận nhãn 80 ca, đặc biệt các near-miss phụ thuộc diễn giải.

## Pipeline đầy đủ, mẫu 48 ca (judge Groq `openai/gpt-oss-120b`)
Hoàn tất 48/48 ca (3 vi phạm + 3 hợp lệ mỗi luật, seed 20261109), 0 Điều chưa kiểm. Judge đổi từ Gemini sang Groq vì hết quota Gemini; khai báo trong NHAT_KY trước khi chạy. Hai ca Gemini cũ nằm ở `full_gemini_pilot/`, không tính.

| Chỉ số (Điều bơm bị gắn critical/warning) | Giá trị |
|---|---|
| TP / FP / FN / TN | 24 / 15 / 0 / 9 |
| Precision | 0,62 (CI95 0,46-0,76) |
| Recall | 1,00 (24/24; CI suy biến) |
| F1 | 0,76 (CI95 0,63-0,87) |

- Judge bắt cả 24 ca vi phạm, kể cả các ca diễn đạt khác mẫu mà rule-only bỏ sót (recall 0,40).
- Nhưng gắn cờ 15/24 ca hợp lệ (62%): 8 `lawful_variant`, 5 `negation_trap`, 1 `number_words`, 1 `long_sentence`. Judge phân biệt kém giữa near-miss và vi phạm.
- Điều khác ngoài Điều bơm bị gắn cờ ở 48/48 ca (trung bình 5,4 Điều/ca, trên hợp đồng nền sạch). Chỉ số ở mức Điều bơm vì vậy không phản ánh số báo nhầm toàn hợp đồng.
- Kết quả là của một model, một lần chạy, 48 ca do tác giả viết; không so sánh được trực tiếp với Gemini.
