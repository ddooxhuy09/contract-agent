# Báo cáo tự kiểm nhãn contract_eval_v1

- Số ca: **378** (từ 154 ca gốc). Quarantine: **9** ca (3 ca gốc). Gắn cờ `low_confidence` (giữ lại): 38 ca.
- Ca có ref không map được vào kho (loại khỏi chấm truy xuất điều luật, vẫn dùng cho Generation): 6.
- Ca mà clause_parser không tách được Điều/Khoản gold (nhãn đúng, lỗi hệ thống tầng a, không quarantine): 0.

## Kết quả theo lớp

| Lớp | Pass | Fail | Không áp dụng | Chưa đủ |
|---|---:|---:|---:|---:|
| V1 | 378 | 0 | 0 | 0 |
| V2 | 378 | 0 | 0 | 0 |
| V3 | 377 | 1 | 0 | 0 |
| V4 | 375 | 3 | 0 | 0 |
| V5 | 378 | 0 | 0 | 0 |
| V6 | 375 | 3 | 0 | 0 |
| V7 | 342 | 20 | 16 | 0 |

- V3: 668 lượt ref kiểm, 444 đoạn trích so với DB (ngưỡng fuzzy 0.8), 1 ref lệch.
- V5: 0 câu hỏi đã sửa vì chứa thông tin gold.
- V6: 1 ca gốc gần trùng (ratio > 0.95) bị loại: LU2-V1≈LU-01

## V7: LLM kiểm chéo độc lập

- Model kiểm chéo: Gemini — lần 1 ['gemini-2.5-flash'], lần 2 ['gemini-2.5-flash', 'gemini-3-flash-preview'] (hệ thống sinh bằng Groq `gpt-oss-120b`); nhiệt độ 0, không thấy nhãn; 8 ca mỗi lượt gọi. Số lượt gọi: 17, token: 60944.
- Đơn vị kiểm: 138 ca gốc có nhãn violation/compliant (đủ 2 lần: 138).
- Cohen's kappa nhãn cấu tạo vs LLM: lần 1 **0.9136** (đồng thuận 0.9565), lần 2 **0.9271** (đồng thuận 0.9638). Hai lần LLM trùng nhau: 0.9638.
- Cả 2 lần khớp nhãn: 130; 1 lần trái nhãn (low_confidence): 3; 2 lần trái nhãn (quarantine): 1; có lần 'không xác định': 4.
- Kappa tính với 'không xác định' là một nhãn riêng (bị tính là bất đồng).

## Quarantine

Theo lớp gây quarantine (đếm theo ca, một ca có thể nhiều lớp): {"V7": 3, "V4": 3, "V6": 3}

| Ca | Lý do |
|---|---|
| OT-09-T1 | V7: LLM ['vi_pham', 'vi_pham'] vs nhãn compliant |
| OT-09-T2 | V7: LLM ['vi_pham', 'vi_pham'] vs nhãn compliant |
| OT-09-T3 | V3: không có ref đã map; V7: LLM ['vi_pham', 'vi_pham'] vs nhãn compliant |
| LU-09-T1 | V4: REVIEW CSV: CẦN BẠN XEM; V7: LLM ['vi_pham', 'hop_le'] vs nhãn compliant |
| LU-09-T2 | V4: REVIEW CSV: CẦN BẠN XEM; V7: LLM ['vi_pham', 'hop_le'] vs nhãn compliant |
| LU-09-T3 | V3: không có ref đã map; V4: REVIEW CSV: CẦN BẠN XEM; V7: LLM ['vi_pham', 'hop_le'] vs nhãn compliant |
| LU2-V1-T1 | V6: gần trùng LU-01 (ratio > 0.95) |
| LU2-V1-T2 | V6: gần trùng LU-01 (ratio > 0.95) |
| LU2-V1-T3 | V6: gần trùng LU-01 (ratio > 0.95) |
