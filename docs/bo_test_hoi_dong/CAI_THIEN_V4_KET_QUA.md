# Kết quả cuối v4: truy xuất căn cứ và kiểm chứng câu trả lời

Ngày 18/11/2026. Baseline là code v3, candidate là v4. Cả hai đều gọi hệ thống/model thật và được chấm bằng cùng judge/rubric; không sửa nhãn để tăng điểm.

![QA trước/sau v4](D:/contract-agent/docs/bo_test_hoi_dong/QA_V4_TRUOC_SAU.png)

**Kết quả chính**

| Nhóm | Số câu mỗi bản | Correctness trước → sau | Đúng đủ trước → sau | Kết luận đúng trước → sau | Nguồn HĐ đúng trước → sau |
|---|---:|---:|---:|---:|---:|
| 32 ca regression đã dùng phân tích lỗi | 32/32 | 79.7% → **90.6%** | 78.1% → **87.5%** | 81.2% → **93.8%** | 96.9% → **100.0%** |
| 8 ca thử việc/nghỉ phép | 8/8 | 100.0% → **87.5%** | 100.0% → **87.5%** | 100.0% → **87.5%** | 100.0% → **87.5%** |
| 16 ca validation không dùng sửa v4 | 16/16 | 93.8% → **96.9%** | 93.8% → **93.8%** | 93.8% → **100.0%** | 100.0% → **100.0%** |

Correctness là điểm trung bình 0–2 chuẩn hóa; đúng đủ là tỷ lệ đạt 2/2. Đây là số đo tự động trên dữ liệu tổng hợp, không phải chứng nhận độ chính xác pháp lý ngoài thực tế.

**Các vòng đã làm và lý do phải có v4**

V2 đưa nội dung Điều hợp đồng vào truy vấn luật. V3 bổ sung chỉ mục chủ đề và toàn Điều trong corpus; dev đạt 32/32 đúng đủ nhưng regression chỉ đạt 27/32, và hai ca mới giảm điểm. Các lỗi gồm đảo nghĩa điều cấm, dùng văn bản lệch phạm vi và coi thiếu chi tiết trong hợp đồng là vi phạm. Các kết quả v3 vẫn được giữ và báo riêng, không bị xóa để thay bằng số đẹp hơn.

V4 thêm đúng một lượt kiểm chứng bằng chính model sinh, chỉ khi có căn cứ chính xác theo chủ đề. Lượt này đọc bản nháp và nguồn, không biết gold hoặc điểm judge. Nếu kiểm chứng lỗi/JSON hỏng thì giữ bản nháp; không lặp đến khi được điểm cao. Không thay retry hoặc node/cạnh LangGraph.

**Sửa code và nguồn kiến thức**

- Lấy thêm Điều 1 thật của hợp đồng khi hỏi Điều cụ thể, để model có loại/thời hạn hợp đồng thay vì hỏi lại dữ kiện đã có.
- Khi đã có căn cứ chính xác, bỏ các đoạn vector bổ sung lệch chủ đề. Giữ retrieval thông thường nếu chưa có căn cứ phù hợp.
- Bổ sung nguyên tắc thỏa thuận và điều kiện có lợi hơn cho người lao động cho các chủ đề phù hợp; bổ sung quyền tiếp cận Tòa án từ Bộ luật Tố tụng dân sự, lấy văn bản thật qua repository và kiểm hiệu lực.
- Kiểm tra chiều của điều cấm, điều kiện áp dụng, phủ định, ngoại lệ, căn cứ được dẫn và việc điều khoản không chép toàn bộ luật. Không tự điền `source_clauses` mà model chưa dẫn.
- Không thêm dependency, SQL trong agent, nhãn/case id benchmark vào ứng dụng, hoặc thay schema/API/auth/streaming/checkpointer.

Ý tưởng tham khảo: [CRAG](https://arxiv.org/abs/2401.15884) về sửa chất lượng truy xuất, [ALCE](https://aclanthology.org/2023.emnlp-main.398/) về viện dẫn và [Self-RAG](https://arxiv.org/abs/2310.11511) về kiểm chứng đầu ra. Đây là cách triển khai riêng, không huấn luyện/tái lập trọn mô hình của paper.

Nguồn chính thức: [BLLĐ hợp nhất 125/VBHN-VPQH](https://vanban.chinhphu.vn/?docid=215248&pageid=27160), [Bộ luật Tố tụng dân sự trên Cổng Chính phủ](https://xaydungchinhsach.chinhphu.vn/toan-van-van-ban-hop-nhat-so-24-vbhn-vpqh-bo-luat-to-tung-dan-su-119230213081059503.htm). Đã tìm nguồn bằng web/MCP Search; không có MCP chuyên luật VN được kết nối. VBPL trả 403 nên dùng nguồn Chính phủ đọc được, không tuyên bố vượt chặn.

**Thiết kế bộ đánh giá và các giới hạn**

Protocol v4 được đóng băng trước kết quả candidate. 40 ca của hai nhóm đầu đã dùng phân tích v3 nên là regression trong phát triển. 16 validation được chọn cân bằng bằng seed 20261120, không trùng ca gốc dev/v2/v3 và không dùng kết quả riêng của chúng để sửa v4. Tuy nhiên chúng vẫn lấy từ bộ v1 từng được đánh giá, cùng các nền tổng hợp; không gọi là benchmark hoàn toàn mới độc lập.

8 ca mới có nguồn luật chính thức, nhưng do tác giả code soạn, chưa có chuyên gia xác nhận. Inference không phân tích gold để sinh hoặc chọn evidence; bước integrity đọc bytes để kiểm hash, đáp án dùng ở bước chấm. Judge Qwen và rubric không đổi giữa hai bản; model sinh GPT-OSS-120b và embedding BGE-M3 không đổi. Bản v3 được nạp từ snapshot để chạy baseline mới, không dùng lại điểm cũ để chọn baseline thấp.

Đã chạy 56 câu × 2 cấu hình = **112 đầu ra QA**, chấm thật từng đầu ra. V4 dùng thêm một lượt model để kiểm chứng nên không phải so sánh cùng số token. Cần xét chi phí và độ trễ cùng độ đúng.

Usage API vòng v4: 223 lời gọi hệ thống, 659,179 token; 112 lời gọi judge, 226,561 token. Số lời gọi có thể lớn hơn 112 vì lượt kiểm chứng và vòng rewrite có sẵn.

**Truy xuất và faithfulness**

| Nhóm | R@5 trước → sau | Faithfulness trước → sau | n faithfulness trước/sau | p50 QA trước → sau |
|---|---:|---:|---:|---:|
| 32 ca regression đã dùng phân tích lỗi | 93.8% → 93.8% | 86.3% → 92.7% | 31; 32 | 2.72s → 6.43s |
| 8 ca thử việc/nghỉ phép | 100.0% → 100.0% | 100.0% → 100.0% | 8; 7 | 2.57s → 6.14s |
| 16 ca validation không dùng sửa v4 | 93.8% → 93.8% | 97.9% → 98.4% | 16; 16 | 2.75s → 6.64s |

R@5 v4 lấy từ trace truy xuất cuối của QA thật; đo hệ thống vector + tra Điều, không phải chất lượng embedding thuần. Danh sách truy xuất và context thực gửi model là hai trường riêng, vì đóng gói prompt có giới hạn ký tự. Faithfulness bỏ câu không có mệnh đề và báo mẫu số riêng; correctness vẫn chấm đủ câu.

**Tăng/giảm từng ca và những ca chưa đúng đủ**

**32 ca regression đã dùng phân tích lỗi**

5 câu tăng, 1 câu giảm, 26 câu không đổi; CI95 chênh correctness [+0.0; +23.4] điểm %, lấy mẫu theo ca gốc.

- `REG-006` / `LU-06-T1`: 1/2 — Kết luận đúng nhưng căn cứ pháp lý sai. Điều 40 BLĐL 2019 quy định về trách nhiệm khi chấm dứt trái pháp luật, không phải nghĩa vụ báo trước 30 ngày (đây là Điều 35). Do đó, lập luận về Điều 40 là thiếu căn cứ phù hợp.
- `REG-008` / `BH-09-T1`: 0/2 — Kết luận sai. Căn cứ Điều 168 khoản 3 BLĐL 2019, người lao động nghỉ việc không hưởng lương từ 14 ngày trở lên không thuộc đối tượng tham gia BHXH bắt buộc, do đó thỏa thuận tại Điều 4.2 là hợp pháp (compliant).
- `REG-021` / `LU2-V2-T1`: 1/2 — Kết luận đúng nhưng giải thích sai căn cứ pháp lý. Điều 8 quy định không trả lương tháng cuối là vi phạm Điều 94 (trả lương đầy đủ) và Điều 48 (thanh toán quyền lợi). Tuy nhiên, việc 'không đền bù ngày phép' (nghỉ phép năm) không bị cấm tuyệt đối khi NLĐ đơn phương chấm dứt trái pháp luật (Điều 40 chỉ quy định mất trợ cấp thôi việc và bồi thường, không nói đến mất phép năm), do đó lập luận rằng Điều 8 trái luật hoàn toàn về cả hai điểm là thiếu chính xác.
- `REG-031` / `DT2-V1-T1`: 0/2 — Kết luận sai. Điều 62 BLĐS quy định chi phí đào tạo phải có chứng từ hợp lệ và bao gồm các khoản chi cụ thể. Việc quy định mức bồi thường cố định (06 tháng lương) mà không gắn với chi phí thực tế có chứng từ là trái quy định, trong khi câu trả lời lại kết luận là hợp pháp.

**8 ca thử việc/nghỉ phép**

0 câu tăng, 1 câu giảm, 7 câu không đổi; CI95 chênh correctness [-37.5; +0.0] điểm %, lấy mẫu theo ca gốc.

- `NEW-04` / `NEW-04`: 0/2 — Câu trả lời là một câu hỏi ngược lại thay vì đưa ra kết luận và lập luận pháp lý, không giải quyết được vấn đề được hỏi.

**16 ca validation không dùng sửa v4**

1 câu tăng, 0 câu giảm, 15 câu không đổi; CI95 chênh correctness [+0.0; +9.4] điểm %, lấy mẫu theo ca gốc.

- `VAL-015` / `DT-01-T1`: 1/2 — Câu trả lời đưa ra kết luận 'có khả năng' (uncertain) trong khi nhãn tham chiếu là 'violation' (chắc chắn). Mặc dù các luận điểm pháp lý (Điều 40, 62 BLĐ) và phân tích về việc quy định mức bồi thường cố định không dựa trên chi phí thực tế là chính xác và có căn cứ, nhưng mức độ chắc chắn của kết luận thấp hơn so với yêu cầu của nhãn tham chiếu, dẫn đến đánh giá là đúng một phần.

**Việc còn cần biết**

Corpus bản sao đang đánh dấu Luật BHXH 41/2024/QH15 là hết hiệu lực toàn bộ; nguồn Chính phủ vẫn có tài liệu áp dụng luật này trong năm 2026. Đây là tín hiệu cần audit trạng thái/phiên bản và quy định chuyên ngành, chưa phải căn cứ để tự bật lại mọi chunk. Vòng này không sửa metadata hiệu lực để ép ca bảo hiểm khớp gold.

Chưa chạy toàn bộ QA 314 câu bằng v4, toàn workflow phân tích, hội thoại nhiều lượt hoặc hợp đồng thực tế. Kết quả hiện chủ yếu cho câu hỏi chỉ rõ Điều. Không lấy điểm cao ở các nhóm trên để tuyên bố mọi chức năng đều đạt cùng mức.

Kiểm tra kỹ thuật: 381 passed, 1 skipped cho test không integration; các file sửa qua ruff F. Có test hồi quy cho lỗi HTTP client dùng qua nhiều event loop: harness đã sửa để các split dùng cùng một loop; các lượt đã chạy được retry cũ xử lý, không xóa hoặc chạy lại chọn điểm. Toàn repo còn F401 cũ ở `evaluation/check_chapter_numbers.py:15`. Chưa commit/push; giữ nguyên dữ liệu, khóa test và kết quả các vòng cũ.

Bằng chứng đầy đủ ở `evaluation/contract_eval_v2/artifacts/reviewed_evidence_v4/`: protocol, snapshot baseline, manifest/hash, đầu vào/gold tách riêng, câu trả lời, context thực, điểm từng ca, usage và `human_review.csv`. Tài liệu nguồn và kết quả v3 ở `RESEARCH_NOTES.md` và `NGHIEN_CUU_V3_KET_QUA.md`.
