# Kết quả vòng v3: cải tiến có nghiên cứu, truy xuất thật và chấm thật

Ngày 18/11/2026. Điểm là số đo tự động trên các nhóm dữ liệu tổng hợp dưới đây; không thay nhãn hoặc rubric để tăng điểm.

**Kết quả trước/sau**

Baseline là **v2 đã có nội dung Điều hợp đồng**; candidate là code mới với truy xuất chính xác theo chủ đề, tinh lọc căn cứ và prompt QA mới. Không dùng baseline yếu chỉ tìm từ câu hỏi để làm mức tăng trông lớn hơn.

| Nhóm | QA / cấu hình | Correctness trước → sau | Đúng đủ trước → sau | Kết luận đúng trước → sau | Nguồn Điều đúng trước → sau |
|---|---:|---:|---:|---:|---:|
| Dev đã phân tích | 32/32; 32/32 | 76.6% → **100.0%** | 71.9% → **100.0%** | 78.1% → **100.0%** | 40.6% → **100.0%** |
| Regression từ test v1 | 32/32; 32/32 | 81.2% → **84.4%** | 78.1% → **84.4%** | 87.5% → **84.4%** | 28.1% → **96.9%** |
| Ca mới đối chiếu nguồn | 8/8; 8/8 | 100.0% → **81.2%** | 100.0% → **75.0%** | 100.0% → **87.5%** | 75.0% → **100.0%** |

Correctness là điểm trung bình 0–2 chuẩn hóa 0–1; đúng đủ là tỷ lệ câu đạt 2/2. Không coi hai đại lượng này là cùng một tỷ lệ chính xác.

**Đã chạy những gì?**

- 80 câu dev từ 16 ca gốc: T1/T2/T3, hỏi lại và đổi số Điều. Retrieval chấm 72 câu có gold luật; QA chấm trước 32 câu T1/đổi số mỗi cấu hình.
- 32 ca regression chọn cân bằng, có seed, từ test v1: tám nhóm × hai nguồn × một vi phạm/một hợp lệ. Không trùng ca gốc dev. Đã dùng trong v1 nên không gọi là test hoàn toàn mới giữ kín.
- Tám ca mới về giới hạn thử việc, lương thử việc và nghỉ hằng năm: bốn vi phạm/bốn hợp lệ, viết trước khi chạy từ nguồn Chính phủ. Do tác giả code soạn và chưa có chuyên gia duyệt nên không phải benchmark độc lập.
- Cùng GPT-OSS-120b sinh, cùng Qwen judge, cùng embedding BGE-M3, cùng kho luật và cùng rubric. Baseline và candidate chạy xen kẽ trên cùng đầu vào. Cả nhãn lẫn cách chấm được giữ nguyên trong vòng này.
- Đáp án gold đọc ở bước chấm; lúc inference chỉ có câu hỏi, hợp đồng và ngữ cảnh lấy qua repository. Không có nhãn/gold Điều luật trong prompt hệ thống.

**Truy xuất, mức hỗ trợ bởi nguồn và chi phí**

| Nhóm | R@5 luật trước → sau | n có gold luật | Faithfulness trước → sau | n faithfulness trước/sau |
|---|---:|---:|---:|---:|
| Dev đã phân tích | 34.7% → **84.7%** | 72; 72 | 76.6% → 100.0% | 31; 32 |
| Regression từ test v1 | 55.2% → **93.8%** | 32; 32 | 84.9% → 89.2% | 31; 31 |
| Ca mới đối chiếu nguồn | 100.0% → **100.0%** | 8; 8 | 100.0% → 83.3% | 8; 8 |

Faithfulness chỉ chấm câu có mệnh đề; câu hỏi ngược hoặc không có mệnh đề được báo bằng mẫu số riêng, không âm thầm coi là đúng. Correctness vẫn tính đủ các câu được judge chấm.

Usage API: 149 lượt gọi sinh, 556,651 token; 144 lượt judge, 336,615 token. Không quy đổi thành tiền khi chưa có hóa đơn/bảng giá tài khoản.

**So sánh theo cặp và các ca còn sai**

**Dev đã phân tích**

- 9 câu tăng điểm, 0 câu giảm, 23 câu không đổi.
- CI95 chênh correctness: [+6.2; +42.2] điểm %; CI95 chênh R@5: [+37.9; +62.0] điểm %.
- Bootstrap 1.000 lần theo ca gốc, giữ các câu cùng ca đi cùng nhau. Dev còn phụ thuộc do nền hợp đồng chung; mẫu mới chỉ có tám ca.

| Gold | Kết luận máy qua judge | Trước | Sau |
|---|---|---:|---:|
| violation | violation | 10 | 16 |
| violation | compliant | 3 | 0 |
| violation | unclear | 3 | 0 |
| compliant | violation | 1 | 0 |
| compliant | compliant | 15 | 16 |
| compliant | unclear | 0 | 0 |

Candidate còn 0 câu chưa đạt trọn điểm:

- Không có câu dưới 2/2 theo judge trong nhóm này; mẫu nhỏ và judge chưa được chuyên gia kiểm, không suy ra ứng dụng đúng 100%.

**Regression từ test v1**

- 4 câu tăng điểm, 2 câu giảm, 26 câu không đổi.
- CI95 chênh correctness: [-9.4; +15.6] điểm %; CI95 chênh R@5: [+27.6; +50.0] điểm %.
- Bootstrap 1.000 lần theo ca gốc, giữ các câu cùng ca đi cùng nhau. Dev còn phụ thuộc do nền hợp đồng chung; mẫu mới chỉ có tám ca.

| Gold | Kết luận máy qua judge | Trước | Sau |
|---|---|---:|---:|
| violation | violation | 14 | 15 |
| violation | compliant | 0 | 0 |
| violation | unclear | 2 | 1 |
| compliant | violation | 1 | 3 |
| compliant | compliant | 14 | 12 |
| compliant | unclear | 1 | 1 |

Candidate còn 5 câu chưa đạt trọn điểm:

- `REG-006` / `LU-06-T1`: 0/2 — Câu trả lời là một câu hỏi ngược lại thay vì đưa ra kết luận về tính hợp pháp của Điều 8, do đó không trả lời được câu hỏi đặt ra.
- `REG-008` / `BH-09-T1`: 0/2 — Kết luận sai so với nhãn tham chiếu (compliant). Câu trả lời cho rằng việc không đóng BHXH/BHYT khi nghỉ không hưởng lương từ 14 ngày trở lên là vi phạm Điều 168 BLĐ, nhưng ngữ cảnh pháp luật cung cấp (Điều 168 khoản 3) lại quy định người sử dụng lao động chỉ có trách nhiệm chi trả khoản tiền tương đương mức đóng cho NLĐ không thuộc đối tượng tham gia BHXH bắt buộc, không bắt buộc phải đóng trực tiếp vào quỹ trong trường hợp này (hoặc ít nhất là không có căn cứ trong ngữ cảnh để khẳng định đây là vi phạm rõ ràng như câu trả lời đã nêu). Ngoài ra, việc trích dẫn Nghị định 74/2025/QH15 là sai số hiệu văn bản (QH15 là Quốc hội, không phải Nghị định), tuy nhiên phần kết luận về BHTN là đúng. Do kết luận tổng thể trái với nhãn tham chiếu và lập luận về BHXH/BHYT thiếu căn cứ phù hợp trong ngữ cảnh, điểm correctness là 0.
- `REG-017` / `TC2-V2-T1`: 0/2 — Câu trả lời kết luận 'không thể khẳng định là vi phạm' (unclear) trong khi đáp án chuẩn là 'violation'. Điều 10 cấm NLĐ khởi kiện ra Tòa án, trái với Điều 187 BLĐ 2019 (Tòa án là cơ quan có thẩm quyền) và nguyên tắc bảo đảm quyền tiếp cận công lý. Việc từ chối kết luận vi phạm là sai.
- `REG-028` / `GT2-C1-T1`: 0/2 — Câu trả lời kết luận sai. Điều 17 khoản 1 Bộ luật Lao động cấm người sử dụng lao động giữ bản chính giấy tờ, do đó việc công ty không giữ bản gốc (chỉ lưu bản sao) là tuân thủ pháp luật (compliant), không phải vi phạm.
- `REG-032` / `DT2-C1-T1`: 0/2 — Kết luận sai. Điều 6 chỉ miễn trừ trách nhiệm bồi hoàn cho đào tạo nội bộ, trong khi Điều 40 và 62 BLĐ 2019 áp dụng cho chi phí đào tạo nghề (thường là đào tạo nâng cao/kỹ năng có hợp đồng đào tạo riêng). Việc miễn trừ cho đào tạo nội bộ không trái quy định bắt buộc của Điều 40/62 vì các điều này không cấm thỏa thuận miễn trừ cho các loại đào tạo không thuộc phạm vi Điều 62 hoặc khi không có chi phí thực tế theo chứng từ. Reference label là compliant.

**Ca mới đối chiếu nguồn**

- 0 câu tăng điểm, 2 câu giảm, 6 câu không đổi.
- CI95 chênh correctness: [-43.8; +0.0] điểm %; CI95 chênh R@5: [+0.0; +0.0] điểm %.
- Bootstrap 1.000 lần theo ca gốc, giữ các câu cùng ca đi cùng nhau. Dev còn phụ thuộc do nền hợp đồng chung; mẫu mới chỉ có tám ca.

| Gold | Kết luận máy qua judge | Trước | Sau |
|---|---|---:|---:|
| violation | violation | 4 | 4 |
| violation | compliant | 0 | 0 |
| violation | unclear | 0 | 0 |
| compliant | violation | 0 | 1 |
| compliant | compliant | 4 | 3 |
| compliant | unclear | 0 | 0 |

Candidate còn 2 câu chưa đạt trọn điểm:

- `NEW-03` / `NEW-03`: 1/2 — Kết luận đúng và căn cứ chính (Điều 26 BLĐ 2019 về lương thử việc) chính xác. Tuy nhiên, câu trả lời đưa ra căn cứ phụ thuộc vào Nghị định 27/2014 (đã hết hiệu lực hoặc không còn áp dụng chung cho trường hợp này theo BLĐ 2019) và tự mâu thuẫn khi vừa nói có khả năng vi phạm thời gian thử việc theo NĐ 27/2014, vừa nói không vi phạm theo Điều 25 BLĐ. Việc viện dẫn văn bản pháp luật không còn hiệu lực hoặc không phù hợp làm giảm độ chính xác của lập luận.
- `NEW-08` / `NEW-08`: 0/2 — Kết luận sai so với nhãn tham chiếu (compliant). Hợp đồng chỉ quy định mức nghỉ 14 ngày cho đối tượng nặng nhọc/độc hại, đây là quyền tối thiểu và không trái luật. Việc không nêu chi tiết các khoản khác của Điều 113 (như nghỉ theo tỷ lệ, lịch nghỉ) không làm cho điều khoản này trở nên trái pháp luật, vì các quy định đó là nghĩa vụ chung của người sử dụng lao động hoặc áp dụng cho các trường hợp khác không nhất thiết phải ghi trong điều khoản này.

**Code và kiến thức đã thay đổi**

1. Làm truy vấn bất biến với số Điều hợp đồng; vẫn giữ số Điều luật đích danh và các con số có ý nghĩa.
2. Chỉ mục chủ đề lao động truy xuất chính xác Điều từ corpus. Nó cung cấp bằng chứng cho cả câu hợp lệ lẫn vi phạm, không có nhãn hay case id benchmark trong code ứng dụng.
3. Ghép đầy đủ các Khoản/Điểm theo thứ tự, loại trùng và phần tràn sang Điều tiếp theo; ưu tiên căn cứ trực tiếp trước kết quả vector bổ sung.
4. Ngừng chèn các đoạn luật cố định lệch chủ đề khi đã có nguồn chính xác. Prompt kiểm chủ thể, hành vi, điều kiện, phủ định/ngoại lệ; không coi thiếu luật là dữ kiện cần người dùng cung cấp.
5. Tách số Điều hợp đồng trong `cited_clauses` khỏi số Điều luật trong phần giải thích. Xác minh nguồn thực, không tự điền nguồn để ăn điểm.

Tham khảo ý tưởng sửa chất lượng truy xuất của [CRAG](https://arxiv.org/abs/2401.15884), phân biệt đúng nội dung với chất lượng viện dẫn của [ALCE](https://aclanthology.org/2023.emnlp-main.398/), và đọc [Self-RAG](https://arxiv.org/abs/2310.11511). Không huấn luyện hay tuyên bố đã tái lập trọn các mô hình trong paper.

Nguồn luật kiểm đối chiếu: [Bộ luật Lao động trên Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=198540&lang=vi&pageid=27160), [văn bản hợp nhất 125/VBHN-VPQH](https://vanban.chinhphu.vn/?docid=215248&pageid=27160). Đã dùng web và MCP Search để tìm nguồn chính thức; không có MCP chuyên luật VN được kết nối, và VBPL trả 403 nên không tuyên bố đọc được trang bị chặn.

**Phần chưa được chứng minh và việc tiếp theo**

Điểm cao ở đây chứng minh kết quả trên đúng các nhóm đã đo. Chưa đo toàn test QA v1 314 câu bằng candidate, chưa đo toàn workflow phân tích, hội thoại nhiều lượt hoặc hợp đồng thực tế. QA mới chủ yếu được đo bằng câu hỏi T1; T2/T3 chỉ có số retrieval ở dev. Không sử dụng điểm tốt của T1 để tuyên bố mọi chức năng đạt cùng mức.

Nhãn mới đã đối chiếu nguồn chính thức nhưng vẫn do cùng tác giả code xây. Judge tự động có thể sai nội dung pháp lý. Để bảo vệ đồ án, nên trình bày kết quả kèm mẫu số/nguồn và các lỗi còn lại; chọn một mẫu đầu ra thật cho người có chuyên môn xem trước khi khẳng định legal correctness ngoài bộ dữ liệu.

**Tái lập và bằng chứng**

- Phương pháp và tài liệu: `evaluation/contract_eval_v2/RESEARCH_NOTES.md`.
- Protocol, baseline snapshot, hash code/data: `artifacts/research_evidence_v3/protocol.json` và `reference_code/`.
- Mỗi nhóm có `inputs.jsonl`, `gold.jsonl`, `manifest.json`, `retrieval.jsonl`, `qa.jsonl`, `judge.jsonl`, `metrics.json`, `human_review.csv` và các bảng điểm từng ca.
- Bộ v1 và output các vòng trước giữ nguyên; không xóa test.lock hoặc sửa gold/rubric sau khi xem kết quả.
