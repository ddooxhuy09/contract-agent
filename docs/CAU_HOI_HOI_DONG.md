# 12 câu hỏi khó của hội đồng: câu trả lời nháp

Trạng thái: nháp, soạn từ hiện trạng mã nguồn đến commit ghi ở `docs/NHAT_KY_THAY_DOI.md`. Chỗ ghi **[ĐIỀN]** là số liệu hoặc sự thật chỉ bạn biết hoặc chỉ có sau khi chạy đánh giá thật; không điền số khi chưa có. Mọi số phải lấy từ `evaluation_results/RESULTS_TUAN.md` và `evaluation/gold/KAPPA.md`.

1. **Gold label do ai tạo, có chuyên gia kiểm không?**
   Hai người gán nhãn độc lập trên các Điều rút ngẫu nhiên có seed từ hợp đồng đã ẩn danh; chuyên gia **[ĐIỀN: ai, chuyên môn gì]** chốt các dòng bất đồng và kiểm mẫu khoảng 5 dòng đồng thuận. Nếu chưa có chuyên gia, nói thẳng "nhãn chưa được chuyên gia kiểm" và để dòng đó trong mọi bảng số liệu.

2. **Kappa là bao nhiêu? Bất đồng xử lý thế nào?**
   Kappa **[ĐIỀN từ KAPPA.md]** trên N **[ĐIỀN]** đơn vị. Dưới 0,6 thì thảo luận, sửa hướng dẫn gán nhãn, chuyên gia chốt các đơn vị bất đồng; danh sách bất đồng ghi trong `ghi_chep_gan_nhan.md`.

3. **Ba thay đổi thiết kế có được chọn sau khi xem kết quả test không?**
   **[ĐIỀN: chỉ bạn biết.]** Điều có thể chứng minh bằng git: bộ test chỉ được khóa ở tag `eval-frozen` và mọi thay đổi sau đó nằm ở `docs/NHAT_KY_THAY_DOI.md`. Đừng nói "không" nếu từng chỉnh sau khi xem kết quả.

4. **Hệ thống có bỏ điều khoản khi judge lỗi không? Đã sửa thế nào?**
   Trước đây có: judge lỗi hoặc trả JSON hỏng thì điều khoản bị coi là sạch, và một analysis rỗng còn được lưu vào cache. Nay điều khoản đó được ghi là chưa kiểm (`unchecked_error` hoặc `unparsable`) trong `analysis.coverage`, giao diện hiện số "Chưa kiểm", không còn banner xanh khi còn điều chưa kiểm, kết quả thiếu không được phục vụ từ cache, và không trích xuất được điều khoản nào thì trả lỗi 502 thay vì kết quả rỗng. Có test cho từng nhánh.

5. **Hệ thống khác gì PAKTON, Kyta, Ojas1584?**
   **[ĐIỀN: bạn cần đọc ba hệ thống này; tôi chưa kiểm chứng gì về chúng.]** Điểm của ContractLens có thể nêu mà có bằng chứng trong repo: phạm vi hợp đồng lao động Việt Nam, đối chiếu kho văn bản luật có trạng thái hiệu lực, báo cáo độ phủ, gold set có kappa và đo độ trung thực trích dẫn.

6. **Độ chính xác cảnh báo so với luật sư là bao nhiêu?**
   Không có đối chiếu với luật sư. Chỉ có độ chính xác so với gold set (nhãn người gán, chuyên gia **[ĐIỀN]**): Precision **[ĐIỀN]**, Recall **[ĐIỀN]**, khoảng tin cậy 95% bootstrap, cỡ mẫu N **[ĐIỀN]** Điều từ M **[ĐIỀN]** hợp đồng. Cỡ mẫu nhỏ nên khoảng rộng; các Điều cùng hợp đồng không độc lập.

7. **Hợp đồng dài hơn 12.000 ký tự xử lý thế nào?**
   Tách và đánh giá điều khoản chạy trên toàn văn bằng quy tắc regex. Giới hạn 12.000 ký tự chỉ áp cho lần gọi LLM bù các trường mà regex bỏ sót (ngày, giá trị hợp đồng, các bên…), có cảnh báo trong log khi bị cắt. Báo cáo cũ nói điều khoản sau mốc đó không được kiểm là chưa đúng. Chưa đo trên tập hợp đồng thật dài; **[ĐIỀN: độ dài trung bình các hợp đồng gold set]**.

8. **Bộ luật Lao động 2019 có được đánh dấu hiệu lực đúng không?**
   Trước khi sửa thì không: cả ba văn bản luật lao động chính mang trạng thái 4 ("hết hiệu lực một phần") nên toàn bộ chunk bị loại khỏi truy xuất (BLLĐ 874, NĐ 145/2020 674, Luật ATVSLĐ 516 chunk). Đã bật lại có sao lưu và hoàn tác được; chi tiết và giới hạn ở `docs/kiem_tra_hieu_luc.md`. Hạn chế còn lại: kho không biết điều nào của Nghị định 145/2020 đã bị sửa đổi sau này; 2033 văn bản trạng thái 4 khác vẫn bị loại.

9. **Chi phí và độ trễ mỗi hợp đồng là bao nhiêu?**
   Chưa có phép đo hệ thống. Điểm dữ liệu rời: phân tích lại một hợp đồng mẫu 5 điều mất khoảng 28 giây; có lần chạy mất hàng chục phút khi bị giới hạn tốc độ của Gemini (tầng miễn phí khoảng 20 yêu cầu mỗi ngày mỗi mô hình, theo ghi chú đánh giá cũ chưa xác minh). **[ĐIỀN nếu đo thêm]** số lần gọi LLM mỗi hợp đồng ≈ số Điều cần judge cộng một lần trích xuất bù trường.

10. **Chống prompt injection từ nội dung hợp đồng thế nào?**
    Chưa có biện pháp riêng: nội dung hợp đồng được đưa thẳng vào prompt (`app/core/prompts.py`). Giảm thiểu hiện có: đầu ra judge phải qua `parse_json_object` và kiểm `severity` hợp lệ, nên chỉ ra được cảnh báo chứ không thực thi hành động nào; dữ liệu theo từng người dùng. Nêu đây là hạn chế đã biết, không nói đã chống được.

11. **Dữ liệu hợp đồng gửi sang Gemini có tuân thủ quy định bảo vệ dữ liệu cá nhân không?**
    Nội dung hợp đồng (có thể có tên, địa chỉ, lương) được gửi tới API Gemini. Chưa đánh giá tuân thủ pháp lý. Với gold set, hợp đồng được ẩn danh trước khi dùng. **[ĐIỀN: bạn cần đối chiếu quy định bảo vệ dữ liệu cá nhân hiện hành và điều khoản dịch vụ của Gemini trước khi khẳng định gì.]**

12. **Pytest pass bao nhiêu? Chạy được trên máy khác không?**
    Xem `docs/test_final.txt`. Khi có `data/` và `evaluation_results/`: tất cả pass, 1 bị bỏ qua. Trên bản clone mới không có hai thư mục này (bị `.gitignore`), 17 test đọc dữ liệu sẽ fail (`docs/test_baseline.txt`); đây là lỗi môi trường, chưa làm các test đó tự bỏ qua. Môi trường kiểm thử: container Python 3.12.
