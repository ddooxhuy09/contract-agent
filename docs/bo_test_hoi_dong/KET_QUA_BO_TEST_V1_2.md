# Kết quả bộ test hợp nhất contract_eval_v1

Thư mục kết quả: `evaluation_results/runs/contract_eval_v1_20261124`. Bộ test đóng băng (SHA-256 trong `evaluation/contract_eval_v1/FROZEN.json`); số chính lấy trên phần **test**, chạy một lần (`test.lock`). Mọi số dưới đây sinh tự động từ `metrics.json` và `verification_stats.json`, đã đối chiếu bằng `python -m evaluation.contract_eval_v1.score check`.

## 0. So sánh v1.1 → v1.2 (cùng bộ test đóng băng, phần test)

Phiên bản trước: `evaluation_results/runs/contract_eval_v1_20261123`. Cùng ca, cùng nhãn, cùng model sinh và judge; chỉ code hệ thống khác. Mỗi cột kèm CI95 riêng; chênh lệch QA tính theo cặp câu ở bảng sau.

| Chỉ số (test) | v1.1 | v1.2 |
|---|---:|---:|
| Truy xuất (vector): R@5 luật, đường QA | 0,76 [0,71; 0,81] | 0,76 [0,71; 0,81] |
| Truy xuất (vector): MRR luật, đường QA | 0,76 [0,71; 0,81] | 0,76 [0,71; 0,81] |
| Truy xuất (vector): R@5 luật, đường phân tích | 0,54 [0,49; 0,59] | 0,90 [0,87; 0,93] |
| Truy xuất (hybrid): R@5 luật, đường QA | 0,76 [0,71; 0,81] | 0,76 [0,71; 0,81] |
| Truy xuất (hybrid): MRR luật, đường QA | 0,75 [0,70; 0,80] | 0,75 [0,70; 0,80] |
| Truy xuất (hybrid): R@5 luật, đường phân tích | 0,54 [0,49; 0,59] | 0,89 [0,86; 0,92] |
| Phát hiện rủi ro: F1 (micro) | 0,83 [0,76; 0,89] | 0,94 [0,89; 0,98] |
| Phát hiện rủi ro: precision | 0,72 [0,63; 0,81] | 0,93 [0,85; 0,98] |
| Phát hiện rủi ro: recall | 0,98 [0,95; 1,00] | 0,95 [0,90; 1,00] |
| Phát hiện rủi ro: báo nhầm trên ca near-miss | 0,51 [0,39; 0,65] | 0,10 [0,02; 0,20] |
| Phát hiện rủi ro: trích đúng Điều gold | 0,60 | 0,85 |
| QA: correctness (0–1) | 0,72 [0,68; 0,76] | 0,71 [0,67; 0,75] |
| QA: tỷ lệ đúng đủ | 0,62 [0,56; 0,67] | 0,60 [0,54; 0,65] |
| QA: kết luận khớp nhãn | 0,75 [0,69; 0,80] | 0,74 [0,68; 0,79] |
| QA: faithfulness | 0,91 [0,89; 0,93] | 0,89 [0,86; 0,92] |
| QA: trích đúng Điều gold | 0,81 [0,76; 0,86] | 0,81 [0,76; 0,86] |
| QA: Điều luật nêu nhưng không có trong context | 0,32 | 0,33 |
| QA: token trung bình | 6218 | 6247 |
| QA: độ trễ p50 (ms) | 7890 | 4420 |

Chênh lệch QA theo cặp câu (v1.2 − v1.1, n=314, bootstrap 1000 lần, seed 42):

| Chỉ số | Chênh lệch | CI95 | Tốt hơn | Kém hơn |
|---|---:|---:|---:|---:|
| Correctness | -0,01 | [-0,04; 0,02] | 18 | 23 |
| Kết luận khớp nhãn | -0,01 | [-0,04; 0,02] | 6 | 8 |
| Faithfulness | -0,02 | [-0,04; 0,01] | 37 | 44 |

Thay đổi cách đo so với v1.1: đường phân tích ở Giai đoạn A gọi đúng `risk_flagger._retrieve_legal` (gồm luật bổ sung theo chủ đề) thay vì gọi thẳng GraphRAG; QA đo như v1.1. Code QA không đổi giữa hai bản, nên chênh lệch QA là dao động của LLM sinh và judge; xem `evaluation/contract_eval_v1/DECISIONS.md`.

## 1. Quy mô bộ test

- Tổng 378 ca từ 154 ca gốc; quarantine 9 ca; còn 369 ca dùng để chấm (test 314, dev 55).
- Nguồn: contract_qa 8, injection 234, injection_v2 93, v04 34.
- Nhãn: compliant 112, n/a 125, violation 132.
- Độ khó: easy 87, expert 6, hard 176, medium 100.
- Theo luật đỏ: ban_lawsuit 43, fine_deduct_wage 43, forfeit_wage_quit 37, no_bhxh 43, ot_unpaid 40, retain_id_papers 43, terminate_pregnancy 43, training_cost_flat 42.
- Template câu hỏi (injection): T1 phát hiện, T2 căn cứ, T3 tổng quát; v04 và contract_qa giữ nguyên câu hỏi (`fixed`): T1 109, T2 109, T3 109, fixed 42.
- Lý do quarantine (theo lớp kiểm): V7 3, V4 3, V6 3; ca gốc bị loại: LU-09, LU2-V1, OT-09.

## 2. Tự kiểm nhãn (script + LLM kiểm chéo, không có người duyệt)

| Lớp | Pass | Fail | Không áp dụng |
|---|---:|---:|---:|
| V1 | 378 | 0 | 0 |
| V2 | 378 | 0 | 0 |
| V3 | 377 | 1 | 0 |
| V4 | 375 | 3 | 0 |
| V5 | 378 | 0 | 0 |
| V6 | 375 | 3 | 0 |
| V7 | 342 | 20 | 16 |

- V7 (Gemini: lần 1 gemini-2.5-flash; lần 2 gemini-2.5-flash, gemini-3-flash-preview; khác model sinh Groq `gpt-oss-120b`; nhiệt độ 0): 138 ca gốc; Cohen's kappa nhãn cấu tạo–LLM lần 1 = **0,914** (đồng thuận 0,957), lần 2 = **0,927** (đồng thuận 0,964).
- Cả 2 lần khớp nhãn: 130; 1 lần trái (giữ, `low_confidence`): 3; 2 lần trái (quarantine): 1. Tổng ca `low_confidence`: 38.
- V3: 444 đoạn trích luật so với văn bản trong kho (fuzzy ≥ 0,8), 1 lượt ref lệch; 6 ca có ref không có trong kho (loại khỏi chấm truy xuất điều luật).
- Chi tiết: `evaluation/contract_eval_v1/VERIFICATION_REPORT.md`.

## 3. Giai đoạn A – Retrieval (trước LLM)

**Tách điều khoản hợp đồng** (clause_parser, không LLM):

| Tập | n hợp đồng/đơn vị | Đúng toàn bộ danh sách Điều | Recall mã Điều | Khớp văn bản |
|---|---:|---:|---:|---:|
| Hợp đồng bơm lỗi | 109 | 1,00 | 1,00 | 1,00 (Điều bơm) |
| v04 (7 hợp đồng) | 7 | 1,00 | 1,00 | 1,00 |
| 6 DOCX gold (đơn vị Điều đã trích) | 30 | – | 1,00 | 1,00 |

**Truy xuất (vector, test)** – CI95 bootstrap 1000 lần, seed 42:

- Điều khoản hợp đồng liên quan câu hỏi (n=255): Hit@1 0,57 [0,52; 0,64], Hit@3 0,84, Hit@5 0,85 [0,80; 0,89].
- Điều khoản hợp đồng QA thực đưa vào ngữ cảnh (nút retrieve, ưu tiên Điều được nêu trong câu hỏi; n=255): Hit@1 0,69 [0,63; 0,75], Hit@5 0,85 [0,81; 0,90].

| Điều luật (khớp mức Điều) | n | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | nDCG@10 | Hit@5 | R@5 mức Khoản |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Theo câu hỏi (đường QA) | 253 | 0,45 | 0,76 | 0,76 [0,71; 0,81] | 0,76 | 0,29 | 0,76 [0,71; 0,81] | 0,75 | 0,81 | 0,67 |
| Theo điều khoản (đường phân tích) | 253 | 0,51 | 0,90 | 0,90 [0,87; 0,93] | 0,90 | 0,35 | 0,90 [0,87; 0,93] | 0,88 | 0,96 | 0,80 |
| ↳ đường QA, câu T1 | 93 | 0,53 | 0,94 | 0,94 | 0,94 | 0,37 | 0,94 | 0,92 | 1,00 | 0,84 |
| ↳ đường QA, câu T2 | 93 | 0,53 | 0,94 | 0,94 | 0,94 | 0,37 | 0,94 | 0,92 | 1,00 | 0,84 |
| ↳ đường QA, câu T3 | 47 | 0,13 | 0,13 | 0,13 | 0,13 | 0,03 | 0,13 | 0,13 | 0,13 | 0,00 |
| ↳ đường QA, câu fixed | 20 | 0,45 | 0,64 | 0,64 | 0,64 | 0,20 | 0,65 | 0,62 | 0,70 | 0,64 |

Đường QA truy xuất luật từ câu hỏi đã gắn nội dung Điều hợp đồng được nêu, cộng luật bổ sung theo chủ đề; câu T3 không nêu Điều cụ thể nên vẫn chỉ có câu hỏi chung chung để truy xuất. Đường phân tích truy xuất từ chính nội dung điều khoản.

- v04 thời điểm (score_temporal_predictions.py, 34 câu): evidence_recall 0,328 (n=34), relation_recall 0,000 (n=14), forbidden_citation_rate 0,111 (n=9), statute_selection_exact_match 0,071 (n=14).
- Ca loại khỏi chấm điều luật vì ref không có trong kho: 3. Độ trễ truy xuất p50 669 ms, p95 1516 ms.

**Truy xuất (hybrid, test)** – CI95 bootstrap 1000 lần, seed 42:

- Điều khoản hợp đồng liên quan câu hỏi (n=255): Hit@1 0,57 [0,52; 0,64], Hit@3 0,84, Hit@5 0,85 [0,80; 0,89].
- Điều khoản hợp đồng QA thực đưa vào ngữ cảnh (nút retrieve, ưu tiên Điều được nêu trong câu hỏi; n=255): Hit@1 0,69 [0,63; 0,75], Hit@5 0,85 [0,81; 0,90].

| Điều luật (khớp mức Điều) | n | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | nDCG@10 | Hit@5 | R@5 mức Khoản |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Theo câu hỏi (đường QA) | 253 | 0,42 | 0,74 | 0,76 [0,71; 0,81] | 0,76 | 0,29 | 0,75 [0,70; 0,80] | 0,74 | 0,81 | 0,67 |
| Theo điều khoản (đường phân tích) | 253 | 0,51 | 0,89 | 0,89 [0,86; 0,92] | 0,89 | 0,35 | 0,90 [0,87; 0,92] | 0,88 | 0,96 | 0,80 |
| ↳ đường QA, câu T1 | 93 | 0,53 | 0,94 | 0,94 | 0,94 | 0,37 | 0,94 | 0,92 | 1,00 | 0,84 |
| ↳ đường QA, câu T2 | 93 | 0,53 | 0,94 | 0,94 | 0,94 | 0,37 | 0,94 | 0,92 | 1,00 | 0,84 |
| ↳ đường QA, câu T3 | 47 | 0,00 | 0,00 | 0,13 | 0,13 | 0,03 | 0,03 | 0,06 | 0,13 | 0,00 |
| ↳ đường QA, câu fixed | 20 | 0,45 | 0,64 | 0,64 | 0,64 | 0,20 | 0,65 | 0,62 | 0,70 | 0,64 |

Đường QA truy xuất luật từ câu hỏi đã gắn nội dung Điều hợp đồng được nêu, cộng luật bổ sung theo chủ đề; câu T3 không nêu Điều cụ thể nên vẫn chỉ có câu hỏi chung chung để truy xuất. Đường phân tích truy xuất từ chính nội dung điều khoản.

- v04 thời điểm (score_temporal_predictions.py, 34 câu): evidence_recall 0,328 (n=34), relation_recall 0,000 (n=14), forbidden_citation_rate 0,111 (n=9), statute_selection_exact_match 0,071 (n=14).
- Ca loại khỏi chấm điều luật vì ref không có trong kho: 3. Độ trễ truy xuất p50 864 ms, p95 1873 ms.

**Zalo legal retrieval (đã khóa, không chạy lại):** fts: R@5 0,009 [0,002; 0,018], MRR@10 0,007 (n=556); hybrid+V3: R@5 0,802 [0,768; 0,835], MRR@10 0,686 (n=556); hybrid: R@5 0,736 [0,701; 0,772], MRR@10 0,642 (n=556); vector: R@5 0,795 [0,763; 0,827], MRR@10 0,682 (n=556).

## 4. Giai đoạn B – Generation (sau LLM)

LLM hệ thống: groq/openai/gpt-oss-120b; judge: groq/qwen/qwen3.8-27b. Đã hoàn tất: phát hiện 115/115 ca test, QA 314/314 câu test.

**Phát hiện rủi ro** (đơn vị: ca gốc; dương tính = critical/warning tại Điều gold; `evaluate_clause` thật, n=115):

| Chỉ số | Giá trị (test) |
|---|---:|
| Precision (micro) | 0,93 [0,85; 0,98] |
| Recall (micro) | 0,95 [0,90; 1,00] |
| F1 (micro) | 0,94 [0,89; 0,98] |
| F1 macro theo luật đỏ | 0,93 |
| Tỷ lệ báo nhầm trên ca near-miss/phủ định | 0,10 [0,02; 0,20] (5/49) |
| Trích đúng Điều gold (ca vi phạm) | 0,85 |
| Trích dẫn ảo: Điều không có trong kho | 0,00 |
| Trích dẫn ảo: Điều không có trong context đã truy xuất | 0,00 |

| Luật đỏ | n | P | R | F1 |
|---|---:|---:|---:|---:|
| ban_lawsuit | 13 | 0,78 | 1,00 | 0,88 |
| fine_deduct_wage | 13 | 1,00 | 1,00 | 1,00 |
| forfeit_wage_quit | 11 | 1,00 | 1,00 | 1,00 |
| no_bhxh | 13 | 0,88 | 1,00 | 0,93 |
| ot_unpaid | 12 | 0,88 | 1,00 | 0,93 |
| retain_id_papers | 13 | 1,00 | 1,00 | 1,00 |
| terminate_pregnancy | 13 | 1,00 | 1,00 | 1,00 |
| training_cost_flat | 12 | 1,00 | 0,50 | 0,67 |

**Hỏi đáp** (QaPipeline thật, mỗi câu một hội thoại mới; 314 câu test, judge chấm 314):

| Chỉ số | Giá trị (test) |
|---|---:|
| Faithfulness (tỷ lệ mệnh đề được context hỗ trợ) | 0,89 [0,86; 0,92] |
| Answer correctness (0–2, chuẩn hóa 0–1) | 0,71 [0,67; 0,75] |
| Tỷ lệ đúng đủ (điểm 2) | 0,60 [0,54; 0,65] |
| Kết luận khớp gold_label (T1/T3/fixed) | 0,74 [0,68; 0,79] |
| Trích đúng Điều gold trong câu trả lời | 0,81 [0,76; 0,86] |
| Điều luật nêu trong câu trả lời nhưng không có trong context | 0,33 |
| Nguồn điều khoản hợp đồng đúng (source_clauses chứa Điều gold) | 0,85 |

Hiệu chuẩn judge: 20 câu trả lời tham chiếu (một nửa đúng, một nửa đảo kết luận) trên ca nhãn chắc chắn; đồng thuận judge–gold = **1,00**.

## 5. Phân tích lỗi theo tầng (phát hiện rủi ro, test)

| Tầng | Ý nghĩa | Số ca |
|---|---|---:|
| (a) | tách điều khoản sai | 0 |
| (b) | retrieval không lấy được luật gold | 0 |
| (c) | có luật gold trong context nhưng LLM kết luận sai | 8 |
| (d) | đúng kết luận nhưng trích sai Điều | 10 |

Chi phí mỗi ca phát hiện: token trung bình 4654, độ trễ p50 4384 ms, p95 7198 ms.
Mỗi câu QA: token trung bình 6247, độ trễ p50 4420 ms, p95 7915 ms.

## 6. Giới hạn

- Ca hợp đồng tự xây bằng **bơm lỗi** (một Điều sai trên hợp đồng nền) và câu hỏi theo template; không đại diện tỷ lệ đúng trên hợp đồng thực tế.
- Nhãn được kiểm chéo bằng script và một LLM khác (Gemini), **chưa có luật sư xác nhận**.
- Phát hiện rủi ro đo bằng `evaluate_clause` (truy xuất + judge) trên Điều gold, không chạy toàn bộ workflow (bỏ lớp luật cố định và hợp nhất kết quả) để tiết kiệm quota; QA tắt bộ nhớ dài hạn để các câu độc lập.
- Trích dẫn trong câu trả lời QA nhận diện bằng regex «Điều N». QA còn chèn đoạn trích BLLĐ cố định (`matching_law_blurbs`) không có path trong kho, nên tỷ lệ «Điều không có trong context» của QA bị đếm cao hơn thực tế.
- Judge faithfulness/correctness là LLM khác họ model sinh (Groq `qwen/qwen3.8-27b`; quota Gemini miễn phí không đủ). Hiệu chuẩn dùng câu trả lời tham chiếu ngắn, dễ phân biệt, nên đồng thuận cao ở đây chưa chứng minh judge chấm đúng câu trả lời dài.
- V7 lần 2 chạy phần lớn bằng `gemini-3-flash-preview` vì `gemini-2.5-flash` hết quota ngày giữa chừng.
- Bộ dev nhỏ (chia theo ca gốc, phân tầng); chỉ số theo từng luật đỏ có n nhỏ, CI rộng.

## 7. Lệnh tái lập

```bash
python -m evaluation.contract_eval_v1.build
python -m evaluation.contract_eval_v1.verify
python -m evaluation.contract_eval_v1.run index
python -m evaluation.contract_eval_v1.run retrieval --label vector
LEGAL_RETRIEVAL_MODE=hybrid python -m evaluation.contract_eval_v1.run retrieval --label hybrid
python -m evaluation.contract_eval_v1.run generation
python -m evaluation.contract_eval_v1.run judge
python -m evaluation.contract_eval_v1.score
python -m evaluation.contract_eval_v1.score check
```
Trên host cần `DATABASE_URL=postgresql://contractlens:contractlens@127.0.0.1:5433/contractlens`.
