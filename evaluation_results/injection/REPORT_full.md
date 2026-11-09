# Bơm lỗi: pipeline đầy đủ (judge: groq/openai/gpt-oss-120b), 48/48 ca mẫu đã hoàn tất

| Luật | n | TP | FP | FN | TN | Precision | Recall | F1 | Chưa kiểm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ot_unpaid | 6 | 3 | 2 | 0 | 1 | 0.60 | 1.00 | 0.75 | 0 |
| no_bhxh | 6 | 3 | 1 | 0 | 2 | 0.75 | 1.00 | 0.86 | 0 |
| retain_id_papers | 6 | 3 | 1 | 0 | 2 | 0.75 | 1.00 | 0.86 | 0 |
| training_cost_flat | 6 | 3 | 2 | 0 | 1 | 0.60 | 1.00 | 0.75 | 0 |
| fine_deduct_wage | 6 | 3 | 2 | 0 | 1 | 0.60 | 1.00 | 0.75 | 0 |
| forfeit_wage_quit | 6 | 3 | 3 | 0 | 0 | 0.50 | 1.00 | 0.67 | 0 |
| terminate_pregnancy | 6 | 3 | 3 | 0 | 0 | 0.50 | 1.00 | 0.67 | 0 |
| ban_lawsuit | 6 | 3 | 1 | 0 | 2 | 0.75 | 1.00 | 0.86 | 0 |
| **Tổng** | 48 | 24 | 15 | 0 | 9 | 0.62 [[0.4615, 0.7647]] | 1.00 [[1.0, 1.0]] | 0.76 [[0.6316, 0.8667]] | 0 |

Ca có cờ rủi ro ở Điều khác ngoài Điều bơm (nền sạch bị gắn cờ): 48/48.
