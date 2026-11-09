# Nguồn gốc `data/dataset.csv`

**Kết luận: CHƯA XÁC ĐỊNH.** Không tìm được link tải, giấy phép hay tác giả. Không được gọi đây là "benchmark công khai" cho đến khi có thông tin này từ người đưa file vào repo.

## Thông tin kiểm chứng được từ chính file và repo
| Mục | Giá trị | Nguồn |
|---|---|---|
| Đường dẫn | `data/dataset.csv` (bị `.gitignore`, không có lịch sử git) | `.gitignore` dòng 86; `git log -- data/dataset.csv` không có commit |
| Thời điểm file trên máy | 2026-09-04 20:03 (mtime), 14.242.818 byte | `ls -la` |
| SHA-256 | `b9ec964eb33fd64799b410e3d2fc7d9ce20409d472a2c34ade5621063da2604f` | `coverage.json` |
| Cột | `qid, doc_id, question, title, context` | đọc file |
| Quy mô | 3.298 dòng, 3.196 `qid`, 724 văn bản gold | đọc file / `coverage.json` |
| Định dạng nhãn | `doc_id` = `<số hiệu>+<số Điều>`, ví dụ `47/2011/tt-bca+7`; `context` là nội dung Điều | đọc file |
| Mô tả trong repo | "legal single-hop QA set"; `context` giữ làm căn cứ tham chiếu | docstring `scripts/build_qa_benchmark.py`, README mục 5 |

## Đã tìm và kết quả
- Tìm trong repo: git log, README, `docs/`, `scripts/build_qa_benchmark.py`, `tests/evaluation/test_dataset_qa.py`. Không có link, giấy phép, tên tác giả. Chỉ có `docs/` bản phản biện ("Claude outputs/Phản biện đồ án Contract Agent.md") ghi `dataset.csv` "bị gitignore, không rõ giấy phép".
- Tìm web (2026-11-09), tìm theo tên cột và theo nguyên văn một câu hỏi trong file ("Tử tù chết sau khi tiêm thuốc độc ... hỗ trợ mai táng ..."): không có kết quả khớp.
- Đã mở thử và loại:
  - https://huggingface.co/datasets/Anakonkai/nlp-traffic-qa: có `doc_id`, `question`, `title`, `context` nhưng thiếu `qid`, thêm nhiều cột khác, nội dung chuyên về giao thông, 2.2k dòng. Không khớp.
  - https://huggingface.co/datasets/thangvip/vietnamese-legal-qa: schema khác hoàn toàn (`doc_name`, `article_content`, `generated_qa_pairs`), 9.715 văn bản. Không khớp.
  - VLQA (https://arxiv.org/abs/2507.19995): chỉ là bài báo, ghi bộ dữ liệu "sẽ công bố"; định danh bằng `Law_id`/`Article_id`. Không có bằng chứng liên quan.

## Quan sát (suy luận, chưa kiểm chứng)
- Nhiều câu hỏi có dạng "… được quy định như thế nào?" và bám sát tiêu đề Điều, nên có thể do mô hình sinh từ Điều luật. Chưa xác nhận ai tạo, có kiểm tra bởi người hay không.

## Việc cần làm
- Hỏi người đưa file vào repo (hoặc người hướng dẫn) về link tải, ngày tải, giấy phép, người tạo câu hỏi. Cập nhật file này khi có.
- Trong báo cáo, mô tả là "bộ hỏi đáp pháp luật tiếng Việt không rõ nguồn" cho đến khi xác định được.
