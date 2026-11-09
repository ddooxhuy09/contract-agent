# injection_v2: rule-only, code CŨ vs code MỚI (32 ca)

Code cũ: commit `fab1cef0`. Code mới: commit `04f1e6c0`. Không LLM.

| Luật | TP cũ→mới | FP cũ→mới | FN cũ→mới | Precision cũ→mới | Recall cũ→mới |
|---|---|---|---|---|---|
| ot_unpaid | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| no_bhxh | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| retain_id_papers | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| training_cost_flat | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| fine_deduct_wage | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| forfeit_wage_quit | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| terminate_pregnancy | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |
| ban_lawsuit | 2→1 | 2→1 | 0→1 | 0.50→0.50 | 1.00→0.50 |

| Tổng (micro) | Cũ | Mới |
|---|---|---|
| TP / FP / FN | 16 / 16 / 0 | 8 / 8 / 8 |
| Precision [CI95] | 0.50 [0.3125, 0.6875] | 0.50 [0.2308, 0.75] |
| Recall [CI95] | 1.00 [1.0, 1.0] | 0.50 [0.25, 0.7647] |
| F1 [CI95] | 0.67 [0.4762, 0.8148] | 0.50 [0.25, 0.6897] |
| Ca hợp lệ bị luật bất kỳ kích hoạt | 16/16 | 8/16 |

## Ca đổi kết quả (luật của chính ca đó có kích hoạt?)

| Ca | Nhãn | Dạng | Cũ | Mới |
|---|---|---|---|---|
| OT2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| OT2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| BH2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| BH2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| GT2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| GT2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| DT2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| DT2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| KL2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| KL2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| LU2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| LU2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| TS2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| TS2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |
| TC2-V2 | violation | unrelated_negation_nearby / phủ định: none | kích hoạt | không |
| TC2-C1 | compliant | negation_trap / phủ định: direct_before | kích hoạt | không |

## Theo nhóm

| Nhóm | n | Kích hoạt cũ | Kích hoạt mới |
|---|---:|---:|---:|
| vi phạm (V1+V2) | 16 | 16 | 8 |
| hợp lệ, phủ định ngay trước (C1) | 8 | 8 | 0 |
| hợp lệ, phủ định sau/bên trong (C2) | 8 | 8 | 8 |
