# contract_eval_v1: bộ test hợp nhất + tự kiểm nhãn + đánh giá Retrieval & Generation

Gộp các bộ có sẵn (injection 80 ca, injection_v2 32 ca, contract_qa 8 câu, v04 34 câu) thành một schema JSONL, sinh câu hỏi bằng template cố định (không dùng LLM để sinh nhãn), tự kiểm nhãn bằng script + LLM kiểm chéo (không có người duyệt), đóng băng, rồi chạy hệ thống thật ở hai giai đoạn.

| File | Nội dung |
|---|---|
| `build.py` | Chuẩn hóa → `cases.jsonl`, `inputs_no_gold.jsonl` (runner đọc), `gold.jsonl` (chỉ bước chấm đọc), `split.json` |
| `verify.py` | V1–V7 → `verification.jsonl`, `quarantine.jsonl`, `VERIFICATION_REPORT.md`, `verification_stats.json`, `FROZEN.json` |
| `run.py` | `index` / `retrieval` (Giai đoạn A, không LLM) / `generation` (Giai đoạn B) / `judge` |
| `score.py` | `metrics.json`, `per_case.csv`, `docs/bo_test_hoi_dong/KET_QUA_BO_TEST_V1.md`; `score check` đối chiếu số |
| `DECISIONS.md` | Các quyết định khi gặp chỗ mơ hồ |

## Template câu hỏi (injection, injection_v2)
- T1 phát hiện: «Điều {n} của hợp đồng có trái quy định pháp luật lao động không?»
- T2 căn cứ: «Điều khoản về {chủ đề} trong hợp đồng cần đối chiếu với điều luật nào?» (chủ đề = tiêu đề Điều)
- T3 tổng quát: «Hợp đồng này có điều khoản nào gây rủi ro cho người lao động không?»

## Chạy (host)
```bash
export DATABASE_URL=postgresql://contractlens:contractlens@127.0.0.1:5433/contractlens PYTHONUTF8=1
python -m evaluation.contract_eval_v1.build
python -m evaluation.contract_eval_v1.verify          # đóng băng khi xong V7
python -m evaluation.contract_eval_v1.run index
python -m evaluation.contract_eval_v1.run retrieval --label vector
LEGAL_RETRIEVAL_MODE=hybrid python -m evaluation.contract_eval_v1.run retrieval --label hybrid
python -m evaluation.contract_eval_v1.run generation  # resume; dừng sạch khi hết quota, ghi RESUME.md
python -m evaluation.contract_eval_v1.run judge
python -m evaluation.contract_eval_v1.score
python -m evaluation.contract_eval_v1.score check
```
Mọi bước sau `verify` kiểm SHA-256 trong `FROZEN.json` trước khi chạy. `generation` ghi `test.lock` khi xong toàn bộ test và từ chối mở thư mục chạy test mới nếu đã có lock.

## Dọn dữ liệu đánh giá trong DB (không tự chạy)
Hợp đồng được nạp dưới user `contract-eval-v1@example.invalid`; id trong `evaluation_results/runs/contract_eval_v1_*/contract_map.json`.
