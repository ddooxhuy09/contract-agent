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
