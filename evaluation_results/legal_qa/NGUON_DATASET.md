# Nguồn gốc `data/dataset.csv`

**Kết luận (cập nhật 2026-11-09): trùng khớp với bộ Hugging Face `DaHaDaHa/zac2021`. Giấy phép: chưa xác định. Người tạo câu hỏi: chưa xác định.**

## Nguồn
- Link: https://huggingface.co/datasets/DaHaDaHa/zac2021 (tài khoản `DaHaDaHa`, tạo trên Hugging Face ngày 2025-08-22 theo API).
- Theo thông tin người dùng cung cấp, đây là dữ liệu Zalo AI Challenge 2021 – Legal Text Retrieval. **Trang Hugging Face không có dataset card và không nói điều đó**; tôi chưa đối chiếu được với nguồn gốc từ Zalo, nên mối liên hệ với cuộc thi là chưa kiểm chứng độc lập.
- Cấu trúc trên HF: cột `question_id` (chuỗi 32 ký tự), `question`, `positive_passages` (1–3 cặp `law_id` + `article_id`). Split gốc của HF: train 2.237 / validation 319 / test 640 (đếm theo `question_id` trùng với file của ta). Repo còn có `processed_legal_corpus.json`; tôi chưa tải và chưa dùng.
- Giấy phép: trang HF và API (`license`, `cardData`) không ghi. **Chưa xác định**, không được giả định là mở.
- Người tạo câu hỏi và cách gán nhãn: không có thông tin trên trang. **Chưa xác định**; không khẳng định do người viết hay do mô hình sinh.

## Đối chiếu với `data/dataset.csv` (đã chạy)
Tải 3 file parquet từ `https://huggingface.co/api/datasets/DaHaDaHa/zac2021/parquet/default/{train,validation,test}/0.parquet`, so theo `qid` = `question_id`; nhãn gold của ta là các cặp (số hiệu `doc_id` trước dấu `+`, số Điều sau dấu `+`), so với (`law_id`, `article_id`) của HF, viết thường.

| Phép so | Số mẫu | Khớp |
|---|---:|---:|
| 20 `question_id` ngẫu nhiên (seed 0): câu hỏi giống hệt | 20 | 20 (100%) |
| 20 `question_id` ngẫu nhiên: tập nhãn gold giống hệt | 20 | 20 (100%) |
| Toàn bộ: `qid` có mặt ở cả hai bên | 3.196 | 3.196 (100%) |
| Toàn bộ: câu hỏi giống hệt | 3.196 | 3.196 (100%) |
| Toàn bộ: tập nhãn gold giống hệt | 3.196 | 3.196 (100%) |

Giới hạn của phép so: chỉ so `question` và nhãn gold. Các cột `title` và `context` của file ta không có trong bảng câu hỏi HF nên chưa đối chiếu; chưa biết chúng đến từ đâu (nghi từ corpus đi kèm nhưng chưa kiểm chứng).

## Thông tin kiểm chứng được từ file và repo
| Mục | Giá trị |
|---|---|
| Đường dẫn | `data/dataset.csv` (bị `.gitignore`, không có lịch sử git) |
| Thời điểm file trên máy | 2026-09-04 20:03 (mtime), 14.242.818 byte |
| SHA-256 | `b9ec964eb33fd64799b410e3d2fc7d9ce20409d472a2c34ade5621063da2604f` |
| Cột | `qid, doc_id, question, title, context` |
| Quy mô | 3.298 dòng, 3.196 `qid`, 724 văn bản gold |

## Ghi chú cho báo cáo
- Có thể ghi "dữ liệu trùng với bộ `DaHaDaHa/zac2021` trên Hugging Face". Chưa nên ghi giấy phép, tác giả câu hỏi hay "benchmark công khai chính thức".
- Split dev/test của ta (`split.json`, chia theo văn bản) **khác** split train/validation/test của HF; không so số liệu trực tiếp với công trình dùng split gốc.
- Script so sánh (dùng `pyarrow`) và file parquet đã tải nằm ngoài repo, không được commit; muốn tái lập thì tải lại 3 file theo URL ở trên.
