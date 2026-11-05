# RAG-only trước và sau khi bật lại chunk luật lao động (2026-11-05)

Câu hỏi: sửa cờ `is_effective` cho Bộ luật Lao động 2019 (45/2019/QH14), Nghị định 145/2020/NĐ-CP và Luật An toàn vệ sinh lao động 2015 (84/2015/QH13) (`docs/kiem_tra_hieu_luc.md`) có làm truy xuất tốt hơn không?

## Cách làm
- Cùng benchmark v04 (34 ca), cùng mã (commit `a7fdfb7`), chạy RAG-only không gọi Gemini trên **bản sao cách ly** của kho (`evaluation/docker-compose.eval.yml`), không phải DB đang dùng.
- Lần 1: bản sao nguyên trạng (cờ chưa sửa). Lần 2: sau khi chạy `scripts.fix_labor_effectivity --apply` trên bản sao (2064 chunk; hoàn tác bằng `--revert labor_eff_20261105_105621`).
- Thư mục chạy cục bộ, không đưa vào git (mỗi thư mục khoảng 100 MB): `runs/rag_only_prefix_20261105/` và `runs/rag_only_labor_eff_fix_20261105/`.

## Kết quả (giai đoạn `final_retrieval`, n = 34)
| Chỉ số | Trước | Sau |
|---|---:|---:|
| Exact provision recall (= recall@5) | 0,201 | 0,230 |
| Cross-document coverage | 0,284 | 0,373 |
| MRR | 0,260 | 0,275 |
| Pooled precision@5 | 0,071 | 0,076 |
| Explicit distractor retrieval rate | 0,000 | 0,000 |

Lần chạy trước khi sửa trùng kết quả cũ (recall 0,201; MRR 0,260 của `rag_only_chunker_asof_20261103`), nên các thay đổi mã gần đây không làm đổi kết quả.

## Theo từng ca
13 trong 34 ca đổi điểm, nhưng chỉ 3 ca đổi recall:
- Tốt lên: `MIX-006` (cộng tác viên làm cố định, 0 → 1) và `MIX-003` (làm thêm ngày nghỉ hằng tuần, 0 → 1).
- Xấu đi: `MIX-009` (đặt cọc dịch vụ dân sự, 1 → 0): nhiều khả năng do các điều của Bộ luật Lao động giờ cạnh tranh với kết quả Bộ luật Dân sự (chưa kiểm tra trace để xác nhận).
- Vẫn 0 sau khi sửa: `MIX-002`, `MIX-008`, `TEMP-014` (câu hỏi về đặt cọc, giữ bản chính CCCD). Chunk Bộ luật Lao động giờ được phép truy xuất nhưng điều kỳ vọng vẫn không vào top 5; nguyên nhân chưa điều tra (xếp hạng hoặc lọc, không còn là cờ hiệu lực).

## Cách đọc
- Tổng cộng +1,0 điểm recall trên 34 ca (từ 6,83 lên 7,83): mức cải thiện nhỏ và n quá bé để kết luận có ý nghĩa thống kê. Một ca xấu đi cho thấy bật lại một kho lớn có đánh đổi.
- Nhãn của v04 là bản nháp tổng hợp (xem `evaluation_results/README.md`), nên đây là độ khớp cấu trúc giữa điều luật truy xuất và điều luật kỳ vọng, không phải đánh giá đúng sai pháp lý.
- Số tuyệt đối vẫn thấp (recall@5 0,230). Sửa cờ hiệu lực là cần nhưng chưa đủ.

## Điều tra ba ca vẫn 0 (MIX-002, MIX-008, TEMP-014)
Đã xem trace của lần chạy sau khi sửa và chạy truy vấn đọc-chỉ trên kho đang dùng. Chưa sửa mã truy xuất.

| Ca | Điều kỳ vọng | Nguyên nhân tìm được |
|---|---|---|
| TEMP-014 | Điều 20 khoản 1 Bộ luật Lao động 2012 | Không phải lỗi truy xuất: Bộ luật 2012 (10/2012/QH13) có trong kho (243 chunk) nhưng trạng thái 2, hết hiệu lực 2021-01-01, nên cả 243 chunk có `is_effective=false` và chỉ mục vector chỉ chứa chunk còn hiệu lực. Ngày `as_of_date` không bật lại văn bản cũ. Hệ thống trả đúng Điều 17 khoản 1 Bộ luật 2019 ở hạng 1. README của v04 cũng nói hệ thống chủ yếu truy xuất luật hiện hành. |
| MIX-002 | Điều 17 khoản 2 BLLĐ 2019 | Nếu tìm riêng trong Bộ luật Lao động, Điều 17 đứng hạng 2-3. Nhưng bước hạt giống toàn kho (k = 4) bị 3-4 chunk gần như trùng của Nghị định 143/2024 (bảo hiểm tai nạn lao động tự nguyện) chiếm hết; Bộ luật Lao động chỉ vào qua tìm trong "văn bản liên quan" với k = 2 trên 8 văn bản (`legal_graph_rag.py:235`), nên điều kỳ vọng bị cắt. Phụ: bước viết lại truy vấn làm mất chữ số ("5 triệu" thành "triệu", "5.000.000" thành "000 000"). |
| MIX-008 | Điều 13 khoản 1 và Điều 17 khoản 1 BLLĐ 2019 | Với câu hỏi diễn đạt "CCCD bản chính", embedding xếp Điều 17 ở hạng 28 trong Bộ luật Lao động (sau Điều 14, 76, 162); bước hạt giống toàn kho lấy Thông tư BNG và Nghị định 27/2014 không liên quan. Từ "giữ bản chính giấy tờ tùy thân" có nguyên văn trong Điều 17 khoản 1, nên nhánh từ khóa lẽ ra giúp được (xem dưới). |

### Phát hiện chung: nhánh tìm từ khóa (FTS) của hybrid search không hoạt động
`PgLegalVectorSearch._fts_search` dùng `plainto_tsquery('simple', ...)`, tức nối mọi từ bằng AND. Với truy vấn của MIX-002 sau khi viết lại, số chunk khớp là **0** trên toàn kho (truy vấn 3 từ "đặt cọc người lao động" khớp 71 chunk). Trong cả ba ca, mọi lần gọi `fts_search` đều trả 0 chunk, nên "hybrid" thực chất chỉ là vector. Chuyển sang OR đơn thuần cũng chưa đủ: thử trong riêng Bộ luật Lao động, `ts_rank_cd` xếp các điều chứa từ chung ("người lao động") lên trước, Điều 17 không vào top 6. Cần xây truy vấn có chọn từ hiếm hoặc dùng cách chấm điểm kiểu BM25.

### Hướng xử lý đề xuất (mỗi thay đổi đo riêng bằng RAG-only trên v04)
1. Sửa nhánh FTS (truy vấn không AND toàn bộ, ưu tiên từ hiếm).
2. Đa dạng hóa hạt giống: giới hạn số chunk mỗi điều/văn bản trong k = 4.
3. Giữ chữ số khi viết lại truy vấn.
4. Với hợp đồng lao động đã nhận diện được, thêm một lượt tìm trong phạm vi Bộ luật Lao động và nghị định hướng dẫn (lưu ý: gợi ý nhãn lao động trước đây làm recall giảm, xem `RAG_SCOPE_ABLATION.md`, nên cần kiểm chứng).
TEMP-014 chỉ giải quyết được nếu bổ sung truy xuất văn bản đã hết hiệu lực theo ngày, đó là tính năng mới, ngoài phạm vi tuần này.
