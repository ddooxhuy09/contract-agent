# Rà soát độ chính xác pipeline — hợp đồng `CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.docx`

Nguồn đối chiếu: báo cáo trước khi sửa `contractlens-f87af2fa.json` (08/11/2026) và lần chạy lại toàn pipeline trên chính hợp đồng đó
(văn bản gốc lấy từ `uploaded_contracts`, **không ghi đè** kết quả đã lưu). Mọi con số dưới đây đo từ hai tệp đó và từ kho pháp điển (Postgres `legal_embeddings`).

## Cách kiểm chứng

| Lớp | Kiểm chứng bằng |
|---|---|
| Retrieval / trích dẫn | Truy vấn trực tiếp `legal_embeddings` (doc 139264) để xem đúng điều/khoản/điểm và thứ tự trả về |
| Hậu xử lý | Chạy `check_labor_red_flags` trên hợp đồng gốc trước và sau khi sửa |
| Trích xuất | `parse_contract` rule-based + lần chạy đầy đủ có LLM gap-fill |
| Hồi quy | `tests/unit/test_pipeline_accuracy.py` (mới), `test_labor_red_flags.py`, `test_risk_flagger.py`, `test_preamble_citations.py`, `tests/evaluation/test_contract_qa_cases.py` |

Kết quả test: **307 passed, 1 skipped** (unit + evaluation); `ruff check` sạch.

## Nguyên nhân gốc và cách sửa từng vấn đề

| # | Lớp lỗi | Nguyên nhân gốc (đã xác minh) | Sửa | Trước → Sau |
|---|---|---|---|---|
| 1 | Hậu xử lý (regex) | `revise_ops` thay bằng regex lười (`{0,80}?`) dừng sớm, để sót «của tháng cuối cùng… bồi thường… 3 tháng tiền lương»; không có bước kiểm lại | Viết lại theo **câu**: tách câu/mục `(i)`, `3.2.` (`clause_text.py`), thay nguyên câu vi phạm, giữ nguyên phần hợp pháp; `revised_clause_problems()` kiểm lại (còn vi phạm? câu cụt? mất số liệu hợp pháp?). Không qua kiểm tra → **không hiển thị**, báo lý do. Áp dụng cả cho bản sửa do LLM sinh (`risk_flagger`) | Điều 3 còn nguyên câu 3 tháng lương → sạch; Điều 5 không còn khối chữ ký |
| 2 | Retrieval (SQL) | `find_article_chunks` sắp `nlevel ASC` rồi `fetch_article_meta` lấy `rows[0]` ⇒ khoản bất kỳ: Điều 98 → K2 (ban đêm), Điều 127 → K1, Điều 137 → K2, Điều 21 → K2 | `fetch_provision(doc, điều, khoản, điểm)` truy vấn đúng `\.D98\.K1(\.\|$)`; mỗi `Ref` khai báo điều+khoản; `legal_basis` sinh từ `refs` nên không lệch | 98/K2, 127/K1, 137/K2 → **98/K1, 127/K2, 137/K3** |
| 2 | Dữ liệu cấu hình | `Điều 141` (trợ cấp ốm đau) bị dẫn cho chấm dứt vì thai sản; `Điều 129` không phải căn cứ khấu trừ | Thay bằng Điều 137 K3 + Điều 8 K1; Điều 127 K2 + Điều 102 K1 (đối chiếu từ corpus) | — |
| 2 | Kiểm tra | Không có kiểm tra nhất quán | `citation_issues()`: `article`/`clause`/`point`/`location` khớp `evidence_path`; quote đúng Điều, có nội dung khoản, không ghép nhiều Điều; thêm `support` regex bắt buộc quote chứa nội dung chứng minh | 22/22 citation của lần chạy lại nhất quán (trước: Điều 98, 127, 137, 21 đều lệch khoản) |
| 3 | Retrieval | Chunk chạy tràn sang khoản/Điều kế tiếp (`## **Điều 99…`), nhiều chunk điểm lặp tiêu đề; ghép 4 chunk | `trim_to_provision`/`build_provision`: cắt ở khoản kế/Điều kế, gộp các điểm một lần, trần 1.200 ký tự. Dùng chung cho `ground_citations` (đường LLM) | Tổng quote **14.679 → 6.785 ký tự**; mỗi quote đúng 1 tiêu đề Điều |
| 4 | Dữ liệu quy tắc | Không có quy tắc riêng cho «bồi thường chi phí đào tạo 3 tháng lương»; Điều 3 còn bị bỏ qua LLM do `skip_llm_clauses` | Flag `training_cost_flat` (Điều 62 K1, K3; Điều 40 K3) và `forfeit_wage_quit` (Điều 94 K1, Điều 40 K2) tách riêng; `RiskItem.findings[]` ghi **câu vi phạm** + căn cứ + confidence cho từng hành vi | Điều 3: 3 → **4 vi phạm độc lập** |
| 4 | Gán Điều | `clause_hint` cố định theo flag | `_locate_clause` tìm Điều thật sự chứa mẫu vi phạm | Test: câu vi phạm ở Điều 7 → báo «Điều 7» |
| 5 | Dữ liệu quy tắc | Mỗi mục Điều 21 chỉ có/không; «đơn vị làm việc/phòng» tính là địa điểm; «ngày nghỉ cuối tuần» trong câu ép OT tính là thời giờ nghỉ; `đào tạo` trong điều khoản bồi thường tính là chế độ đào tạo; lương thiếu «trả lương» → bị xếp «thiếu» | Chia mục thành `Part` theo đúng điểm của khoản 1; 4 trạng thái `co / chua_day_du / thieu / khong_ap_dung`; thêm giới tính, địa điểm cụ thể, thời giờ nghỉ ngơi; BHXH chỉ nêu việc «không đóng» ⇒ không tính là có; `ppe` = không áp dụng cho việc văn phòng/nghiên cứu (trừ khi có từ khóa độc hại) | Lương: «thiếu» → **chưa đầy đủ** (có mức lương); thêm 4 mục chưa đầy đủ; `analysis.required_content` + bảng trong báo cáo |
| 6 | Hậu xử lý | `check_preamble_citations` thêm cảnh báo khi văn bản chỉ «hết hiệu lực một phần» dù không chỉ ra nội dung sai | Trạng thái một phần chỉ là ngữ cảnh khi đã có lỗi thật (hết hiệu lực, sai số hiệu, sai ngày) | Mục «Căn cứ pháp lý đầu HĐ cần rà soát» **biến mất** khỏi kết quả (0.80 → không có) |
| 7 | Rule + LLM + prompt | `_extract_line_around` lấy cả dòng = cả Điều; CCCD gán `tax_id` (prompt «MST/CCCD/CMND»); `duration` hard-code `None`; LLM chép cả đoạn | Trích theo **câu**; `Party.id_number` tách khỏi `tax_id` (+ sửa đầu ra LLM); `duration` tính từ ngày bắt đầu/kết thúc; mỗi field LLM bị cắt về đúng chủ đề (`_clean_llm_field`); prompt yêu cầu 1–2 câu đúng chủ đề; regex ngày nhận «15 tháng 07 năm 2026», «đến hết ngày…» | `tax_id` CCCD → `id_number`; `duration` null → **6 tháng**; `confidentiality` 903 → 55 ký tự; `payment_terms` hết dính khoản bảo hiểm; `indemnity` chỉ còn câu bồi thường |
| 8 | Báo cáo | `ty_le_da_kiem` bị đọc như chất lượng | Thêm `coverage.pham_vi` và `coverage.phat_hien` (số rủi ro, Điều chưa có rủi ro, Điều chỉ kiểm bằng quy tắc, độ tin cậy TB, số rủi ro tin cậy thấp, lưu ý) | Báo cáo markdown có mục «Phạm vi và độ tin cậy» |
| 9 | Dữ liệu / logic | `parse_as_of("15 tháng 07 năm 2026")` âm thầm trả về **hôm nay**; nhãn «· 2026-07-15» không nói là ngày ký | `parse_vn_date`; `analysis.legal_as_of` (ngày ký = cơ sở, ngày phân tích, so sánh trạng thái BLLĐ hai thời điểm); mọi `citation.status` ghi «tại ngày ký 2026-07-15» | Xem mục Cơ sở đối chiếu pháp luật |
| 10 | Hậu xử lý | `confidence=0.9` gán cứng | `evidence_confidence`: trần theo flag (training 0.85), −0.1 mỗi lỗi nhất quán/không xác minh, 0.45 nếu không có căn cứ; đường LLM: `min(confidence LLM, trần chứng cứ)`; ghi `confidence_notes` | Hợp đồng gốc: Điều 3 = 0.85, các Điều còn lại 0.9 vì căn cứ **đều xác minh và nhất quán**; không có corpus → thấp hơn ở mọi Điều (test) |

## Điều chưa làm được / giới hạn cần biết

- **Điều 1 chưa được LLM chấm lại**: quota Gemini free-tier (20 request/ngày/key) đã hết khi chạy lại, nên `coverage` của lần chạy lại là 4/5 (Điều 1 `unchecked_error`). Phần đường LLM (`evidence_confidence`, chặn bản sửa không hợp lệ) được kiểm bằng unit test với LLM giả, chưa kiểm bằng gọi Gemini thật.
- `skip_llm_clauses` vẫn bỏ qua LLM cho Điều đã có cảnh báo critical (giữ nguyên thiết kế tiết kiệm quota). Rủi ro độc lập mới phải thêm thành quy tắc; thông tin này giờ hiển thị trong `coverage.phat_hien.dieu_chi_kiem_bang_quy_tac`.
- Phát hiện «thiếu nội dung Điều 21» dựa trên mẫu câu nên có thể bỏ sót cách diễn đạt khác; trần confidence 0.8 và ghi chú đi kèm.
- Hiệu lực theo thời gian: kho chỉ có trạng thái **hiện tại** của từng điều (`is_effective`) và trạng thái cấp văn bản theo ngày; hệ thống so sánh văn bản ở ngày ký và hôm nay, nhưng sửa đổi ở cấp điều khoản giữa hai mốc chưa phát hiện được.
- Không có tập chuẩn (gold) cho hợp đồng này nên recall/precision của phát hiện chưa đo được; bộ `tests/evaluation` hiện kiểm độ phủ quy tắc trên hợp đồng mẫu.

## Thay đổi chính (tệp)

`app/agents/`: `clause_text.py` (mới), `labor_red_flags.py`, `labor_completeness.py`, `legal_citations.py`, `labor_code_resolver.py`, `clause_parser.py`, `preamble_citations.py`, `risk_flagger.py`, `effectivity.py`, `workflow.py`; `app/core/{dates,prompts}.py`; `app/schemas/contract.py` (field tùy chọn: `Party.id_number`, `RiskItem.findings/confidence_notes`, `ContractAnalysis.legal_as_of/required_content`); `app/application/use_cases/report.py`; `frontend/src/components/ContractProfile.jsx`.
