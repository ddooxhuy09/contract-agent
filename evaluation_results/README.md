# evaluation_results — kết quả benchmark

Mọi thứ ở đây là **đầu ra** của `evaluation/`. Không có code, không có đề bài. Đề bài nằm ở
[`evaluation/benchmark/v04/`](../evaluation/benchmark/v04/README.md).

```
evaluation_results/
├── reports/     báo cáo tổng hợp, so sánh nhiều lần chạy (đọc trước)
└── runs/        mỗi thư mục con = một lần chạy, tự đủ (báo cáo, metrics, điểm từng case)
```

## Đọc theo thứ tự này

1. [`reports/CHUNKER_ASOF_RUN.md`](reports/CHUNKER_ASOF_RUN.md): lần chạy mới nhất và cách đọc số liệu.
2. [`reports/RAG_SCOPE_ABLATION.md`](reports/RAG_SCOPE_ABLATION.md): vì sao bỏ labor hint, vì sao xếp seed trước.
3. [`reports/STATUS4_AUDIT.md`](reports/STATUS4_AUDIT.md): vì sao chưa lọc theo ngày cho văn bản "hết hiệu lực một phần".
4. [`reports/qa_coverage.md`](reports/qa_coverage.md), [`reports/missing_legal_documents.csv`](reports/missing_legal_documents.csv): văn bản trong `dataset.csv` chưa có trong corpus.

## Các lần chạy RAG-only (không gọi Gemini, n = 34)

Hai cột số là `exact_provision_recall` và `mrr` của giai đoạn `final_retrieval`, đọc từ `RETRIEVAL_METRICS.json`.
Nhãn gold là bản nháp tổng hợp, nên đây là độ khớp cấu trúc, không phải đánh giá đúng sai về pháp lý.

| Run | Thay đổi | Ngày truyền vào retrieval | Exact provision recall | MRR |
|---|---|---|---:|---:|
| [`rag_only`](runs/rag_only/RAG_ONLY_REPORT.md) | Baseline RAG-only đầu tiên, còn gợi ý nhãn lao động (labor hint) | không | 0.152 | 0.160 |
| [`rag_only_no_labor_hint`](runs/rag_only_no_labor_hint/RAG_ONLY_REPORT.md) | Bỏ labor hint | không | 0.201 | 0.185 |
| [`rag_only_seed_first_20261026`](runs/rag_only_seed_first_20261026/RAG_ONLY_REPORT.md) | Xếp seed của hybrid search lên trước phần mở rộng đồ thị | không | 0.201 | 0.260 |
| [`rag_only_chunker_asof_20261103`](runs/rag_only_chunker_asof_20261103/RAG_ONLY_REPORT.md) | Sau sửa chunker + truyền `as_of_date` (**mặc định hiện tại**) | `as_of_date` | 0.201 | 0.260 |
| [`rag_only_chunker_txdate_20261103`](runs/rag_only_chunker_txdate_20261103/RAG_ONLY_REPORT.md) | Như trên nhưng truyền `transaction_date` (làm tụt TEMP-009) | `transaction_date` | 0.191 | 0.245 |

## Các thư mục khác trong `runs/`

| Thư mục | Nội dung |
|---|---|
| `baseline_20261019/` | Baseline có sinh câu trả lời (Gemini), **dừng giữa chừng vì hết quota**: 11/34 case có kết quả. Không dùng để so sánh với RAG-only. Có `ISOLATION_AND_EXECUTION_NOTES.md`. |
| `smoke/`, `smoke_real/` | Chạy thử 5 case. `smoke/` là preflight không có đầu ra mô hình. |
| `rerank_ablation_20261026/` | So sánh offline các chính sách rerank trên pool đã lưu, không gọi mô hình. |

## Một thư mục run có gì

| File | Ý nghĩa |
|---|---|
| `RAG_ONLY_REPORT.md` | Báo cáo của lần chạy |
| `RETRIEVAL_METRICS.json` | Recall, MRR theo từng giai đoạn |
| `CASE_BY_CASE_RESULTS.csv`, `case_scores.json` | Điểm và kết quả từng case |
| `ERROR_ANALYSIS.md`, `TEMPORAL_RETRIEVAL_DIAGNOSTICS.json` | Case sai và phần temporal |
| `execution_metadata.json` | Cấu hình, mã băm nguồn, dấu vân tay corpus |
| `predictions.jsonl`, `traces/`, `corpus_snapshot.json` | Dữ liệu thô, **nặng, bị git bỏ qua**. Sinh lại bằng runner. |

Các file `execution_metadata.json` là bản ghi lịch sử nên giữ nguyên đường dẫn lúc chạy (trước khi gom thư mục ngày 2026-11-03).
