# Rà soát bộ test trước lượt chạy full

Cập nhật: lượt full đã hoàn thành sau bản chuẩn bị này; xem [kết quả full](KET_QUA_FULL_QA_WORKFLOW.md). Các trạng thái “chưa chạy” phía dưới là ghi nhận tại thời điểm chuẩn bị, không phải trạng thái hiện tại.

Ngày 18/11/2026. **Đã hoàn thành rà cấu trúc và nguồn tham chiếu, sửa lỗi mất căn cứ trong bản chuẩn bị mới. Chưa chạy full và chưa có điểm mới.** Đây chưa phải xác nhận đáp án bởi luật sư. Không đổi nhãn theo kết quả model.

## 1. Bộ test đến từ đâu?

| Nguồn | Ca gốc trước loại | Câu trước loại | Câu giữ lại | Đặc điểm |
|---|---:|---:|---:|---|
| injection | 80 | 240 | 234 | Bơm hoặc thay một Điều trên nền HĐLĐ giả lập; 8 nhóm rủi ro |
| injection_v2 | 32 | 96 | 93 | Biến thể phủ định, câu dễ nhầm; cùng nền và nhóm chủ đề |
| contract_qa | 8 | 8 | 8 | Câu hỏi cố định trên cùng hợp đồng demo có nhiều lỗi |
| v04 | 34 | 34 | 34 | Lao động, dân sự, thương mại, tiêu dùng, giao dịch điện tử, hiệu lực/chuyển tiếp |
| Tổng | 154 | 378 | 369 | 151 ca gốc giữ lại; test 314, dev 55 |

Ba dạng câu trên mỗi ca injection: T1 hỏi Điều cụ thể có trái luật; T2 hỏi căn cứ; T3 tìm rủi ro toàn hợp đồng. Sau loại có 109 câu mỗi dạng. Còn lại 28 câu cố định và 14 câu temporal. Vì vậy 369 câu không phải 369 tình huống độc lập. Một hợp đồng có thể được hỏi nhiều lần, nhiều hợp đồng dùng cùng nền.

Đã đọc các bản ghi cases/gold/inputs/verification, đối chiếu khóa và nội dung; đọc đủ 120 tệp hợp đồng được chúng tham chiếu (bao gồm ca bị loại), snapshot 117 hợp đồng còn sử dụng. Chỉ đọc tệp fixture được chỉ đích danh, không quét thư mục dữ liệu hay đọc kết quả chạy cũ. DOCX được trích theo đoạn từ XML để snapshot text; bước này không kiểm OCR hoặc upload.

## 2. Bộ test hiện tốt ở đâu, yếu ở đâu?

**Điểm tốt:** có ca vi phạm và ca chống báo nhầm; câu hỏi được tách khỏi gold; chia nhóm theo ca gốc; có kiểm hash và kiểm chéo LLM; có các câu về thời điểm áp dụng luật. Các ca dễ phủ định rất hữu ích cho sửa generation.

**Các vấn đề thực tế:**

1. **Mất căn cứ khi hợp nhất v04.** Có 20 câu thiếu ít nhất một căn cứ bắt buộc so với `required_provision_ids` và danh mục `legal_provisions` của bộ gốc. Ví dụ TEMP-006 mất cả Điều 52 và 53 Luật GDĐT 2023. Đây là lỗi chuyển đổi dữ liệu, không phải lỗi của hệ thống tìm luật. Trong 34 bản ghi v04 mới, đã chuẩn hóa cả căn cứ, điểm/khoản, id provision và URL nguồn; 20 bản ghi trong đó được khôi phục căn cứ thiếu.
2. **Chấm các nhiệm vụ khác nhau bằng một kết luận nhị phân dễ sai.** T2 chỉ hỏi căn cứ; MIX-006 hỏi nhận diện quan hệ lao động; TEMP hỏi luật theo thời điểm. Không được bắt mọi câu phải trả lời “violation/compliant”.
3. **Gold cho T3 chưa chú thích đầy đủ toàn hợp đồng.** Gold tập trung lỗi bơm. Model tìm thấy rủi ro khác có căn cứ không tự động là báo nhầm; không được dùng gold đó để công bố F1 toàn bộ phát hiện trên mọi Điều.
4. **38 câu low_confidence vẫn cần báo riêng.** Có cả vấn đề hoàn trả đào tạo, phạm vi bảo hiểm và kết luận phụ thuộc dữ kiện. Không xóa các câu này để tăng điểm; vẫn chạy đủ và báo thêm phân tích độ nhạy.
5. **5 cặp gần trùng ở mức đoạn gold (ngưỡng ký tự 0,90), 2 cặp qua dev/test:** TS-06 / TS2-C1 và MIX-014 / MIX-011. Đây là dấu hiệu trùng ngữ nghĩa, không phải bằng chứng hai câu hoàn toàn giống mọi dữ kiện. Giữ split lịch sử, công khai hạn chế; lần này không được gọi test là holdout chưa từng dùng.
6. **Tính độc lập hạn chế:** test từng chạy và có ca đã dùng phân tích v3/v4; v04 tự khai là demo cần duyệt pháp lý; chưa có xác nhận chuyên gia. Điểm LLM judge không tương đương tỷ lệ chính xác pháp lý thực tế.
7. **Thiếu căn cứ trong corpus khác với gold sai.** Ví dụ luật chuyên ngành BHXH và trạng thái phiên bản cần kiểm riêng. Không được tự bật văn bản hết hiệu lực hoặc sửa gold chỉ để model khớp.

## 3. Đã cập nhật những gì?

Bản chuẩn bị: `evaluation/contract_eval_v2/artifacts/full_preflight/`.

- `case_review.csv`: đủ 378 câu, nguồn, ca gốc, split, nhiệm vụ, nhãn cũ, cờ cần xem, trạng thái loại.
- `contract_inventory.json`: 120 nguồn, hash gốc, snapshot và độ dài.
- `inputs.jsonl`: 369 câu với tên snapshot trung tính; không chứa gold/căn cứ/thông tin nhãn.
- `gold.jsonl`: giữ nguyên nhãn cũ, bổ sung nhiệm vụ, required facts và khôi phục căn cứ v04 từ danh mục nguồn.
- `corrections.json`: 34 bản ghi v04 được chuẩn hóa, trong đó 20 ca bổ sung căn cứ thiếu; lưu trước/sau.
- `near_duplicates.json`, `audit_summary.json`, `manifest.json`: cặp gần trùng, thống kê, hash.
- `task_rubric.json`: tiêu chí phân biệt câu hỏi Điều cụ thể, tìm luật, toàn hợp đồng, temporal và câu cố định.

Giữ nguyên 9 câu loại và toàn bộ bộ v1 đóng băng, không ghi đè các kết quả v2–v4. Chưa sửa nhãn mơ hồ khi chưa đủ nguồn và điều kiện. Giữ 314 test / 55 dev để không lẫn cải tiến dữ liệu với thay đổi số lượng câu.

## 4. PDF thật người dùng gửi

Đã đọc trực quan 5 trang: 4 trang nội dung, 1 trang trắng. Không có text layer để trích trực tiếp. Đã phóng to trang 2 và 3 kiểm tra các đoạn dễ đọc nhầm:

- Có phép năm theo tỷ lệ cho người làm dưới 12 tháng; không coi đó là vi phạm.
- Khoản đào tạo ghi **100%** phí và chế độ trong thời gian đào tạo, không phải gấp 10 lần. Cần xét hợp đồng đào tạo, chứng từ và điều kiện; không kết luận mọi hoàn trả đều trái luật.
- 08 giờ/ngày, 48 giờ/tuần không tự chứng minh vi phạm thời giờ bình thường.

Tài liệu có dữ liệu định danh, chữ ký và dấu. Không đưa PDF/ảnh gốc vào payload model. Đã soạn 7 đoạn/biến thể ẩn danh ở `real_contract_excerpt_cases.json`; đánh dấu đoạn từ nguồn, đoạn chuẩn hóa và đoạn cố ý chỉnh sửa. Chúng là nhóm bổ sung riêng, **không gộp vào điểm 314 câu và chưa chạy**. Bản đầy đủ chưa được chứng nhận sạch; text runner không đo OCR của scan này.

Nguồn pháp luật đối chiếu: [BLLĐ hợp nhất 125/VBHN-VPQH](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/9/125-vbhn-vpqh.pdf), [Luật BHXH 41/2024/QH15](https://xaydungchinhsach.chinhphu.vn/toan-van-luat-so-41-2024-qh15-bao-hiem-xa-hoi-119240723163650489.htm). Cần phân biệt ngày ký, ngày đánh giá, luật chuyên ngành và điều chuyển tiếp; không suy hiệu lực từng Điều chỉ từ trạng thái toàn văn bản.

## 5. Phạm vi lượt full đã chuẩn bị

Runner mới: `python -m evaluation.contract_eval_v2.full_run <stage>`.

| Bước | Số lượng | Đo được gì |
|---|---:|---|
| check | 369 câu + nguồn/hash | Offline, không gọi model |
| index | 117 hợp đồng | Chunk/embed/repository thật, DB đánh giá riêng |
| qa | 314 test + 55 dev | Graph QA thật, mỗi câu hội thoại riêng, trace ngữ cảnh cuối |
| workflow | 117 hợp đồng | LangGraph phân tích toàn văn thật, không chọn Điều gold trước |
| judge | 369 đầu ra QA | GPT-OSS sinh, Qwen chấm theo nhiệm vụ, lưu disputed_gold |
| score | Đòi đủ QA/judge/workflow | QA từng split/từng nhiệm vụ; coverage/unchecked toàn workflow |

Runner dừng khi phát sinh lỗi, giữ record lỗi; resume không chọn lại câu theo điểm và không coi bản ghi thất bại là hoàn thành. Chỉ công bố điểm cuối khi đủ đầu ra dự kiến. Không thay provider, model, code hoặc dữ liệu giữa lượt; code khóa khi chạy bắt đầu. Pipeline phân tích tự suy mốc pháp lý từ hợp đồng theo hành vi thật, không giả vờ hỗ trợ historical override khi interface không có.

**Giới hạn cần hiểu trước khi chạy:** runner full đã chuẩn bị về kỹ thuật, nhưng chưa có gold đầy đủ mọi rủi ro ở 117 hợp đồng để công bố F1 toàn workflow. Vì vậy lượt này đo chạy toàn luồng và độ bao phủ; không lấy F1 từ phép đo trên Điều gold trước đây thay cho F1 toàn workflow. Judge mới sửa cách chấm theo nhiệm vụ nên không so trực tiếp điểm này với điểm v1/v4 như một A/B cùng rubric. Mẫu real excerpt chưa nối vào runner full, chỉ là bộ bổ sung chuẩn bị riêng.

Không có cam kết điểm sẽ cao sau khi chạy đủ. Những lỗi còn lại, chi phí, token, độ trễ và các câu bị judge nghi gold đều phải xuất trong báo cáo. 117 workflow có thể tạo nhiều lượt gọi trên mỗi hợp đồng, nên không suy chi phí từ chỉ 369 câu QA; không có giá tiền cố định đáng tin khi chưa có usage thật.

## 6. Kiểm tra và trạng thái bàn giao trước chạy

- Kiểm hash nguồn và snapshot: đạt; 369 id duy nhất; 314 test, 55 dev; gold không vào input.
- 3 test mới kiểm giữ dân số test, sửa ref temporal, text snapshot khớp đủ 120 nguồn: đạt trên host và container Linux.
- Toàn bộ pytest gồm integration hiện có: **386 passed, 1 skipped** trong container, khóa model để trống. Hai test integration hiện có chỉ kiểm health/models, không chứng minh toàn luồng DB/API/upload/SSE.
- Frontend lint và build: đạt. Không ghi đè thay đổi frontend có sẵn của người dùng.
- Ruff F toàn `app scripts evaluation`: đạt sau khi bỏ import `re` không dùng ở `evaluation/check_chapter_numbers.py`. Không đổi thuật toán file đó.
- Chưa commit/push. Chưa gọi model hoặc nạp DB cho lượt full này. Không xóa hợp đồng đánh giá cũ.

**Đây là thông báo trước lượt full theo yêu cầu người dùng. Chưa khởi chạy full.** Những giới hạn về gold chuyên gia, F1 toàn workflow và OCR được ghi rõ để không mô tả “đã sẵn sàng kỹ thuật” thành “đã bảo đảm chính xác pháp lý”.
