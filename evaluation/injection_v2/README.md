# injection_v2: bộ ca để đo xử lý phủ định của bước quét luật cố định

Bộ này **khác** bộ 80 ca `evaluation/injection` (đã đóng băng, không sửa, không chạy lại để báo số mới). Mục đích: đo trước/sau khi `labor_red_flags.py` dùng kiểm tra phủ định (như `_violates`) ở bước quét. Quy mô nhỏ có chủ đích: 32 ca = 8 luật x (2 vi phạm + 2 hợp lệ). Chỉ số theo từng luật rất thô, chỉ có ý nghĩa mô tả.

## Cấu trúc mỗi luật
| Ca | Nhãn | Ý nghĩa |
|---|---|---|
| `V1` | vi phạm | mẫu quen thuộc, regex cũ bắt |
| `V2` | vi phạm | vẫn vi phạm thật nhưng có chữ «không» khác (hoặc «nếu không») trong 30 ký tự trước cụm khóa; kiểm xem kiểm tra phủ định có nuốt nhầm vi phạm thật không |
| `C1` | hợp lệ | **phủ định ngay trước cụm khóa** («không giữ bản gốc…», «nghiêm cấm… không trả lương làm thêm») |
| `C2` | hợp lệ | **phủ định ở dạng khác**: đứng *sau* cụm khóa (7 luật) hoặc *bên trong* đoạn khớp (ban_lawsuit) |

Mỗi luật có đúng 2 ca phủ định hợp lệ (C1, C2); yêu cầu tối thiểu là 1.

## Điều tác giả biết khi viết (khai báo để người đọc tự đánh giá)
- Bộ viết **trước** khi sửa code, nhưng tác giả đã đọc `_violates` (cửa sổ 30 ký tự phía trước, từ khóa `không|cấm|nghiêm cấm`) và đã định sẵn V2 để thử điểm yếu của nó và C2 để thử dạng phủ định nằm ngoài cửa sổ đó. Vì vậy **không nên đọc bộ này như tỉ lệ đúng trên văn bản thực**; nó đo đúng đặc tính của cách kiểm tra phủ định, không đo độ phủ ngôn ngữ.
- Kỳ vọng của tác giả (ghi trước khi chạy): code cũ kích hoạt cả 16 ca hợp lệ (đó là lý do chúng là bẫy); code mới sửa được C1 (8 ca) nhưng không sửa được C2 (8 ca), và có thể bỏ sót một số V2.
- Cột `regex_expected` là dự đoán của tác giả cho code **cũ** (`hit` / `trap`).
- Căn cứ pháp lý (`legal_basis`) lấy từ bộ 80 ca đã đối chiếu với BLLĐ 2019 trong DB. Chưa có luật sư xác nhận nhãn.

## Cách chấm
Giống bộ 80 ca, phần rule-only: luật `r` "kích hoạt" ở một ca nếu `check_labor_red_flags(text, None)` trả về finding có `key == r`. Dương tính thật của `r` = ca `violation` có `rule_id == r`; mọi ca khác là âm tính với `r`. Precision, recall, F1 từng luật và micro; CI95 bootstrap theo ca (1000 lần, seed 20261109) cho chỉ số tổng, rất rộng do n=32.

## Chạy
```
python -m evaluation.injection_v2.run build
python -m evaluation.injection_v2.run check
python -m evaluation.injection_v2.run rule-only --label old   # code trước khi sửa
python -m evaluation.injection_v2.run rule-only --label new   # code sau khi sửa
python -m evaluation.injection_v2.run report
```
`base_contract.txt` là bản sao nguyên văn nền của bộ 80 ca (cùng SHA-256, ghi trong `manifest.json`); bước quét luật cố định không dùng LLM nên các cờ judge trên nền (xem `evaluation_results/injection/BASE_CONTRACT_FLAGS.md`) không liên quan.

## Đóng băng
Commit chứa các file này gắn tag `injection-v2-frozen` trước khi sửa `labor_red_flags.py`. Sau tag không sửa `cases.jsonl`, `base_contract.txt`, `contracts/` hay cách chấm.
