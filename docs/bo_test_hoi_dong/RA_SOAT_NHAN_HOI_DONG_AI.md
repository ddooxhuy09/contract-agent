# Rà soát nhãn phần test bằng hội đồng AI 3 phòng

Ngày 24/11/2026. Không có luật sư tham gia. Theo yêu cầu của tác giả, nhãn của 128 ca gốc thuộc phần test contract_eval_v1 được rà lại bởi 3 "phòng" độc lập. Mỗi phòng là một tác tử Claude Opus 5.5 riêng. Phương pháp và quy tắc gộp được ghi trong `evaluation/contract_eval_v1/DECISIONS.md` **trước** khi có kết quả.

## Cách làm

- **Hồ sơ ẩn nhãn** (`python -m evaluation.contract_eval_v1.ai_panel build`), mỗi ca gồm:
  - mã ngẫu nhiên thay cho id gốc, vì id gốc như `DT2-V1` lộ nhãn;
  - loại hợp đồng, ngày áp dụng;
  - câu hỏi: với ca bơm lỗi dùng mẫu trung tính "Điều X có trái quy định pháp luật lao động không?";
  - nguyên văn điều khoản;
  - tập luật tham khảo (59 Điều): Điều gold, Điều liền trước và liền sau, và Điều theo chủ đề của BLLĐ.
- **Ba phòng làm độc lập.** Cùng hướng dẫn (`evaluation_results/ai_panel_v1/ANNOTATOR_GUIDE.md`), nhưng đọc theo thứ tự khác nhau: tăng dần, giảm dần, lẻ rồi chẵn. Không phòng nào thấy nhãn bộ test hay kết quả của phòng khác.
- **Nhãn:** `violation`, `compliant`, `n/a` (câu hỏi không đòi kết luận hợp pháp/trái luật), `unclear`.
- **Gộp:** nhãn nào có ít nhất 2/3 phiếu thì lấy; ngược lại là `unclear` (`ai_panel merge`).

## Kết quả

| Chỉ số | Giá trị |
|---|---:|
| Số ca gốc | 128 |
| Đồng thuận giữa 3 phòng (Fleiss kappa) | 0,982 |
| Ca cả 3 phòng cùng nhãn | 126/128 |
| Kappa từng cặp A–B / A–C / B–C | 0,973 / 0,986 / 0,986 |
| Nhãn hội đồng khớp nhãn bộ test | 124/128 (0,97) |
| Cohen kappa hội đồng – nhãn bộ test | 0,945 |
| Ca hội đồng không quyết được (`unclear`) | 0 |
| Đa số phòng nêu đúng Điều gold (ca có Điều gold) | 100/113 |

**Ma trận (nhãn bộ test → nhãn hội đồng):**

| | → violation | → compliant | → n/a |
|---|---:|---:|---:|
| violation | 65 | 0 | 1 |
| compliant | 0 | 49 | 0 |
| n/a | 2 | 1 | 10 |

**Theo nguồn ca:**

| Nguồn | Khớp |
|---|---:|
| injection | 62/62 |
| injection_v2 | 31/31 |
| v04 | 24/27 |
| contract_qa | 7/8 |

- Toàn bộ ca bơm lỗi khớp nhãn, kể cả 46 ca near-miss hợp lệ.
- Không ca nào bị đảo chiều giữa vi phạm và hợp lệ.

## Bốn ca lệch

Cả bốn ca đều lệch ở chỗ câu hỏi có đòi kết luận hay không. Về nội dung pháp lý, lý do của các phòng trùng với đáp án tham chiếu của bộ test.

| Ca | Nhãn bộ test | Hội đồng | Ghi chú |
|---|---|---|---|
| MIX-006 | violation | n/a (3/3) | Hỏi "cộng tác viên làm cố định, nhận lương có thể coi là HĐLĐ không". Cả ba phòng kết luận là HĐLĐ theo Điều 13 BLLĐ, khớp đáp án tham chiếu, nhưng coi đây là câu hỏi định danh quan hệ chứ không phải "trái luật". |
| QA-08 | n/a | violation (2/3) | Hỏi "hợp đồng còn thiếu nội dung bắt buộc nào". Hai phòng kết luận hợp đồng thiếu nội dung theo Điều 21 nên trái luật; một phòng coi là câu hỏi liệt kê. |
| TEMP-003 | n/a | compliant (3/3) | Hợp đồng qua thư điện tử không bị phủ nhận giá trị chỉ vì là thông điệp dữ liệu. Khớp đáp án tham chiếu (Điều 34 Luật GDĐT 2005). |
| TEMP-007 | n/a | violation (3/3) | Điều khoản từ bỏ quyền khiếu kiện trong hợp đồng tiêu dùng 5/2024 không có hiệu lực. Khớp đáp án tham chiếu (Điều 16 Luật BVQLNTD 2010). |

Ca không nhất trí nhưng vẫn khớp nhãn: LU-06 (compliant, 2 phòng compliant, 1 phòng unclear). Hợp đồng không nêu loại, nên chưa rõ mức báo trước 30 ngày có bất lợi cho người lao động hay không.

## Ảnh hưởng tới kết quả v1.2

Chỉ số v1.2 trên toàn phần test, so với trên 124 ca gốc mà hội đồng đồng ý với nhãn (`ai_panel sensitivity`):

| Chỉ số (test) | Toàn bộ | Ca hội đồng đồng ý |
|---|---:|---:|
| Phát hiện rủi ro: số ca | 115 | 114 |
| Precision | 0,93 | 0,93 |
| Recall | 0,95 | 0,95 |
| F1 | 0,94 | 0,94 |
| Báo nhầm trên ca near-miss | 0,10 | 0,10 |
| QA: số câu đã chấm | 314 | 310 |
| QA: correctness (0–1) | 0,71 | 0,71 |
| QA: kết luận khớp nhãn | 0,74 | 0,73 |

Kết luận v1.2 không đổi khi bỏ các ca hội đồng không đồng ý. Không sửa nhãn của bộ đã đóng băng.

## Giới hạn

- **Đây không phải thẩm định của luật sư.** Ba phòng cùng một mô hình, nên lỗi có thể tương quan; đồng thuận cao giữa các phòng không chứng minh nhãn đúng.
- **Nhãn bộ test cũng do LLM tạo và kiểm.** Hội đồng khớp với nhãn cho thấy nhãn nhất quán với cách hiểu luật của một mô hình mạnh, chưa phải với thực tiễn xét xử.
- **Chỉ số Điều gold không hoàn toàn độc lập.** Tập luật tham khảo chứa Điều gold (lẫn với Điều kề bên và Điều theo chủ đề), nên "nêu đúng Điều gold" bị ảnh hưởng.
- **Ca v04 về thời điểm áp dụng luật** (2005 vs 2023) không có Điều tương ứng trong tập tham khảo; các phòng dựa vào hiểu biết riêng.
- **Phòng A tự khai** đã chạy một lệnh Python đếm dòng trên chính file kết quả của mình, trái hướng dẫn "không chạy code". Lệnh không đọc file nào khác.

## Tái lập

```bash
python -m evaluation.contract_eval_v1.ai_panel build
# 3 phòng gán nhãn theo ANNOTATOR_GUIDE.md -> room_A/B/C.jsonl
python -m evaluation.contract_eval_v1.ai_panel merge
python -m evaluation.contract_eval_v1.ai_panel sensitivity --run-dir evaluation_results/runs/contract_eval_v1_20261124
```

Dữ liệu: `evaluation_results/ai_panel_v1/` (packet.jsonl, law.json, key.json, room_A/B/C.jsonl, merged.jsonl, metrics.json, sensitivity.json).
