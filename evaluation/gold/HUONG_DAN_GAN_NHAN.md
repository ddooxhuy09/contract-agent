# Hướng dẫn gán nhãn gold set

Mỗi dòng trong `annotation_template.csv` là **một Điều** của một hợp đồng lao động đã ẩn danh. Hai người gán nhãn làm **độc lập**, không xem nhãn của nhau; chuyên gia chốt các dòng bất đồng.

## Cách điền
| Cột | Giá trị |
|---|---|
| `annN_co_rui_ro` | `1` nếu Điều này có ít nhất một nội dung trái hoặc rủi ro theo pháp luật lao động Việt Nam; `0` nếu không. Không bỏ trống. |
| `annN_luat_dau_ra` | Nếu `1`: mã luật đỏ phù hợp trong bảng dưới, hoặc `khac` nếu là rủi ro thật nhưng không thuộc 7 mục. Nếu `0`: để trống. Nhiều mục thì ngăn bằng dấu `;`. |
| `annN_dieu_luat_dung` | Điều luật bạn dùng làm căn cứ, ví dụ `Điều 98 BLLĐ 2019`. Chỉ ghi điều bạn đã mở văn bản gốc kiểm tra. Để trống nếu `0`. |
| `expert_final` | Chuyên gia ghi `0`, `1`, hoặc `1:<mã luật>` cho các dòng bất đồng và một mẫu ngẫu nhiên khoảng 5 dòng đồng thuận. |
| `ghi_chu` | Lý do khi không chắc. Đánh dấu `?` ở đầu ghi chú nếu bạn thật sự không chắc; không đoán. |

## Định nghĩa "có rủi ro" cho 7 luật đỏ
Căn cứ theo bộ luật đỏ mà hệ thống kiểm bằng quy tắc; định nghĩa dưới đây để người gán dùng chung tiêu chí, không phải để hệ thống chấm theo.

| Mã | Gán `1` khi Điều có nội dung | Căn cứ tham khảo |
|---|---|---|
| `ot_unpaid` | bắt buộc làm thêm giờ, hoặc tuyên bố làm thêm không được trả lương làm thêm | Điều 98, 107 BLLĐ 2019 |
| `no_bhxh` | thỏa thuận không đóng BHXH/BHYT bắt buộc | Điều 21 BLLĐ; Luật BHXH |
| `retain_id_papers` | yêu cầu người lao động giao bản gốc giấy tờ tùy thân hoặc bằng cấp cho công ty giữ | Điều 17 BLLĐ |
| `forfeit_wage_quit` | tước lương tháng cuối hoặc lương chưa trả khi người lao động chấm dứt hợp đồng | Điều 94, 96 BLLĐ |
| `fine_deduct_wage` | công ty tự đặt hình thức kỷ luật phạt tiền hoặc khấu trừ lương | Điều 127, 129 BLLĐ |
| `terminate_pregnancy` | cho phép công ty đơn phương chấm dứt vì người lao động kết hôn, mang thai hoặc nuôi con nhỏ | Điều 137, 141 BLLĐ |
| `ban_lawsuit` | cấm hoặc hạn chế quyền khởi kiện ra Tòa án, hoặc trao quyền quyết định tranh chấp cho một bên | Điều 179, 187 BLLĐ |
| `khac` | rủi ro thật nhưng ngoài 7 mục (ví dụ thử việc vượt thời hạn, điều khoản mơ hồ gây bất lợi) | ghi điều luật ở `annN_dieu_luat_dung` |

## Quy tắc chung
1. Đọc **nguyên Điều**, không chỉ một câu. Tiêu chí là nội dung của Điều, không phải tiêu đề.
2. Đối chiếu **văn bản gốc** (vanban.chinhphu.vn hoặc thuvienphapluat.vn), không dựa vào bản tóm tắt thứ cấp hay đầu ra của hệ thống. Không chạy hệ thống trên các dòng này trước khi gán nhãn xong.
3. Chỉ gán `1` khi nội dung thật sự trái hoặc bất lợi hơn mức pháp luật cho phép, tính theo ngày ký hợp đồng. Điều khoản chỉ "nên cải thiện" thì gán `0` và ghi chú.
4. Không chắc: gán theo nhận định tốt nhất, thêm `?` vào ghi chú. Chuyên gia ưu tiên các dòng có `?`.
5. Không sửa nhãn sau khi đã xem nhãn của người kia. Chỉ chuyên gia mới ghi `expert_final`.
6. Ghi thời gian bắt đầu và kết thúc vào `ghi_chep_gan_nhan.md`.

## Sau khi gán
- `python -m evaluation.gold.kappa --write` tạo `KAPPA.md`. Nếu kappa dưới 0,6: thảo luận, sửa hướng dẫn này, rồi chuyên gia chốt các dòng bất đồng.
- `python -m evaluation.gold.make_split` chia dev/test theo hợp đồng và ghi `split.json`.
- Sau đó đóng băng (tag `eval-frozen`): không sửa `evaluation/gold/` nữa.
