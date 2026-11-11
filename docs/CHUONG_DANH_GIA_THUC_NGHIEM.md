# Chương 5. Đánh giá thực nghiệm

> Bản nháp soạn ngày 10/11/2026 từ các báo cáo trong `evaluation_results/` và `docs/NHAT_KY_THAY_DOI.md`. Mọi số liệu lấy từ file kết quả đã commit.
> Đánh số chương, bảng, hình theo mẫu báo cáo của khoa khi ghép vào.

## 5.1. Mục tiêu và câu hỏi đánh giá

ContractLens gồm ba thành phần có thể đo riêng: (1) truy xuất văn bản pháp luật, (2) phát hiện rủi ro bằng luật cố định (8 "luật đỏ" trong `app/agents/labor_red_flags.py`), (3) đánh giá từng điều khoản bằng mô hình ngôn ngữ lớn (LLM judge). Chương này trả lời bốn câu hỏi:

- **RQ1.** Module truy xuất tìm đúng điều luật đến mức nào, và thành phần tìm kiếm từ khoá (FTS) trong cơ chế lai (hybrid RRF) có đóng góp không?
- **RQ2.** Hệ thống phát hiện được bao nhiêu vi phạm đã biết trong hợp đồng lao động, ở từng thành phần (luật cố định và LLM judge)?
- **RQ3.** Hệ thống báo nhầm đến mức nào trên điều khoản hợp lệ và trên một hợp đồng không bị bơm lỗi?
- **RQ4.** Các thay đổi thiết kế (đổi cấu hình truy xuất, xử lý câu phủ định) có cải thiện kết quả không?

Chương **không** đánh giá độ chính xác pháp lý của câu trả lời theo nghĩa "luật sư đồng ý". Đề tài chưa có chuyên gia pháp lý kiểm nhãn; giới hạn này được nêu ở mục 5.9.

## 5.2. Nguyên tắc thực nghiệm

Báo cáo đánh giá trước đây của dự án (bộ v04, 34 câu) có hai điểm yếu: nhãn là bản nháp tổng hợp chưa được kiểm và một số thay đổi thiết kế được chọn sau khi xem kết quả trên chính bộ test. Các thí nghiệm trong chương này được tổ chức để tránh hai điểm đó:

1. **Nhãn không do hệ thống tạo.** Benchmark truy xuất dùng bộ dữ liệu bên ngoài. Bộ phát hiện rủi ro dùng nhãn có được do cấu tạo (bơm lỗi), không dùng nhãn do LLM sinh.
2. **Đóng băng trước khi chạy.** Bộ test, cách chấm và quy tắc quyết định được commit và gắn tag trước khi chạy hệ thống (bảng 5.9, phụ lục 5.A).
3. **Tách dev/test.** Mọi điều chỉnh làm trên dev. Tập test chạy đúng một lần cho mỗi cấu hình; script tự tạo file khoá để chặn chạy lại.
4. **Khai báo trước.** Các biến thể được thử và quy tắc chọn được ghi vào nhật ký trước khi chạy.
5. **Báo cáo độ bất định.** Khoảng tin cậy 95% bằng bootstrap (1000 lần lấy mẫu lại theo đơn vị đánh giá); so sánh hai cấu hình dùng bootstrap ghép cặp trên cùng tập câu.
6. **Truy vết được.** Mỗi kết quả ghi hash commit, SHA-256 của dữ liệu và cấu hình.
7. **Báo cáo cả kết quả xấu.** Kết quả âm tính được giữ nguyên (mục 5.6, 5.7).

## 5.3. Thí nghiệm 1: truy xuất văn bản pháp luật (RQ1)

### 5.3.1. Dữ liệu

- **Nguồn:** `data/dataset.csv`, 3.298 dòng, 3.196 câu hỏi, 724 văn bản. Mỗi câu có nhãn là cặp (số hiệu văn bản, số Điều); 93 câu có nhiều hơn một dòng nhãn (84 câu có hai dòng, 9 câu có từ ba dòng trở lên).
- **Xuất xứ:** đối chiếu toàn bộ 3.196 câu với bộ Hugging Face `DaHaDaHa/zac2021`: 100% trùng mã câu hỏi, nội dung câu hỏi và nhãn. Theo tên và cấu trúc, đây là dữ liệu cuộc thi Zalo AI Challenge 2021 – Legal Text Retrieval; tuy nhiên trang Hugging Face không có mô tả nên mối liên hệ với cuộc thi và giấy phép **chưa được kiểm chứng độc lập** (`evaluation_results/legal_qa/NGUON_DATASET.md`).
- **Chia dev/test:** theo văn bản (băm MD5 số hiệu văn bản, 20% dev), để câu hỏi của cùng một văn bản không nằm ở cả hai tập: dev 523 câu, test 2.673 câu. Đóng băng ở tag `legalqa-split-frozen`.

### 5.3.2. Độ phủ của kho dữ liệu

Hệ thống chỉ tìm trong các đoạn còn hiệu lực (`is_effective`, văn bản không có `status_flag = 2`). Bộ dữ liệu được gán nhãn năm 2021, nên nhiều văn bản gold đã hết hiệu lực (bảng 5.1).

**Bảng 5.1. Trạng thái điều luật gold trong kho (3.196 câu)**

| Trạng thái | Số câu | Tỷ lệ |
|---|---:|---:|
| Điều gold tìm kiếm được | 772 | 24,2% |
| Văn bản có trong kho nhưng không tìm kiếm được | 2.257 | 70,6% |
| Văn bản không có trong kho | 162 | 5,1% |
| Văn bản tìm được nhưng thiếu đúng Điều | 5 | 0,2% |

Trong 2.257 câu "có nhưng không tìm được": 1.509 câu (66,9%) do văn bản đã hết hiệu lực toàn bộ, 679 câu (30,1%) do văn bản hết hiệu lực một phần (`status_flag = 4`) nhưng toàn bộ đoạn bị đánh dấu không hiệu lực, phần còn lại do thiếu đoạn hoặc thiếu embedding (`coverage_breakdown.md`). Nhóm thứ hai là một phát hiện về dữ liệu: cờ hiệu lực của văn bản đang được sao xuống mọi đoạn, nên các điều **còn hiệu lực** của văn bản sửa đổi một phần cũng bị ẩn. Lỗi này chưa được sửa.

Vì vậy kết quả chính được báo cáo trên các câu có điều gold tìm kiếm được (`--only-covered`), kèm con số trên toàn bộ tập test.

### 5.3.3. Cấu hình so sánh và chỉ số

- `fts`: chỉ tìm từ khoá (PostgreSQL `plainto_tsquery`).
- `vector`: chỉ tìm ngữ nghĩa (BGE-M3, pgvector).
- `hybrid` (cũ): kết hợp hai nhánh bằng Reciprocal Rank Fusion (k = 60), cấu hình mặc định ban đầu của ứng dụng.
- `hybrid + V3`: biến thể được chọn trên dev (mục 5.3.4).

Chỉ số: Recall@k (k = 1, 5, 10, khớp cả văn bản và số Điều), MRR@10, DocRecall@10 (chỉ khớp văn bản), độ trễ. Kết quả được gộp theo Điều trước khi xếp hạng. Thí nghiệm không gọi LLM.

### 5.3.4. Điều chỉnh trên dev

Phân tích lỗi trên dev (216 câu, `PHAN_TICH_LOI_DEV.md`) cho thấy nhánh FTS dùng ngữ nghĩa AND trên cả câu hỏi nên rỗng ở 50/216 câu và chỉ đúng 7/216 câu; khi trộn bằng RRF, kết quả nhiễu của FTS chen vào hạng 2 ở 150/216 câu. Ba biến thể được khai báo trước: V1 (FTS dùng OR), V2 (V1 + loại đoạn không thuộc Điều nào), V3 (V2 + RRF có trọng số 0,7 vector / 0,3 FTS). Quy tắc: chọn biến thể có MRR@10 cao nhất trên dev. V3 được chọn (MRR@10 = 0,711 trên dev), nhưng khoảng tin cậy của chênh lệch V3 − vector trên dev đã chứa 0 (`DEV_BIEN_THE.md`).

### 5.3.5. Kết quả trên tập test

**Bảng 5.2. Kết quả truy xuất trên tập test (556/2.673 câu có điều gold tìm kiếm được, mỗi cấu hình chạy một lần)**

| Cấu hình | R@1 | R@5 [CI95] | R@10 | MRR@10 [CI95] | DocR@10 | Độ trễ median |
|---|---:|---|---:|---|---:|---:|
| fts | 0,005 | 0,009 [0,002; 0,018] | 0,014 | 0,007 [0,001; 0,014] | 0,025 | 85 ms |
| vector | 0,594 | 0,795 [0,763; 0,827] | 0,836 | 0,682 [0,649; 0,715] | 0,910 | 294 ms |
| hybrid (cũ) | 0,581 | 0,736 [0,701; 0,772] | 0,791 | 0,642 [0,609; 0,677] | 0,894 | 347 ms |
| hybrid + V3 | 0,590 | 0,802 [0,768; 0,835] | 0,842 | 0,686 [0,655; 0,719] | 0,908 | 4.237 ms |

**Bảng 5.3. So sánh ghép cặp MRR@10 (bootstrap 95%, cùng 556 câu)**

| So sánh | Chênh lệch | CI95 |
|---|---:|---|
| hybrid cũ − vector | −0,040 | [−0,048; −0,031] |
| hybrid + V3 − vector | +0,004 | [−0,006; +0,014] |
| hybrid + V3 − hybrid cũ | +0,044 | [+0,029; +0,057] |

Nguồn: `evaluation_results/legal_qa/TEST_KET_QUA.md`.

### 5.3.6. Thảo luận

- Tìm kiếm ngữ nghĩa bằng BGE-M3 đạt Recall@5 = 0,795 và tìm đúng văn bản trong top 10 ở 91% câu.
- **Cơ chế lai ban đầu kém hơn chỉ dùng vector, có ý nghĩa thống kê** (MRR −0,040, CI không chứa 0). Nguyên nhân là nhánh FTS gần như không tìm được kết quả đúng nhưng vẫn chen kết quả nhiễu vào danh sách trộn.
- Sửa nhánh FTS (V3) đưa hybrid về **ngang** vector (CI chứa 0) nhưng chậm hơn khoảng 14 lần do truy vấn OR khớp gần như toàn bộ khoảng 1 triệu đoạn. Vì vậy đề tài **không** tuyên bố cơ chế lai là đóng góp; kết luận là tìm kiếm ngữ nghĩa đủ tốt trên benchmark này.
- Nếu tính các câu không thể tìm (văn bản hết hiệu lực hoặc thiếu) là trượt, Recall@10 trên toàn bộ 2.673 câu test chỉ khoảng 17,4% (vector). Con số này phản ánh lệch thời điểm giữa nhãn năm 2021 và trạng thái hiệu lực hiện tại, không phản ánh chất lượng xếp hạng; nhưng nó cũng cho thấy hệ thống không trả lời được câu hỏi về văn bản đã hết hiệu lực.
- Benchmark này đo truy xuất pháp luật chung, không đo rà soát hợp đồng.

## 5.4. Thí nghiệm 2: chọn cấu hình truy xuất cho ứng dụng

Từ kết quả 5.3, đề tài kiểm tra xem chuyển sang vector-only có làm xấu phần hợp đồng không, trên bộ v04 (34 tình huống hợp đồng, nhãn nháp tổng hợp). Quy tắc khai báo trước: đổi sang vector-only nếu số ca đúng không thấp hơn hybrid quá 1 ca.

Kết quả (commit `087256a`): exact provision recall 0,299 ở cả hai cấu hình, MRR 0,300 ở cả hai; cross-document coverage 0,446 (hybrid) và 0,461 (vector). Theo quy tắc, mặc định của ứng dụng được đổi sang vector-only (commit `7148b39`).

Bộ v04 có nhãn chưa được kiểm và n = 34, nên thí nghiệm này chỉ là kiểm tra "không làm hỏng", không phải bằng chứng về chất lượng.

## 5.5. Thí nghiệm 3: phát hiện vi phạm bằng bơm lỗi (RQ2, RQ3)

### 5.5.1. Thiết kế

Vì không có chuyên gia gán nhãn, đề tài dùng phương pháp bơm lỗi: nhãn có được do cách tạo ca.

- **Hợp đồng nền:** một hợp đồng lao động 11 Điều do tác giả soạn; 8 Điều là "vị trí" ứng với 8 luật đỏ.
- **Ca thử:** mỗi luật có 5 ca **vi phạm** và 5 ca **hợp lệ gần giống** (near-miss), tổng 80 ca. Mỗi ca thay đúng một Điều của hợp đồng nền.
- **Đa dạng diễn đạt:** mỗi luật có 3/5 ca vi phạm viết khác mẫu quen thuộc (diễn đạt lại, số bằng chữ, viết tắt, câu dài). Ca hợp lệ gồm câu phủ định chứa từ khoá, biến thể hợp pháp và ca sát ngưỡng.
- **Căn cứ:** mỗi ca ghi điều luật BLLĐ 2019 tương ứng (Điều 17, 40, 48, 62, 94, 98, 102, 107, 124, 127, 137, 138, 168, 179, 187).
- **Đóng băng:** tag `injection-frozen` (commit `e268fcb`) trước khi chạy hệ thống. Cách chấm khai báo trong `evaluation/injection/README.md`.

### 5.5.2. Luật cố định (80 ca, không LLM)

**Bảng 5.4. Kết quả luật cố định (tổng micro trên 8 luật)**

| TP | FP | FN | Precision [CI95] | Recall [CI95] | F1 [CI95] |
|---:|---:|---:|---|---|---|
| 16 | 14 | 24 | 0,53 [0,36; 0,73] | 0,40 [0,25; 0,56] | 0,46 [0,30; 0,60] |

- Luật cố định bắt đúng **16/16** ca viết theo mẫu quen thuộc, nhưng bỏ sót toàn bộ 24 ca viết khác mẫu (diễn đạt lại 10, số bằng chữ 5, viết tắt 5, câu dài 4). Recall 0,40 bị chặn trên do thiết kế bộ ca (3/5 ca khác mẫu), nên nó đo khả năng khái quát hoá, không phải recall kỳ vọng trên hợp đồng thật.
- 14/40 ca hợp lệ bị báo nhầm: 7 ca là câu phủ định hợp lệ ("Công ty không áp dụng hình thức phạt tiền"), 7 ca là nội dung hợp pháp chứa từ khoá. Bước quét không xét phủ định.
- Không có luật nào kích hoạt nhầm trên ca của luật khác.

### 5.5.3. Pipeline đầy đủ với LLM judge (48 ca)

Do hạn mức gọi API, pipeline đầy đủ chạy trên mẫu khai báo trước: 3 vi phạm + 3 hợp lệ mỗi luật (48 ca, seed cố định). Judge ban đầu là Gemini nhưng hết hạn mức sau 2 ca; đề tài đổi sang Groq `openai/gpt-oss-120b` (nhiệt độ 0), ghi vào nhật ký trước khi chạy. Hai ca Gemini không được tính. Cấu hình demo của ứng dụng cũng được chuyển sang judge này để hệ thống được đánh giá trùng với hệ thống trình diễn.

Một ca được tính là dương tính khi Điều bị bơm có cờ `critical` hoặc `warning`.

**Bảng 5.5. Kết quả pipeline đầy đủ (48 ca)**

| TP | FP | FN | TN | Precision [CI95] | Recall | F1 [CI95] | Điều chưa kiểm |
|---:|---:|---:|---:|---|---:|---|---:|
| 24 | 15 | 0 | 9 | 0,62 [0,46; 0,76] | 1,00 | 0,76 [0,63; 0,87] | 0 |

- Pipeline bắt **24/24** ca vi phạm, kể cả các ca viết khác mẫu mà luật cố định bỏ sót.
- Nhưng 15/24 ca hợp lệ (62%) bị gắn cờ: 8 biến thể hợp pháp, 5 câu phủ định, 1 số bằng chữ, 1 câu dài.
- Ở cả 48/48 ca, các Điều khác ngoài Điều bị bơm cũng bị gắn cờ (trung bình 4,4 Điều có số mỗi ca; 5,4 nếu tính cả cờ ở cấp toàn văn).

## 5.6. Thí nghiệm 4: hợp đồng nền không bơm lỗi (RQ3)

Để biết các cờ ở Điều khác có phải báo nhầm không, pipeline được chạy trên chính hợp đồng nền (11/11 Điều được kiểm, một lần chạy). Kết quả: 8 cờ (7 `warning`, 1 `critical`). Tác giả phân loại từng cờ theo văn bản BLLĐ 2019 trong kho (`BASE_CONTRACT_FLAGS.md`); phân loại chưa có chuyên gia xác nhận.

**Bảng 5.6. Phân loại cờ trên hợp đồng nền**

| Loại | Số cờ | Ví dụ |
|---|---:|---|
| Báo nhầm | 6 | Điều 8: judge đòi báo trước 45 ngày, nhưng hợp đồng xác định thời hạn 24 tháng chỉ cần 30 ngày (Điều 35 khoản 1 điểm b) |
| Cảnh báo có căn cứ | 1 | Hợp đồng nền thiếu thông tin định danh các bên theo Điều 21 khoản 1 điểm a, b |
| Không chắc | 1 | Điều 9: góp ý soạn thảo về lao động nữ mang thai, luật đã cấm sẵn ở Điều 137 |

Hai lỗi của judge đáng chú ý:

- **Áp sai số liệu luật:** cờ `critical` duy nhất (Điều 8) sai về thời hạn báo trước.
- **Khuyến nghị trái luật:** ở Điều 5, judge đề nghị người sử dụng lao động giữ bản chính giấy tờ của người lao động, trong khi Điều 17 khoản 1 cấm việc này. Judge cũng hai lần trích Nghị định 27/2014, văn bản chỉ áp dụng cho lao động giúp việc gia đình.

Quan sát thêm (sau khi xem dữ liệu, mẫu nhỏ, chỉ mang tính gợi ý): trong lần chạy 48 ca, ca hợp lệ đặt vào các Điều mà hợp đồng nền đã bị gắn cờ sẵn bị gắn cờ 14/21 lần; ca đặt vào Điều 4 (nền không bị gắn cờ) chỉ 1/3. Nghĩa là phần lớn báo nhầm có thể đến từ xu hướng gắn cờ sẵn của judge trên các Điều đó, không nhất thiết do nội dung ca. Chỉ số khai báo ban đầu ở bảng 5.5 được giữ nguyên.

Hợp đồng nền cũng không hoàn toàn sạch: nó thiếu thông tin định danh (Điều 21), và còn thiếu điểm e, h của Điều 21 khoản 1 mà pipeline không phát hiện.

## 5.7. Thí nghiệm 5: xử lý câu phủ định trong luật cố định (RQ4)

Từ mục 5.5.2, đề tài thử sửa bước quét để bỏ qua kết quả khớp đứng sau từ phủ định (cửa sổ 30 ký tự, dừng ở dấu câu). Để tránh đánh giá trên dữ liệu đã xem, một bộ mới 32 ca (8 luật × 2 vi phạm + 2 hợp lệ, tập trung vào phủ định) được viết và đóng băng (tag `injection-v2-frozen`) **trước** khi sửa code.

**Bảng 5.7. Luật cố định trước và sau khi xử lý phủ định (bộ injection_v2)**

| | Trước | Sau |
|---|---|---|
| TP / FP / FN | 16 / 16 / 0 | 8 / 8 / 8 |
| Precision [CI95] | 0,50 [0,31; 0,69] | 0,50 [0,23; 0,75] |
| Recall [CI95] | 1,00 | 0,50 [0,25; 0,76] |
| F1 [CI95] | 0,67 [0,48; 0,81] | 0,50 [0,25; 0,69] |

Bản sửa loại được cả 8 báo nhầm khi từ phủ định đứng ngay trước cụm khoá, nhưng làm mất cả 8 vi phạm có một chữ "không" khác đứng gần (ví dụ "không đền bù ngày phép và không trả lương tháng cuối"), và không xử lý phủ định đứng sau cụm khoá. Kết quả ròng không tốt hơn. Bộ ca cố ý cân bằng giữa hai kiểu câu này nên con số phản ánh sự đánh đổi của heuristic, không phản ánh tần suất ngoài thực tế.

Với công cụ sàng lọc rủi ro, bỏ sót vi phạm nguy hiểm hơn báo nhầm (báo nhầm còn được người dùng kiểm lại). Vì recall giảm từ 1,00 xuống 0,50 mà precision không đổi (0,50), bản sửa được đặt sau cờ cấu hình `RED_FLAG_NEGATION_CHECK` (commit `6ba982d`) và **tắt mặc định**: ứng dụng dùng hành vi quét cũ; bật cờ cho đúng hành vi của bản sửa ban đầu (commit `04f1e6c`). Sau khi đưa vào cờ, rule-only trên injection_v2 được chạy lại ở cả hai trạng thái: cờ tắt cho TP/FP/FN = 16/16/0 và trùng từng ca với cột "Trước" của bảng 5.7; cờ bật cho 8/8/8 và trùng cột "Sau". Hai trạng thái có test đơn vị (`tests/unit/test_red_flags_negation.py`).

## 5.8. Độ tin cậy của phần mềm

- **Không còn lỗi im lặng.** Điều khoản mà judge lỗi hoặc trả JSON hỏng được đánh dấu `unchecked_error` / `unparsable` và hiện là "Chưa kiểm" trên giao diện, thay vì bị coi là không có rủi ro. Kết quả phân tích có trường độ phủ (`tong_so_dieu`, `da_kiem`, `chua_kiem`, `ty_le_da_kiem`). Trong các lần chạy đánh giá, số Điều chưa kiểm được báo riêng (bảng 5.5: 0 Điều).
- **Kiểm thử tự động:** `pytest tests/unit tests/evaluation`: 331 passed, 1 skipped ở tag `defense-freeze` (sau khi thêm cờ phủ định và các test của nó).
- **Lỗi `.agent-harness/HANDOFF.md` khi chạy thử end-to-end với judge Groq: đã tìm ra nguyên nhân, không phải lỗi của hệ thống.** Một Điều từng bị đánh dấu chưa kiểm với lỗi này (hệ thống ghi nhận đúng là "chưa kiểm", không nuốt lỗi). Giả thuyết ban đầu là model tự gọi công cụ đọc file; **không đúng**: không có `tool_calls` hay lỗi HTTP, và ứng dụng không truyền công cụ nào cho model. Nguyên nhân là một file `h2.py` ngoài dự án nằm trong thư mục Temp của máy phát triển; khi script chạy từ thư mục đó, `import h2` (gói HTTP/2 mà thư viện HTTP nạp) chạy nhầm file này. Tái hiện trực tiếp được, và lỗi biến mất khi script chạy từ thư mục khác. Chạy hợp đồng demo qua API 5 lần liên tiếp: số Điều chưa kiểm mỗi lần là 0, 0, 0, 0, 0 (5/5 Điều được kiểm). Đã thêm log phản hồi thô của Groq khi lỗi để lần sau thấy ngay nguyên nhân thật nếu có (`docs/NHAT_KY_THAY_DOI.md`).

## 5.9. Tổng hợp và thảo luận

**Bảng 5.8. Trả lời các câu hỏi đánh giá**

| Câu hỏi | Kết luận | Mức chắc chắn |
|---|---|---|
| RQ1 | Tìm kiếm vector đạt R@5 = 0,795 trên 556 câu test. Hybrid ban đầu kém vector có ý nghĩa; sửa FTS chỉ đưa về ngang. Ứng dụng đã chuyển sang vector-only. | Cao trong phạm vi câu còn hiệu lực; thấp trên toàn bộ dataset (24% độ phủ) |
| RQ2 | Luật cố định chính xác với mẫu quen nhưng không khái quát được (recall 0,40 trên bộ có 60% ca khác mẫu). LLM judge bắt 24/24 vi phạm. | Trung bình: ca do tác giả viết, chưa có chuyên gia |
| RQ3 | Báo nhầm cao: 35% ca hợp lệ ở luật cố định, 62% ở judge; 6/8 cờ trên hợp đồng nền là báo nhầm, có lỗi áp sai luật và khuyến nghị trái luật. | Trung bình: một model, một lần chạy |
| RQ4 | Đổi sang vector-only không làm xấu v04. Xử lý phủ định không cải thiện. | Thấp đến trung bình (n nhỏ) |

**Điểm chính:** hệ thống **nhạy nhưng thiếu đặc hiệu**. Hai thành phần bổ sung cho nhau (luật cố định chính xác theo mẫu, LLM bắt được cách diễn đạt khác), nhưng judge LLM báo nhầm nhiều và có thể đưa ra nhận định sai luật. Do đó đầu ra của hệ thống chỉ nên được dùng như **danh sách điểm cần người kiểm tra**, không phải kết luận pháp lý.

**Đóng góp của chương:**
1. Một quy trình đánh giá có kiểm soát cho hệ thống rà soát hợp đồng tiếng Việt khi không có chuyên gia: benchmark ngoài cho truy xuất, bơm lỗi có nhãn do cấu tạo cho phát hiện rủi ro, đóng băng và chạy test một lần.
2. Bằng chứng định lượng rằng cơ chế lai RRF ban đầu làm giảm chất lượng truy xuất, và quyết định thiết kế dựa trên quy tắc khai báo trước.
3. Phân tích báo nhầm của LLM judge trên hợp đồng tiếng Việt, kèm ví dụ lỗi áp dụng luật cụ thể.

## 5.10. Mối đe doạ đến tính hợp lệ

- **Nhãn chưa có chuyên gia:** ca bơm lỗi và phân loại cờ trên hợp đồng nền do tác giả thực hiện (có mô hình hỗ trợ viết ca). Một số ca hợp lệ phụ thuộc cách diễn giải luật.
- **Tính đại diện:** ca bơm lỗi chỉ có một Điều sai mỗi hợp đồng, một hợp đồng nền, văn bản thuần (không qua bước đọc DOCX). Kết quả không cho biết tỷ lệ đúng trên hợp đồng thực tế.
- **Cỡ mẫu:** 48 ca pipeline (6 ca mỗi luật), 32 ca injection_v2; chỉ số theo từng luật rất thô.
- **Một model, một lần chạy:** judge Groq `gpt-oss-120b`, nhiệt độ 0, chưa đo độ lặp lại; kết quả không so sánh được với Gemini.
- **Benchmark truy xuất:** chỉ 20,8% câu test có điều gold còn hiệu lực trong kho; tập con này nghiêng về văn bản còn hiệu lực. Nguồn dữ liệu chưa xác định được giấy phép. Chia dev/test riêng của đề tài, nên không so trực tiếp với kết quả công bố dùng split gốc.
- **Quy trình:** lần chạy test của `hybrid + V3` thực hiện sau khi đã thấy kết quả test của ba cấu hình còn lại, do lỗi khoá test (khoá đặt theo mode, chặn nhầm V3). Thay đổi giữa hai commit chỉ ở tên file khoá, không đụng logic truy xuất; ghi trong nhật ký.
- **Mã chưa commit lúc chạy pipeline 48 ca:** phần tích hợp judge Groq được viết và chạy trước khi commit; kết quả ghi commit `ed30fdd`, mã Groq chỉ có trong commit `f23ba86` (cùng commit chứa kết quả). Vì vậy lần chạy này không gắn với một commit sạch.
- **Hợp đồng nền chưa sạch hoàn toàn** (thiếu thông tin Điều 21), ảnh hưởng đến cách đọc số cờ ở Điều khác.

## 5.11. Hướng phát triển

1. Nhờ chuyên gia pháp lý kiểm nhãn bộ 80 ca và các cờ trên hợp đồng nền; mở rộng sang hợp đồng thực tế đã ẩn danh.
2. Giảm báo nhầm của judge: buộc judge trích đúng đoạn vi phạm và điều luật hỗ trợ, đối chiếu tự động trích dẫn với văn bản trong kho, hạ mức các cảnh báo "thiếu nội dung" khi hợp đồng đã dẫn chiếu luật. Đánh giá trên bộ ca mới.
3. Sửa cờ hiệu lực ở mức điều cho văn bản hết hiệu lực một phần (660 câu benchmark bị ảnh hưởng).
4. Đo độ lặp lại của judge (nhiều lần chạy) và so sánh nhiều model.
5. Xử lý phủ định theo cú pháp thay vì cửa sổ ký tự.

## Phụ lục 5.A. Truy vết kết quả

**Bảng 5.9. Commit, tag và file kết quả**

| Thí nghiệm | Đóng băng | Commit chạy | File kết quả |
|---|---|---|---|
| Truy xuất: split | tag `legalqa-split-frozen` | — | `evaluation_results/legal_qa/split.json` |
| Truy xuất: dev | — | `551e9e2` | `legal_qa/DEV_BIEN_THE.md` |
| Truy xuất: test | khoá `legal_qa/test_locks/` | `ae9e230`, `78d4437` (V3) | `legal_qa/TEST_KET_QUA.md`, tag `legalqa-test-done` |
| Chọn cấu hình (v04) | quy tắc trong `docs/NHAT_KY_THAY_DOI.md` | `087256a`; đổi mặc định `7148b39` | `evaluation_results/reports/RAG_V04_HYBRID_VS_VECTOR.md` |
| Bơm lỗi 80 ca | tag `injection-frozen` (`e268fcb`) | rule-only `ed30fdd`; pipeline: mã tại `ed30fdd` cộng phần judge Groq chưa commit lúc chạy, kết quả commit ở `f23ba86` | `injection/REPORT_rule_only.md`, `injection/REPORT_full.md`, `injection/BAO_CAO.md` |
| Hợp đồng nền | — | chạy ở `f23ba86`, kết quả commit ở `84c8d5e` | `injection/BASE_CONTRACT_FLAGS.md` |
| Phủ định | tag `injection-v2-frozen` (`fab1cef`) | cũ `fab1cef`, mới `04f1e6c`; đưa vào cờ, tắt mặc định `6ba982d` | `injection_v2/BAO_CAO.md` |
