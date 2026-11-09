# Bơm lỗi: rule-only (không LLM), n=80 ca, commit `e268fcb0`

| Luật | TP | FP | FN | Precision | Recall | F1 | FP trên near-miss của chính nó |
|---|---:|---:|---:|---:|---:|---:|---:|
| ot_unpaid | 2 | 1 | 3 | 0.67 | 0.40 | 0.50 | 1/5 |
| no_bhxh | 2 | 3 | 3 | 0.40 | 0.40 | 0.40 | 3/5 |
| retain_id_papers | 2 | 3 | 3 | 0.40 | 0.40 | 0.40 | 3/5 |
| training_cost_flat | 2 | 1 | 3 | 0.67 | 0.40 | 0.50 | 1/5 |
| fine_deduct_wage | 2 | 2 | 3 | 0.50 | 0.40 | 0.44 | 2/5 |
| forfeit_wage_quit | 2 | 1 | 3 | 0.67 | 0.40 | 0.50 | 1/5 |
| terminate_pregnancy | 2 | 2 | 3 | 0.50 | 0.40 | 0.44 | 2/5 |
| ban_lawsuit | 2 | 1 | 3 | 0.67 | 0.40 | 0.50 | 1/5 |
| **Tổng (micro)** | 16 | 14 | 24 | 0.53 [[0.3571, 0.7308]] | 0.40 [[0.25, 0.5556]] | 0.46 [[0.3, 0.5977]] | 14/40 ca hợp lệ bị kích hoạt luật bất kỳ |

CI95 bootstrap theo ca (1000 lần). Mỗi luật chỉ có 10 ca nên chỉ số theo từng luật rất thô.
