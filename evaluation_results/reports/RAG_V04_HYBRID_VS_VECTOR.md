# RAG-only v04: hybrid (cũ) so với vector-only

Mục đích: kiểm tra "không làm hỏng" khi bỏ nhánh FTS khỏi truy xuất pháp luật. v04 có 34 ca với nhãn nháp tổng hợp, **không phải bằng chứng chính**. Quy tắc quyết định được ghi trước khi chạy trong `docs/NHAT_KY_THAY_DOI.md` (commit `087256a`).

## Cách chạy
- Worker cách ly `contractlens-eval-01a154eb` (bản sao DB/Neo4j), `evaluation.rag_only`, không có khóa Gemini, 0 lượt gọi model, corpus luật không đổi trước/sau.
- Cùng commit `087256a`, mã sạch (`app/`, `evaluation/`). Hai lần chạy chỉ khác `LEGAL_RETRIEVAL_MODE`.
- (a) `rag_v04_hybrid_20261109` (`hybrid`), (b) `rag_v04_vector_20261109` (`vector`). 34/34 hoàn tất mỗi lần.

## Kết quả (`final_retrieval`, n=34)
| Chỉ số | (a) hybrid | (b) vector-only |
|---|---:|---:|
| Exact provision recall | 0,2990 | 0,2990 |
| Số ca tương đương (recall × 34) | 10,17 | 10,17 |
| Số ca có recall > 0 | 15 | 15 |
| MRR | 0,3000 | 0,3000 |
| R@1 / R@3 / R@5 / R@10 | 0,1422 / 0,2304 / 0,2696 / 0,2990 | giống hệt |
| Cross-document coverage | 0,4461 | 0,4608 |
| Thời gian chạy toàn bộ 34 ca (gồm index 7 hợp đồng) | 101 s | 59 s |

## Ca đổi điểm (6/34 ca khác nhau ở ít nhất một chỉ số)
| Ca | Nhiệm vụ | Thay đổi (hybrid → vector) |
|---|---|---|
| MIX-020 | multi_hop | cross-document coverage 0,0 → 0,5; recall giữ 0 |
| MIX-017 | risk | số chunk trả về 3 → 7; recall/MRR giữ 1,0 |
| MIX-016 | risk | số chunk trả về 3 → 4; recall/MRR giữ 1,0 |
| MIX-012 | risk | số chunk trả về 4 → 10; recall giữ 0 |
| MIX-014 | multi_hop | số chunk trả về 4 → 6; recall giữ 0 |
| MIX-011 | risk | số chunk trả về 7 → 9; recall giữ 0 |

Không có ca nào đổi recall hoặc MRR. Chỉ một ca đổi điểm chất lượng (MIX-020, tăng). Năm ca còn lại chỉ trả nhiều chunk hơn: vector-only không có nhánh FTS lọc/giảm số kết quả, nên ngữ cảnh đưa vào LLM có thể dài hơn (chưa đo ảnh hưởng chi phí/độ chính xác sinh đáp án).

## Quyết định (theo quy tắc khai báo trước)
`recall(b) × 34 = 10,17 ≥ recall(a) × 34 − 1 = 9,17` ⇒ **đổi mặc định ứng dụng sang vector-only** (`legal_retrieval_mode = "vector"` trong `app/core/settings.py`). Có thể quay lại hybrid bằng biến môi trường `LEGAL_RETRIEVAL_MODE=hybrid`, không cần đổi code. `pytest tests/unit tests/evaluation`: 311 passed, 1 skipped.

## Giới hạn
- n=34, nhãn nháp tổng hợp, recall chỉ 0,299: kiểm tra này có độ nhạy thấp, kết luận chỉ là "không thấy hỏng".
- Benchmark pháp luật chung (zac2021, test n=556) cho thấy vector hơn hybrid cũ có ý nghĩa (MRR@10 0,6816 so với 0,6420); v04 không mâu thuẫn nhưng cũng không xác nhận thêm.
- FTS có thể giúp với truy vấn chứa số hiệu văn bản hoặc từ khoá đúng chữ; v04 và zac2021 không đo trường hợp này. Chưa đánh giá.
- Chưa đo phần sinh đáp án (không chạy Gemini).
