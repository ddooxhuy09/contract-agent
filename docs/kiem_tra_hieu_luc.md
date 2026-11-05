# Kiểm tra trạng thái hiệu lực của luật lao động trong cơ sở dữ liệu

Ngày kiểm: 2026-11-05. Đo trên Postgres đang chạy (`docker compose`, bảng `legal_documents` và `legal_embeddings`), chỉ đọc.

## Kết luận
**Trường hợp (b) trong kế hoạch: cờ sai.** Toàn bộ chunk của ba văn bản luật lao động chính có `is_effective = false`, nên bị loại khỏi tìm kiếm vector (`PgLegalVectorSearch` lọc `c.is_effective`, `app/infrastructure/vector/pg_search.py`). Hệ quả: truy vấn về thử việc không thể trả về Điều 25 Bộ luật Lao động 2019.

| Văn bản | doc_id | `status_flag` | Số chunk | `is_effective=true` trước | sau sửa |
|---|---|---:|---:|---:|---:|
| 45/2019/QH14 (Bộ luật Lao động 2019) | 139264 | 4 | 874 | 0 | 874 |
| 145/2020/NĐ-CP | 152668 | 4 | 674 | 0 | 674 |
| 84/2015/QH13 (Luật An toàn vệ sinh lao động) | 70811 | 4 | 516 | 0 | 516 |

## Nguyên nhân
- Cả ba văn bản mang `status_flag = 4` ("Hết hiệu lực một phần") từ metadata vbpl. Cờ này đặt ở cấp văn bản và được sao xuống mọi nút (45/2019/QH14: 220/220 điều có trạng thái 4, không điều nào có `eff_to`).
- Quy tắc đồng bộ chỉ coi trạng thái 1 hoặc 5 là còn hiệu lực (`trg_sync_embedding_effective`, `schema.sql`), nên trạng thái 4 đồng nghĩa "không hiệu lực" khi truy xuất.
- Toàn kho có 2036 văn bản trạng thái 4 với 216.957 chunk `is_effective=false` (21% kho). Báo cáo `evaluation_results/reports/STATUS4_AUDIT.md` đã ghi nhận hiện tượng này và kết luận dữ liệu không đủ để lọc theo ngày: nút trạng thái 4 chỉ có `eff_from`, không có `eff_to`.
- Trong code, `agents/effectivity.evaluate_document_effectivity` vẫn coi trạng thái 4 là được trích dẫn, nên chỉ lớp truy xuất bị lệch.

## Đã làm
- `scripts/fix_labor_effectivity.py`: bật lại `is_effective` cho chunk của ba văn bản trên, trừ chunk dưới nút đã hết hiệu lực (trạng thái 2/3 hoặc `eff_to` đã qua; ở ba văn bản này không có nút nào như vậy). Mặc định chỉ đếm, `--apply` mới ghi, `--revert <RUN_TAG>` hoàn tác.
- Đã chạy `--apply` trên DB đang chạy: 2064 chunk được bật lại, run_tag `labor_eff_20261105_094046`, id lưu ở bảng `legal_eff_fix_backup`. Khởi động lại API không làm đổi các cờ này.
- Kiểm tra truy xuất: truy vấn "thử việc không quá 60 ngày công việc đòi hỏi trình độ cao đẳng" trả Điều 25 khoản 1, 2, 3 của Bộ luật Lao động 2019 (`139264.C3.M1.D25.K1-3`). Trước sửa, ba văn bản này không thể xuất hiện trong kết quả.

## Giới hạn cần ghi nhận
- Chỉ sửa ba văn bản trong danh sách cho phép. 2033 văn bản trạng thái 4 còn lại giữ nguyên (chunk vẫn bị loại), vì dữ liệu không cho biết điều nào đã hết hiệu lực.
- Việc coi ba văn bản này là còn hiệu lực dựa vào quyết định của người thực hiện đề tài. **Cần đối chiếu ngày hiệu lực và tình trạng với nguồn chính thống (vanban.chinhphu.vn hoặc thuvienphapluat.vn) và ghi link, ngày truy cập vào mục này.** Một số điều của Nghị định 145/2020 có thể đã bị sửa đổi hoặc thay thế; kho hiện không biết điều nào.
- Cờ ở bảng phân cấp (`legal_articles.status_flag` …) vẫn là 4; chỉ cờ truy xuất `legal_embeddings.is_effective` được sửa. Nếu nạp lại hoặc khôi phục DB từ bản sao cũ, cần chạy lại script.
- Truy vấn nêu thẳng tên luật ("theo Bộ luật Lao động 2019 là bao lâu") vẫn có thể lấy nhầm điều khoản "Hiệu lực thi hành" của văn bản khác. Đây là chất lượng truy xuất, tách biệt với lỗi cờ hiệu lực, chưa xử lý.

## Bằng chứng (đầu ra truy vấn, trước sửa)
```
     doc_num      | status_flag | is_effective | count
 145/2020/NĐ-CP   |           4 | f            |   674
 45/2019/QH14     |           4 | f            |   874
 84/2015/QH13     |           4 | f            |   516
```
