# ContractLens: bộ test đã được làm rõ và kết quả cải tiến có đối chứng

Ngày: 18/11/2026. Đây là thí nghiệm **dev sau v1**, không phải điểm test giữ kín mới.

![So sánh trước/sau trên dev](D:/contract-agent/docs/bo_test_hoi_dong/QA_DEV_TRUOC_SAU.png)

**Kết luận và số liệu chính**

Đã sửa QA để lấy đúng Điều hợp đồng được hỏi rồi dùng nội dung Điều đó để tìm luật. Trên cùng tập dev, R@5 luật tăng từ **4.2% lên 34.7%** (72 câu có căn cứ gold; 16 ca gốc). CI95 của chênh lệch, lấy mẫu theo ca gốc: [+17.6; +45.7] điểm %.

QA tăng điểm theo judge và CI95 chênh lệch trên 0 trong tập dev này; còn cần người kiểm và test độc lập.

| Chỉ số | Trước sửa | Sau sửa | Mẫu số/ý nghĩa |
|---|---:|---:|---|
| Retrieval luật R@5 | 4.2% | 34.7% | 72 câu có gold luật; 16 ca gốc |
| R@5 riêng câu T1 | 0.0% | 43.8% | 16 câu chỉ nêu số Điều |
| R@5 sau đổi số Điều | 0.0% | 40.6% | 16 câu, cùng nội dung nghĩa vụ |
| QA correctness trung bình | 51.6% | 78.1% | 32/32 và 32/32 câu được judge chấm |
| QA đúng đủ 2/2 | 40.6% | 71.9% | Tỷ lệ đạt trọn điểm, khác correctness trung bình |
| QA kết luận khớp nhãn | 59.4% | 81.2% | Nhãn kế thừa, chưa có người xác nhận |
| QA faithfulness | 53.8% | 82.2% | 31/32 và 30/32 câu có mệnh đề để chấm |
| QA trả đúng nguồn Điều hợp đồng | 28.1% | 56.2% | `source_clauses` chứa Điều gold |

QA theo cặp: **13 câu tốt lên, 2 câu xấu đi, 17 câu không đổi**. CI95 của chênh correctness: [+9.4; +46.9] điểm %.

Số QA là đánh giá tự động bằng LLM judge chưa được người hiệu chuẩn trên đầu ra này. Không dùng các số dev này thay điểm test v1, không suy ra tỷ lệ đúng trên hợp đồng thực tế, không so trực tiếp điểm QA dev này với 0,51 trên toàn test v1.

**1. Đã làm gì khác so với chỉ viết lại báo cáo?**

- Sửa mã chạy thật trong QA; giữ API, prompt sinh, auth, streaming, retry và checkpointer.
- Tạo bộ dev có 80 câu hỏi, đáp án tách riêng, đường dẫn/id trung tính, hash dữ liệu và hợp đồng.
- Thêm đổi cách hỏi và đổi số Điều để kiểm tra hệ thống có phụ thuộc mẫu/vị trí không.
- Chạy ba cấu hình retrieval để phân biệt tác động lấy đúng Điều với tác động đưa nội dung vào truy vấn luật.
- Chạy QA trước/sau trên cùng đầu vào; lưu câu trả lời, nguồn, context thực, token và thời gian.
- Xuất audit chất lượng, kết quả từng ca và bảng kiểm nhãn/đầu ra cho người duyệt.
- Có 17 test tự động mới; toàn bộ test không integration: 372 passed, 1 skipped trong container.

**2. Bộ test đến từ đâu, số nào là hợp đồng, số nào là câu?**

```text
Bộ hợp nhất v1: 154 ca gốc → 378 câu
├─ injection:    80 ca × 3 câu = 240
├─ injection_v2: 32 ca × 3 câu =  96
├─ fixture QA:    8 câu
└─ v04:          34 tình huống giả lập
   Loại 3 ca gốc / 9 câu → 151 ca gốc / 369 câu
   ├─ dev:  23 ca gốc /  55 câu
   └─ test: 128 ca gốc / 314 câu

Thí nghiệm hiện tại: chỉ lấy 16 ca injection trong dev v1
└─ mỗi ca: T1 + T2 + T3 + hỏi lại + đổi số Điều = 5 câu
   → 80 câu / 16 ca gốc / 32 văn bản hợp đồng (16 gốc + 16 đổi số)
```

Các hợp đồng này là tổng hợp, dùng chung nền 11 Điều. Mỗi nhóm có ca vi phạm và ca hợp lệ gần giống. Đáp án được kế thừa từ cách xây ca và kiểm chéo v1; không sinh lại nhãn để khớp kết quả. Các ca có quan hệ với nhau, nên không coi 80 câu hoặc 32 văn bản là những mẫu độc lập hoàn toàn.

Bộ Zalo bên ngoài chỉ dùng để đánh giá truy xuất pháp luật riêng, không được gộp vào 80 câu dev này và không chứng minh QA hợp đồng tốt. Chi tiết nguồn v1 ở báo cáo phân tích đi kèm.

**3. Vì sao phép chấm rõ hơn?**

| Phép đo | Số kỳ vọng | Số hoàn tất | Số được chấm |
|---|---:|---:|---:|
| Retrieval baseline | 80 | 80 | 72 có gold luật |
| Retrieval reference_only | 80 | 80 | 72 có gold luật |
| Retrieval grounded | 80 | 80 | 72 có gold luật |
| QA baseline | 32 | 32 | 32 |
| QA grounded | 32 | 32 | 32 |

Tám câu T3 trên ca hợp lệ không có gold luật/Điều cần tìm nên không chấm recall luật. Chúng vẫn nằm trong bộ và trong số hoàn tất, không bị loại vì hệ thống trả lời khó. QA chọn trước 32 câu T1 gốc/đổi số; không lấy các câu trả lời đẹp để chọn mẫu sau khi chạy.

R@5 đo mức bao phủ căn cứ gold trong năm kết quả, không phải độ chính xác câu trả lời. Correctness là điểm trung bình 0–2 chuẩn hóa; tỷ lệ đúng đủ là số câu đạt 2/2. Faithfulness là mức context hỗ trợ các mệnh đề, không tự xác minh luật đúng. Câu chỉ hỏi ngược không có mệnh đề được bỏ khỏi trung bình faithfulness, nên bảng ghi riêng 31/32 và 30/32; correctness vẫn chấm đủ 32 câu mỗi bên. Khoảng tin cậy lấy mẫu theo 16 ca gốc; vẫn chưa xử lý hết phụ thuộc do dùng chung hợp đồng nền.

**4. Đối chứng cho thấy chính xác điều gì?**

| Cấu hình | Cách lấy Điều | Truy vấn luật | R@5 |
|---|---|---|---:|
| baseline | Vector như cũ | Câu hỏi | 4.2% |
| reference_only | Ưu tiên đúng số Điều được hỏi | Vẫn chỉ câu hỏi | 4.2% |
| grounded | Ưu tiên đúng số Điều được hỏi | Câu hỏi + nội dung Điều | 34.7% |

Lấy đúng Điều nhưng không đưa nội dung đó vào tìm luật chưa cải thiện recall luật. Sự tăng điểm nằm ở cấu hình có nội dung Điều. Đây là bằng chứng cho việc thiếu thông tin truy vấn, không phải bằng chứng chỉ cần đổi vector sang hybrid hoặc tăng số kết quả là đủ.

| Kiểu câu hỏi | n chấm luật | Trước | Sau |
|---|---:|---:|---:|
| T1 | 16 | 0.0% | 43.8% |
| T2 | 16 | 12.5% | 12.5% |
| T3 | 8 | 12.5% | 12.5% |
| paraphrase | 16 | 0.0% | 53.1% |
| renumbered | 16 | 0.0% | 40.6% |

T2 và T3 giữ nguyên truy vấn theo thiết kế nên chưa được cải thiện bởi thay đổi này. Điểm giữa T1 và đổi số Điều chưa hoàn toàn bằng nhau: truy vấn vẫn chứa các số/diễn đạt có thể ảnh hưởng embedding. Chưa thể tuyên bố hệ thống bất biến với việc đánh số.

**5. Báo nhầm và giới hạn của đầu ra**

- Trước: báo vi phạm trên ca gold hợp lệ 2/16 câu. Các câu gốc/đổi số dùng cùng ca, không phải những hợp đồng hợp lệ độc lập.
- Sau: báo vi phạm trên ca gold hợp lệ 0/16 câu. Các câu gốc/đổi số dùng cùng ca, không phải những hợp đồng hợp lệ độc lập.

| Nhãn gold QA | Kết luận của máy (qua judge) | Trước | Sau |
|---|---|---:|---:|
| Vi phạm | Vi phạm | 7 | 10 |
| Vi phạm | Hợp lệ | 2 | 3 |
| Vi phạm | Chưa kết luận / hỏi lại | 7 | 3 |
| Hợp lệ | Vi phạm | 2 | 0 |
| Hợp lệ | Hợp lệ | 12 | 16 |
| Hợp lệ | Chưa kết luận / hỏi lại | 2 | 0 |

Trên 16 câu gold vi phạm, bản sau vẫn có 3 câu kết luận hợp lệ và 3 câu chưa kết luận. Số câu vi phạm bị kết luận hợp lệ tăng từ 2 lên 3, dù tổng điểm tăng. Đây là lỗi phải xử lý, không che bằng điểm trung bình. Không dùng 0/16 báo nhầm QA để thay tỷ lệ báo nhầm 20/49 của bước phát hiện rủi ro v1: hai phép đo khác nhau.

Truy xuất tốt hơn chưa bảo đảm kết luận tốt hơn. Cần đọc các ca xấu đi, kiểm nhãn còn tranh cãi và xem LLM có thực sự áp dụng đúng điều kiện/ngoại lệ. Không sửa nhãn theo câu trả lời của model.

**6. Ví dụ trước/sau để tự kiểm tra**

**DEV-002-1 — nguồn BH-07-T1; điểm 0/2 → 2/2**

Câu hỏi: Điều 4 của hợp đồng có trái quy định pháp luật lao động không? Nhãn kế thừa: `compliant`.

- Trước: Kết luận: Điều 4 của hợp đồng trái quy định pháp luật lao động. Căn cứ: - BLLĐ Điều 168 khoản 1: Người sử dụng lao động, người lao động phải tham gia bảo hiểm xã hội bắt buộc; không thể thỏa thuận loại trừ. - Điều 4.1 hợp đồng cho rằng người lao động không phải tham gia bảo hiểm xã hội bắt buộc vì đang hưởng lương hưu và công ty không đóng bảo hiểm, điều này vi phạm quy định bắt buộc tham gia bảo hiểm xã hội. Khuyến nghị: Điều chỉnh hợp đồng, yêu cầu công ty thực hiện đóng bảo hiểm xã hội bắt buộc cho người lao động dù đang hưởng lương hưu, hoặc tham khảo các ngoại lệ pháp luật (nếu có) để xác định đúng đối tượng.…
- Sau: Kết luận: Điều 4 của hợp đồng không trái quy định pháp luật lao động. Căn cứ: - BLLĐ Điều 168 khoản 1: Người sử dụng lao động, người lao động phải tham gia bảo hiểm xã hội bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp; không thể thỏa thuận loại trừ. - Bộ luật Lao động (45/2019/QH14) Điều 168 khoản 3: Đối với người lao động không thuộc đối tượng tham gia bảo hiểm xã hội bắt buộc, người sử dụng lao động có trách nhiệm chi trả thêm cùng lúc với kỳ trả lương một khoản tiền tương đương mức người sử dụng lao động đóng bảo hiểm xã hội bắt buộc. - Điều 4 hợp đồng đã ghi rõ người lao động không thuộc đối tượng tham gia bảo hiểm xã hội bắt buộc và công…

Đây là trích đoạn minh họa theo điểm judge; mở trace và `human_review.csv` để kiểm đầy đủ.

**DEV-002-5 — nguồn BH-07-T1; điểm 0/2 → 2/2**

Câu hỏi: Điều 34 của hợp đồng có trái quy định pháp luật lao động không? Nhãn kế thừa: `compliant`.

- Trước: Kết luận: Điều 34 của hợp đồng trái quy định pháp luật lao động. Căn cứ: - BLLĐ Điều 168 khoản 1: Người sử dụng lao động và người lao động phải tham gia bảo hiểm xã hội bắt buộc; không được thỏa thuận loại trừ. - Điều 34 hợp đồng quy định công ty không tham gia đóng bảo hiểm xã hội bắt buộc cho người lao động đang hưởng lương hưu và chỉ trả một khoản tiền tương đương, điều này vi phạm yêu cầu bắt buộc tham gia bảo hiểm xã hội. Khuyến nghị: Điều chỉnh Điều 34 để đảm bảo người lao động và công ty tham gia đầy đủ bảo hiểm xã hội bắt buộc theo quy định của Bộ luật Lao động, hoặc kiểm tra xem có quy định ngoại lệ nào áp dụng cho người đang hưởng l…
- Sau: Kết luận: Điều 34 của hợp đồng không trái quy định pháp luật lao động. Căn cứ: - BLLĐ · Điều 168 khoản 1: Người sử dụng lao động, người lao động phải tham gia bảo hiểm xã hội bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp; không thể thỏa thuận loại trừ. - 45/2019/QH14 Điều 168 khoản 3: Đối với người lao động không thuộc đối tượng tham gia bảo hiểm xã hội bắt buộc, người sử dụng lao động có trách nhiệm chi trả thêm cùng lúc với kỳ trả lương một khoản tiền cho người lao động tương đương với mức người sử dụng lao động đóng bảo hiểm xã hội bắt buộc. - Điều 34 hợp đồng: 34.1 xác nhận người lao động không thuộc đối tượng bắt buộc và công ty không th…

Đây là trích đoạn minh họa theo điểm judge; mở trace và `human_review.csv` để kiểm đầy đủ.

**DEV-010-1 — nguồn LU-10-T1; điểm 2/2 → 1/2**

Câu hỏi: Điều 8 của hợp đồng có trái quy định pháp luật lao động không? Nhãn kế thừa: `compliant`.

- Trước: Kết luận: Điều 8 của hợp đồng không trái quy định của Bộ luật Lao động. Căn cứ: - Điều 8 hợp đồng quy định người lao động nếu không báo trước vẫn được trả lương cho những ngày đã làm và phải bồi thường theo quy định của pháp luật. - Bộ luật Lao động cho phép người sử dụng lao động yêu cầu người lao động bồi thường khi người lao động đơn phương chấm dứt hợp đồng mà không thông báo trước (theo các quy định về thời hạn báo trước và bồi thường trong Điều 35‑37 của BLLĐ). Điều 39 của Bộ luật Lao động quy định việc chấm dứt đơn phương trái pháp luật chỉ áp dụng khi không tuân thủ các quy định này, không cấm việc yêu cầu bồi thường. - Vì Điều 8 chỉ …
- Sau: Kết luận: Điều 8 của hợp đồng không trái quy định của Bộ luật Lao động. Căn cứ: - Điều 35 Bộ luật Lao động 45/2019/QH14 quy định người lao động có quyền đơn phương chấm dứt hợp đồng nhưng phải báo trước; nếu không báo trước, người lao động phải bồi thường cho người sử dụng lao động và người sử dụng lao động vẫn phải trả lương cho những ngày đã làm việc. Điều 8 của hợp đồng phản ánh đúng nội dung này, chỉ ra việc trả lương cho ngày làm việc và bồi thường theo quy định pháp luật. - Điều 137 khoản 3 BLLĐ cấm chấm dứt vì lý do mang thai, nuôi con dưới 12 tháng; Điều 8 không đề cập đến các trường hợp này, nên không vi phạm. Khuyến nghị: Khi thực h…

Đây là trích đoạn minh họa theo điểm judge; mở trace và `human_review.csv` để kiểm đầy đủ.

**DEV-013-1 — nguồn TC-04-T1; điểm 1/2 → 0/2**

Câu hỏi: Điều 10 của hợp đồng có trái quy định pháp luật lao động không? Nhãn kế thừa: `violation`.

- Trước: Kết luận: Điều 10 của hợp đồng có khả năng trái quy định pháp luật lao động vì quy định người lao động từ bỏ quyền khởi kiện sau 30 ngày không được quy định trong Bộ luật Lao động và các văn bản hướng dẫn; luật không cho phép các điều khoản hợp đồng hạn chế quyền khiếu nại của người lao động. Cần rà soát toàn văn Bộ luật Lao động và các nghị định liên quan để xác nhận definitively.…
- Sau: Bạn có văn bản nào quy định thời hạn khởi kiện hoặc khiếu nại của người lao động theo luật lao động không?…

Đây là trích đoạn minh họa theo điểm judge; mở trace và `human_review.csv` để kiểm đầy đủ.

**7. Những điều còn thiếu để báo cáo thuyết phục ở mức đồ án**

| Điều kiện | Bằng chứng hiện tại | Việc còn cần |
|---|---|---|
| Dữ liệu v1 còn nguyên | 6/6 hash khớp | Giữ nguyên v1 và test.lock |
| Nhãn do người kiểm | 0/112 ô duyệt được điền | Người có chuyên môn xem nhãn và căn cứ |
| Gold set 30 Điều | Hai người gán và chuyên gia đều chưa điền nhãn | Gán độc lập; không dùng nhãn AI thay người |
| Test mới giữ kín | Chưa có trong thí nghiệm này | Thu thập đa nền/nguồn, gán nhãn trước, khóa trước khi chọn cấu hình |
| Workflow phân tích toàn hợp đồng | F1 v1 dùng Điều gold chỉ sẵn | Đo cả tìm Điều, luật cố định, LLM, hợp nhất và cảnh báo trên nền sạch |
| QA nhiều lượt và streaming | Chưa đo trong thí nghiệm dev này | Có tập riêng nếu đưa thành tuyên bố của đồ án |
| Temporal | V1 đang gộp 27 test + 7 dev trong nhóm 34 câu | Báo riêng test; xác minh phiên bản và adapter xuất cạnh |

Một tập dev tốt hơn không tự biến thành benchmark pháp lý đáng tin cậy. Phần không thể tự hoàn tất thay người là xác nhận nhãn độc lập và bổ sung hợp đồng thực tế được phép sử dụng. Đã tạo `LABEL_REVIEW.csv` cho 16 ca nguồn và `human_review.csv` cho đầu ra để công việc này có đầu vào cụ thể.

Về khả năng tái lập: hai cấu hình dùng cùng DB bản sao; snapshot có 137.151 văn bản, 1.004.988 embedding và 660.960 quan hệ văn bản. Đây là snapshot số lượng, không phải hash toàn nội dung corpus. 64/64 truy vấn và danh sách path trong trace QA khớp bước retrieval tương ứng. 64 lượt sinh dùng 227.409 token; 64 lượt judge dùng 137.519 token theo usage API. Độ trễ QA trung vị quan sát khoảng 2,54 → 3,06 giây; có cache và warm-up, chưa phải benchmark hiệu năng độc lập.

**8. Thứ tự cải thiện tiếp theo dựa trên bằng chứng**

1. Kiểm thủ công các ca regression và ca compliant bị báo nhầm trong bảng đầu ra. Chốt lại nhãn có tranh cãi trước khi tối ưu kết luận.
2. Cải thiện áp dụng phủ định/ngoại lệ và phân biệt thiếu dữ kiện với vi phạm; luôn theo dõi recall để tránh đổi báo nhầm lấy bỏ sót.
3. Kiểm soát định danh nguồn: phân biệt Điều hợp đồng với Điều luật; xác minh căn cứ có hỗ trợ kết luận, không chỉ tồn tại trong kho.
4. Thiết kế riêng truy vấn cho câu tổng quát T3; thay đổi hiện tại chưa xử lý loại này.
5. Chốt phương pháp, chuẩn bị holdout mới đa dạng và đánh giá toàn luồng. Dùng v1/dev làm hồi quy, không công bố điểm dev như test độc lập.

**9. File nào nên đọc và dùng để bảo vệ?**

- Báo cáo này: kết luận trước/sau, nguồn, mẫu số, đối chứng và giới hạn.
- `evaluation/contract_eval_v2/QUALITY_AUDIT.json`: bằng chứng kiểm chất lượng v1.
- `evaluation/contract_eval_v2/README.md`: phương pháp, quy tắc, lệnh tái lập.
- `evaluation/contract_eval_v2/artifacts/dev_clause_grounding/metrics.json`: số tổng hợp.
- `per_case_metrics.json`, `paired_qa_changes.json`: điểm từng ca và regression.
- `retrieval.jsonl`, `qa.jsonl`, `judge.jsonl`: nguồn, câu trả lời và lý do chấm thực tế.
- `LABEL_REVIEW.csv`, `human_review.csv`: phần cần người xác minh.

Chưa commit/push. Các hợp đồng dev mới ở DB bản sao dưới user `contract-eval-v2-dev@example.invalid`; không tự xóa. Ruff toàn repo còn F401 đã có ở `evaluation/check_chapter_numbers.py`; các file thay đổi qua kiểm tra F.
