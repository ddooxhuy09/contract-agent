# Đối chiếu số liệu chương 5 và bộ test hội đồng với file kết quả

Sinh bởi `python -m evaluation.check_chapter_numbers`. Chỉ báo, không sửa chương.

Tổng 172 số: **171 khớp, 1 lệch**.

## Lệch

| Vị trí | Mục | Trong chương | Thực tế |
|---|---|---|---|
| 5.5.3 | trung bình số ĐIỀU khác bị gắn cờ (không tính cờ toàn văn) | 5.4 | 4.4167 |

## Toàn bộ

| Vị trí | Mục | Trong chương | Thực tế | Kết quả |
|---|---|---|---|---|
| 5.3.1 | số dòng dataset | 3298 | 3298 | khớp |
| 5.3.1 | số câu hỏi | 3196 | 3196 | khớp |
| 5.3.1 | số văn bản (cắt hậu tố +Điều của doc_id) | 724 | 724 | khớp |
| 5.3.1 | câu có >1 dòng nhãn | 93 | 93 | khớp |
| 5.3.1 | câu có đúng 2 dòng nhãn | 84 | 84 | khớp |
| 5.3.1 | câu có >=3 dòng nhãn | 9 | 9 | khớp |
| 5.3.1 | n_dev | 523 | 523 | khớp |
| 5.3.1 | n_test | 2673 | 2673 | khớp |
| 5.3.2 / bảng 5.1 | số câu article_searchable | 772 | 772 | khớp |
| 5.3.2 / bảng 5.1 | tỷ lệ article_searchable (%) | 24.2 | 24.1552 | khớp |
| 5.3.2 / bảng 5.1 | số câu doc_present_not_searchable | 2257 | 2257 | khớp |
| 5.3.2 / bảng 5.1 | tỷ lệ doc_present_not_searchable (%) | 70.6 | 70.6195 | khớp |
| 5.3.2 / bảng 5.1 | số câu doc_missing | 162 | 162 | khớp |
| 5.3.2 / bảng 5.1 | tỷ lệ doc_missing (%) | 5.1 | 5.0688 | khớp |
| 5.3.2 / bảng 5.1 | số câu doc_searchable_article_missing | 5 | 5 | khớp |
| 5.3.2 / bảng 5.1 | tỷ lệ doc_searchable_article_missing (%) | 0.2 | 0.1564 | khớp |
| 5.3.2 | coverage_breakdown.md chứa 1.509 | 1.509 | có trong coverage_breakdown.md | khớp |
| 5.3.2 | coverage_breakdown.md chứa 66,9% | 66,9% | có trong coverage_breakdown.md | khớp |
| 5.3.2 | coverage_breakdown.md chứa 679 | 679 | có trong coverage_breakdown.md | khớp |
| 5.3.2 | coverage_breakdown.md chứa 30,1% | 30,1% | có trong coverage_breakdown.md | khớp |
| 5.3.2 | coverage_breakdown.md chứa 660 | 660 | có trong coverage_breakdown.md | khớp |
| bảng 5.2 [fts] | n | 556 | 556 | khớp |
| bảng 5.2 [fts] | R@1 | 0.005 | 0.0054 | khớp |
| bảng 5.2 [fts] | R@5 | 0.009 | 0.009 | khớp |
| bảng 5.2 [fts] | R@5 CI thấp | 0.002 | 0.0018 | khớp |
| bảng 5.2 [fts] | R@5 CI cao | 0.018 | 0.018 | khớp |
| bảng 5.2 [fts] | R@10 | 0.014 | 0.0144 | khớp |
| bảng 5.2 [fts] | MRR@10 | 0.007 | 0.0068 | khớp |
| bảng 5.2 [fts] | MRR CI thấp | 0.001 | 0.0013 | khớp |
| bảng 5.2 [fts] | MRR CI cao | 0.014 | 0.0144 | khớp |
| bảng 5.2 [fts] | DocR@10 | 0.025 | 0.0252 | khớp |
| bảng 5.2 [vector] | n | 556 | 556 | khớp |
| bảng 5.2 [vector] | R@1 | 0.594 | 0.5935 | khớp |
| bảng 5.2 [vector] | R@5 | 0.795 | 0.795 | khớp |
| bảng 5.2 [vector] | R@5 CI thấp | 0.763 | 0.7626 | khớp |
| bảng 5.2 [vector] | R@5 CI cao | 0.827 | 0.8273 | khớp |
| bảng 5.2 [vector] | R@10 | 0.836 | 0.8363 | khớp |
| bảng 5.2 [vector] | MRR@10 | 0.682 | 0.6816 | khớp |
| bảng 5.2 [vector] | MRR CI thấp | 0.649 | 0.6494 | khớp |
| bảng 5.2 [vector] | MRR CI cao | 0.715 | 0.7147 | khớp |
| bảng 5.2 [vector] | DocR@10 | 0.91 | 0.9101 | khớp |
| bảng 5.2 [hybrid] | n | 556 | 556 | khớp |
| bảng 5.2 [hybrid] | R@1 | 0.581 | 0.5809 | khớp |
| bảng 5.2 [hybrid] | R@5 | 0.736 | 0.7356 | khớp |
| bảng 5.2 [hybrid] | R@5 CI thấp | 0.701 | 0.7014 | khớp |
| bảng 5.2 [hybrid] | R@5 CI cao | 0.772 | 0.7716 | khớp |
| bảng 5.2 [hybrid] | R@10 | 0.791 | 0.7914 | khớp |
| bảng 5.2 [hybrid] | MRR@10 | 0.642 | 0.642 | khớp |
| bảng 5.2 [hybrid] | MRR CI thấp | 0.609 | 0.6085 | khớp |
| bảng 5.2 [hybrid] | MRR CI cao | 0.677 | 0.6774 | khớp |
| bảng 5.2 [hybrid] | DocR@10 | 0.894 | 0.8939 | khớp |
| bảng 5.2 [hybrid+V3] | n | 556 | 556 | khớp |
| bảng 5.2 [hybrid+V3] | R@1 | 0.59 | 0.5899 | khớp |
| bảng 5.2 [hybrid+V3] | R@5 | 0.802 | 0.8022 | khớp |
| bảng 5.2 [hybrid+V3] | R@5 CI thấp | 0.768 | 0.768 | khớp |
| bảng 5.2 [hybrid+V3] | R@5 CI cao | 0.835 | 0.8345 | khớp |
| bảng 5.2 [hybrid+V3] | R@10 | 0.842 | 0.8417 | khớp |
| bảng 5.2 [hybrid+V3] | MRR@10 | 0.686 | 0.6857 | khớp |
| bảng 5.2 [hybrid+V3] | MRR CI thấp | 0.655 | 0.6547 | khớp |
| bảng 5.2 [hybrid+V3] | MRR CI cao | 0.719 | 0.719 | khớp |
| bảng 5.2 [hybrid+V3] | DocR@10 | 0.908 | 0.9083 | khớp |
| bảng 5.2 [fts] | độ trễ median (ms) | 85 | 85 | khớp |
| bảng 5.2 [vector] | độ trễ median (ms) | 294 | 294 | khớp |
| bảng 5.2 [hybrid] | độ trễ median (ms) | 347 | 347 | khớp |
| bảng 5.2 [hybrid+V3] | độ trễ median (ms) | 4237 | 4237 | khớp |
| bảng 5.3 | TEST_KET_QUA.md chứa −0,0395 | [−0,0483; −0,0312] (chương làm tròn 3 chữ số) | −0,0395 | [−0,0483; −0,0312] | có trong TEST_KET_QUA.md | khớp |
| bảng 5.3 | TEST_KET_QUA.md chứa +0,0042 | [−0,0061; +0,0139] (chương làm tròn 3 chữ số) | +0,0042 | [−0,0061; +0,0139] | có trong TEST_KET_QUA.md | khớp |
| bảng 5.3 | TEST_KET_QUA.md chứa +0,0437 | [+0,0290; +0,0571] (chương làm tròn 3 chữ số) | +0,0437 | [+0,0290; +0,0571] | có trong TEST_KET_QUA.md | khớp |
| 5.3.6 / 5.10 | tỷ lệ câu test đánh giá được | 0.208 | 0.208 | khớp |
| 5.3.6 | R@10 vector trên toàn bộ 2.673 câu | 0.174 | 0.174 | khớp |
| 5.3.6 | V3 chậm hơn vector ~ lần | 14 | 14 | khớp |
| 5.3.4 | PHAN_TICH_LOI_DEV.md chứa 50/216 | 50/216 | có trong PHAN_TICH_LOI_DEV.md | khớp |
| 5.3.4 | PHAN_TICH_LOI_DEV.md chứa 7/216 | 7/216 | có trong PHAN_TICH_LOI_DEV.md | khớp |
| 5.3.4 | PHAN_TICH_LOI_DEV.md chứa 150/216 | 150/216 | có trong PHAN_TICH_LOI_DEV.md | khớp |
| 5.3.4 | DEV_BIEN_THE.md chứa 0,7112 | 0,7112 | có trong DEV_BIEN_THE.md | khớp |
| 5.4 | RAG_V04_HYBRID_VS_VECTOR.md chứa 0,2990 (chương làm tròn 3 chữ số) | 0,2990 | có trong RAG_V04_HYBRID_VS_VECTOR.md | khớp |
| 5.4 | RAG_V04_HYBRID_VS_VECTOR.md chứa 0,3000 (chương làm tròn 3 chữ số) | 0,3000 | có trong RAG_V04_HYBRID_VS_VECTOR.md | khớp |
| 5.4 | RAG_V04_HYBRID_VS_VECTOR.md chứa 0,4461 (chương làm tròn 3 chữ số) | 0,4461 | có trong RAG_V04_HYBRID_VS_VECTOR.md | khớp |
| 5.4 | RAG_V04_HYBRID_VS_VECTOR.md chứa 0,4608 (chương làm tròn 3 chữ số) | 0,4608 | có trong RAG_V04_HYBRID_VS_VECTOR.md | khớp |
| 5.5.1 | số ca bơm lỗi | 80 | 80 | khớp |
| bảng 5.4 | TP | 16 | 16 | khớp |
| bảng 5.4 | FP | 14 | 14 | khớp |
| bảng 5.4 | FN | 24 | 24 | khớp |
| bảng 5.4 | precision | 0.53 | 0.5333 | khớp |
| bảng 5.4 | precision CI thấp | 0.36 | 0.3571 | khớp |
| bảng 5.4 | precision CI cao | 0.73 | 0.7308 | khớp |
| bảng 5.4 | recall | 0.4 | 0.4 | khớp |
| bảng 5.4 | recall CI thấp | 0.25 | 0.25 | khớp |
| bảng 5.4 | recall CI cao | 0.56 | 0.5556 | khớp |
| bảng 5.4 | f1 | 0.46 | 0.4571 | khớp |
| bảng 5.4 | f1 CI thấp | 0.3 | 0.3 | khớp |
| bảng 5.4 | f1 CI cao | 0.6 | 0.5977 | khớp |
| 5.5.2 | ca formulaic bắt đúng | 16 | 16 | khớp |
| 5.5.2 | ca formulaic tổng | 16 | 16 | khớp |
| 5.5.2 | ca vi phạm bị bỏ sót: paraphrase | 10 | 10 | khớp |
| 5.5.2 | ca vi phạm bị bỏ sót: number_words | 5 | 5 | khớp |
| 5.5.2 | ca vi phạm bị bỏ sót: abbreviation | 5 | 5 | khớp |
| 5.5.2 | ca vi phạm bị bỏ sót: long_sentence | 4 | 4 | khớp |
| 5.5.2 | tổng ca vi phạm bị bỏ sót | 24 | 24 | khớp |
| 5.5.2 | ca hợp lệ bị báo nhầm | 14 | 14 | khớp |
| 5.5.2 | báo nhầm là câu phủ định (negation_trap) | 7 | 7 | khớp |
| 5.5.2 | báo nhầm là nội dung hợp pháp chứa từ khoá (các kiểu còn lại) | 7 | 7 | khớp |
| 5.5.2 | ca hợp lệ tổng | 40 | 40 | khớp |
| 5.5.2 | ca bị luật của luật khác kích hoạt | 0 | 0 | khớp |
| bảng 5.5 | TP | 24 | 24 | khớp |
| bảng 5.5 | FP | 15 | 15 | khớp |
| bảng 5.5 | FN | 0 | 0 | khớp |
| bảng 5.5 | TN | 9 | 9 | khớp |
| bảng 5.5 | UNCHECKED | 0 | 0 | khớp |
| bảng 5.5 | N | 48 | 48 | khớp |
| bảng 5.5 | precision | 0.62 | 0.6154 | khớp |
| bảng 5.5 | precision CI thấp | 0.46 | 0.4615 | khớp |
| bảng 5.5 | precision CI cao | 0.76 | 0.7647 | khớp |
| bảng 5.5 | recall | 1.0 | 1.0 | khớp |
| bảng 5.5 | F1 | 0.76 | 0.7619 | khớp |
| bảng 5.5 | F1 CI thấp | 0.63 | 0.6316 | khớp |
| bảng 5.5 | F1 CI cao | 0.87 | 0.8667 | khớp |
| 5.5.3 | số bản ghi pipeline | 48 | 48 | khớp |
| 5.5.3 | FP pipeline: lawful_variant | 8 | 8 | khớp |
| 5.5.3 | FP pipeline: negation_trap | 5 | 5 | khớp |
| 5.5.3 | FP pipeline: number_words | 1 | 1 | khớp |
| 5.5.3 | FP pipeline: long_sentence | 1 | 1 | khớp |
| 5.5.3 | ca có mục khác bị gắn cờ (kể cả cờ toàn văn, ref rỗng) | 48 | 48 | khớp |
| 5.5.3 | trung bình số mục khác bị gắn cờ (tính cả cờ toàn văn) | 5.4 | 5.4167 | khớp |
| 5.5.3 | ca có ít nhất một Điều khác (có số) bị gắn cờ | 48 | 48 | khớp |
| 5.5.3 | trung bình số ĐIỀU khác bị gắn cờ (không tính cờ toàn văn) | 5.4 | 4.4167 | LỆCH |
| 5.6 | số cờ trên hợp đồng nền | 8 | 8 | khớp |
| 5.6 | cờ warning | 7 | 7 | khớp |
| 5.6 | cờ critical | 1 | 1 | khớp |
| 5.6 | Điều đã kiểm | 11 | 11 | khớp |
| 5.6 | ca hợp lệ ở Điều nền bị cờ: bị gắn cờ | 14/21 | 14/21 | khớp |
| 5.6 | ca hợp lệ ở Điều nền không cờ (Điều 4) | 1/3 | 1/3 | khớp |
| 5.6 | tổng FP khớp bảng 5.5 | 15 | 15 | khớp |
| bảng 5.7 | old TP | 16 | 16 | khớp |
| bảng 5.7 | old FP | 16 | 16 | khớp |
| bảng 5.7 | old FN | 0 | 0 | khớp |
| bảng 5.7 | old precision | 0.5 | 0.5 | khớp |
| bảng 5.7 | old recall | 1.0 | 1.0 | khớp |
| bảng 5.7 | old F1 | 0.67 | 0.6667 | khớp |
| bảng 5.7 | new TP | 8 | 8 | khớp |
| bảng 5.7 | new FP | 8 | 8 | khớp |
| bảng 5.7 | new FN | 8 | 8 | khớp |
| bảng 5.7 | new precision | 0.5 | 0.5 | khớp |
| bảng 5.7 | new recall | 0.5 | 0.5 | khớp |
| bảng 5.7 | new F1 | 0.5 | 0.5 | khớp |
| bảng 5.7 | REPORT.md chứa 0.50 [0.3125, 0.6875] (chương làm tròn 2 chữ số) | 0.50 [0.3125, 0.6875] | có trong REPORT.md | khớp |
| bảng 5.7 | REPORT.md chứa 0.50 [0.2308, 0.75] (chương làm tròn 2 chữ số) | 0.50 [0.2308, 0.75] | có trong REPORT.md | khớp |
| bảng 5.7 | REPORT.md chứa 1.00 [1.0, 1.0] (chương làm tròn 2 chữ số) | 1.00 [1.0, 1.0] | có trong REPORT.md | khớp |
| bảng 5.7 | REPORT.md chứa 0.50 [0.25, 0.7647] (chương làm tròn 2 chữ số) | 0.50 [0.25, 0.7647] | có trong REPORT.md | khớp |
| bảng 5.7 | REPORT.md chứa 0.67 [0.4762, 0.8148] (chương làm tròn 2 chữ số) | 0.67 [0.4762, 0.8148] | có trong REPORT.md | khớp |
| bảng 5.7 | REPORT.md chứa 0.50 [0.25, 0.6897] (chương làm tròn 2 chữ số) | 0.50 [0.25, 0.6897] | có trong REPORT.md | khớp |
| BO_TEST_HOI_DONG: kiểm tra nhãn | tổng số ca trong bảng kiểm | 112 | 112 | khớp |
| BO_TEST_HOI_DONG: kiểm tra nhãn | số ca 'ĐÚNG' | 101 | 101 | khớp |
| BO_TEST_HOI_DONG: kiểm tra nhãn | số ca 'ĐÚNG – CÓ LƯU Ý' | 10 | 10 | khớp |
| BO_TEST_HOI_DONG: kiểm tra nhãn | số ca 'CẦN BẠN XEM' | 1 | 1 | khớp |
| BO_TEST_HOI_DONG: kiểm tra nhãn | số ca 'SAI' | 0 | 0 | khớp |
| bảng 5.9 | tag injection-frozen | e268fcb | e268fcb | khớp |
| bảng 5.9 | tag injection-v2-frozen | fab1cef | fab1cef | khớp |
| bảng 5.9 | commit 6ba982d | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 04f1e6c | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit f23ba86 | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 84c8d5e | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 087256a | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 7148b39 | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit ae9e230 | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 78d4437 | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit 551e9e2 | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit ed30fdd | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit fab1cef | tồn tại | tồn tại | khớp |
| bảng 5.9 | commit e268fcb | tồn tại | tồn tại | khớp |
| bảng 5.8 (RQ3) | báo nhầm luật cố định (%) | 35 | 35.0 | khớp |
| mục 5.5.3 / bảng 5.8 | báo nhầm judge (%) = 15/24 | 62 | 62.5 | khớp |
