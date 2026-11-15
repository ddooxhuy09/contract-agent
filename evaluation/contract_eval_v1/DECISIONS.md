# Quyết định khi gặp chỗ mơ hồ (contract_eval_v1)

Mỗi dòng: quyết định — lý do.

- Đơn vị chia dev/test là `base_case_id` (3 câu T1/T2/T3 của một ca luôn cùng phía), phân tầng theo nguồn + luật đỏ + nhãn, seed 42, dev = làm tròn xuống 25% mỗi tầng — tránh rò rỉ giữa các câu cùng hợp đồng; tầng nhỏ (2 ca) dồn hết vào test nên test thực tế ≈ 85% (≥ 70% theo yêu cầu).
- `gold_legal_refs` của injection/injection_v2 lấy từ cột `legal_basis` của ca (đã đối chiếu BLLĐ trong REVIEW CSV); đoạn trích luật trong REVIEW CSV chỉ dùng cho kiểm V3/V7 — `legal_basis` là nguồn nhãn do cấu tạo, CSV là bằng chứng kiểm.
- contract_qa không có căn cứ luật trong fixture: lấy `legal_basis` của luật đỏ tương ứng trong bộ injection — suy ra trực tiếp từ định nghĩa luật đỏ, không dùng LLM.
- T2 (câu hỏi căn cứ) có `gold_label = n/a` — câu hỏi không hỏi kết luận vi phạm; T3 hợp lệ có `gold_clause_ids = []` và không có ref — câu tổng quát không trỏ tới Điều nào khi hợp đồng không có lỗi bơm.
- v04: `gold_label` = violation khi `expected_verdict` ∈ {critical, warning}, compliant khi `ok`, còn lại n/a; `gold_clause_ids` lấy từ Điều/Khoản gold (trong JSON v04) chứa `contract_excerpt_span`; câu hỏi = scenario + question như `rag_only.py`.
- Map ref sang kho: khóa là `lquery` `<doc_id>.*.D<điều>[.K<khoản>].*` trên `legal_embeddings.path`; ref không có văn bản/Điều trong kho → `unmapped_refs` (6 ca v04: Luật Thương mại 36/2005/QH11 không có trong kho, BLDS Điều 328 k1 không có path).
- V2: nếu Điều/Khoản gold có thật trong văn bản (dòng tiêu đề) nhưng clause_parser không tách ra thì **không** quarantine, gắn cờ `parser_mismatch` và tính là lỗi tầng (a) — đó là lỗi hệ thống, không phải lỗi nhãn.
- V3: so từng đoạn trích (tách theo «...») trong REVIEW CSV / evidence v04 với văn bản Điều trong DB bằng tỷ lệ ký tự khớp theo thứ tự (SequenceMatcher), ngưỡng 0,8; ref không có đoạn trích chỉ kiểm tồn tại.
- V4: «CẦN BẠN XEM» trong REVIEW CSV → quarantine (LU-09); «ĐÚNG – CÓ LƯU Ý» → giữ, `low_confidence`.
- V5: token rò rỉ = mã luật đỏ, chữ violation/compliant, số hiệu văn bản gold, «Điều N» với N là Điều luật gold (trừ khi N là số Điều hợp đồng được hỏi); nếu có thì thay bằng «điều luật liên quan» và ghi lại.
- V6: so trùng ở mức ca gốc trên nội dung điều khoản (+ câu hỏi với ca `fixed`); T3 có câu hỏi giống hệt nhau giữa các ca nên không so câu hỏi template.
- V7: hệ thống sinh bằng Groq `openai/gpt-oss-120b` (LLM_PROVIDER=groq) nên kiểm chéo bằng Gemini `gemini-2.5-flash`, nhiệt độ 0, 2 lần; gộp 8 ca mỗi lượt gọi để vừa hạn mức Gemini miễn phí; «không xác định» không tính là trái nhãn nhưng gắn `low_confidence`; kappa tính với «không xác định» là nhãn riêng.
- Hợp đồng .txt/.md được nạp vào DB bằng đúng `chunk_by_clause` + embedder + repository như `UploadContract` (use case này chỉ nhận docx/pdf/ảnh); .docx đi qua `UploadContract` thật; tất cả thuộc user riêng `contract-eval-v1@example.invalid`.
- Truy xuất điều khoản hợp đồng gọi `retrieve_contract(question, contract_id, k=10)` (QA thật dùng k=5) để tính được Hit@5 và xem thứ hạng xa hơn; Hit@1/3/5 chỉ dùng 5 vị trí đầu nên trùng với cấu hình thật nếu thứ hạng ổn định.
- Truy xuất điều luật đo hai đường thật: đường QA (`retrieve_legal(augment_qa_retrieval_query(q), k=5)` như `_retrieve_node`) và đường phân tích (`LegalGraphRag.retrieve_for_clause(title, summary, k_seed=4, max_total=10)` như `evaluate_clause`, không có job_context); khớp mức Điều, báo thêm mức Khoản.
- Giai đoạn B phát hiện rủi ro gọi `evaluate_clause` (truy xuất + judge thật) chỉ trên Điều gold thay vì cả workflow (~12 lượt LLM/hợp đồng) — tiết kiệm quota ~12 lần; hệ quả: không đo lớp luật cố định/hợp nhất, ghi trong giới hạn.
- QA: dùng graph QA thật nhưng checkpointer `MemorySaver` và tắt bộ nhớ dài hạn (load/save_qa_memory no-op) trong tiến trình đánh giá — mỗi câu là hội thoại mới, không rò câu trả lời của T1 sang T2/T3; không ghi checkpoint vào DB.
- Judge faithfulness + correctness dùng Groq `qwen/qwen3.8-27b` (khác họ model sinh gpt-oss-120b), nhiệt độ 0, JSON mode, 3 câu trả lời mỗi lượt — Gemini miễn phí chỉ ~20 lượt/ngày/model, không đủ cho ~130 lượt; hiệu chuẩn bằng 20 câu trả lời tham chiếu dựng sẵn (10 đúng, 10 đảo kết luận) trên ca nhãn chắc chắn (V7 2 lần khớp, không low_confidence/ref_mismatch) — biết trước đáp án nên đo được độ đồng thuận judge–gold.
- Trích dẫn trong câu trả lời QA nhận bằng regex «Điều N» có từ khóa văn bản luật theo sau, hoặc N không phải số Điều của hợp đồng — câu trả lời QA là văn bản tự do, không có trường trích dẫn có cấu trúc.
- v04 temporal: hit QA được đổi sang `provision_id` của v04 theo (số hiệu, Điều, Khoản) rồi chạy `score_temporal_predictions.py` có sẵn; `relation_edge_ids` để trống vì hệ thống không xuất cạnh quan hệ.
- V7: khi `gemini-2.5-flash` hết quota ngày giữa lần 2, kiểm chéo tự chuyển sang `gemini-3-flash-preview` (vẫn khác model sinh); model của từng mục ghi trong `v7_cache/run*.json` và báo cáo — không dừng chờ quota theo yêu cầu chạy tự động.
- contract_qa dùng id trung tính `QA-01..08` (id fixture như `ban_lawsuit` trùng mã luật đỏ, là rò rỉ gold trong `inputs_no_gold.jsonl`); id gốc giữ ở trường `fixture_id`.
- Groq từng chặn API (ngưỡng cảnh báo chi tiêu) trong lúc chạy; người dùng nới hạn mức rồi Giai đoạn B chạy tiếp; runner coi lỗi «spend alert / blocked API access» là dừng cứng và ghi RESUME.md.
