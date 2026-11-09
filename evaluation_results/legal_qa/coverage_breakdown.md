# Phân rã 2.257 câu `doc_present_not_searchable`

Chỉ đọc DB (`legal_documents`, `legal_embeddings`), không sửa. Nguồn: `coverage.json` (tạo 2026-11-09) và truy vấn trực tiếp cùng ngày. Mọi số lấy từ output thật.

## Định nghĩa
Câu thuộc nhóm này khi văn bản gold có trong `legal_documents` nhưng **không có chunk nào** thoả điều kiện tìm kiếm của hệ thống: `is_effective` và `embedding IS NOT NULL` và `status_flag IS DISTINCT FROM 2`. Nguyên nhân được gán **loại trừ nhau theo thứ tự ưu tiên**: (1) `status_flag=2`; (2) văn bản không có chunk; (3) có chunk nhưng không chunk nào `is_effective`; (4) có chunk hiệu lực nhưng `embedding` đều NULL; (5) có chunk hiệu lực có embedding nhưng path không có token `D<số>`. Vì thứ tự ưu tiên, văn bản `status_flag=2` cũng thường có `is_effective=false`; số ở dòng (1) không loại bỏ khả năng đó (xem bảng chunk bên dưới).

## Mức văn bản (452 số hiệu gold thuộc nhóm này)
| Nguyên nhân chính | Số văn bản |
|---|---:|
| (1) `status_flag=2` (hết hiệu lực) | 307 |
| (3) mọi chunk `is_effective=false` (văn bản không phải cờ 2) | 130, trong đó `status_flag=4` là 122, `status_flag=1` là 8 |
| (2) không có chunk nào | 9 |
| (4) `embedding` NULL | 4 |
| (5) không có token `D<số>` | 2 |

## Mức câu hỏi (2.257 câu)
| Nguyên nhân | Số câu | Tỷ lệ |
|---|---:|---:|
| (1) văn bản `status_flag=2` | 1.509 | 66,9% |
| (3) chunk `is_effective=false`, văn bản `status_flag` 4 hoặc 1 | 679 (660 ở cờ 4, 19 ở cờ 1) | 30,1% |
| (2) không có chunk | 48 | 2,1% |
| (4) `embedding` NULL | 7 | 0,3% |
| (5) không có token `D<số>` | 4 | 0,2% |
| Hỗn hợp (các văn bản gold của cùng một câu có nguyên nhân khác nhau) | 10 | 0,4% |

Phép cộng: 1.509 + 679 + 48 + 7 + 4 + 10 = 2.257. Nhóm hỗn hợp: 8 câu (ineffective + status2), 1 câu (ineffective + no_article_token), 1 câu (null_embedding + status2).

## Mức chunk (62.495 chunk của các văn bản này)
| Chỉ số | Số chunk |
|---|---:|
| Tổng chunk | 62.495 |
| `is_effective = true` | 4.060 |
| `embedding` khác NULL | 60.711 |
| `is_effective` và có embedding | 3.646 |
| Chunk thuộc văn bản `status_flag=2` | 28.755 |
| …trong đó `is_effective = true` | 3.666 (bị loại do cờ văn bản 2) |

## Điểm đáng chú ý
- **Văn bản "hết hiệu lực một phần" (`status_flag=4`) bị ẩn khỏi tìm kiếm toàn bộ**: 122 văn bản, 660 câu (29% của nhóm, 20,6% của 3.196 câu gốc), vì mọi chunk của chúng có `is_effective=false`. `docs/kiem_tra_hieu_luc.md` đã ghi cờ văn bản được sao xuống mọi nút và chỉ sửa tay 3 văn bản luật lao động. Đây là hành vi của dữ liệu/trigger hiện tại, không phải của benchmark. Có thể làm hệ thống bỏ sót điều còn hiệu lực của văn bản sửa đổi một phần; chưa xác minh ảnh hưởng lên phần hợp đồng và **chưa sửa** (quy tắc: không sửa DB).
- Phần lớn nguyên nhân (67%) là văn bản đã hết hiệu lực hoàn toàn: nếu dataset là bộ Zalo 2021 như người dùng cho biết (chưa kiểm chứng độc lập) thì nhãn gán từ thời điểm đó còn DB phản ánh hiệu lực hiện tại; khi đó đây là lệch thời điểm hơn là lỗi truy xuất. Suy luận, chưa xác minh.
- Embedding NULL ảnh hưởng không đáng kể (7 câu thuần, +1 hỗn hợp).

## Giới hạn
- Truy vấn coverage không áp `_EXCLUDE_TYPES` (loại chunk trong `pg_search`), nên `article_searchable` có thể hơi lạc quan; chưa đo mức chênh.
- Khi một số hiệu có nhiều bản ghi trong `legal_documents`, lấy bản ghi gần "tìm kiếm được" nhất để gán nguyên nhân.
- Bảng này chỉ giải thích nhóm `doc_present_not_searchable`; 162 câu `doc_missing` và 5 câu `doc_searchable_article_missing` không nằm trong đây.
