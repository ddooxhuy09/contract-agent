# ContractLens v0.4: Bản xem trước 34 test case

Bộ mô phỏng, **không phải ground truth pháp lý đã được chuyên gia chứng nhận**. Có 20 case từ v0.3 và 14 case mới kiểm tra luật cũ/luật mới/chuyển tiếp/sửa đổi/bổ sung.

Mỗi câu hỏi được tạo từ một hoặc nhiều điều khoản và tình huống; câu hỏi không được lấy nguyên xi từ một benchmark công khai. Độ khó được xác định bằng độ phức tạp nghiệp vụ và đường đi trong đồ thị quan hệ; tất cả case đều có `difficulty.level` là easy/medium/hard/expert.

| ID | Độ khó | Mốc pháp lý | Câu hỏi | Căn cứ bắt buộc | Quan hệ |
|---|---|---|---|---|---|
| MIX-017 | easy | 2026-10-17 | Có được loại trừ toàn bộ trách nhiệm pháp lý bắt buộc với người tiêu dùng? | CON-25.1 | — |
| TEMP-006 | expert | 2024-08-10 | Cùng hợp đồng điện tử lập 15/06/2024 nhưng ngày 10/08/2024 hai bên thỏa thuận áp dụng luật mới. Có còn mặc định dùng Luật 2005 theo quy định chuyển tiếp? | E23-53.1, E23-52.1 | REPL-E-2024 |
| MIX-018 | hard | 2026-10-17 | Đã bấm Đồng ý trên website thì điều khoản tước quyền khiếu kiện có hợp pháp? | E-36.3, CON-25.2 | — |
| TEMP-014 | hard | 2020-10-10 | Tháng 10/2020, hợp đồng yêu cầu doanh nghiệp giữ bản chính giấy tờ tùy thân. Dẫn Điều 20 Bộ luật Lao động 2012 hay Điều 17 Bộ luật Lao động 2019? | L12-20.1 | REPL-LAB-2021 |
| MIX-007 | hard | 2026-10-17 | Tại sao tên gọi cộng tác viên không tự động miễn BHXH? | LAB-13.1, SI-2.1.a | — |
| MIX-006 | hard | 2026-10-17 | Gọi là cộng tác viên nhưng làm cố định nhận lương, có thể được coi là hợp đồng lao động không? | LAB-13.1 | — |
| MIX-012 | easy | 2026-10-17 | Điều khoản phạt 6% của phần nghĩa vụ vi phạm có vượt ngưỡng thông thường không? | COM-301 | — |
| TEMP-009 | expert | 2024-08-20 | Hợp đồng tiêu dùng ký tháng 5/2024, đến tháng 8/2024 vẫn thực hiện; nội dung/hình thức khác quy định luật 2023, các bên chưa thỏa thuận sửa đổi. Có thể mặc nhiên chỉ áp dụng Luật 2023 không? | C23-80.1.a, C23-79.2, C10-16.1.b | REPL-C-2024 |
| MIX-019 | medium | 2026-10-17 | Nếu có hai cách hiểu về hợp đồng theo mẫu thì luôn giải thích theo ý doanh nghiệp? | CON-24 | — |
| MIX-005 | easy | 2026-10-17 | Thỏa thuận không cấp bảo hộ và miễn trách nhiệm cho công ty có ổn không? | SAFE-7.2.b | — |
| MIX-003 | easy | 2026-10-17 | Mức trả 150% cho làm thêm ngày nghỉ hằng tuần có đạt mức tối thiểu? | LAB-98.1.b | — |
| MIX-004 | hard | 2026-10-17 | Có thể trả tiền thay BHXH bắt buộc cho nhân viên hợp đồng 24 tháng? | LAB-168.1, SI-2.1.a, SI-13.1 | — |
| MIX-008 | easy | 2026-10-17 | Nếu xác định đây là HĐLĐ theo bản chất, điều kiện nộp CCCD bản chính ra sao? | LAB-13.1, LAB-17.1 | — |
| TEMP-011 | expert | 2022-08-20 | Ngày 20/08/2022, quy định về báo cáo thay đổi lao động tại khoản 2 Điều 4 Nghị định 145/2020 phải đọc cùng văn bản sửa đổi nào? | N35-73.1, N145-4.2 | AMEND-145-2022 |
| MIX-020 | hard | 2026-10-17 | Điều khoản xác nhận quyền khiếu kiện trong hợp đồng điện tử có bị cấm? | CON-25.2, E-36.3 | — |
| MIX-013 | hard | 2026-10-17 | Việc giao kết hợp đồng mua bán qua email có vô hiệu chỉ vì không ký trên giấy? | E-35.1, COM-24.1 | — |
| MIX-014 | hard | 2026-10-17 | Nếu hợp đồng ký qua email thì điều khoản phạt 12% có tự động hợp pháp? | E-36.3, COM-301 | — |
| TEMP-010 | hard | 2022-03-01 | Vào tháng 3/2022, có thể viện dẫn Nghị định 35/2022/NĐ-CP để khẳng định khoản 2 Điều 4 Nghị định 145/2020 đã bị sửa đổi chưa? | N145-4.2 | AMEND-145-2022 |
| TEMP-003 | medium | 2024-05-10 | Hợp đồng được giao kết qua thư điện tử ngày 10/05/2024 có bị phủ nhận giá trị pháp lý chỉ vì là thông điệp dữ liệu không? | E05-33, E05-34 | REPL-E-2024 |
| MIX-009 | medium | 2026-10-17 | Có thể kết luận đặt cọc dịch vụ dân sự bị cấm chỉ vì HĐLĐ cấm đặt cọc không? | CIV-328.1 | — |
| MIX-002 | easy | 2026-10-17 | Công ty được nhận 5 triệu đồng đặt cọc từ người lao động không? | LAB-17.2 | — |
| TEMP-001 | medium | 2024-06-20 | Tháng 6/2024, nhân viên ký hợp đồng lao động 24 tháng thuộc nhóm đối tượng BHXH bắt buộc theo văn bản nào và điểm nào? | SI14-2.1.a | REPL-SI-2025 |
| TEMP-013 | expert | 2026-10-17 | Nghị định 145/2020 đang được CSDL quốc gia ghi hết hiệu lực một phần. Có đúng là toàn bộ điều khoản trong nghị định đều không được trích dẫn trong năm 2026? | N35-73.1, N10-49.1 | AMEND-145-2022, ADD-145-2024 |
| MIX-011 | easy | 2026-10-17 | Phạt 12% trên toàn bộ hợp đồng cho vi phạm một phần nghĩa vụ có phù hợp? | COM-301 | — |
| TEMP-012 | expert | 2024-04-01 | Ngày 01/04/2024, quy định báo cáo thay đổi lao động đối với khu công nghệ cao có khoản bổ sung nào trong Điều 4 Nghị định 145/2020? | N10-49.1, N145-4.4, N35-73.1 | ADD-145-2024, AMEND-145-2022 |
| MIX-016 | easy | 2026-10-17 | Nhà cung cấp có quyền đơn phương sửa mọi nội dung hợp đồng đã giao kết? | CON-25.3 | — |
| MIX-015 | easy | 2026-10-17 | Điều khoản người tiêu dùng không được khiếu nại, khởi kiện có được phép? | CON-25.2 | — |
| TEMP-005 | expert | 2024-08-10 | Hợp đồng điện tử lập 15/06/2024, đến 10/08/2024 chưa thực hiện xong và các bên không thỏa thuận áp dụng luật mới. Có được tiếp tục viện dẫn luật 2005 không? | E23-53.1, E05-34, E23-52.2 | REPL-E-2024 |
| TEMP-008 | hard | 2024-08-20 | Hợp đồng tiêu dùng ký mới tháng 8/2024 có điều khoản cấm người tiêu dùng khởi kiện. Cần viện dẫn điều nào của luật mới? | C23-25.2, C23-79.1 | REPL-C-2024 |
| MIX-001 | easy | 2026-10-17 | Có vi phạm về giữ giấy tờ gốc không? | LAB-17.1 | — |
| MIX-010 | hard | 2026-10-17 | Có đủ căn cứ kết luận hợp đồng dịch vụ giữa hai cá nhân này là HĐLĐ? | LAB-13.1, CIV-385 | — |
| TEMP-007 | hard | 2024-05-20 | Hợp đồng tiêu dùng tháng 5/2024 có điều khoản từ bỏ quyền khiếu nại, khởi kiện. Điều khoản đó có được phép theo luật đang áp dụng lúc ký không? | C10-16.1.b | REPL-C-2024 |
| TEMP-004 | hard | 2024-08-11 | Hợp đồng điện tử ký tháng 8/2024 nên căn cứ Luật Giao dịch điện tử 2005 hay 2023? Nêu mốc thay thế. | E23-52.1, E23-52.2 | REPL-E-2024 |
| TEMP-002 | hard | 2025-08-01 | Tháng 8/2025, người làm theo hợp đồng lao động 24 tháng có thuộc diện tham gia BHXH bắt buộc không? Căn cứ vì sao không dùng luật 2014? | SI24-2.1.a, SI24-13.1, SI24-140.1, SI24-140.2 | REPL-SI-2025 |

## Chi tiết các test temporal

Bộ gốc 20 case giữ nguyên nội dung và được bổ sung provenance, độ khó mới, timestamp, phiên bản và schema graph.

### TEMP-001 · MEDIUM · BHXH 2014 before replacement

**Câu hỏi:** Tháng 6/2024, nhân viên ký hợp đồng lao động 24 tháng thuộc nhóm đối tượng BHXH bắt buộc theo văn bản nào và điểm nào?

**Tình huống:** Công dân Việt Nam, làm việc theo HĐLĐ xác định thời hạn 24 tháng.

**Ngày đánh giá:** 2024-06-20; **ngày giao dịch:** 2024-06-20

**Đáp án tham chiếu:** Áp dụng điểm a khoản 1 Điều 2 Luật BHXH 2014 (58/2014/QH13); Luật 2024 chưa có hiệu lực.

**Đúng cấp Điều/Khoản/Điểm:** SI14-2.1.a

**Không dùng như căn cứ chính:** SI24-2.1.a

**Cạnh quan hệ cần suy ra:** REPL-SI-2025

**Các ý bắt buộc:**
- Luật BHXH 2014 là phiên bản áp dụng tại ngày 20/06/2024
- Không lấy luật BHXH 2024 có hiệu lực từ 01/07/2025 để viện dẫn như luật đang áp dụng năm 2024

**Nguồn:**
- Luật Bảo hiểm xã hội năm 2014 (58/2014/QH13), Điều 2 khoản 1 điểm a: “Người làm việc theo hợp đồng lao động không xác định thời hạn, hợp đồng lao động xác định thời hạn”  https://vbpl.moj.gov.vn/bonoivu/Pages/vbpq-print.aspx?ItemID=46744

### TEMP-002 · HARD · BHXH 2024 after replacement

**Câu hỏi:** Tháng 8/2025, người làm theo hợp đồng lao động 24 tháng có thuộc diện tham gia BHXH bắt buộc không? Căn cứ vì sao không dùng luật 2014?

**Tình huống:** Công dân Việt Nam, HĐLĐ 24 tháng, đơn vị sử dụng lao động.

**Ngày đánh giá:** 2025-08-01; **ngày giao dịch:** 2025-08-01

**Đáp án tham chiếu:** Thuộc đối tượng theo điểm a khoản 1 Điều 2 Luật 2024; người sử dụng lao động có trách nhiệm theo khoản 1 Điều 13; Điều 140 xác lập mốc thay thế.

**Đúng cấp Điều/Khoản/Điểm:** SI24-2.1.a, SI24-13.1, SI24-140.1, SI24-140.2

**Không dùng như căn cứ chính:** SI14-2.1.a

**Cạnh quan hệ cần suy ra:** REPL-SI-2025

**Các ý bắt buộc:**
- Luật BHXH 2024 có hiệu lực từ 01/07/2025
- Luật BHXH 2014 hết hiệu lực từ mốc này (cần xét các điều khoản chuyển tiếp khi có)

**Nguồn:**
- Luật Bảo hiểm xã hội năm 2024 (41/2024/QH15), Điều 2 khoản 1 điểm a: “hợp đồng lao động xác định thời hạn có thời hạn từ đủ 01 tháng trở lên”  https://xaydungchinhsach.chinhphu.vn/toan-van-luat-so-41-2024-qh15-bao-hiem-xa-hoi-119240723163650489.htm
- Luật Bảo hiểm xã hội năm 2024 (41/2024/QH15), Điều 13 khoản 1: “Đăng ký tham gia bảo hiểm xã hội bắt buộc cho người lao động theo quy định của Luật này”  https://xaydungchinhsach.chinhphu.vn/toan-van-luat-so-41-2024-qh15-bao-hiem-xa-hoi-119240723163650489.htm
- Luật Bảo hiểm xã hội năm 2024 (41/2024/QH15), Điều 140 khoản 1: “Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2025.”  https://xaydungchinhsach.chinhphu.vn/toan-van-luat-so-41-2024-qh15-bao-hiem-xa-hoi-119240723163650489.htm
- Luật Bảo hiểm xã hội năm 2024 (41/2024/QH15), Điều 140 khoản 2: “Luật Bảo hiểm xã hội số 58/2014/QH13”  https://xaydungchinhsach.chinhphu.vn/toan-van-luat-so-41-2024-qh15-bao-hiem-xa-hoi-119240723163650489.htm

### TEMP-003 · MEDIUM · Electronic transactions 2005 historical

**Câu hỏi:** Hợp đồng được giao kết qua thư điện tử ngày 10/05/2024 có bị phủ nhận giá trị pháp lý chỉ vì là thông điệp dữ liệu không?

**Tình huống:** Hai doanh nghiệp giao kết hợp đồng thông qua thư điện tử tháng 5/2024.

**Ngày đánh giá:** 2024-05-10; **ngày giao dịch:** 2024-05-10

**Đáp án tham chiếu:** Không bị phủ nhận chỉ vì thể hiện dưới dạng thông điệp dữ liệu theo Điều 34 Luật Giao dịch điện tử 2005.

**Đúng cấp Điều/Khoản/Điểm:** E05-33, E05-34

**Không dùng như căn cứ chính:** E23-36.3

**Cạnh quan hệ cần suy ra:** REPL-E-2024

**Các ý bắt buộc:**
- Ngày 10/05/2024 áp dụng luật GDĐT 2005, không phải luật GDĐT 2023 (01/07/2024)

**Nguồn:**
- Luật Giao dịch điện tử năm 2005 (51/2005/QH11), Điều 33: “Hợp đồng điện tử là hợp đồng được thiết lập dưới dạng thông điệp dữ liệu theo quy định của Luật này.”  https://vanban.chinhphu.vn/?docid=29675&pageid=27160
- Luật Giao dịch điện tử năm 2005 (51/2005/QH11), Điều 34: “Giá trị pháp lý của hợp đồng điện tử không thể bị phủ nhận chỉ vì hợp đồng đó được thể hiện dưới dạng thông điệp dữ liệu.”  https://vanban.chinhphu.vn/?docid=29675&pageid=27160

### TEMP-004 · HARD · Electronic transactions 2023 contemporary

**Câu hỏi:** Hợp đồng điện tử ký tháng 8/2024 nên căn cứ Luật Giao dịch điện tử 2005 hay 2023? Nêu mốc thay thế.

**Tình huống:** Hợp đồng được xác lập lần đầu vào tháng 8/2024.

**Ngày đánh giá:** 2024-08-11; **ngày giao dịch:** 2024-08-11

**Đáp án tham chiếu:** Áp dụng Luật GDĐT 2023; khoản 1, 2 Điều 52 xác định mốc và quan hệ hết hiệu lực của Luật 2005.

**Đúng cấp Điều/Khoản/Điểm:** E23-52.1, E23-52.2

**Không dùng như căn cứ chính:** E05-34

**Cạnh quan hệ cần suy ra:** REPL-E-2024

**Các ý bắt buộc:**
- Luật 2023 có hiệu lực 01/07/2024, thay thế luật 2005, trừ trường hợp chuyển tiếp

**Nguồn:**
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 52 khoản 1: “Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024.”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 52 khoản 2: “Luật Giao dịch điện tử số 51/2005/QH11 hết hiệu lực”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913

### TEMP-005 · EXPERT · Electronic transaction transitional exception

**Câu hỏi:** Hợp đồng điện tử lập 15/06/2024, đến 10/08/2024 chưa thực hiện xong và các bên không thỏa thuận áp dụng luật mới. Có được tiếp tục viện dẫn luật 2005 không?

**Tình huống:** Hợp đồng xác lập trước 01/07/2024, chưa thực hiện xong; không có thỏa thuận áp dụng luật 2023.

**Ngày đánh giá:** 2024-08-10; **ngày giao dịch:** 2024-06-15

**Đáp án tham chiếu:** Có, khoản 1 Điều 53 Luật 2023 cho phép tiếp tục thực hiện theo luật 2005 trong trường hợp nêu ra, trừ khi các bên thỏa thuận áp dụng luật mới.

**Đúng cấp Điều/Khoản/Điểm:** E23-53.1, E05-34, E23-52.2

**Không dùng như căn cứ chính:** Không

**Cạnh quan hệ cần suy ra:** REPL-E-2024

**Các ý bắt buộc:**
- Điều 53 khoản 1 có ngoại lệ cho giao dịch xác lập trước 01/07/2024 và chưa thực hiện xong
- Luật cũ vẫn có thể áp dụng theo ngoại lệ mặc dù nhìn chung đã hết hiệu lực

**Nguồn:**
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 53 khoản 1: “Giao dịch điện tử được xác lập trước ngày Luật này có hiệu lực thi hành”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913
- Luật Giao dịch điện tử năm 2005 (51/2005/QH11), Điều 34: “Giá trị pháp lý của hợp đồng điện tử không thể bị phủ nhận chỉ vì hợp đồng đó được thể hiện dưới dạng thông điệp dữ liệu.”  https://vanban.chinhphu.vn/?docid=29675&pageid=27160
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 52 khoản 2: “Luật Giao dịch điện tử số 51/2005/QH11 hết hiệu lực”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913

### TEMP-006 · EXPERT · Electronic transaction opt-in new law

**Câu hỏi:** Cùng hợp đồng điện tử lập 15/06/2024 nhưng ngày 10/08/2024 hai bên thỏa thuận áp dụng luật mới. Có còn mặc định dùng Luật 2005 theo quy định chuyển tiếp?

**Tình huống:** Các bên đã thỏa thuận áp dụng luật 2023 cho giao dịch xác lập tháng 6/2024 chưa hoàn tất.

**Ngày đánh giá:** 2024-08-10; **ngày giao dịch:** 2024-06-15

**Đáp án tham chiếu:** Không mặc định dùng luật 2005; thỏa thuận áp dụng luật 2023 là ngoại lệ được nêu trong khoản 1 Điều 53.

**Đúng cấp Điều/Khoản/Điểm:** E23-53.1, E23-52.1

**Không dùng như căn cứ chính:** E05-34

**Cạnh quan hệ cần suy ra:** REPL-E-2024

**Các ý bắt buộc:**
- Ngoại lệ tại khoản 1 Điều 53 không bắt buộc dùng luật cũ khi các bên thỏa thuận áp dụng luật 2023

**Nguồn:**
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 53 khoản 1: “Giao dịch điện tử được xác lập trước ngày Luật này có hiệu lực thi hành”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913
- Luật Giao dịch điện tử năm 2023 (20/2023/QH15), Điều 52 khoản 1: “Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024.”  https://vbpl.moj.gov.vn/bothongtin/Pages/vbpq-toanvan.aspx?ItemID=165913

### TEMP-007 · HARD · Consumer contract 2010 historical

**Câu hỏi:** Hợp đồng tiêu dùng tháng 5/2024 có điều khoản từ bỏ quyền khiếu nại, khởi kiện. Điều khoản đó có được phép theo luật đang áp dụng lúc ký không?

**Tình huống:** Hợp đồng theo mẫu với người tiêu dùng, điều khoản hạn chế khiếu nại/khởi kiện.

**Ngày đánh giá:** 2024-05-20; **ngày giao dịch:** 2024-05-20

**Đáp án tham chiếu:** Điều khoản bị hạn chế hiệu lực theo điểm b khoản 1 Điều 16 Luật BVQLNTD 2010; không viện dẫn luật 2023 như đã hiệu lực trước 01/07/2024.

**Đúng cấp Điều/Khoản/Điểm:** C10-16.1.b

**Không dùng như căn cứ chính:** C23-25.2

**Cạnh quan hệ cần suy ra:** REPL-C-2024

**Các ý bắt buộc:**
- Tại 20/05/2024, luật BVQLNTD 2010 đang áp dụng
- Điểm b khoản 1 Điều 16 quy định điều khoản hạn chế quyền khiếu nại khởi kiện không có hiệu lực

**Nguồn:**
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2010 (59/2010/QH12), Điều 16 khoản 1 điểm b: “Hạn chế, loại trừ quyền khiếu nại, khởi kiện của người tiêu dùng;”  https://vanban.chinhphu.vn/?docid=98755&pageid=27160

### TEMP-008 · HARD · Consumer contract 2023 current

**Câu hỏi:** Hợp đồng tiêu dùng ký mới tháng 8/2024 có điều khoản cấm người tiêu dùng khởi kiện. Cần viện dẫn điều nào của luật mới?

**Tình huống:** Giao dịch mới tháng 8/2024, doanh nghiệp đưa điều khoản cấm khiếu kiện.

**Ngày đánh giá:** 2024-08-20; **ngày giao dịch:** 2024-08-20

**Đáp án tham chiếu:** Không được quy định điều khoản hạn chế/loại trừ quyền khiếu nại khởi kiện; căn cứ khoản 2 Điều 25 và Điều 79 Luật 2023.

**Đúng cấp Điều/Khoản/Điểm:** C23-25.2, C23-79.1

**Không dùng như căn cứ chính:** C10-16.1.b

**Cạnh quan hệ cần suy ra:** REPL-C-2024

**Các ý bắt buộc:**
- Luật BVQLNTD 2023 có hiệu lực 01/07/2024
- Khoản 2 Điều 25 ngăn doanh nghiệp quy định điều khoản loại trừ quyền khiếu nại khởi kiện

**Nguồn:**
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2023 (19/2023/QH15), Điều 25 khoản 2: “Hạn chế, loại trừ quyền khiếu nại, khởi kiện của người tiêu dùng;”  https://vbpl.moj.gov.vn/botuphap/Pages/vbpq-toanvan.aspx?ItemID=161263
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2023 (19/2023/QH15), Điều 79 khoản 1: “Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024.”  https://vbpl.moj.gov.vn/botuphap/Pages/vbpq-toanvan.aspx?ItemID=161263

### TEMP-009 · EXPERT · Consumer transitional ongoing contract

**Câu hỏi:** Hợp đồng tiêu dùng ký tháng 5/2024, đến tháng 8/2024 vẫn thực hiện; nội dung/hình thức khác quy định luật 2023, các bên chưa thỏa thuận sửa đổi. Có thể mặc nhiên chỉ áp dụng Luật 2023 không?

**Tình huống:** Giao dịch đang thực hiện, xác lập trước 01/07/2024, nội dung/hình thức khác luật 2023, chưa sửa đổi.

**Ngày đánh giá:** 2024-08-20; **ngày giao dịch:** 2024-05-20

**Đáp án tham chiếu:** Không; cần xem xét điều khoản chuyển tiếp tại điểm a khoản 1 Điều 80 Luật BVQLNTD 2023 để xác định khả năng tiếp tục áp dụng luật 2010 cho giao dịch đang thực hiện.

**Đúng cấp Điều/Khoản/Điểm:** C23-80.1.a, C23-79.2, C10-16.1.b

**Không dùng như căn cứ chính:** Không

**Cạnh quan hệ cần suy ra:** REPL-C-2024

**Các ý bắt buộc:**
- Điểm a khoản 1 Điều 80 có trường hợp tiếp tục áp dụng luật 2010 đối với giao dịch chuyển tiếp
- Không dùng chỉ trạng thái hết hiệu lực của luật 2010 để loại bỏ mọi trường hợp áp dụng

**Nguồn:**
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2023 (19/2023/QH15), Điều 80 khoản 1 điểm a: “Giao dịch giữa tổ chức, cá nhân kinh doanh và người tiêu dùng chưa được thực hiện”  https://vbpl.moj.gov.vn/botuphap/Pages/vbpq-toanvan.aspx?ItemID=161263
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2023 (19/2023/QH15), Điều 79 khoản 2: “Luật Bảo vệ quyền lợi người tiêu dùng số 59/2010/QH12”  https://vbpl.moj.gov.vn/botuphap/Pages/vbpq-toanvan.aspx?ItemID=161263
- Luật Bảo vệ quyền lợi người tiêu dùng năm 2010 (59/2010/QH12), Điều 16 khoản 1 điểm b: “Hạn chế, loại trừ quyền khiếu nại, khởi kiện của người tiêu dùng;”  https://vanban.chinhphu.vn/?docid=98755&pageid=27160

### TEMP-010 · HARD · Decree original before amendment

**Câu hỏi:** Vào tháng 3/2022, có thể viện dẫn Nghị định 35/2022/NĐ-CP để khẳng định khoản 2 Điều 4 Nghị định 145/2020 đã bị sửa đổi chưa?

**Tình huống:** Đơn vị yêu cầu xác định văn bản gốc liên quan chế độ báo cáo thay đổi lao động năm 2022.

**Ngày đánh giá:** 2022-03-01; **ngày giao dịch:** 2022-03-01

**Đáp án tham chiếu:** Chưa; phải xem phiên bản khoản 2 Điều 4 của Nghị định 145/2020 đang áp dụng ngày 01/03/2022.

**Đúng cấp Điều/Khoản/Điểm:** N145-4.2

**Không dùng như căn cứ chính:** N35-73.1

**Cạnh quan hệ cần suy ra:** AMEND-145-2022

**Các ý bắt buộc:**
- Nghị định 35/2022 được ban hành 28/05/2022 và có hiệu lực 15/07/2022
- Không gắn nội dung sửa đổi 2022 vào mốc 01/03/2022

**Nguồn:**
- Nghị định số 145/2020/NĐ-CP (145/2020/NĐ-CP), Điều 4 khoản 2: “Định kỳ 06 tháng”  https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-35-2022-ND-CP-quan-ly-khu-cong-nghiep-kinh-te-482305.aspx

### TEMP-011 · EXPERT · Decree amended clause

**Câu hỏi:** Ngày 20/08/2022, quy định về báo cáo thay đổi lao động tại khoản 2 Điều 4 Nghị định 145/2020 phải đọc cùng văn bản sửa đổi nào?

**Tình huống:** Doanh nghiệp hỏi khoản 2 Điều 4 sau đợt sửa đổi năm 2022.

**Ngày đánh giá:** 2022-08-20; **ngày giao dịch:** 2022-08-20

**Đáp án tham chiếu:** Phải đọc khoản 2 Điều 4 Nghị định 145/2020 theo nội dung được sửa đổi bởi khoản 1 Điều 73 Nghị định 35/2022.

**Đúng cấp Điều/Khoản/Điểm:** N35-73.1, N145-4.2

**Không dùng như căn cứ chính:** Không

**Cạnh quan hệ cần suy ra:** AMEND-145-2022

**Các ý bắt buộc:**
- Điều 73 khoản 1 Nghị định 35/2022 sửa đổi, bổ sung khoản 2 Điều 4 Nghị định 145/2020 từ 15/07/2022

**Nguồn:**
- Nghị định số 35/2022/NĐ-CP (35/2022/NĐ-CP), Điều 73 khoản 1: “Sửa đổi, bổ sung khoản 2 Điều 4”  https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-35-2022-ND-CP-quan-ly-khu-cong-nghiep-kinh-te-482305.aspx
- Nghị định số 145/2020/NĐ-CP (145/2020/NĐ-CP), Điều 4 khoản 2: “Định kỳ 06 tháng”  https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-35-2022-ND-CP-quan-ly-khu-cong-nghiep-kinh-te-482305.aspx

### TEMP-012 · EXPERT · Decree added clause for high tech park

**Câu hỏi:** Ngày 01/04/2024, quy định báo cáo thay đổi lao động đối với khu công nghệ cao có khoản bổ sung nào trong Điều 4 Nghị định 145/2020?

**Tình huống:** Người sử dụng lao động hoạt động trong khu công nghệ cao.

**Ngày đánh giá:** 2024-04-01; **ngày giao dịch:** 2024-04-01

**Đáp án tham chiếu:** Khoản 4 Điều 4 Nghị định 145/2020 được bổ sung bởi khoản 1 Điều 49 Nghị định 10/2024; khoản 2 Điều 4 trước đó đã được sửa đổi bởi Nghị định 35/2022.

**Đúng cấp Điều/Khoản/Điểm:** N10-49.1, N145-4.4, N35-73.1

**Không dùng như căn cứ chính:** Không

**Cạnh quan hệ cần suy ra:** ADD-145-2024, AMEND-145-2022

**Các ý bắt buộc:**
- Khoản 1 Điều 49 Nghị định 10/2024 bổ sung khoản 4 Điều 4 Nghị định 145/2020 từ 25/03/2024
- Bản quy định Điều 4 có nhiều phiên bản; phải chọn đúng bản tại ngày 01/04/2024

**Nguồn:**
- Nghị định số 10/2024/NĐ-CP (10/2024/NĐ-CP), Điều 49 khoản 1: “Bổ sung khoản 4 vào Điều 4”  https://hethongphapluat.com/nghi-dinh-10-2024-nd-cp-quy-dinh-ve-khu-cong-nghe-cao.html
- Nghị định số 145/2020/NĐ-CP (145/2020/NĐ-CP), Điều 4 khoản 4: “Đối với khu công nghệ cao, việc báo cáo sử dụng lao động thực hiện như sau:”  https://hethongphapluat.com/nghi-dinh-10-2024-nd-cp-quy-dinh-ve-khu-cong-nghe-cao.html
- Nghị định số 35/2022/NĐ-CP (35/2022/NĐ-CP), Điều 73 khoản 1: “Sửa đổi, bổ sung khoản 2 Điều 4”  https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-35-2022-ND-CP-quan-ly-khu-cong-nghiep-kinh-te-482305.aspx

### TEMP-013 · EXPERT · Partial effectivity limitation

**Câu hỏi:** Nghị định 145/2020 đang được CSDL quốc gia ghi hết hiệu lực một phần. Có đúng là toàn bộ điều khoản trong nghị định đều không được trích dẫn trong năm 2026?

**Tình huống:** Người dùng hỏi cách hiểu trạng thái hiệu lực trên hệ thống VBPL, không yêu cầu kết luận khoản cụ thể đã sửa sau năm 2025.

**Ngày đánh giá:** 2026-10-17; **ngày giao dịch:** 2026-10-17

**Đáp án tham chiếu:** Không. CSDL VBPL ghi Nghị định 145/2020 hết hiệu lực một phần; phải kiểm tra phạm vi từng điều/khoản bị thay đổi và các văn bản sửa đổi, không loại toàn bộ nghị định.

**Đúng cấp Điều/Khoản/Điểm:** N35-73.1, N10-49.1

**Không dùng như căn cứ chính:** Không

**Cạnh quan hệ cần suy ra:** AMEND-145-2022, ADD-145-2024

**Các ý bắt buộc:**
- Hết hiệu lực một phần không đồng nghĩa hết hiệu lực toàn bộ
- Muốn kết luận quy định cụ thể phải đối chiếu các sửa đổi liên quan và thời điểm áp dụng
- Không gán trạng thái từng khoản chưa kiểm chứng

**Nguồn:**
- Nghị định số 35/2022/NĐ-CP (35/2022/NĐ-CP), Điều 73 khoản 1: “Sửa đổi, bổ sung khoản 2 Điều 4”  https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-35-2022-ND-CP-quan-ly-khu-cong-nghiep-kinh-te-482305.aspx
- Nghị định số 10/2024/NĐ-CP (10/2024/NĐ-CP), Điều 49 khoản 1: “Bổ sung khoản 4 vào Điều 4”  https://hethongphapluat.com/nghi-dinh-10-2024-nd-cp-quy-dinh-ve-khu-cong-nghe-cao.html

### TEMP-014 · HARD · Labor law historical article renumbering

**Câu hỏi:** Tháng 10/2020, hợp đồng yêu cầu doanh nghiệp giữ bản chính giấy tờ tùy thân. Dẫn Điều 20 Bộ luật Lao động 2012 hay Điều 17 Bộ luật Lao động 2019?

**Tình huống:** Điều khoản ký năm 2020, chỉ hỏi căn cứ tại thời điểm ký.

**Ngày đánh giá:** 2020-10-10; **ngày giao dịch:** 2020-10-10

**Đáp án tham chiếu:** Điều 20 khoản 1 Bộ luật Lao động 2012 tại thời điểm tháng 10/2020, không phải Điều 17 Bộ luật Lao động 2019 được áp dụng sau 01/01/2021.

**Đúng cấp Điều/Khoản/Điểm:** L12-20.1

**Không dùng như căn cứ chính:** LAB-17.1

**Cạnh quan hệ cần suy ra:** REPL-LAB-2021

**Các ý bắt buộc:**
- Bộ luật Lao động 2019 có hiệu lực 01/01/2021
- Điều 20 khoản 1 Bộ luật Lao động 2012 là căn cứ cho mốc tháng 10/2020

**Nguồn:**
- Bộ luật Lao động năm 2012 (10/2012/QH13), Điều 20 khoản 1: “Giữ bản chính giấy tờ tuỳ thân, văn bằng, chứng chỉ của người lao động.”  https://vanban.chinhphu.vn/?classid=1&docid=163542&orggroupid=1&pageid=27160
