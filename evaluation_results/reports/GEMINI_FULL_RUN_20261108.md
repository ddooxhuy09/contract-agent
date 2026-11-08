# Lần chạy đầy đủ có Gemini sau khi bật lượt tìm phạm vi luật lao động (2026-11-08)

Câu hỏi: trên cấu hình đang dùng (`RAG_LABOR_SCOPE=true`, commit `f683a20`), phân tích đầy đủ có Gemini chạy ra sao? Trước đây chỉ đo RAG-only (`LABOR_EFFECTIVITY_RAG_RUN.md`).

**Lần chạy chưa xong: 15 trong 34 ca.** Hết quota Gemini theo ngày, dừng sạch tại MIX-013. Các ca còn lại chạy tiếp bằng `--resume` vào ngày hôm sau, cùng thư mục.

## Cách làm
- Bản sao cách ly (`evaluation/docker-compose.eval.yml`, project `contractlens-eval-01a154eb`), cờ hiệu lực đã sửa. DB đang dùng không bị chạm; fingerprint kho luật trước và sau trùng nhau (`legal_corpus_unchanged: true`).
- Benchmark v04 (34 ca, nhãn nháp tổng hợp), thư mục `runs/gemini_full_laborscope_20261108/`.
- 3 key Gemini free tier (20 request/ngày/key). Tổng 57 lượt gọi model cho 15 ca.

## Hai lỗi phải sửa trước khi chạy được
Lần chạy ngày 06/11 có 5 ca risk fail liên tiếp, nên đã dừng để tìm nguyên nhân.

1. **`_extract_clauses` ra 0 điều khoản trên cả 7 hợp đồng benchmark** (commit `f683a20`). Regex đòi dấu câu sau `Điều N`, nhưng các hợp đồng viết `Điều 1` rồi xuống dòng, và 4 file dùng `Mục A` / `Mục 1` / `Khoản A` mà parser không có nhánh dự phòng. Mọi ca risk vì vậy fail với "no clauses could be extracted". Nay dùng chung `find_headings` của `app/document/chunker.py`, là chỗ đã được sửa đúng chuyện này từ 03/11.

| Hợp đồng | Điều khoản trước | Sau | Kiểu tiêu đề |
|---|---:|---:|---|
| CTR-LAB-01 | 0 | 7 | `Điều N` |
| CTR-CTV-02 | 0 | 6 | `Mục N` |
| CTR-CIV-03 | 0 | 4 | `Mục A` |
| CTR-COM-04 | 0 | 5 | `Điều N` |
| CTR-COM-05 | 0 | 4 | `Điều N` |
| CTR-CONS-06 | 0 | 6 | `Khoản A` |
| CTR-CONS-07 | 0 | 5 | `Khoản A` |

2. **Gap-fill của LLM làm mất toàn bộ kết quả trích xuất.** Prompt yêu cầu trả `null` cho thông tin không có trong văn bản, hợp đồng benchmark lại ẩn danh tên bên, nên model trả `parties[].name = null` và `Party.name: str` từ chối, kéo theo cả `ContractAnalysis`. Nay bỏ party thiếu tên hoặc thiếu vai trò, và nếu kết quả gộp vẫn bị schema từ chối thì giữ kết quả regex. Schema không nới lỏng.

Sau khi sửa, cả 6 ca risk trong 15 ca này đều chạy xong, trong đó 5 ca trước đây fail.

## Kết quả (n = 15, chưa đủ bộ)
Trạng thái: 11 `completed`, 4 `unsupported_capability` (ca về thời gian; hệ thống chưa truy xuất luật theo ngày), **0 fail**. Lần chạy generation trước (`baseline_20261019`) có 11/34 ca và có ca fail.

Truy xuất (giai đoạn `final_retrieval`):

| Chỉ số | Giá trị |
|---|---:|
| Exact provision recall | 0,222 |
| MRR | 0,250 |
| Cross-document coverage | 0,467 |
| Pooled precision@5 | 0,067 |
| Explicit distractor retrieval rate | 0,000 |

Phân loại rủi ro (6 ca risk có nhãn):

| Chỉ số | Giá trị |
|---|---:|
| Severity accuracy | 0,667 (4/6) |
| Critical: precision / recall | 1,00 / 0,80 |

Nhầm lẫn: 4 ca `critical` đúng, 1 ca `critical` bị hạ thành `warning`, 1 ca `ok` bị nâng thành `warning`. Tức là hệ thống nghiêng về phía cảnh báo quá mức hơn là bỏ sót, nhưng 6 ca thì quá ít để nói gì chắc chắn.

Chất lượng câu trả lời (`answer_correctness`, `faithfulness`, `citation_support_accuracy`) vẫn `null`: chưa có judge được hiệu chỉnh và chưa có người rà. 15 ca đã có đủ prompt, bằng chứng và câu trả lời trong `traces/` để rà tay theo `ANSWER_RUBRIC.md`.

## Giới hạn khi đọc số liệu
- **15 trong 34 ca, không phải một tập con chọn ngẫu nhiên** mà là 15 ca đầu theo thứ tự chạy. Không so sánh trực tiếp các con số truy xuất ở đây với 0,270 của RAG-only trên 34 ca.
- Nhãn v04 là bản nháp tổng hợp, nên đây là độ khớp cấu trúc giữa điều luật truy xuất và điều luật kỳ vọng, không phải đánh giá đúng sai pháp lý.
- Hai bản sửa parser thay đổi hành vi trích xuất điều khoản của toàn hệ thống, không chỉ trong eval. Các lần đánh giá trước ngày 08/11 không so sánh được với lần này.
- `stopped_on_quota.cases_left` trong `execution_metadata.json` của lần chạy này bị runner đếm sai (34 thay vì 19); đã sửa tay giá trị đó và sửa lỗi đếm trong mã. Dữ liệu gốc `predictions.jsonl` không bị tác động.
- `predictions.jsonl`, `traces/` không đưa vào git.

## Chạy tiếp
```powershell
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml up -d postgres neo4j
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps worker python -u -m evaluation.run_benchmark --isolated-db --enable-llm --resume --output-dir /workspace/evaluation_results/runs/gemini_full_laborscope_20261108
```
19 ca còn lại, trong đó 7 ca risk với khoảng 8 lượt gọi model mỗi ca. Cần khoảng 80 request, tức hơn một ngày quota của 3 key.

Lần thử chạy tiếp chiều 08/11 với 3 key mới không thêm được ca nào, dừng sạch tại MIX-013 lần nữa. Trạng thái 3 key đó với `gemini-2.5-flash`:

| Key | Kết quả 1 request thử |
|---|---|
| 1 | 404 `NOT_FOUND` — "no longer available to new users" (project tạo sau khi Google đóng model cho người dùng mới), dù ListModels vẫn liệt kê model |
| 2 | OK, nhưng hết quota ngày ngay sau đó |
| 3 | 429 hết quota ngày, retry sau ~20h |

Lỗi 404 ở key 1 không phải lỗi quota nên phần xoay key cũ không nhận ra, mọi ca sẽ fail trên key đầu danh sách; nay `rotate_api_key_on_key_failure` chuyển key cho cả hai loại lỗi "key này không chạy được" (hết quota ngày, không có quyền dùng model).

`gemini-3.8-flash` thì cả 3 key đều không bị 404/429, tức còn quota ở pool riêng của model đó — nhưng đổi model giữa lần chạy thì 19 ca còn lại không còn so sánh được với 15 ca đã chạy trên `gemini-2.5-flash`.

Lần chạy dở dang ngày 06/11 (`runs/gemini_full_laborscope_20261106/`, 12 bản ghi, 5 ca risk fail) giữ lại để tham khảo, chạy trên mã trước khi sửa parser, **không** gộp với lần này.
