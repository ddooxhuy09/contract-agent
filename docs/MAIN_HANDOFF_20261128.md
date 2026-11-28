# Bàn giao main — 28/11/2026

## Nội dung đưa lên main

- Tích hợp `eval/contract-eval-v1`: căn cứ luật theo chủ đề cho clause judge, phân biệt vi phạm với thiếu nội dung; kết quả v1.1/v1.2, liên kết test.lock và audit nhãn bằng ba phòng AI độc lập. Các kết quả đánh giá là artifact lịch sử, không phải xác nhận độ chính xác pháp lý.
- Tích hợp `feat/pii-masking-prompt-guard`: che PII bằng regex trước các lời gọi LLM văn bản của agent, khôi phục giá trị trong câu trả lời; bọc dữ liệu hợp đồng/ký ức trong thẻ dữ liệu và phát hiện câu lệnh nhắm vào AI trước clause judge. Thêm test masking và prompt guard, cùng harness AgentDojo.
- Sửa lỗi khôi phục PII chứa dấu ngoặc kép hoặc dấu gạch chéo ngược làm hỏng JSON. Giữ JSON escaping, cấu trúc output và Markdown fence; thêm test hồi quy.
- Không đổi API, auth, schema DB, SSE, checkpointer hoặc retry trong commit sửa JSON.

## Giới hạn cần biết

- Che PII dựa trên regex, không bảo đảm nhận diện mọi tên/địa chỉ. OCR ảnh vẫn gửi ảnh gốc tới nhà cung cấp LLM; không có che PII trong ảnh.
- `.env.example` tắt LangSmith tracing mặc định. File `.env` đang có trên máy mỗi thành viên không tự đổi; kiểm tra `LANGCHAIN_TRACING_V2` trước khi dùng dữ liệu thật.
- Đây là bản tích hợp source. HTTP 200 của dịch vụ đang chạy không chứng minh mọi luồng với DB/LLM thật đạt; bộ test tích hợp ở lượt rà soát trước không hoàn tất.

## Phần giữ local, không push

- Nhánh `codex/wip-local-20261128`, commit `c746f7b`: parser/chunker, scope/citation, căn cứ phần đầu, QA toàn hợp đồng, evaluation v2 và giao diện đang làm.
- QA toàn hợp đồng trong WIP còn cắt ngữ cảnh ở 16.000 ký tự; chưa đưa thay đổi này vào main.
- File kết quả chưa tracked trong `evaluation_results/` và `tmp/` giữ nguyên trên máy. Stash `codex-pre-merge-20261128` vẫn giữ làm dự phòng trước merge.

## Kiểm chứng bản bàn giao

- Backend trên main (không gồm WIP): `399 passed, 1 skipped` với `python -m pytest tests -q --ignore=tests/integration --timeout=45`.
- Sau điều chỉnh cuối xử lý JSON/fence và văn bản thuần bắt đầu bằng placeholder: riêng `test_masking.py` đạt `8 passed`.
- `python -m ruff check app scripts evaluation --select F`, frontend `npm run lint` và `npm run build`: đạt.
- Lượt `423 passed, 1 skipped` trước đó có cả phần WIP; không dùng số này để mô tả main bàn giao.

## Cách cập nhật cho team

Sau khi cất hoặc commit phần đang sửa trên máy riêng:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
```

Không cần lấy nhánh WIP local. Cấu hình API key và `JWT_SECRET` trên máy riêng; không copy/commit `.env`.
