# Reranking ablation trên corpus hiện có (offline)

## Phương pháp

Chạy lại thứ hạng trên đúng candidate pool đã quan sát trong 34 trace của `rag_only_no_labor_hint`. Không gọi model, không kết nối PostgreSQL/Neo4j, không đổi corpus. Candidate pool lấy từ sự kiện `graph_expanded` (trước `_order_for_prompt`), seed order lấy từ thứ tự hybrid search đã lưu.

Baseline tái lập đúng **34/34** thứ tự `final_retrieval` đã lưu; các policy được khai báo trước khi đọc gold, gold chỉ được load sau khi mọi bảng xếp hạng đã cố định.

as_of dùng cho hiệu lực = `2026-10-20` (ngày bắt đầu run).
Thành phần candidate pool: {'seed': 143, 'related': 48, 'sibling': 48}.
Baseline có ít nhất một chunk expansion xếp trên một seed ở **16/34** case.

Các policy:

| Policy | Cách xếp |
|---|---|
| saved_final | Thứ tự thực tế đã lưu trong trace (tham chiếu, không phải policy) |
| baseline | Thứ tự production trước thay đổi (đóng băng): hiệu lực → loại văn bản → status/năm → role → score |
| seed_normative | hiệu lực → role (seed trước) → loại văn bản → status/năm → cosine |
| seed_search | hiệu lực → role → giữ đúng thứ tự hybrid search của seed → cosine/loại văn bản |
| seed_cosine | hiệu lực → role → cosine → loại văn bản; seed chỉ có FTS xếp dưới seed có cosine |
| seed_only | bỏ toàn bộ graph expansion, giữ seed theo thứ tự search (tham chiếu trần) |
| production_new | gọi trực tiếp `LegalGraphRag._order_for_prompt` sau khi sửa (kiểm tra implementation) |

## Kết quả tổng

| Policy | n | R@1 | R@3 | R@5 | R@10 | MRR | Coverage | Số chunk trả về |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| saved_final | 34 | 0.098 | 0.108 | 0.147 | 0.201 | 0.185 | 0.201 | 6.412 |
| baseline | 34 | 0.098 | 0.108 | 0.147 | 0.201 | 0.185 | 0.201 | 6.412 |
| seed_normative | 34 | 0.098 | 0.162 | 0.201 | 0.201 | 0.201 | 0.201 | 6.412 |
| seed_search | 34 | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | 0.201 | 6.412 |
| seed_cosine | 34 | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | 0.201 | 6.412 |
| seed_only | 34 | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | 0.201 | 4.088 |
| production_new | 34 | 0.142 | 0.191 | 0.201 | 0.201 | 0.260 | 0.201 | 6.412 |

## Theo nhiệm vụ (R@5 / MRR)

| Policy | Task | n | R@5 | MRR |
|---|---|---:|---:|---:|
| saved_final | qa | 13 | 0.077 | 0.060 |
| saved_final | multi_hop | 7 | 0.214 | 0.357 |
| saved_final | risk | 13 | 0.192 | 0.231 |
| saved_final | classification | 1 | 0.000 | 0.000 |
| baseline | qa | 13 | 0.077 | 0.060 |
| baseline | multi_hop | 7 | 0.214 | 0.357 |
| baseline | risk | 13 | 0.192 | 0.231 |
| baseline | classification | 1 | 0.000 | 0.000 |
| seed_normative | qa | 13 | 0.192 | 0.090 |
| seed_normative | multi_hop | 7 | 0.262 | 0.381 |
| seed_normative | risk | 13 | 0.192 | 0.231 |
| seed_normative | classification | 1 | 0.000 | 0.000 |
| seed_search | qa | 13 | 0.192 | 0.231 |
| seed_search | multi_hop | 7 | 0.262 | 0.405 |
| seed_search | risk | 13 | 0.192 | 0.231 |
| seed_search | classification | 1 | 0.000 | 0.000 |
| seed_cosine | qa | 13 | 0.192 | 0.231 |
| seed_cosine | multi_hop | 7 | 0.262 | 0.405 |
| seed_cosine | risk | 13 | 0.192 | 0.231 |
| seed_cosine | classification | 1 | 0.000 | 0.000 |
| seed_only | qa | 13 | 0.192 | 0.231 |
| seed_only | multi_hop | 7 | 0.262 | 0.405 |
| seed_only | risk | 13 | 0.192 | 0.231 |
| seed_only | classification | 1 | 0.000 | 0.000 |
| production_new | qa | 13 | 0.192 | 0.231 |
| production_new | multi_hop | 7 | 0.262 | 0.405 |
| production_new | risk | 13 | 0.192 | 0.231 |
| production_new | classification | 1 | 0.000 | 0.000 |

## So với baseline (paired, n=34)

| Policy | R@5 tốt hơn | bằng | kém hơn | ΔR@5 TB | ΔMRR TB | Δ hạng gold TB | Case được cứu | Case bị đẩy xuống |
|---|---:|---:|---:|---:|---:|---:|---|---|
| seed_normative | 3 | 31 | 0 | 0.054 | 0.016 | 0.324 | TEMP-009, TEMP-011, MIX-009 | — |
| seed_search | 3 | 31 | 0 | 0.054 | 0.075 | 0.588 | TEMP-009, TEMP-011, MIX-009 | — |
| seed_cosine | 3 | 31 | 0 | 0.054 | 0.075 | 0.588 | TEMP-009, TEMP-011, MIX-009 | — |
| seed_only | 3 | 31 | 0 | 0.054 | 0.075 | 0.588 | TEMP-009, TEMP-011, MIX-009 | — |
| production_new | 3 | 31 | 0 | 0.054 | 0.075 | 0.588 | TEMP-009, TEMP-011, MIX-009 | — |

Δ hạng gold dương nghĩa là chunk gold đầu tiên lên gần top hơn (None được quy ước hạng 99).

## Đọc kết quả

- Graph expansion không thêm evidence gold nào trong tập này: coverage của seed và final bằng nhau ở cả 34 case. Vì vậy thay đổi R@5/MRR ở đây hoàn toàn do thứ hạng, không do candidate pool.
- Policy đưa seed lên trước expansion sửa trực tiếp hiện tượng final R@5 thấp hơn seed R@5.
- `production_new` phải trùng `seed_search`; nếu hai dòng khác nhau thì bản sửa production chưa đúng.
- `seed_cosine` và `seed_search` khác nhau ở cách xử lý seed chỉ có FTS (score = RRF, rất nhỏ). Đây là điểm cần chọn có chủ đích, không nên tối ưu theo từng case.
- `seed_only` là tham chiếu trần cho ranking, không phải đề xuất bỏ GraphRAG. Expansion vẫn có thể hữu ích cho ngữ cảnh sinh đáp án, nhưng lần này generation chưa được đo.

## Giới hạn

- n=34, nhãn gold là synthetic draft chưa được chuyên gia pháp lý xác minh; chênh lệch nhỏ có thể do nhiễu.
- Đánh giá offline trên candidate pool đã lưu, không chứng minh hành vi trên corpus/câu hỏi khác.
- Chưa có temporal retrieval, chưa có generation/answer quality; date chỉ dùng để xếp hiệu lực.
- Không sửa corpus, không đổi `is_effective`, không dùng gold để chọn policy.
