# Bộ test trình bày với hội đồng

Tài liệu tóm tắt hai bộ test của đề tài, cách xây dựng, cách kiểm tra và kết quả. Chi tiết thí nghiệm: `docs/CHUONG_DANH_GIA_THUC_NGHIEM.md`.

| | Bộ 1: truy xuất pháp luật | Bộ 2: rà soát hợp đồng lao động |
|---|---|---|
| Nguồn nhãn | Dữ liệu bên ngoài (Zalo AI Challenge 2021 – Legal Text Retrieval) | Bơm lỗi: nhãn có được do cách tạo ca |
| Quy mô | 3.196 câu hỏi, 724 văn bản; test 2.673 câu (556 câu đánh giá được) | 80 ca (8 luật đỏ × 10) + 32 ca kiểm tra phủ định |
| Đo cái gì | Module tìm điều luật | Phát hiện điều khoản vi phạm và báo nhầm |
| Kiểm tra nhãn | Đối chiếu 100% với bản công bố trên Hugging Face | Đối chiếu từng ca với văn bản BLLĐ 2019 và Luật BHXH 2024 |
| Đóng băng | tag `legalqa-split-frozen` | tag `injection-frozen`, `injection-v2-frozen` |

---

## Bộ 1. Truy xuất pháp luật (bộ thu thập từ bên ngoài)

**Nguồn.** `data/dataset.csv` trùng 100% (3.196/3.196 câu: mã câu hỏi, nội dung câu hỏi và nhãn) với bộ Hugging Face `DaHaDaHa/zac2021`. Theo tên và cấu trúc, đây là dữ liệu Zalo AI Challenge 2021 – Legal Text Retrieval. Trang Hugging Face không có mô tả, nên giấy phép và người tạo câu hỏi **chưa xác định**; khi trình bày cần nói đúng như vậy.

**Định dạng.** Mỗi câu hỏi có nhãn là (số hiệu văn bản, số Điều). Ví dụ (đã đối chiếu với bản Hugging Face):

| Câu hỏi | Nhãn |
|---|---|
| Hội Chữ thập đỏ có được ưu tiên khi xuất nhập khẩu thuốc, thiết bị y tế khi khẩn cấp không? | 03/2011/NĐ-CP, Điều 6 |
| Mức phạt khi điều khiển xe ô tô lạng lách | 100/2019/NĐ-CP, Điều 5 |
| Liên thông trong giáo dục từ tháng 7/2020 được quy định như thế nào? | 43/2019/QH14, Điều 10 |
| Quản lý giấy phép KCB trong quân đội được quy định như thế nào? | 50/2019/NĐ-CP, Điều 25 |

**Cách dùng.** Chia dev/test theo văn bản (dev 523, test 2.673). Mọi điều chỉnh làm trên dev; test chạy một lần cho mỗi cấu hình, có file khoá chặn chạy lại.

**Kết quả chính (test, 556 câu có điều luật còn hiệu lực trong kho):** vector R@5 = 0,795 [0,763; 0,827]; hybrid ban đầu kém vector có ý nghĩa thống kê (ΔMRR = −0,040 [−0,048; −0,031]). Chỉ 20,8% câu test đánh giá được vì phần lớn văn bản năm 2021 đã hết hiệu lực; tính trên toàn bộ 2.673 câu, R@10 khoảng 17%.

---

## Bộ 2. Rà soát hợp đồng lao động (bộ tự xây dựng)

### Cách xây dựng
- **Phương pháp bơm lỗi:** một hợp đồng lao động nền 11 Điều; mỗi ca thay đúng một Điều bằng một điều khoản **vi phạm** hoặc **hợp lệ gần giống** (near-miss). Nhãn có được do cách viết ca, không do hệ thống hay LLM gán.
- **8 luật đỏ** theo BLLĐ 2019: làm thêm giờ không trả lương / bắt buộc; không đóng BHXH; giữ bản chính giấy tờ; bồi thường đào tạo cố định; phạt tiền / khấu trừ lương; tước lương tháng cuối; chấm dứt vì kết hôn / mang thai; cấm khởi kiện.
- **Đa dạng diễn đạt:** mỗi luật có 3/5 ca vi phạm viết khác mẫu quen thuộc (diễn đạt lại, số bằng chữ, viết tắt, câu dài). Ca hợp lệ gồm câu phủ định chứa từ khoá, biến thể hợp pháp, ca sát ngưỡng.
- **Đóng băng** trước khi chạy hệ thống; cách chấm khai báo trước trong `evaluation/injection/README.md`.

### Ví dụ (mỗi luật một cặp vi phạm / hợp lệ)

| Luật | Vi phạm | Hợp lệ (gần giống) | Căn cứ |
|---|---|---|---|
| Làm thêm giờ | OT-04: giờ làm thêm ngày thường, nghỉ, lễ đều trả 100%, không áp dụng hệ số | OT-07: "Công ty cam kết không trả lương làm thêm giờ thấp hơn mức tối thiểu..." | Điều 98 k1, Điều 107 k2 |
| BHXH | BH-04: hai bên đồng ý không kê khai lao động với cơ quan BHXH 12 tháng đầu, trả phụ cấp tiền mặt thay thế | BH-07: NLĐ đang hưởng lương hưu, Công ty không đóng BHXH bắt buộc và chi trả khoản tương đương | Điều 168; Luật BHXH 2024 Điều 2 k7 |
| Giấy tờ | GT-03: Công ty tạm giữ CCCD gốc và hộ chiếu đến khi đủ 12 tháng | GT-07: xuất trình bản chính để đối chiếu, trả lại ngay | Điều 17 k1 |
| Đào tạo | DT-02: hoàn lại phí đào tạo bằng sáu tháng lương, không phụ thuộc chi phí thực tế | DT-09: hoàn trả chi phí thực tế có chứng từ theo hợp đồng đào tạo, trừ phần đã làm việc | Điều 62, Điều 40 k3 |
| Phạt tiền | KL-02: đi muộn quá 15 phút bị trừ 200.000 đồng vào lương | KL-07: khấu trừ để bồi thường tài sản hư hỏng, không quá 30% lương thực trả | Điều 127 k2, Điều 102 |
| Lương tháng cuối | LU-02: nghỉ không báo trước đủ 30 ngày thì giữ lại toàn bộ lương kỳ cuối | LU-07: chấm dứt trái luật chỉ bồi thường nửa tháng lương và tiền những ngày không báo trước; lương đã làm vẫn trả đủ | Điều 94 k1, Điều 40 k2 |
| Thai sản | TS-02: lao động nữ có thai trong 24 tháng đầu thì hợp đồng đương nhiên hết hiệu lực | TS-08: chấm dứt do hai bên thỏa thuận theo đề nghị tự nguyện của NLĐ | Điều 137 k3, Điều 34 k3 |
| Khởi kiện | TC-02: phán quyết của Ban Giám đốc là chung thẩm, NLĐ từ bỏ quyền đưa ra cơ quan tư pháp | TC-09: hòa giải nội bộ 07 ngày, không làm mất quyền yêu cầu hòa giải viên hoặc khởi kiện | Điều 187, 188, 190 |

### Kiểm tra nhãn (ngày 11/11/2026)
Từng ca trong 112 ca được đối chiếu với văn bản BLLĐ 2019 (bản toàn văn trên hrspring.vn) và Luật BHXH 2024 (Điều 2 khoản 7, Điều 33 khoản 5). Bảng kiểm tra đầy đủ, có cột để duyệt: `docs/bo_test_hoi_dong/REVIEW_BO_TEST_HOP_DONG.csv`.

| Kết luận | Số ca |
|---|---:|
| Đúng | 101 |
| Đúng, có lưu ý (câu chữ hoặc phụ thuộc diễn giải) | 10 |
| Cần xem lại (nhãn tranh cãi được) | 1 (LU-09) |
| Sai nhãn | 0 |

- **4 ca đào tạo cố định** (DT-01, DT-05, DT2-V1, DT2-V2): nhãn vi phạm theo cách hiểu phổ biến; luật không cấm thẳng con số "X tháng lương", nên mức chắc chắn trung bình.
- **LU-09** (nhãn hợp lệ): câu "thanh toán đồng thời với việc hoàn tất bàn giao" có thể bị hiểu là điều kiện hoá việc trả lương.
- Đây là kiểm tra của người làm đề tài có trợ lý AI hỗ trợ, **không phải xác nhận của luật sư**.

### Kết quả chính
- Luật cố định (80 ca): bắt đúng 16/16 ca viết theo mẫu, nhưng recall 0,40 trên bộ có 60% ca khác mẫu; báo nhầm 14/40 ca hợp lệ.
- Pipeline có LLM judge (48 ca, Groq `gpt-oss-120b`): recall 1,00 (24/24), precision 0,62; báo nhầm 15/24 ca hợp lệ.
- Hợp đồng nền: 6/8 cờ là báo nhầm, có lỗi áp sai Điều 35 và khuyến nghị trái Điều 17 k1.

---

## Cách nói với hội đồng (gợi ý)
1. "Bộ 1 là dữ liệu bên ngoài, nhãn không do em tạo; em chia dev/test và chỉ chạy test một lần."
2. "Bộ 2 em tự xây vì chưa có bộ công khai cho hợp đồng lao động tiếng Việt. Em dùng bơm lỗi để nhãn có được do cấu tạo, đóng băng trước khi chạy, và đối chiếu từng ca với văn bản luật."
3. "Giới hạn: chưa có luật sư xác nhận; ca do em viết nên không đại diện cho tỷ lệ đúng trên hợp đồng thực tế."
4. "Kết luận: hệ thống nhạy nhưng báo nhầm nhiều, nên đầu ra là danh sách điểm cần người kiểm tra, không phải kết luận pháp lý."
