# Phân tích lỗi trên tập dev (hybrid, `--only-covered`)

Run: `runs/dev_hybrid_20261109_101622` (n=216). Chỉ đọc `predictions.jsonl` và đọc DB; không sửa code, không sửa DB. Mọi số liệu lấy từ output thật.

## Tổng quan 45 câu `rank = null` (21% của 216)
- 26/45 đã tìm đúng văn bản (`doc_rank` khác null) nhưng sai Điều; 19/45 sai cả văn bản.
- So với mode vector (cùng 216 câu): vector đúng mà hybrid sai = 7 câu; hybrid đúng mà vector sai = 0 câu; cả hai sai = 38 câu.
- FTS đúng được 7 câu và không câu nào mà vector sai.

## Phân loại 20 câu ngẫu nhiên (seed 42, rút từ 45 câu null)
| Nhóm | Số câu | Câu (#) |
|---|---:|---|
| A. Thiếu văn bản | 0 | (không có: lọc `article_searchable` đã loại trước) |
| B. Đúng văn bản, sai Điều | 9 | 3, 5, 6, 8, 9, 10, 16, 17, 18 |
| C. Gold bị lọc hiệu lực | 1 | 15 |
| D. Câu hỏi mơ hồ (không nêu văn bản, nhiều văn bản cùng chủ đề) | 4 | 1, 2, 14, 19 |
| E. Lỗi xếp hạng (vector có trong top 10, hybrid mất) | 4 | 7, 11, 12, 20 |
| F. Truy xuất nhầm văn bản dù câu hỏi khá cụ thể | 2 | 4, 13 |

Cách gán nhóm là đánh giá thủ công của tôi dựa trên câu hỏi, nhãn gold, trạng thái gold trong DB và top kết quả; nhóm D và F là phán đoán, không có người kiểm chéo.

Chi tiết từng câu (qid rút gọn 8 ký tự; "vec" = rank của mode vector):
| # | qid | Gold | Quan sát | Nhóm |
|---|---|---|---|---|
| 1 | e4a526f7 | 167/2013 Đ5 | "Ném đất vào xe của người khác bị phạt bao nhiêu?", top toàn văn bản khác; vec cũng trượt | D |
| 2 | 31a2b754 | 104/2016/QH13 Đ30 | Câu hỏi về Bộ Tài chính, top là các thông tư 2025-2026; vec trượt | D |
| 3 | 0ae92a99 | 11/2020/TT-BGDĐT Đ5 | Văn bản đúng ở rank 1 nhưng là chunk không có Điều (phần mở đầu) | B |
| 4 | 67bf93ef | 41/2019/QH14 Đ19 | Top là NĐ 2026 và luật khác; vec trượt | F |
| 5 | 51093c2e | 24/2018/TT-BYT Đ4 | Văn bản đúng ở rank 3, sai Điều (Đ1); văn bản anh em 05/2020/TT-BYT cùng nội dung | B |
| 6 | 4fa97766 | 167/2013 Đ55 | Top là Đ52, Đ57, Đ56 cùng nghị định | B |
| 7 | 38e2cfc4 | 24/2018/TT-BYT Đ2 | Đúng văn bản ở rank 1 (Đ1); vec tìm đúng ở rank 9 | E |
| 8 | 2cd9e9ab | 24/2018/TT-BYT Đ4 | Đúng văn bản ở rank 1 (Đ1) | B |
| 9 | d001ff18 | 167/2013 Đ5 | Top là Đ59, Đ61 cùng nghị định | B |
| 10 | 23d7532c | 44/2020 Đ27 | Top là Đ26, Đ22 cùng nghị định | B |
| 11 | 9dc15c94 | 26/2020/TT-BYT Đ1 | vec tìm đúng ở rank 6, hybrid trượt | E |
| 12 | 0dcd23ee | 24/2018/TT-BYT Đ2 | vec rank 9, hybrid trượt | E |
| 13 | e9efc5d3 | 41/2019/QH14 Đ65 | Top toàn NĐ 94/2025 | F |
| 14 | d1499d10 | 167/2013 Đ49 | Top 4 thông tư không liên quan | D |
| 15 | d6e0c0d1 | 08/2020/NĐ-CP Đ6 và 39/2009/QH12 Đ2 | Gold thứ nhất: văn bản `status_flag=2`, 0/5 chunk còn hiệu lực nên bị lọc; gold thứ hai vẫn tìm được nhưng không lên top | C |
| 16 | edf01202 | 11/2020/TT-BGDĐT Đ9 | Văn bản đúng ở rank 3, chunk không có Điều | B |
| 17 | 5ce131cc | 11/2020/TT-BGDĐT Đ10 | Văn bản đúng ở rank 3, chunk không có Điều | B |
| 18 | 72e11998 | 102/2014 Đ36 | Top là Đ10, Đ37 cùng nghị định | B |
| 19 | 0413e796 | 167/2013 Đ5 | "Say rượu, bia gây mất trật tự..." top là văn bản quân đội | D |
| 20 | e5474143 | 41/2019/QH14 Đ54 | Văn bản đúng ở rank 2 (Đ52); vec rank 9 | E |

## Phát hiện cấu trúc (có số đo, chưa sửa)
1. **FTS làm nhiễu hybrid.** `_fts_search` dùng `plainto_tsquery('simple', <cả câu hỏi>)`, tức bắt buộc chunk chứa tất cả từ. Kết quả: mode `fts` rỗng ở 50/216 câu và chỉ đúng 7/216 câu. Khi trộn RRF với trọng số bằng nhau, hit đứng đầu của FTS (điểm RRF ≈ 0,016) chen vào rank 2 ở **150/216** câu; 165/216 câu có ít nhất một mục chỉ đến từ FTS trong top 10. Các chunk hay lặp lại nhất ở rank 1-3: `02/2025/tt-bkhdt` Điều 3 (43 lần), `139/2026/nd-cp` Điều 5 (35 lần), `07/2025/tt-btnmt` Điều 5 (16 lần).
2. **Hệ quả đo được:** phân bố rank của hybrid có 136 câu ở rank 1, chỉ 2 câu ở rank 2 nhưng 22 câu ở rank 3. Hybrid không tốt hơn vector: R@5 0,7731 so với 0,7917, R@10 0,7917 so với 0,8241 (cùng 216 câu; CI chồng lấp nhiều nên chưa kết luận được là hybrid kém hơn).
3. **Chunk không có Điều** (phần mở đầu, path dạng `.PREAMBLE`, `article=None`) chiếm 150/2091 mục trong top 10 và tính là một mục xếp hạng. Chúng đẩy kết quả có Điều xuống.
4. **Văn bản anh em / bản trùng nội dung** (ví dụ 24/2018/TT-BYT và 05/2020/TT-BYT) làm các câu cùng mẫu bị lẫn.
5. **Thiên lệch tập covered:** `--only-covered` giữ 216/523 câu dev (41%), toàn bộ là văn bản còn hiệu lực trong DB. Không đại diện cho 3.196 câu gốc. Xem `coverage.json`.

## Có phải bug không?
- **Chuẩn hoá số hiệu và token `D<số>`: không có lỗi.** 671/724 văn bản gold có trong DB; 0 văn bản gold có bản trùng chỉ khác số 0 đầu (DB có 49 cặp như vậy nhưng không cặp nào thuộc văn bản gold).
- Mục 1 và 3 là **hành vi thiết kế của hệ thống** (trọng số RRF bằng nhau, FTS dùng AND, chunk mở đầu không bị loại), không phải bug dễ thấy. Điều chỉnh chúng là tinh chỉnh tham số, nên **tôi không sửa** theo quy tắc "không chỉnh để làm đẹp số". Cần bạn quyết định có tinh chỉnh trên dev hay không (đề xuất ở báo cáo).
