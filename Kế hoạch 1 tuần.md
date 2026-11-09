# Kế hoạch 1 tuần: sửa đồ án ContractLens trước buổi bảo vệ

> Tài liệu theo dõi tiến độ. Đánh dấu `[x]` khi xong. Mỗi ngày có mục tiêu, việc cần làm, tiêu chí hoàn thành và phương án cắt bớt nếu thiếu thời gian.
> Đường dẫn file lấy từ báo cáo phân tích. Nếu dòng code đã lệch, tìm theo tên hàm hoặc tên file.

---

## 0. Nguyên tắc cần giữ suốt tuần

1. **Chốt phạm vi trước, không mở thêm tính năng.** Tuần này không thêm chức năng mới. Chỉ sửa, đo và nói đúng những gì đã làm.
2. **Ghi lại mọi số liệu kèm commit.** Mỗi lần chạy đánh giá phải lưu kết quả vào `evaluation_results/` kèm hash commit và ngày giờ.
3. **Đóng băng bộ test sau Ngày 4.** Từ thời điểm đó không sửa gold set, không đổi prompt và không đổi ngưỡng. Nếu buộc phải đổi, ghi lại trong `docs/NHAT_KY_THAY_DOI.md` và báo cáo rõ.
4. **Báo cáo cả kết quả xấu.** Số thấp vẫn là số thật. Hội đồng đánh giá cao việc trung thực hơn số đẹp nhưng không kiểm chứng được.
5. **Nếu tới Ngày 5 mà gold set chưa xong**, chuyển sang phương án cắt bớt ở mục 9.

---

## 1. Tổng quan

| Ngày | Chủ đề | Đầu ra chính | Ước tính |
|---|---|---|---|
| Ngày 1 (Thứ 2) | Xác minh nền tảng, chốt phạm vi | Commit đóng băng, kết quả pytest, trạng thái hiệu lực luật | 5–6 giờ |
| Ngày 2 (Thứ 3) | Sửa lỗi nuốt âm thầm | Trạng thái "chưa kiểm", coverage, không cache lỗi | 5–6 giờ |
| Ngày 3 (Thứ 4) | Sửa lỗi đầu vào; bắt đầu gán nhãn | `.doc` xử lý đúng, xử lý giới hạn 12.000 ký tự, file gán nhãn | 6 giờ |
| Ngày 4 (Thứ 5) | Hoàn tất gold set, tính kappa, đóng băng | Gold set có chuyên gia kiểm, kappa, tag `eval-frozen` | 6 giờ |
| Ngày 5 (Thứ 6) | Chạy đánh giá | Bảng số liệu có CI, trích dẫn đã kiểm | 6–7 giờ |
| Ngày 6 (Thứ 7) | Viết lại tài liệu, sửa bảo mật nhẹ | README, slide, bảng giới hạn, các sửa bảo mật | 5–6 giờ |
| Ngày 7 (Chủ nhật) | Diễn tập và nộp | Demo trên máy sạch, bộ câu hỏi, checklist nộp | 4–5 giờ |

---

## 2. Ngày 1 (Thứ 2): Xác minh nền tảng và chốt phạm vi

**Mục tiêu:** biết chính xác hệ thống hiện tại chạy được gì, và có một mốc đóng băng để so sánh về sau.

### Việc 1.1: Đóng băng commit hiện tại
- [ ] Mở PowerShell tại `D:\contract-agent`.
- [ ] Chạy:
  ```powershell
  git status
  git add -A
  git commit -m "Snapshot trước khi sửa theo kế hoạch 1 tuần"
  git tag baseline-tuan-0
  ```
- [ ] Nếu có file nhạy cảm chưa được ignore (`.env`), kiểm tra lại trước khi commit. Báo cáo ghi `.env` không nằm trong git, nhưng vẫn nên kiểm tra bằng `git status`.

**Tiêu chí xong:** có tag `baseline-tuan-0`.

### Việc 1.2: Chạy pytest trên môi trường sạch
- [ ] Tạo môi trường mới:
  ```powershell
  py -3.12 -m venv .venv-clean
  .venv-clean\Scripts\activate
  pip install -r requirements.txt
  pytest -q 2>&1 | Tee-Object -FilePath docs\test_baseline.txt
  ```
- [ ] Ghi vào `docs/test_baseline.txt`: số pass, số fail, số lỗi, danh sách test fail.
- [ ] Với mỗi test fail, ghi một dòng lý do: lỗi môi trường, lỗi code, hay test cũ không còn đúng.

**Lưu ý:** báo cáo ghi nhận cache cũ liệt kê 13 test fail, nhưng chưa rõ trạng thái hiện tại. Bạn cần con số thực tế.

**Tiêu chí xong:** có file `docs/test_baseline.txt` với số liệu thực. Tất cả test fail đã được phân loại.

### Việc 1.3: Kiểm tra trạng thái hiệu lực của luật trong database
Báo cáo nêu rủi ro: toàn bộ chunk Bộ luật Lao động 2019 (45/2019/QH14) và Nghị định 145/2020 có thể đang bị đánh dấu `is_effective = false`. Đây là lỗi quan trọng nhất cần xác minh.

- [ ] Mở `schema.sql` để tìm tên bảng và cột (xem vùng khoảng dòng 369–881 theo báo cáo).
- [ ] Kết nối database và chạy truy vấn đếm. Tên bảng/cột dưới đây là **ví dụ**, cần đổi theo schema thực:
  ```sql
  SELECT van_ban, is_effective, COUNT(*)
  FROM <bang_chunk_luat>
  WHERE van_ban IN ('BLLĐ 45/2019', 'NĐ 145/2020')
  GROUP BY van_ban, is_effective;
  ```
- [ ] Kiểm tra `evaluation/audit.py` (dòng ~208) để biết tài liệu đã đọc flag này từ đâu.
- [ ] Đối chiếu ngày hiệu lực với văn bản gốc trên vanban.chinhphu.vn hoặc thuvienphapluat.vn. Ghi lại link và ngày truy cập.

**Kết quả có thể xảy ra:**
- (a) Flag đúng: chỉ cần ghi nhận, không sửa.
- (b) Flag sai do lỗi ánh xạ: sửa dữ liệu và chạy lại index. Đây là việc phải làm trước khi đánh giá.
- (c) Dữ liệu không có: ghi giới hạn rõ ràng và dựa vào fallback.

**Tiêu chí xong:** có một dòng kết luận ghi trong `docs/kiem_tra_hieu_luc.md`, kèm bằng chứng (ảnh chụp kết quả truy vấn hoặc đoạn SQL output).

### Việc 1.4: Chốt phạm vi và thông báo cho giảng viên hướng dẫn
- [ ] Viết một trang `docs/PHAM_VI.md` với nội dung:
  - Hệ thống làm gì: rà soát hợp đồng lao động tiếng Việt, phát hiện rủi ro theo 7 luật đỏ và trích dẫn điều luật.
  - Hệ thống **không** làm gì: không tư vấn pháp lý, không xử lý hợp đồng dân sự/thương mại, không đảm bảo độ chính xác của câu trả lời.
- [ ] Gửi giảng viên hướng dẫn một tin ngắn:
  > "Em đang thu hẹp đề tài về rà soát hợp đồng lao động, bổ sung đánh giá trên bộ gold set có chuyên gia kiểm và đo độ trung thực của trích dẫn. Em xin ý kiến thầy/cô về phạm vi này trước khi em hoàn thiện."
- [ ] Nếu chưa được phản hồi trong ngày, vẫn tiếp tục làm theo phạm vi này. Ghi lại thời điểm đã gửi.

**Tiêu chí xong:** có `docs/PHAM_VI.md` và đã gửi tin nhắn cho giảng viên.

### Checkpoint cuối Ngày 1
- [x] Có tag `baseline-tuan-0`
- [x] Có kết quả pytest thực
- [x] Có kết luận về hiệu lực luật
- [x] Có `docs/PHAM_VI.md`

**Nếu thiếu thời gian:** bỏ bớt việc 1.4 chi tiết, chỉ gửi tin nhắn cho giảng viên. Không bỏ việc 1.3.

---

## 3. Ngày 2 (Thứ 3): Sửa lỗi nuốt âm thầm

**Mục tiêu:** hệ thống không còn biến "không tìm thấy rủi ro" thành "đã kiểm và sạch". Đây là lỗi làm mất tin cậy nhất.

### Việc 2.1: Thêm trạng thái "chưa kiểm" cho từng điều khoản
Vị trí liên quan:
- `app/agents/workflow.py` dòng ~112–116: clause bị bỏ khi judge lỗi, với `risks = []`.
- `app/agents/risk_flagger.py` dòng ~171–183: JSON judge hỏng bị coi là ok.

- [ ] Thêm trường `status` cho mỗi kết quả clause, nhận một trong các giá trị: `checked`, `unchecked_error`, `unparsable`.
- [ ] Khi judge thất bại sau số lần retry, đặt `status = unchecked_error`. Không đặt `risks = []` một cách im lặng.
- [ ] Khi JSON judge không parse được, đặt `status = unparsable`. Không coi là ok.
- [ ] Đảm bảo `risks` không mang ý nghĩa "đã kiểm" khi status không phải `checked`.

### Việc 2.2: Cập nhật test
- [ ] Mở `tests/.../test_analysis_retry.py` quanh dòng 85–95. Test hiện đang khẳng định clause bị bỏ là hành vi đúng.
- [ ] Sửa test để khẳng định: clause phải có `status = unchecked_error`, không được biến mất khỏi kết quả.
- [ ] Thêm một test mới: judge trả về JSON hỏng hai lần, kết quả phải có `status = unparsable`.

### Việc 2.3: Coverage trong response
- [ ] Thêm vào response của API phân tích các trường:
  ```json
  "coverage": {
    "tong_so_dieu": 0,
    "da_kiem": 0,
    "chua_kiem": 0,
    "ty_le_da_kiem": 0.0
  }
  ```
- [ ] Đây là đại lượng mà bộ đánh giá đang thiếu. Nó cũng là thứ hội đồng sẽ hỏi.

### Việc 2.4: Không cache analysis lỗi
Vị trí liên quan:
- `app/agents/workflow.py` dòng ~362: analysis rỗng được lưu.
- `app/api/contracts.py` dòng ~125 và ~150–153: đọc cache.

- [ ] Khi extraction hoặc phân tích thất bại, trả về trạng thái lỗi rõ ràng. Không lưu vào bảng kết quả cache.
- [ ] Thêm test: lần phân tích lỗi không tạo bản ghi cache.

### Việc 2.5: Chạy lại test
- [ ] `pytest -q` và so sánh với `docs/test_baseline.txt`.
- [ ] Ghi kết quả vào `docs/test_sau_ngay2.txt`.

**Tiêu chí xong:**
- [x] Không còn đường đi nào mà clause lỗi được coi là "sạch".
- [x] Test `test_analysis_retry.py` khẳng định hành vi mới.
- [x] Coverage có mặt trong response.
- [x] Analysis lỗi không vào cache.

**Nếu thiếu thời gian:** ưu tiên 2.1 và 2.2. Nếu 2.3 chưa xong, ghi trong báo cáo rằng coverage là việc tiếp theo.

---

## 4. Ngày 3 (Thứ 4): Sửa lỗi đầu vào và bắt đầu gán nhãn

**Mục tiêu:** đầu vào không gây lỗi âm thầm, và bắt đầu bộ gold set.

### Việc 3.1: Xử lý file `.doc`
Vị trí: `app/api/contracts.py` dòng ~30 (allowlist), `app/document/parser.py` dòng ~60–61.

- [ ] Chọn một trong hai cách:
  - **Cách A (nhanh):** bỏ `.doc` khỏi allowlist. Trả về lỗi "Định dạng .doc chưa được hỗ trợ, vui lòng chuyển sang .docx".
  - **Cách B:** giữ `.doc` nhưng không cho qua python-docx. Trả lỗi rõ ràng.
- [ ] Cách A được khuyên dùng vì nhanh và an toàn.
- [ ] Thêm test: upload `.doc` nhận lỗi rõ ràng.

### Việc 3.2: Giới hạn 12.000 ký tự
Vị trí: `app/agents/clause_parser.py` dòng ~407.

- [ ] Kiểm tra hợp đồng trung bình dài bao nhiêu. Đếm trên 5–10 file thật.
- [ ] Lựa chọn:
  - **Cách A (nhanh):** giữ giới hạn, nhưng khi vượt quá thì đặt `coverage` thấp và ghi cảnh báo "chỉ kiểm 12.000 ký tự đầu".
  - **Cách B:** chia theo đoạn và xử lý từng phần. Chỉ làm nếu còn thời gian.
- [ ] Ghi quyết định vào `docs/NHAT_KY_THAY_DOI.md`.

### Việc 3.3: Xử lý PDF scan
Vị trí: `app/api/contracts.py` dòng ~75–90.

- [ ] Hiện tại báo "parsing failed" nhưng vẫn lưu. Sửa để không lưu và trả lỗi rõ.

### Việc 3.4: Chuẩn bị file gán nhãn gold set
Đây là phần quyết định điểm phương pháp. Làm ngay hôm nay để các ngày sau chỉ cần gán.

- [ ] Chọn **6 đến 8 hợp đồng lao động** đã ẩn danh (xóa tên, số CCCD, số điện thoại, địa chỉ). Đảm bảo có nguồn hợp pháp để dùng.
- [ ] Từ mỗi hợp đồng, chọn 4–5 điều khoản. Tổng cộng khoảng **30 đơn vị**.
- [ ] Tạo file `evaluation/gold/annotation_template.csv` với các cột:

  | Cột | Ý nghĩa |
  |---|---|
  | `unit_id` | Mã đơn vị, ví dụ HDLD01_D05 |
  | `contract_id` | Mã hợp đồng ẩn danh |
  | `dieu` | Số điều |
  | `noi_dung` | Nội dung điều khoản |
  | `ann1_co_rui_ro` | Người gán 1: có rủi ro không (0/1) |
  | `ann1_luat_dau_ra` | Người gán 1: rủi ro thuộc luật nào trong 7 luật đỏ |
  | `ann1_dieu_luat_dung` | Người gán 1: điều luật được trích dẫn đúng |
  | `ann2_co_rui_ro` | Người gán 2: tương tự |
  | `ann2_luat_dau_ra` | Người gán 2 |
  | `ann2_dieu_luat_dung` | Người gán 2 |
  | `expert_final` | Chuyên gia chốt nhãn |
  | `ghi_chu` | Ghi chú |

- [ ] Viết `evaluation/gold/HUONG_DAN_GAN_NHAN.md` với 1 trang hướng dẫn: định nghĩa "rủi ro" cho từng luật đỏ, cách trích dẫn điều luật, và khi nào đánh dấu không chắc.
- [ ] Liên hệ người gán: **một người bạn thứ hai** và **một chuyên gia** (giảng viên, luật sư, hoặc người làm HR có hiểu luật lao động). Nếu chưa có chuyên gia, ghi rõ trong báo cáo rằng nhãn chưa được chuyên gia kiểm.

**Tiêu chí xong:**
- [x] Đã có file template và hướng dẫn.
- [x] Đã chọn xong hợp đồng và điều khoản.
- [ ] Đã có người tham gia gán nhãn và đã hẹn chuyên gia.

**Nếu thiếu thời gian:** giảm số đơn vị xuống 20. Không bỏ cột `ann2`, vì thiếu nó thì không tính được kappa.

---

## 5. Ngày 4 (Thứ 5): Hoàn tất gold set, tính kappa, đóng băng

**Mục tiêu:** có nhãn đáng tin cậy, đo được độ đồng thuận, và khóa bộ test.

### Việc 4.1: Gán nhãn độc lập
- [ ] Người gán 1 và người gán 2 làm **độc lập**, không trao đổi, trong khoảng 2–3 giờ.
- [ ] Không xem nhãn của nhau.
- [ ] Ghi thời gian bắt đầu và kết thúc vào `evaluation/gold/ghi_chep_gan_nhan.md`.

### Việc 4.2: Tính kappa
- [ ] Tính Cohen's kappa cho cột `ann1_co_rui_ro` và `ann2_co_rui_ro`. Có thể dùng Python:
  ```python
  from sklearn.metrics import cohen_kappa_score
  import pandas as pd
  df = pd.read_csv("evaluation/gold/annotation_template.csv")
  print(cohen_kappa_score(df.ann1_co_rui_ro, df.ann2_co_rui_ro))
  ```
- [ ] Ghi kết quả vào `evaluation/gold/KAPPA.md`.
- [ ] Nếu kappa dưới 0,6, cần thảo luận và xem lại hướng dẫn gán nhãn. Ghi lại các trường hợp bất đồng.

### Việc 4.3: Chuyên gia chốt nhãn
- [ ] Với các đơn vị bất đồng, chuyên gia chọn nhãn cuối cùng, ghi vào cột `expert_final`.
- [ ] Với đơn vị đồng thuận, `expert_final` lấy theo nhãn chung.
- [ ] Chuyên gia cũng kiểm lại một mẫu ngẫu nhiên khoảng 5 đơn vị đồng thuận, để chắc hướng dẫn được áp dụng đúng.

### Việc 4.4: Chia dev và test
- [ ] Chia theo **hợp đồng**, không chia theo điều khoản, để tránh rò rỉ.
- [ ] Ví dụ: 2 hợp đồng làm dev (dùng để kiểm tra code), 4 hợp đồng làm test.
- [ ] Ghi vào `evaluation/gold/split.json`.
- [ ] **Không xem kết quả trên test trước Ngày 5.**

### Việc 4.5: Đóng băng
- [ ] Tạo commit và tag:
  ```powershell
  git add evaluation/gold docs
  git commit -m "Đóng băng gold set và phân chia dev/test"
  git tag eval-frozen
  ```
- [ ] Từ đây không sửa `evaluation/gold/`. Mọi thay đổi ghi vào `docs/NHAT_KY_THAY_DOI.md`.

**Tiêu chí xong:**
- [ ] Có nhãn cuối cùng cho toàn bộ đơn vị.
- [ ] Có kappa và ghi chép bất đồng.
- [ ] Có chia dev/test theo hợp đồng.
- [ ] Có tag `eval-frozen`.

**Nếu thiếu thời gian:** nếu không có chuyên gia, dùng nhãn đồng thuận của hai người và ghi rõ "chưa có chuyên gia kiểm" trong mọi bảng số liệu.

---

## 6. Ngày 5 (Thứ 6): Chạy đánh giá

**Mục tiêu:** có bảng số liệu có khoảng tin cậy, và kiểm tra trích dẫn.

### Việc 5.1: Chuẩn bị script đánh giá
- [ ] Tạo `evaluation/run_eval.py` hoặc tận dụng script có sẵn. Script cần:
  - Đọc `evaluation/gold/annotation_template.csv` và `split.json`.
  - Chạy hệ thống trên tập **test** (4 hợp đồng).
  - Xuất `evaluation_results/YYYYMMDD_test.json` kèm hash commit.
- [ ] Kiểm tra trên tập **dev** trước để chắc script không lỗi.

### Việc 5.2: Các phép đo cần có
| Phép đo | Cách tính | Ghi chú |
|---|---|---|
| Coverage | Tỷ lệ điều khoản được kiểm | Đại lượng mới từ Ngày 2 |
| Precision, Recall, F1 (phát hiện rủi ro) | So với `expert_final` ở mức điều khoản | Cho hệ thống đầy đủ |
| False Rate | Tỷ lệ cảnh báo sai | Theo ContractEval |
| Độ trung thực trích dẫn | Xem việc 5.4 | Đo riêng |

- [ ] Tính khoảng tin cậy 95% bằng bootstrap (1000 lần lặp).

### Việc 5.3: Baseline
- [ ] **Baseline 1: rule-only.** Chỉ chạy `labor_red_flags.py`, không gọi LLM. Dùng để chứng minh phần LLM có đóng góp gì.
- [ ] **Baseline 2 (nếu còn thời gian): không RAG.** Judge nhận clause mà không có ngữ cảnh truy xuất.
- [ ] Ghi cả ba cấu hình vào cùng một bảng để so sánh.

### Việc 5.4: Kiểm tra độ trung thực trích dẫn
- [ ] Lấy **50 trích dẫn** (từ các cảnh báo của hệ thống trên test hoặc từ câu trả lời QA).
- [ ] Với mỗi trích dẫn, hai người kiểm 3 câu hỏi:
  1. Điều luật được trích có tồn tại không?
  2. Điều luật có còn hiệu lực tại thời điểm hợp đồng không?
  3. Nội dung điều luật có thực sự hỗ trợ khẳng định không?
- [ ] Ghi kết quả vào `evaluation/gold/kiem_trich_dan.csv`.
- [ ] Tính tỷ lệ mỗi tiêu chí.

### Việc 5.5: Gemini quota
Báo cáo ghi nhận quota khoảng 20 yêu cầu mỗi ngày (theo notes, chưa xác minh).
- [ ] Trước khi chạy, ước tính số lệnh gọi = số clause trên test × số lần judge.
- [ ] Nếu vượt quota, chạy theo ngày, hoặc dùng baseline rule-only đầy đủ và chỉ chạy LLM cho một phần. Ghi rõ điều này trong báo cáo.
- [ ] Lưu toàn bộ kết quả trung gian để không phải chạy lại.

### Việc 5.6: Ghi kết quả
- [ ] Lưu `evaluation_results/RESULTS_TUAN.md` với bảng số liệu, khoảng tin cậy, và số cấu hình.
- [ ] Ghi số xấu cũng như số tốt.

**Tiêu chí xong:**
- [ ] Có bảng số liệu cho ít nhất hai cấu hình (đầy đủ và rule-only).
- [ ] Có khoảng tin cậy.
- [ ] Có kết quả kiểm trích dẫn trên 50 mẫu.
- [ ] Kết quả lưu kèm hash commit.

**Nếu thiếu thời gian:** bỏ baseline không RAG. Không bỏ kiểm trích dẫn.

---

## 7. Ngày 6 (Thứ 7): Viết lại tài liệu và sửa bảo mật nhẹ

**Mục tiêu:** tài liệu khớp với những gì hệ thống thực sự làm và đo được.

### Việc 6.1: Sửa README
- [x] Đổi tiêu đề và mô tả từ "hợp đồng" thành "hợp đồng lao động".
- [ ] Xóa các tuyên bố chưa có bằng chứng:
  - Nhiều nhà cung cấp LLM (hiện chỉ có Gemini).
  - Chat time-travel hoặc `as_of_date` (API hiện không nhận tham số này).
  - Human-in-the-loop, nếu chỉ có API và không có giao diện.
- [x] Thêm mục **Giới hạn** gồm: chưa đo được độ chính xác câu trả lời, gold set có bao nhiêu đơn vị, chưa kiểm chứng trên hợp đồng ngoài bộ dữ liệu, file `.doc` không hỗ trợ.

### Việc 6.2: Sửa slide
- [ ] Gộp các bản deck trùng lặp thành một bản.
- [ ] Thêm một slide "Những gì chưa làm và giới hạn".
- [ ] Thay mọi con số cũ bằng số từ `RESULTS_TUAN.md`, kèm khoảng tin cậy.
- [ ] Thêm slide so sánh với PAKTON, Kyta, Ojas1584, nhấn vào phần đo độ trung thực trích dẫn và gold set có chuyên gia.

### Việc 6.3: Sửa bảo mật nhẹ
Làm từng việc, mỗi việc kèm một test nhỏ nếu có thể:
- [x] Giới hạn số lần đăng nhập sai (ví dụ 5 lần mỗi 15 phút).
- [x] Đăng ký trùng email: trả thông báo chung, không lộ email đã tồn tại (vị trí hiện trả 409).
- [x] Mật khẩu tối thiểu 8 ký tự (hiện 6).
- [x] Giới hạn kích thước upload (ví dụ 10 MB) tại `app/api/routes.py` quanh dòng 127.
- [x] Ghim phiên bản trong `requirements.txt` (chạy `pip freeze` và copy các phiên bản đang dùng).
- [x] Đổi cổng database và credential mặc định, hoặc ghi rõ đây là môi trường phát triển và không đưa ra production.

**Tiêu chí xong:**
- [ ] README và slide không còn tuyên bố nào không có bằng chứng.
- [x] Có mục giới hạn rõ ràng.
- [x] Các sửa bảo mật đã chạy được, pytest vẫn pass ở mức như trước.

**Nếu thiếu thời gian:** ưu tiên 6.1 và 6.2. Phần 6.3 chỉ làm 2–3 việc quan trọng nhất (đăng nhập, upload, requirements) và ghi các việc còn lại vào mục "Hướng phát triển".

---

## 8. Ngày 7 (Chủ nhật): Diễn tập và nộp

**Mục tiêu:** demo chạy được, trả lời được câu hỏi khó, nộp đúng hạn.

### Việc 7.1: Chạy pytest lần cuối
- [ ] `pytest -q > docs/test_final.txt`
- [ ] So sánh với `test_baseline.txt`. Nếu số fail tăng, kiểm tra lại trước khi nộp.

### Việc 7.2: Diễn tập demo trên máy sạch
- [ ] Clone repo hoặc copy vào thư mục mới, không dùng môi trường đang phát triển.
- [ ] Chạy `docker compose up` (hoặc hướng dẫn trong README).
- [ ] Demo với **một hợp đồng nhỏ** đã chuẩn bị sẵn.
- [ ] Đo thời gian chạy. Mục tiêu: dưới 15 phút từ đầu đến cuối.
- [ ] Nếu demo lỗi, có sẵn ảnh chụp kết quả để trình bày.

### Việc 7.3: Chuẩn bị 12 câu hỏi khó
Viết câu trả lời ngắn (3–5 câu) cho mỗi câu, lưu trong `docs/CAU_HOI_HOI_DONG.md`:

1. Gold label do ai tạo, có chuyên gia kiểm không?
2. Kappa là bao nhiêu? Bất đồng xử lý thế nào?
3. Ba thay đổi thiết kế có được chọn sau khi xem kết quả test không? Hiện đã xử lý ra sao?
4. Hệ thống bỏ điều khoản khi judge lỗi không? Đã sửa thế nào?
5. Hệ thống khác gì PAKTON, Kyta, Ojas1584?
6. Độ chính xác cảnh báo so với luật sư là bao nhiêu?
7. Hợp đồng dài hơn 12.000 ký tự xử lý thế nào?
8. Luật Bộ luật Lao động 2019 có được đánh dấu hiệu lực đúng không?
9. Chi phí và độ trễ mỗi hợp đồng là bao nhiêu?
10. Chống prompt injection từ nội dung hợp đồng thế nào?
11. Dữ liệu hợp đồng gửi sang Gemini có tuân thủ quy định bảo vệ dữ liệu cá nhân không?
12. Pytest pass bao nhiêu? Chạy được trên máy khác không?

### Việc 7.4: Checklist nộp
- [ ] Báo cáo cuối cùng đã cập nhật số liệu thật.
- [ ] Slide đã sửa và không còn tuyên bố sai.
- [ ] README đã cập nhật.
- [ ] `evaluation_results/` có kết quả kèm hash commit.
- [ ] `docs/NHAT_KY_THAY_DOI.md` đã ghi đầy đủ mọi thay đổi sau `eval-frozen`.
- [ ] Tag cuối: `git tag nop-bao-ve` và push.
- [ ] Đã gửi bản nộp cho giảng viên đúng hạn.

**Nếu thiếu thời gian:** bỏ 7.3 chi tiết, nhưng vẫn đọc lại 12 câu hỏi trước khi bảo vệ.

---

## 9. Phương án cắt bớt (nếu bị trễ)

Nếu đến Ngày 5 mà chưa xong gold set, cắt theo thứ tự sau. Không cắt theo thứ tự khác.

| Mức | Cắt gì | Điều kiện để giữ đề tài có giá trị |
|---|---|---|
| 1 | Baseline không RAG | Vẫn có rule-only |
| 2 | Số đơn vị gold giảm từ 30 xuống 20 | Vẫn có kappa |
| 3 | Chuyên gia chỉ kiểm mẫu ngẫu nhiên 5 đơn vị | Ghi rõ trong báo cáo |
| 4 | Kiểm trích dẫn giảm từ 50 xuống 20 | Vẫn có tỷ lệ và ghi rõ cỡ mẫu |
| 5 | Bảo mật nhẹ chỉ còn đăng nhập và upload | Ghi phần còn lại vào hướng phát triển |

**Không bao giờ cắt:** Ngày 2 (lỗi nuốt âm thầm), việc kiểm hiệu lực luật (1.3), và việc ghi lại kết quả xấu.

---

## 10. Nhật ký tiến độ

Điền mỗi tối.

| Ngày | Đã làm | Chưa xong | Vấn đề gặp phải | Quyết định mới |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |

---

## 11. Các file cần tạo trong tuần này

- [x] `docs/test_baseline.txt`
- [x] `docs/kiem_tra_hieu_luc.md`
- [x] `docs/PHAM_VI.md`
- [x] `docs/test_sau_ngay2.txt`
- [x] `docs/NHAT_KY_THAY_DOI.md`
- [x] `evaluation/gold/annotation_template.csv`
- [x] `evaluation/gold/HUONG_DAN_GAN_NHAN.md`
- [ ] `evaluation/gold/ghi_chep_gan_nhan.md`
- [ ] `evaluation/gold/KAPPA.md`
- [ ] `evaluation/gold/split.json`
- [ ] `evaluation/gold/kiem_trich_dan.csv`
- [x] `evaluation/run_eval.py`
- [ ] `evaluation_results/RESULTS_TUAN.md`
- [x] `docs/CAU_HOI_HOI_DONG.md`
- [x] `docs/test_final.txt`

---

## 12. Giới hạn của kế hoạch này

- Các đường dẫn file và số dòng lấy từ báo cáo phân tích, chưa được đối chiếu lại với mã nguồn hiện tại. Nếu lệch, tìm theo tên hàm.
- Tên bảng và cột trong database là ví dụ. Cần đối chiếu với `schema.sql`.
- Thời lượng ước tính giả định bạn làm khoảng 5–7 giờ mỗi ngày. Nếu ít thời gian hơn, dùng phương án cắt bớt ở mục 9.
- Nhãn luật pháp Việt Nam cần đối chiếu văn bản gốc, không dựa vào nguồn thứ cấp.
- Kế hoạch này không đảm bảo kết quả đo đạt điểm cao. Nó đảm bảo đề tài trung thực hơn, có bằng chứng hơn, và sửa được những lỗi hội đồng sẽ hỏi.
