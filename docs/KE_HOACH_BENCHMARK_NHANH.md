# Kế hoạch nhanh: benchmark truy xuất pháp luật chung → bộ test hợp đồng

Script: `evaluation/legal_qa_retrieval.py`. Kết quả: `evaluation_results/legal_qa/`.
Không gọi Gemini, không tốn quota. Chạy trên máy có DB (Docker đang bật).

## Bước 0. Ghi nguồn gốc dataset (15 phút, bắt buộc)
- [ ] Ghi vào `evaluation_results/legal_qa/NGUON_DATASET.md`: tải `data/dataset.csv` từ đâu (link), ngày tải, giấy phép, ai viết câu hỏi.
- Không có mục này thì không gọi được là "benchmark công khai" và mất phần uy tín.

## Bước 1. Coverage (10–20 phút)
```powershell
python -m evaluation.legal_qa_retrieval coverage
```
- [ ] Ghi lại: có bao nhiêu câu có điều luật gold **tìm kiếm được** (`article_searchable`).
- Nếu tỷ lệ thấp (dưới khoảng 50%): kết quả chính phải báo cáo trên tập `--only-covered`, kèm tỷ lệ coverage. Không nói "recall thấp" khi thực ra là thiếu văn bản.

## Bước 2. Đóng băng split (1 phút)
```powershell
python -m evaluation.legal_qa_retrieval split
git add evaluation_results/legal_qa/split.json evaluation/legal_qa_retrieval.py
git commit -m "eval: freeze legal QA dev/test split"
git tag legalqa-split-frozen
```
Dev ≈ 523 câu, test ≈ 2.673 câu, chia theo văn bản.

## Bước 3. Chạy dev, chỉnh thoải mái (nửa ngày)
```powershell
python -m evaluation.legal_qa_retrieval run --split dev --mode fts    --only-covered
python -m evaluation.legal_qa_retrieval run --split dev --mode vector --only-covered
python -m evaluation.legal_qa_retrieval run --split dev --mode hybrid --only-covered
```
- `fts` = baseline từ khóa, `vector` = chỉ BGE-M3, `hybrid` = RRF của hệ thống. Ba mode này chính là ablation.
- Chạy thử nhanh: thêm `--limit 100`.
- [ ] Mỗi lần chỉnh code/tham số, commit rồi chạy lại dev. Ghi thay đổi vào `docs/NHAT_KY_THAY_DOI.md`.
- [ ] Xem `predictions.jsonl` các câu `rank = null` để tìm lỗi (sai chuẩn hoá số hiệu, thiếu điều, lọc hiệu lực...).

## Bước 4. Chạy test MỘT lần (1–2 giờ)
Chỉ chạy khi đã chốt cấu hình và commit sạch (không có `*` trong RESULTS.md).
```powershell
python -m evaluation.legal_qa_retrieval run --split test --mode fts    --only-covered
python -m evaluation.legal_qa_retrieval run --split test --mode vector --only-covered
python -m evaluation.legal_qa_retrieval run --split test --mode hybrid --only-covered
```
Script tự khoá: chạy lại test sẽ bị từ chối. Báo cáo cả khi hybrid không thắng.

## Bước 5. Bộ test hợp đồng (sau khi xong bước 4)
1. **Bơm lỗi có nhãn biết trước** (bằng chứng chính cho phần hợp đồng): chèn vi phạm theo 7 luật đỏ vào điều khoản sạch, trộn điều khoản hợp lệ, đo precision/recall từng luật.
2. **Silver set do AI tạo** (chỉ tham khảo): câu hỏi về hợp đồng, sinh bằng mô hình khác Gemini, yêu cầu diễn đạt lại không chép từ khoá; tự kiểm 50 mục ngẫu nhiên, báo cáo tỷ lệ hợp lệ.

## Cách trình bày trong báo cáo
| Lớp | Nguồn nhãn | Vai trò |
|---|---|---|
| Benchmark pháp luật chung | Dataset bên ngoài | Bằng chứng chính cho module truy xuất |
| Bơm lỗi hợp đồng | Nhãn biết trước do cấu tạo | Bằng chứng chính cho phát hiện rủi ro |
| Silver set AI | Mô hình sinh, người kiểm mẫu | Tham khảo, phát hiện lỗi |

Giới hạn cần ghi: chưa có chuyên gia luật kiểm; benchmark chung đo truy xuất, không đo rà soát hợp đồng.
