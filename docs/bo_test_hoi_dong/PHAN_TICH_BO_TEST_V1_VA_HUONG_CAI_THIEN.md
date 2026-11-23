# Phân tích bộ test ContractLens v1 và hướng cải thiện đồ án

Đây là phân tích mốc v1 **trước lượt cải tiến**. Kết quả sửa QA và đo trước/sau mới hơn nằm ở [báo cáo cải tiến có đối chứng](D:/contract-agent/docs/bo_test_hoi_dong/CAI_THIEN_V2_KET_QUA_VA_BANG_CHUNG.md).

Ngày phân tích: 18/11/2026. Nhánh kiểm tra: `eval/contract-eval-v1`, commit đầu nhánh `bffb38f`.

**Kết luận trước:** Lần chạy đánh giá v1 đã hoàn tất theo phạm vi được ghi trong báo cáo. Công việc tiếp theo là cải thiện hệ thống dựa trên các lỗi đã đo, bổ sung kiểm chứng do người thực hiện và đánh giá toàn luồng. Điểm mạnh hiện tại là phát hiện được nhiều ca vi phạm trong bộ tự xây. Điểm yếu đáng ưu tiên là hỏi đáp tìm luật thiếu ngữ cảnh hợp đồng, báo nhầm điều khoản hợp lệ và viện dẫn chưa đúng căn cứ.

**1. Hiện đang làm tới đâu?**

| Công việc | Trạng thái có bằng chứng | Cách hiểu |
|---|---|---|
| Hợp nhất dữ liệu, tách đầu vào và đáp án | Đã có đủ file | Đã xây được một bộ đánh giá có thể truy vết |
| Kiểm tra nhãn V1–V7 và loại ca tranh cãi/trùng | Đã có báo cáo, kết quả từng ca | Có kiểm tra tự động và LLM kiểm chéo; chưa thay thế chuyên gia |
| Đóng băng dữ liệu | Cả 6 file đều khớp SHA-256 khi kiểm tra lại | Bộ đánh giá hiện tại còn đúng các byte đã đóng băng |
| Đánh giá retrieval | Báo cáo có kết quả vector và hybrid | Đã có mốc so sánh trước khi sửa |
| Đánh giá phát hiện rủi ro | Báo cáo ghi hoàn tất 115/115 ca test | Chạy `evaluate_clause` trên Điều gold đã được chỉ sẵn |
| Đánh giá QA | Báo cáo ghi hoàn tất 314/314 câu test và judge | Đã chạy đường hỏi đáp thật, mỗi câu một hội thoại mới |
| Kiểm chứng toàn bộ workflow phân tích trong v1 | Chưa được phép đo trên thay thế ở trên bao phủ | Chưa thể dùng F1 v1 làm điểm toàn ứng dụng |
| Gán nhãn độc lập bằng người cho gold set 30 Điều | Các cột người gán 1, người gán 2 và chuyên gia đều đang trống | Đây là một phần còn dang dở, tách biệt với lần chạy v1 |
| Sửa các lỗi tìm thấy và chứng minh cải thiện | Chưa có kết quả sau sửa trong tài liệu v1 | Đây là giai đoạn tiếp theo |

Ba commit đánh giá đã có trong lịch sử Git. Phiên này chưa commit hoặc push thêm. Workspace có thay đổi khác ở `frontend/src/api.js` và thư mục kết quả `injection_v3`; báo cáo này không đánh giá tiến độ của chúng.

Phạm vi kiểm tra của phiên này: đọc tài liệu và thống kê trực tiếp dữ liệu trong `evaluation/`; xác nhận hash, cấu trúc chia tập, nhãn và các cột duyệt; chạy lại 11 test của mã đánh giá, đều qua. Các điểm retrieval/generation dưới đây lấy từ `KET_QUA_BO_TEST_V1.md`. Theo quy tắc repo, không mở `data/` hay `evaluation_results/`, nên phiên này không đối chiếu lại từng dự đoán thô, không chạy lại `score check`, không gọi LLM hoặc truy cập DB. Kết quả 355 passed và đối chiếu 358/358 là thông tin của lần chạy trước, không phải kiểm tra mới của phiên này.

**2. Bộ test lấy từ đâu?**

Đồ án có hai nhóm bằng chứng khác nhau: dữ liệu truy xuất luật bên ngoài và bộ hợp đồng/tình huống tự xây. Cần trình bày riêng nguồn gốc của chúng.

| Nguồn của bộ hợp nhất v1 | Số ca gốc | Cách tạo | Số câu trước loại | Số câu giữ lại |
|---|---:|---|---:|---:|
| `evaluation/injection/` | 80 | Hợp đồng nền 11 Điều; thay một Điều bằng nội dung vi phạm hoặc hợp lệ gần giống | 240 | 234 |
| `evaluation/injection_v2/` | 32 | Cố ý thử phủ định và những cách diễn đạt gây nhầm cho luật cố định | 96 | 93 |
| `tests/fixtures/contract_qa_cases.json` | 8 | Fixture câu hỏi QA có sẵn trong repo | 8 | 8 |
| `evaluation/benchmark/v04/` | 34 | Tình huống giả lập: 20 câu kế thừa v0.3 và 14 câu về thời gian, sửa đổi, chuyển tiếp | 34 | 34 |
| Tổng | 154 | | 378 | 369 |

80 + 32 ca bơm lỗi, mỗi ca tạo ba câu hỏi, nên có `(80 + 32) × 3 + 8 + 34 = 378` câu. Sau khi loại ba ca gốc, còn 151 ca gốc tương ứng 369 câu. **369 câu không có nghĩa là 369 hợp đồng khác nhau hoặc 369 quan sát độc lập.**

Trong bộ 80 ca ban đầu, có 40 vi phạm và 40 hợp lệ. Bộ 32 ca có 16 vi phạm và 16 hợp lệ. Ca hợp lệ gần giống, còn gọi là near-miss, được viết để chứa từ khóa dễ làm máy báo nhầm.

Ví dụ từ dữ liệu: `OT-01` có câu nói người lao động phải làm thêm nhưng thời gian đó không được tính thêm tiền lương, được gán nhãn vi phạm. `OT2-C1` viết “Công ty nghiêm cấm mọi hành vi không trả lương làm thêm giờ cho NLĐ”, được gán nhãn hợp lệ. Hai câu đều chứa cụm “không trả lương làm thêm”, nhưng ý nghĩa trái nhau. Đây là ví dụ về thiết kế test, không phải một xác nhận pháp lý mới của báo cáo này.

Tám nhóm kiểm tra là làm thêm giờ, bảo hiểm bắt buộc, giữ bản chính giấy tờ, chi phí đào tạo, phạt tiền/khấu trừ lương, giữ lương khi nghỉ việc, chấm dứt liên quan thai sản và hạn chế khởi kiện. Phạm vi này hữu ích cho rà soát hợp đồng lao động, nhưng chưa bao phủ mọi loại hợp đồng hay mọi vấn đề pháp lý.

Nhãn chủ yếu có được do cách tác giả xây ca và căn cứ luật đã ghi trong ca. Script kiểm cấu trúc, đối chiếu kho luật và LLM kiểm chéo hỗ trợ kiểm tra nhãn. Bộ này không phải tập hợp đồng thực tế đã được luật sư gán nhãn. Riêng `injection_v2` được xây với hiểu biết về điểm yếu của bộ luật cố định, nên phù hợp để kiểm tra một lỗi cụ thể hơn là ước lượng độ chính xác ngoài thực tế.

Nguồn bên ngoài được báo cáo riêng là Zalo AI Challenge 2021 – Legal Text Retrieval, theo tài liệu truy vết đến bản `DaHaDaHa/zac2021`: 3.196 câu hỏi, chia 523 dev và 2.673 test; chỉ 556 câu test có điều luật còn hiệu lực trong kho để đánh giá. Bộ này đo tìm luật, không đo hiểu hợp đồng hay chất lượng QA. Tài liệu chưa xác định được đầy đủ tác giả câu hỏi và giấy phép. Phiên phân tích này không kiểm chứng lại trang nguồn bên ngoài.

**3. Một ca test được tổ chức thế nào?**

Mỗi ca có hợp đồng đầu vào, câu hỏi, đáp án kỳ vọng và thông tin truy vết. Ví dụ `OT-01-T1` trỏ đến hợp đồng `OT-01.txt`, hỏi “Điều 2 của hợp đồng có trái quy định pháp luật lao động không?”. Đáp án lưu riêng Điều hợp đồng cần tìm, nội dung Điều đó, nhãn và các Điều/Khoản luật dùng đối chiếu.

| File | Vai trò dễ hiểu |
|---|---|
| `cases.jsonl` | Bảng tổng hợp đề bài, đáp án và nguồn gốc |
| `inputs_no_gold.jsonl` | Đề đưa cho runner: id, đường dẫn hợp đồng, loại hợp đồng, câu hỏi và mốc thời gian |
| `gold.jsonl` | Đáp án cho bước chấm: Điều hợp đồng, nhãn, căn cứ luật, các ý cần có |
| `split.json` | Danh sách ca gốc thuộc dev hoặc test |
| `verification.jsonl` | Kết quả kiểm tra và cờ của từng câu |
| `quarantine.jsonl` | Chín câu bị loại khỏi chấm |
| `FROZEN.json` | Hash để phát hiện thay đổi dữ liệu sau đóng băng |
| `DECISIONS.md` | Giải thích các quyết định về nhãn, cách chạy và ngoại lệ |

Ba kiểu câu hỏi trên một ca bơm lỗi:

- T1 — phát hiện: hỏi một số Điều hợp đồng có trái luật không. Thường không nêu chủ đề.
- T2 — căn cứ: hỏi điều khoản về một chủ đề cần đối chiếu luật nào. Không yêu cầu kết luận vi phạm.
- T3 — tổng quát: hỏi hợp đồng có điều khoản rủi ro không. Không chỉ sẵn Điều cần xem.

Sau loại, mỗi kiểu có 109 câu; 42 câu còn lại giữ nguyên câu hỏi từ fixture/v04. Nhãn `n/a` có 125 câu vì một số câu không hỏi kết luận vi phạm. Nó không đồng nghĩa với ca thiếu đáp án hoặc câu trả lời sai.

**4. Chia dev/test có hợp lý không?**

Dev dùng để chọn cách sửa; test dùng để báo kết quả sau khi đã chốt phương pháp. V1 chia theo `base_case_id`, giữ ba câu T1/T2/T3 của cùng ca ở cùng một phía. Kiểm tra hiện tại không có ca gốc trùng giữa hai tập.

| Nguồn sau loại | Dev | Test |
|---|---:|---:|
| injection | 48 | 186 |
| injection_v2 | 0 | 93 |
| contract_qa | 0 | 8 |
| v04 | 7 | 27 |
| Tổng câu | 55 | 314 |
| Tổng ca gốc | 23 | 128 |

Tỷ lệ thực tế khoảng 15% dev và 85% test do chia theo nhiều tầng nhỏ và làm tròn xuống. Điểm cần chú ý: **dev không có `injection_v2`**, trong khi đây là nhóm kiểm tra phủ định rất quan trọng. Muốn thử sửa phủ định, nên tạo thêm ca dev mới cùng loại hiện tượng, không chuyển ca test đã đóng băng sang dev.

Không trùng `base_case_id` giúp tránh rò rỉ trực tiếp giữa ba câu cùng ca. Điều đó chưa chứng minh các hợp đồng nền, cách diễn đạt và chủ đề giữa dev/test hoàn toàn độc lập.

**5. Có thể tin nhãn đến mức nào?**

Ba ca gốc bị loại là `LU-09` do bảng review đánh dấu cần xem, `LU2-V1` vì gần trùng `LU-01`, và `OT-09` vì LLM kiểm chéo bất đồng với nhãn ở cả hai lần. Mỗi ca có ba câu, tổng cộng chín câu bị loại.

V7 kiểm chéo 138 ca gốc có nhãn vi phạm/hợp lệ bằng Gemini, khác model sinh câu trả lời. Kappa lần 1 là 0,914 và lần 2 là 0,927: mức đồng thuận cao giữa nhãn cấu tạo và LLM. **Kappa không phải độ chính xác của ContractLens, cũng không chứng minh nhãn đúng pháp lý.** Hai bên vẫn có thể cùng sai.

Còn 38 câu được giữ nhưng gắn `low_confidence`, gồm 35 test và 3 dev. File kiểm tra có tổng cộng 41 cờ này nếu tính cả câu đã bị loại; vì vậy con số 38 trong báo cáo là số còn dùng để chấm, không mâu thuẫn với file.

Phần kiểm chứng bằng người chưa hoàn tất trong các file hiện tại: bảng review 112 ca có 0/112 ô “Bạn duyệt (Đ/S)” được điền. Gold set riêng có 30 Điều từ sáu hợp đồng tổng hợp do AI viết, nhưng cả ba nhóm cột người gán 1, người gán 2 và chuyên gia đều trống. Các nhãn AI nháp không được coi là nhãn người. Sáu hợp đồng này đã dùng kiểm tra tách Điều; không vì thế mà đã có bộ đánh giá pháp lý do người gán nhãn.

**6. Đọc kết quả như thế nào?**

Retrieval là bước tìm đúng điều khoản hợp đồng và điều luật trước khi viết câu trả lời. Generation là bước LLM đọc những gì đã tìm và đưa ra kết luận.

| Chỉ số | Nghĩa dễ hiểu | Tránh hiểu nhầm |
|---|---|---|
| Hit@5 | Trong năm kết quả đầu có ít nhất một kết quả đúng hay không | Có một kết quả đúng chưa chắc có đủ mọi căn cứ |
| Recall@5 / R@5 | Trung bình tìm được bao nhiêu phần căn cứ gold trong năm kết quả đầu | Không phải tỷ lệ câu trả lời đúng |
| Precision phát hiện | Trong các lần báo rủi ro, bao nhiêu lần đúng | Precision thấp nghĩa là báo nhầm nhiều |
| Recall phát hiện | Trong các ca vi phạm thật, bắt được bao nhiêu | Recall cao vẫn có thể kèm rất nhiều báo nhầm |
| F1 | Cân bằng precision và recall | Không bao gồm mọi khía cạnh chất lượng ứng dụng |
| Faithfulness | Các mệnh đề trả lời được context cung cấp hỗ trợ đến mức nào | Context hỗ trợ chưa tự chứng minh đúng pháp lý |
| Correctness | Điểm đúng so với đáp án theo rubric của judge | Điểm trung bình chuẩn hóa khác tỷ lệ câu hoàn toàn đúng |

Khoảng như `[0,80; 0,92]` là khoảng tin cậy 95% theo phương pháp bootstrap đã công bố. Nó phản ánh bất định lấy mẫu theo cách tính đó; không bao gồm mọi thiên lệch do dữ liệu tự xây, nhãn và judge.

**7. Kết quả retrieval: vướng nhất ở đâu?**

| Phép đo | Kết quả v1 | Ý nghĩa thực tế |
|---|---:|---|
| Tách Điều trên các tập được kiểm | 1,00 | Hoạt động tốt trên văn bản và đơn vị Điều đã kiểm; chưa chứng minh đọc mọi PDF/ảnh thực tế tốt |
| Tìm Điều hợp đồng liên quan câu hỏi | Hit@5 = 0,85; n=255 | Khoảng 85% ca được chấm có Điều gold trong năm kết quả đầu |
| Tìm luật từ nội dung điều khoản | R@5 = 0,54; n=253 | Tìm được trung bình khoảng 54% căn cứ gold |
| Tìm luật chỉ từ câu hỏi QA, vector | R@5 = 0,11; n=253 | Mất nhiều căn cứ ngay trước khi LLM trả lời |
| Tìm luật chỉ từ câu hỏi QA, hybrid | R@5 = 0,16 | Có tăng, nhưng còn thấp; chưa đủ để giải quyết vấn đề |
| Riêng T1 trên đường QA | R@5 = 0,00; n=93 | Câu hỏi chỉ nêu số Điều hợp đồng không giúp xác định chủ đề luật |

Ví dụ, người dùng hỏi “Điều 4 có trái luật không?”. Nếu tìm luật chỉ bằng câu hỏi này, máy chưa biết Điều 4 nói về lương, bảo hiểm hay nghỉ việc. Theo tài liệu chạy, đường QA tìm luật từ câu hỏi còn ngữ cảnh hợp đồng đi riêng. Đây là lý do có cơ sở để thử đưa nội dung Điều hợp đồng vào truy vấn tìm luật.

Hybrid làm QA R@5 tăng từ 0,11 lên 0,16, tức 5 điểm phần trăm; đường tìm luật từ điều khoản gần như không đổi ở mức làm tròn 0,54. Độ trễ truy xuất trung vị tăng từ 664 lên 961 ms. Vì vậy chưa có căn cứ chọn hybrid như lời giải chính, hoặc khẳng định nó tốt hơn ở mọi chỉ số.

Mốc Zalo bên ngoài cho vector R@5 = 0,795 trên 556 câu có thể đánh giá. Con số này không mâu thuẫn với QA R@5 = 0,11: hai tập hỏi khác nhau và QA hợp đồng có thể không chứa thông tin chủ đề. Cũng không được nói 79,5% trên toàn bộ 2.673 câu test, vì chỉ 20,8% số câu có thể chấm trong kho hiện tại.

Nhóm thời gian v04 báo evidence recall 0,343 và chọn đúng tập văn bản 0,071. Cần ghi rõ các số đó đang dùng **34 câu v04**, gồm 27 test và 7 dev theo `split.json`; chúng không phải một kết quả chỉ trên test như các bảng chính. Relation recall bằng 0 còn bị giới hạn bởi adapter để trống danh sách cạnh quan hệ, nên chưa đủ để kết luận GraphRAG bên trong hoàn toàn không dùng quan hệ.

**8. Kết quả phát hiện rủi ro: nhạy nhưng hay báo nhầm**

Trên 115 ca test, báo cáo ghi precision 0,76; recall 0,98; F1 0,86 với khoảng tin cậy `[0,80; 0,92]`. Cách hiểu: bắt được gần hết ca vi phạm trong tập đã chấm, nhưng khoảng 24% các lần báo rủi ro là báo nhầm. Đây là tỷ lệ trên bộ test đã thiết kế, không phải dự báo trực tiếp tỷ lệ ngoài thực tế.

Trên 49 ca hợp lệ gần giống/phủ định, hệ thống báo nhầm 20 ca, tức 41%. Đây là vấn đề quan trọng với trải nghiệm sử dụng: người dùng khó tin danh sách cảnh báo nếu nhiều điều khoản hợp lệ cũng bị coi là sai.

Điểm theo chủ đề gợi ý ưu tiên xem lỗi ở BHXH (precision 0,58), thai sản (0,64) và làm thêm giờ (0,70). Nhóm phạt tiền/khấu trừ đạt 1,00 trên 13 ca; mẫu quá nhỏ để kết luận chủ đề này đã được giải quyết hoàn toàn.

Trích đúng Điều gold trên ca vi phạm chỉ đạt 0,58. Hai phép kiểm “Điều không tồn tại trong kho/context” đều bằng 0 ở đường phát hiện không có nghĩa là căn cứ đều đúng: máy vẫn có thể chọn một Điều có thật nhưng không phù hợp với kết luận.

Giới hạn quan trọng: runner đưa đúng Điều gold vào `evaluate_clause`. Phép đo này đã bỏ bài toán tự tìm Điều cần phân tích, đồng thời không đo lớp luật cố định và hợp nhất kết quả của workflow đầy đủ. Vì vậy không được trình bày “toàn hệ thống chính xác 86%”.

**9. Kết quả hỏi đáp: phần cần cải thiện mạnh nhất**

| Chỉ số trên 314 câu test | Giá trị | Cách đọc |
|---|---:|---|
| Faithfulness | 0,55 | Mức hỗ trợ bởi context còn thấp theo judge |
| Correctness chuẩn hóa | 0,51 | Điểm trung bình so với đáp án còn thấp |
| Tỷ lệ đạt trọn điểm 2/2 | 0,40 | Khoảng 40% câu được judge chấm đúng đủ |
| Kết luận khớp nhãn trên nhóm áp dụng | 0,62 | Chưa ổn định khi kết luận hợp lệ/vi phạm |
| Trích đúng Điều gold | 0,54 | Cần cải thiện chọn và trình bày căn cứ |
| `source_clauses` chứa Điều gold | 0,25 | Cần kiểm tra cả chọn nguồn lẫn cách ghi nguồn đầu ra |

Không nên gọi correctness 0,51 là “51% câu trả lời hoàn toàn đúng”; tỷ lệ đúng đủ trong báo cáo là 40%. Hit@5 hợp đồng 0,85 mà nguồn đầu ra đúng 0,25 cũng không tự chứng minh retrieval bị lỗi toàn bộ: cần theo dõi Điều gold từ danh sách tìm được, context thực gửi LLM đến `source_clauses` cuối cùng.

Tỷ lệ Điều nêu trong QA nhưng không có trong context được báo là 0,71. Đây là tín hiệu cần kiểm tra, nhưng không thể gọi thẳng là “71% câu trả lời bịa luật”. Cách đo dựa vào regex “Điều N”; QA có thêm đoạn luật cố định chưa được ghi path trong context để chấm. Cần sửa khả năng quan sát và định danh nguồn trước khi kết luận độ lớn thực của lỗi này.

Judge dùng Qwen khác họ với model sinh GPT-OSS. Hiệu chuẩn 20 câu tham chiếu cho đồng thuận 1,00, nhưng các câu ngắn và gồm những đáp án đảo kết luận dễ phân biệt. Chưa đủ bằng chứng rằng judge đánh giá chính xác câu trả lời dài, nhiều căn cứ và ngoại lệ. Cần một mẫu câu trả lời thật được người chấm độc lập.

**10. Phân tích lỗi cho biết nên sửa gì?**

| Tầng lỗi trong phép đo phát hiện | Số ca | Hướng xử lý |
|---|---:|---|
| Tách Điều sai | 0 | Chưa ưu tiên sửa parser từ bằng chứng v1 |
| Không truy xuất được luật gold | 4 | Kiểm corpus, truy vấn, scope và xếp hạng |
| Có luật gold nhưng LLM kết luận sai | 17 | Sửa cách áp dụng điều kiện, phủ định và ngoại lệ |
| Đúng kết luận nhưng dẫn sai Điều | 26 | Ràng buộc căn cứ và kiểm tra ý nghĩa viện dẫn |

Đây là phân tích lỗi của đường phát hiện được đo, không phải phân rã lỗi của toàn bộ QA. Nó cho thấy chỉ cải thiện retrieval chưa đủ cho phát hiện rủi ro. Với QA, retrieval lại đang có điểm yếu riêng rất rõ. Vì vậy cần sửa đúng đường xử lý thay vì dùng một kết luận chung “mọi lỗi đều do generation”.

**11. Thứ tự cải thiện được đề xuất**

Các mục dưới đây là đề xuất dựa trên bằng chứng, chưa được triển khai trong phiên này. Đường dẫn sửa là nơi cần khảo sát theo bản đồ mã nguồn; phải xem symbol và các test liên quan trước khi thay đổi.

| Ưu tiên | Thay đổi cụ thể | Cách chứng minh có ích |
|---|---|---|
| 1. QA hiểu Điều đang được hỏi trước khi tìm luật | Với câu chỉ nêu số Điều, lấy đúng Điều hợp đồng rồi ghép câu hỏi, tiêu đề và nội dung Điều thành truy vấn luật. Với câu tổng quát, thử chọn các Điều liên quan trong giới hạn context | So sánh trên dev mới: R@5 T1, correctness QA, độ trễ; không chỉ đo retrieval |
| 2. Giảm báo nhầm phủ định/ngoại lệ | Buộc kết luận xét chủ thể, hành vi, điều kiện áp dụng, phủ định và ngoại lệ; thử các cặp câu gần giống chỉ khác một yếu tố | Báo tỷ lệ báo nhầm cùng recall/F1; tránh giảm báo nhầm bằng cách bỏ sót vi phạm |
| 3. Kiểm soát căn cứ đầu ra | Gắn định danh rõ văn bản–Điều–Khoản cho nguồn; ghi nhận mọi đoạn luật thực vào prompt, kể cả đoạn chèn cố định; kiểm tra căn cứ có hỗ trợ kết luận | Trích đúng gold, nguồn không có trong context đã ghi nhận, mẫu kiểm thủ công |
| 4. Kiểm tra đường ghi nguồn hợp đồng | Theo dõi Điều gold từ retrieval đến prompt và `source_clauses` | Tỷ lệ nguồn đầu ra đúng; tập câu tìm được đúng nhưng trả nguồn sai |
| 5. Kiểm chứng toàn workflow | Chạy một tập hợp đồng nhỏ có đối chứng qua phân tích đầy đủ, gồm luật cố định, LLM và hợp nhất | F1 toàn luồng, báo nhầm trên Điều nền sạch, số Điều chưa kiểm và chi phí |
| 6. Bổ sung corpus/thời gian đúng phạm vi | Rà ref thiếu; với lịch sử, xác minh phiên bản chính thức và phạm vi sửa đổi trước khi đo | Báo coverage riêng, điểm trên các ca đủ nguồn; không lặng lẽ bỏ ca khó |

Nơi khảo sát: QA ở `app/agents/qa_agent.py`, `app/infrastructure/retrieval/query_rewrite.py` và `app/vectorstore/retriever.py`; đánh giá điều khoản ở `app/agents/risk_flagger.py` và prompt ở `app/core/prompts.py`; căn cứ ở `app/agents/legal_citations.py`; luật cố định ở `app/agents/labor_red_flags.py`. Kết quả v1 chưa đo luật cố định trong workflow, nên không thể từ lỗi của `evaluate_clause` suy ra chỉ cần sửa regex.

Chưa nên đổi model chỉ vì thấy điểm thấp. Trước hết đo tác động của việc bổ sung đúng ngữ cảnh và ràng buộc căn cứ. Sau đó mới so model bằng cùng đầu vào, cùng rubric và báo kèm chi phí/độ trễ. Tăng recall nhưng giảm tốc độ quá nhiều hoặc tăng báo nhầm có thể làm sản phẩm kém hữu ích hơn.

**12. Cần làm gì tiếp theo để đồ án thuyết phục hơn?**

1. **Chốt phạm vi trình bày.** Đặt trọng tâm vào rà soát và hỏi đáp hợp đồng lao động. Đưa thử nghiệm lịch sử/chuyển tiếp thành phần mở rộng nếu chưa triển khai đầy đủ; vẫn công khai kết quả thấp và giới hạn.
2. **Làm chắc nhãn.** Ưu tiên người có chuyên môn xem các ca `low_confidence`, ca near-miss và các ví dụ dùng để bảo vệ. Hoàn tất nhãn độc lập cho 30 Điều nếu muốn sử dụng gold set đó. Khi gán nhãn, người thứ hai không xem nhãn AI hoặc nhãn người thứ nhất. Nhãn chưa chắc cần ghi rõ, không sửa chỉ để khớp hệ thống.
3. **Chuẩn bị dev bổ sung.** Tạo ca mới về phủ định, câu chỉ nêu số Điều, nguồn viện dẫn và hợp đồng không có lỗi. Không kéo test v1 vào dev. V1 đã được phân tích lỗi, nên thích hợp làm mốc hồi quy; nên có một tập giữ kín mới cho xác nhận tổng quát hóa.
4. **Làm một cải tiến mỗi thí nghiệm.** Bắt đầu với truy vấn QA có nội dung Điều. Ghi lại cấu hình, commit, dữ liệu, số ca thành công/thất bại, điểm, chi phí và thời gian. Sau đó mới thêm kiểm tra căn cứ hoặc cải tiến kết luận.
5. **Kiểm chứng toàn luồng trên mẫu nhỏ đã chốt trước.** Có ca vi phạm, ca hợp lệ, phủ định, nhiều vấn đề trong một hợp đồng và hợp đồng sạch. Không suy rộng F1 một Điều thành chất lượng toàn hợp đồng.
6. **Chốt cấu hình rồi mới đo cuối.** Giữ nguyên bộ v1 và `test.lock`; không xóa khóa hay ghi đè kết quả cũ. Thiết kế một thí nghiệm phiên bản mới có quy tắc chấm khai báo trước. Nếu so trên v1, ghi rõ đó là kiểm tra hồi quy sau khi đã biết lỗi; dùng holdout mới cho kết luận độc lập.

Khi tính bất định cho tập có ba câu từ cùng ca, nên kiểm tra phương pháp bootstrap và ưu tiên lấy mẫu theo ca gốc/hợp đồng để giữ các câu liên quan đi cùng nhau. Báo riêng kết quả có và không có nhóm nhãn kém chắc chắn như một phân tích độ nhạy đã định trước, thay vì chỉ công bố nhóm có điểm cao.

Bảng kết quả trước/sau nên có: QA R@5 theo T1/T2/T3, correctness, faithfulness, tỷ lệ đúng đủ, nguồn đúng; phát hiện precision/recall/F1 và báo nhầm; viện dẫn đúng; coverage, độ trễ và chi phí. Mục tiêu là cải thiện đồng thời độ đúng và khả năng kiểm chứng, không chọn riêng một chỉ số đẹp.

Để nâng chất lượng bảo vệ đồ án, giá trị lớn nhất là chứng minh được chuỗi: **thiết kế phép đo → tìm đúng điểm yếu → sửa có lý do → so sánh có đối chứng → nói rõ giới hạn**. Chưa có căn cứ để hứa một thay đổi cụ thể sẽ làm điểm hệ thống hoặc điểm hội đồng tăng đến mức nào.

**13. Có thể trình bày với hội đồng thế nào?**

“Em xây bộ đánh giá hợp nhất gồm 378 câu từ 154 ca gốc. Sau kiểm tra và loại các ca trùng hoặc chưa chắc chắn, còn 369 câu, chia theo ca gốc thành 55 dev và 314 test. Phần lớn ca hợp đồng là dữ liệu tổng hợp có đối chứng, chưa đại diện hợp đồng thực tế. Em đánh giá riêng tìm nguồn và sinh câu trả lời. Bước đánh giá điều khoản có recall cao nhưng báo nhầm nhiều; QA yếu ở cả tìm căn cứ từ câu hỏi thiếu chủ đề và sử dụng căn cứ. Em dùng các kết quả này để chọn cải tiến và thiết kế phép đo trước/sau. F1 0,86 thuộc phép đo trên Điều đã chỉ sẵn, không phải độ chính xác toàn ứng dụng.”

Các cách nói cần tránh: “378 hợp đồng thực tế”, “kappa 0,927 nghĩa là hệ thống đúng 92,7%”, “QA đúng hoàn toàn 51%”, “judge được chứng minh đúng 100%”, “không có Điều ảo nghĩa là mọi viện dẫn đều đúng”, hoặc “pytest qua nghĩa là câu trả lời pháp lý đúng”.

**Tài liệu nguồn để đọc tiếp**

- [Kết quả định lượng v1](D:/contract-agent/docs/bo_test_hoi_dong/KET_QUA_BO_TEST_V1.md).
- [Cấu trúc và lệnh của bộ hợp nhất](D:/contract-agent/evaluation/contract_eval_v1/README.md), [quyết định phương pháp](D:/contract-agent/evaluation/contract_eval_v1/DECISIONS.md), [báo cáo kiểm nhãn](D:/contract-agent/evaluation/contract_eval_v1/VERIFICATION_REPORT.md).
- [Nguồn bộ bơm lỗi](D:/contract-agent/evaluation/injection/README.md), [bộ phủ định](D:/contract-agent/evaluation/injection_v2/README.md), [benchmark v04](D:/contract-agent/evaluation/benchmark/v04/README.md).
- [Nguồn dữ liệu bên ngoài và bối cảnh các phép đo trước](D:/contract-agent/docs/bo_test_hoi_dong/BO_TEST_HOI_DONG.md). Tài liệu này có số của các thí nghiệm cũ; không trộn chúng với v1 như cùng một lần chạy.
- [Hướng dẫn gán nhãn gold set](D:/contract-agent/evaluation/gold/HUONG_DAN_GAN_NHAN.md), [bản đồ mã nguồn](D:/contract-agent/docs/CODEBASE_MAP.md).
