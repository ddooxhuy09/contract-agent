# QA Benchmark Coverage

## Dataset

- Số mẫu: **3298**
- Số văn bản nguồn: **724**
- Câu hỏi xuất hiện từ hai lần trở lên: **93**
- QID xuất hiện từ hai lần trở lên: **93**
- Mẫu có context tham chiếu: **3298**

## Corpus Coverage

- Metadata văn bản tìm thấy trong local corpus: **1**
- Mẫu có văn bản local tương ứng: **0**
- Văn bản nguồn còn thiếu: **724**

`missing_from_local_corpus` chỉ phản ánh các file corpus trong repository. Nếu database đang chạy có dump riêng, cần chạy kiểm tra bổ sung trên database.

## Missing By Type

- Thông tư: **378**
- Nghị định: **245**
- Văn bản Quốc hội: **52**
- Khác: **33**
- Thông tư liên tịch: **16**

## Top Source Documents By Question Count

- `100/2019/NĐ-CP`: 413 mẫu
- `91/2015/QH13`: 65 mẫu
- `41/2019/QH14`: 50 mẫu
- `155/2020/NĐ-CP`: 46 mẫu
- `15/2020/NĐ-CP`: 45 mẫu
- `35/2019/NĐ-CP`: 45 mẫu
- `82/2020/NĐ-CP`: 33 mẫu
- `43/2019/QH14`: 30 mẫu
- `63/2019/NĐ-CP`: 28 mẫu
- `06/2021/NĐ-CP`: 28 mẫu

## Project-Critical Gaps

- `45/2019/QH14` - Bộ luật Lao động: bắt buộc bổ sung cho `labor_code_resolver`, red flags và QA hợp đồng lao động.
- `91/2015/QH13` - Bộ luật Dân sự: xuất hiện trong hợp đồng mẫu và dataset nhưng chưa có local corpus.
- Nhóm văn bản về BHXH, BHYT, BHTN: cần crawl và xác định văn bản hiện hành theo ngày phân tích trước khi dùng làm căn cứ.
- Các nghị định/thông tư xử phạt và hướng dẫn chuyên ngành: chỉ ingest khi có nhu cầu nghiệp vụ tương ứng; không dùng làm căn cứ chung cho mọi hợp đồng.
