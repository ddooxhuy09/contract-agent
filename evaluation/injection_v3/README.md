# injection_v3: đo hai cờ giảm báo nhầm (tắt vs bật)

Bộ ca mới để đo `JUDGE_FINDING_TYPES` + `RED_FLAG_LLM_VERIFY` (xem `docs/NHAT_KY_THAY_DOI.md`, mục 15/11/2026). Khác bộ 80 ca và injection_v2 (đã đóng băng, không sửa). Lý do có bộ mới: hai cờ được thiết kế **sau khi** phân tích lỗi trên bộ 48 ca (`evaluation_results/reports/PHAN_TICH_LOI_THEO_BUOC.md`), nên đo lại trên bộ đó sẽ là tối ưu trên tập test.

## Cấu trúc
| File | Nội dung |
|---|---|
| `bases/A.txt` | Nền A: công nhân vận hành CNC, HĐ **không xác định thời hạn** (báo trước 45 ngày), có bảo hộ lao động, 12 Điều |
| `bases/B.txt` | Nền B: kỹ sư kiểm thử, HĐ **xác định 12 tháng** (30 ngày), văn phòng (bảo hộ "không áp dụng"), **thứ tự Điều khác A/C** |
| `bases/C.txt` | Nền C: nhân viên bán hàng nữ, HĐ **xác định 36 tháng** (30 ngày), làm ca |
| `cases.jsonl` | 48 ca: `case_id, base, rule_id, label, kind, phrasing, body, legal_basis, note` |
| `contracts/` | Hợp đồng đã chèn (giữ tiêu đề Điều của nền, thay toàn bộ thân Điều slot) |
| `make_cases.py` | Nguồn của `cases.jsonl` (chạy một lần trước đóng băng) |
| `run.py` | `build`, `check`, `full --flags off/on`, `report` |

Ba nền đều đủ nội dung Điều 21 khoản 1 BLLĐ 2019 (a đến k), kể cả thông tin định danh các bên (bài học từ nền của bộ 80 ca, vốn thiếu Điều 21 nên bị cờ ở 47/48 ca). Tên công ty, người, số CCCD đều là giả.

## Thiết kế ca
Mỗi luật đỏ 6 ca, mỗi nền đúng 1 vi phạm + 1 hợp lệ của mỗi luật (16 ca/nền):

| Loại | Nhãn | Ý nghĩa |
|---|---|---|
| `V-a` | vi phạm | mẫu quen thuộc, regex trúng |
| `V-b` | vi phạm | diễn đạt lại, regex không trúng |
| `V-c` | vi phạm | dạng khác (số bằng chữ, mức vượt giới hạn, biện pháp bảo đảm bằng tiền, cam kết không sinh con…) |
| `C-a` | hợp lệ | câu phủ định/câu cấm chứa cụm từ khoá (regex trúng nhầm) |
| `C-b` | hợp lệ | biến thể hợp pháp nêu cụ thể (2 ca regex cũng trúng: ngoại lệ 14 ngày BHXH, quyền của lao động nữ mang thai Điều 138) |
| `C-c` | hợp lệ | chỉ dẫn chiếu "theo Bộ luật Lao động", không chép lại luật |

Kết quả `check` lúc soạn (regex, không LLM): V-a và C-a trúng ở cả 8 luật; C-b trúng ở `no_bhxh`, `terminate_pregnancy`; V-b, V-c, C-c không trúng. Ba nền không kích hoạt regex nào và bộ kiểm Điều 21 (`assess_mandatory_fields`) báo đủ cả ba (nền C được sửa câu 3.3 thành "Thời hạn trả lương: ngày 07 hằng tháng" sau lần kiểm đầu vì bộ kiểm không nhận câu cũ; ca không bị sửa sau lần kiểm).

## Điều người viết biết khi soạn (khai báo để người đọc tự đánh giá)
- Ca do cùng mô hình đã viết hai cờ soạn, sau khi đã thấy phân tích lỗi. Các loại `C-a`, `C-c` nhắm đúng hai kiểu báo nhầm mà cờ muốn sửa; vì vậy bộ này đo **cờ có sửa được các kiểu lỗi đã biết trên văn bản mới không**, không đo tỷ lệ báo nhầm trên hợp đồng thực tế.
- Văn bản ca không được chạy qua pipeline LLM trước khi đóng băng (chỉ chạy regex và bộ kiểm Điều 21 như trên).
- Nhãn và căn cứ pháp lý do người viết đối chiếu với BLLĐ 2019, Luật BHXH 2024; **chưa có luật sư xác nhận**. Ca dễ tranh luận: `LU-Cb` (nghĩa vụ bồi thường của NLĐ chấm dứt trái luật), `GT-Vc` (đặt cọc, thuộc Điều 17 khoản 2 chứ không phải giữ giấy tờ), `DT-Vc` (phí đào tạo hội nhập).

## Cách chấm (khai báo trước khi chạy)
- Đơn vị là ca. **Dương tính** khi có rủi ro `critical` hoặc `warning` tại Điều đã bơm. Mức `info` (cờ bật: "góp ý", "thiếu nội dung", cờ regex judge không xác nhận) **không** tính dương tính. Ca có Điều chưa kiểm không được lưu và chạy lại sau.
- Chỉ số chính: TP, FP, FN, TN; precision, recall, F1 trên 48 ca, CI95 bootstrap theo ca (1000 lần, seed 20261109).
- Chỉ số phụ (chỉ báo cáo): số Điều khác ngoài Điều bơm có cờ critical/warning (trung bình mỗi ca); cờ critical/warning trên 3 nền sạch chạy riêng; kết quả theo loại ca và theo luật.
- Hai cấu hình chạy cùng commit, cùng judge (Groq `openai/gpt-oss-120b`, nhiệt độ 0), cùng kho luật: `off` (cả hai cờ tắt) và `on` (cả hai cờ bật). Hai cờ được đo **chung**, không tách được đóng góp riêng.

## Quy tắc chấp nhận (khai báo trước, không đổi sau khi xem kết quả)
Bật cả hai cờ làm mặc định của ứng dụng **khi và chỉ khi**, trên đủ 48/48 ca ở cả hai cấu hình:
1. `FP(on) ≤ FP(off) − 3` (bớt ít nhất 3 ca hợp lệ bị gắn cờ trên 24 ca hợp lệ), **và**
2. `FN(on) ≤ FN(off) + 1` (bỏ sót thêm tối đa 1 vi phạm trên 24 ca vi phạm).

Nếu một cấu hình chưa đủ 48 ca thì không quyết định. Không đạt thì giữ cờ tắt và ghi kết quả âm tính. Chạy một lần mỗi cấu hình; không chạy lại để lấy kết quả khác.

## Chạy
```
python -m evaluation.injection_v3.run build
python -m evaluation.injection_v3.run check
python -m evaluation.injection_v3.run full --flags off
python -m evaluation.injection_v3.run full --flags on
python -m evaluation.injection_v3.run report
```
Mỗi cấu hình 51 hợp đồng (3 nền + 48 ca), khoảng 12 lượt gọi judge mỗi hợp đồng; cấu hình `on` thêm khoảng 1 lượt mỗi ca có regex trúng. Lệnh `full` có resume: hết hạn mức thì chạy lại lệnh, ca đã lưu được bỏ qua. Không chạy script từ thư mục Temp (xem `docs/DEMO_CHECKLIST.md`).

## Đóng băng
Commit chứa thư mục này được gắn tag `injection-v3-frozen` trước khi chạy `full`. Sau tag không sửa `bases/`, `cases.jsonl`, `contracts/`, cách chấm hay quy tắc chấp nhận.
