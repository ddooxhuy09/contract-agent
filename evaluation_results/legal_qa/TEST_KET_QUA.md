# Kết quả test: truy xuất pháp luật chung (zac2021), chạy một lần

Tập: test (split đóng băng, chia theo văn bản), `--only-covered`, n=556 trong 2.673 câu test (20,8%). Mỗi cấu hình chạy đúng một lần (có file khoá trong `test_locks/`). Không gọi LLM, 0 lỗi truy vấn. `predictions.jsonl` bị `.gitignore`, chỉ có `metrics.json` trong repo.

| Cấu hình | n | R@1 | R@5 [CI95] | R@10 | MRR@10 [CI95] | DocR@10 | Độ trễ median / p95 (ms) | Commit |
|---|---:|---:|---|---:|---|---:|---|---|
| fts (cũ) | 556 | 0,0054 | 0,0090 [0,0018; 0,0180] | 0,0144 | 0,0068 [0,0013; 0,0144] | 0,0252 | 85 / 153 | ae9e230 |
| vector | 556 | 0,5935 | 0,7950 [0,7626; 0,8273] | 0,8363 | 0,6816 [0,6494; 0,7147] | 0,9101 | 294 / 432 | ae9e230 |
| hybrid (cũ) | 556 | 0,5809 | 0,7356 [0,7014; 0,7716] | 0,7914 | 0,6420 [0,6085; 0,6774] | 0,8939 | 347 / 488 | ae9e230 |
| hybrid + V3 | 556 | 0,5899 | 0,8022 [0,7680; 0,8345] | 0,8417 | 0,6857 [0,6547; 0,7190] | 0,9083 | 4.237 / 6.609 | 78d4437 |

## So sánh ghép cặp MRR@10 (bootstrap 95%, cùng 556 câu)
| So sánh | Chênh | CI95 |
|---|---:|---|
| hybrid cũ − vector | −0,0395 | [−0,0483; −0,0312] |
| hybrid+V3 − vector | +0,0042 | [−0,0061; +0,0139] |
| hybrid+V3 − hybrid cũ | +0,0437 | [+0,0290; +0,0571] |

## Kết luận
- Kết quả trên test **trùng với dự đoán từ dev**: hybrid cũ kém vector có ý nghĩa; V3 hơn hybrid cũ có ý nghĩa nhưng **không hơn vector** (CI chứa 0). Không tuyên bố hybrid vượt vector.
- Tìm kiếm chỉ bằng vector gần như tốt ngang V3 mà nhanh hơn ~14 lần (median 0,29 s so với 4,2 s). Về kỹ thuật, vector đơn thuần là lựa chọn hợp lý trên benchmark này.
- FTS (cách hệ thống đang dùng, `plainto_tsquery`) gần như không đóng góp (MRR@10 0,007).
- Ghi chú về quá trình: lần chạy `hybrid+V3` đầu bị từ chối do khoá test đặt tên theo `mode` (chặn nhầm vì `hybrid.lock`). Đã sửa tên khoá theo `mode+variant` (commit `78d4437`) rồi chạy V3 đúng một lần. Ba cấu hình kia chạy ở `ae9e230`; V3 ở `78d4437` (khác chỉ ở tên khoá). Chi tiết: `docs/NHAT_KY_THAY_DOI.md`.

## Giới hạn khi trình bày
- Chỉ **20,8% câu test** nằm trong tập đánh giá (văn bản còn hiệu lực và tìm kiếm được trong DB). Nếu tính cả câu không thể tìm (gold bị lọc hiệu lực, thiếu văn bản) là trượt, thì R@10 trên toàn bộ 2.673 câu test chỉ khoảng 465/2.673 = 17,4% (vector) và 468/2.673 = 17,5% (V3) (số suy ra từ R@10 × 556, làm tròn). Nguyên nhân chính là lệch hiệu lực thời gian, không phải chất lượng xếp hạng; xem `coverage_breakdown.md`.
- Nguồn dataset khớp `DaHaDaHa/zac2021`; giấy phép và người tạo câu hỏi chưa xác định (`NGUON_DATASET.md`). Không so trực tiếp với số liệu công bố dùng split gốc.
- Benchmark này đo truy xuất pháp luật chung, không đo rà soát hợp đồng. V3 chưa được áp dụng cho ứng dụng.
