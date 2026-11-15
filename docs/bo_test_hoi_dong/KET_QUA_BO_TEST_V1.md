# Kết quả bộ test hợp nhất contract_eval_v1

Thư mục kết quả: `evaluation_results/runs/contract_eval_v1_20261115`. Bộ test đóng băng (SHA-256 trong `evaluation/contract_eval_v1/FROZEN.json`); số chính lấy trên phần **test**, chạy một lần (`test.lock`). Mọi số dưới đây sinh tự động từ `metrics.json` và `verification_stats.json`, đã đối chiếu bằng `python -m evaluation.contract_eval_v1.score check`.

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

| Điều luật (khớp mức Điều) | n | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | nDCG@10 | Hit@5 | R@5 mức Khoản |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Theo câu hỏi (đường QA) | 253 | 0,07 | 0,11 | 0,11 [0,08; 0,15] | 0,11 | 0,04 | 0,12 [0,09; 0,17] | 0,10 | 0,17 | 0,09 |
| Theo điều khoản (đường phân tích) | 253 | 0,22 | 0,46 | 0,54 [0,49; 0,59] | 0,55 | 0,17 | 0,52 [0,48; 0,57] | 0,46 | 0,74 | 0,51 |
| ↳ đường QA, câu T1 | 93 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| ↳ đường QA, câu T2 | 93 | 0,06 | 0,13 | 0,13 | 0,13 | 0,05 | 0,17 | 0,12 | 0,26 | 0,12 |
| ↳ đường QA, câu T3 | 47 | 0,13 | 0,13 | 0,13 | 0,13 | 0,03 | 0,13 | 0,13 | 0,13 | 0,00 |
| ↳ đường QA, câu fixed | 20 | 0,27 | 0,50 | 0,55 | 0,55 | 0,15 | 0,48 | 0,46 | 0,65 | 0,49 |

Đường QA truy xuất luật chỉ từ câu hỏi (ngữ cảnh hợp đồng đi riêng), nên câu T1/T3 chỉ nêu số Điều hợp đồng gần như không mang thông tin chủ đề; đường phân tích truy xuất từ chính nội dung điều khoản.

- v04 thời điểm (score_temporal_predictions.py, 34 câu): evidence_recall 0,343 (n=34), relation_recall 0,000 (n=14), forbidden_citation_rate 0,111 (n=9), statute_selection_exact_match 0,071 (n=14).
- Ca loại khỏi chấm điều luật vì ref không có trong kho: 3. Độ trễ truy xuất p50 664 ms, p95 1673 ms.

**Truy xuất (hybrid, test)** – CI95 bootstrap 1000 lần, seed 42:

- Điều khoản hợp đồng liên quan câu hỏi (n=255): Hit@1 0,57 [0,52; 0,64], Hit@3 0,84, Hit@5 0,85 [0,80; 0,89].

| Điều luật (khớp mức Điều) | n | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | nDCG@10 | Hit@5 | R@5 mức Khoản |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Theo câu hỏi (đường QA) | 253 | 0,02 | 0,06 | 0,16 [0,12; 0,20] | 0,16 | 0,05 | 0,09 [0,06; 0,11] | 0,10 | 0,22 | 0,14 |
| Theo điều khoản (đường phân tích) | 253 | 0,22 | 0,45 | 0,54 [0,49; 0,59] | 0,55 | 0,17 | 0,52 [0,47; 0,57] | 0,45 | 0,74 | 0,51 |
| ↳ đường QA, câu T1 | 93 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| ↳ đường QA, câu T2 | 93 | 0,00 | 0,06 | 0,26 | 0,26 | 0,08 | 0,12 | 0,14 | 0,39 | 0,27 |
| ↳ đường QA, câu T3 | 47 | 0,00 | 0,00 | 0,13 | 0,13 | 0,03 | 0,03 | 0,06 | 0,13 | 0,00 |
| ↳ đường QA, câu fixed | 20 | 0,27 | 0,45 | 0,55 | 0,55 | 0,15 | 0,46 | 0,45 | 0,65 | 0,49 |

Đường QA truy xuất luật chỉ từ câu hỏi (ngữ cảnh hợp đồng đi riêng), nên câu T1/T3 chỉ nêu số Điều hợp đồng gần như không mang thông tin chủ đề; đường phân tích truy xuất từ chính nội dung điều khoản.

- v04 thời điểm (score_temporal_predictions.py, 34 câu): evidence_recall 0,343 (n=34), relation_recall 0,000 (n=14), forbidden_citation_rate 0,111 (n=9), statute_selection_exact_match 0,071 (n=14).
- Ca loại khỏi chấm điều luật vì ref không có trong kho: 3. Độ trễ truy xuất p50 961 ms, p95 2174 ms.

**Zalo legal retrieval (đã khóa, không chạy lại):** fts: R@5 0,009 [0,002; 0,018], MRR@10 0,007 (n=556); hybrid+V3: R@5 0,802 [0,768; 0,835], MRR@10 0,686 (n=556); hybrid: R@5 0,736 [0,701; 0,772], MRR@10 0,642 (n=556); vector: R@5 0,795 [0,763; 0,827], MRR@10 0,682 (n=556).

## 4. Giai đoạn B – Generation (sau LLM)

LLM hệ thống: groq/openai/gpt-oss-120b; judge: groq/qwen/qwen3.8-27b. Đã hoàn tất: phát hiện 115/115 ca test, QA 314/314 câu test.

**Phát hiện rủi ro** (đơn vị: ca gốc; dương tính = critical/warning tại Điều gold; `evaluate_clause` thật, n=115):

| Chỉ số | Giá trị (test) |
|---|---:|
| Precision (micro) | 0,76 [0,67; 0,85] |
| Recall (micro) | 0,98 [0,95; 1,00] |
| F1 (micro) | 0,86 [0,80; 0,92] |
| F1 macro theo luật đỏ | 0,86 |
| Tỷ lệ báo nhầm trên ca near-miss/phủ định | 0,41 [0,27; 0,55] (20/49) |
| Trích đúng Điều gold (ca vi phạm) | 0,58 |
| Trích dẫn ảo: Điều không có trong kho | 0,00 |
| Trích dẫn ảo: Điều không có trong context đã truy xuất | 0,00 |

| Luật đỏ | n | P | R | F1 |
|---|---:|---:|---:|---:|
| ban_lawsuit | 13 | 0,70 | 1,00 | 0,82 |
| fine_deduct_wage | 13 | 1,00 | 1,00 | 1,00 |
| forfeit_wage_quit | 11 | 0,86 | 1,00 | 0,92 |
| no_bhxh | 13 | 0,58 | 1,00 | 0,74 |
| ot_unpaid | 12 | 0,70 | 1,00 | 0,82 |
| retain_id_papers | 13 | 0,88 | 1,00 | 0,93 |
| terminate_pregnancy | 13 | 0,64 | 1,00 | 0,78 |
| training_cost_flat | 12 | 0,75 | 1,00 | 0,86 |

**Hỏi đáp** (QaPipeline thật, mỗi câu một hội thoại mới; 314 câu test, judge chấm 314):

| Chỉ số | Giá trị (test) |
|---|---:|
| Faithfulness (tỷ lệ mệnh đề được context hỗ trợ) | 0,55 [0,51; 0,58] |
| Answer correctness (0–2, chuẩn hóa 0–1) | 0,51 [0,47; 0,56] |
| Tỷ lệ đúng đủ (điểm 2) | 0,40 [0,35; 0,46] |
| Kết luận khớp gold_label (T1/T3/fixed) | 0,62 [0,54; 0,68] |
| Trích đúng Điều gold trong câu trả lời | 0,54 [0,48; 0,59] |
| Điều luật nêu trong câu trả lời nhưng không có trong context | 0,71 |
| Nguồn điều khoản hợp đồng đúng (source_clauses chứa Điều gold) | 0,25 |

Hiệu chuẩn judge: 20 câu trả lời tham chiếu (một nửa đúng, một nửa đảo kết luận) trên ca nhãn chắc chắn; đồng thuận judge–gold = **1,00**.

## 5. Phân tích lỗi theo tầng (phát hiện rủi ro, test)

| Tầng | Ý nghĩa | Số ca |
|---|---|---:|
| (a) | tách điều khoản sai | 0 |
| (b) | retrieval không lấy được luật gold | 4 |
| (c) | có luật gold trong context nhưng LLM kết luận sai | 17 |
| (d) | đúng kết luận nhưng trích sai Điều | 26 |

Chi phí mỗi ca phát hiện: token trung bình 5314, độ trễ p50 5608 ms, p95 9478 ms.
Mỗi câu QA: token trung bình 3436, độ trễ p50 3077 ms, p95 4982 ms.

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
