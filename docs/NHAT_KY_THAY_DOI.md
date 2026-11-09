# Nhật ký thay đổi theo kế hoạch 1 tuần

Ghi lại các quyết định và thay đổi so với kế hoạch gốc. Mốc đối chiếu: tag `baseline-tuan-0` (commit `dd1782f`).

## Ngày 1
- **Không dùng `git add -A`** để chụp snapshot: sẽ kéo cả các file riêng chưa theo dõi (ví dụ `.serena/`, `docs/presentations/`, `tests/fixtures/legal_qa.jsonl` 15 MB). Chỉ gắn tag lên HEAD đã sạch.
- **Môi trường kiểm thử sạch** là container api (Python 3.12), không phải venv 3.12 cục bộ (máy dùng 3.11). Kết quả: `docs/test_baseline.txt`.
- **Hiệu lực luật:** cờ sai, đã sửa dữ liệu cho 3 văn bản luật lao động, có bảng sao lưu. Chi tiết và giới hạn: `docs/kiem_tra_hieu_luc.md`.

## Ngày 2: lỗi nuốt âm thầm
- Điều khoản mà judge lỗi hoặc trả JSON hỏng không còn bị coi là sạch. `analysis.coverage` ghi `tong_so_dieu`, `da_kiem`, `chua_kiem`, `ty_le_da_kiem` và danh sách điều chưa kiểm kèm trạng thái `unchecked_error` hoặc `unparsable`.
- Judge trả JSON thiếu `severity` hoặc có `severity` ngoài `critical|warning|ok` cũng tính là không dùng được (trước đây thiếu `severity` bị coi là "ok").
- Không trích xuất được điều khoản nào: `/analyze` trả 502, không lưu kết quả (trước đây lưu một analysis rỗng rồi phục vụ từ cache).
- Cache chỉ phục vụ kết quả đầy đủ: analysis không có điều khoản hoặc có `chua_kiem > 0` sẽ được chạy lại.
- Giao diện: điều chưa kiểm tính riêng ("Chưa kiểm"), không tính vào "Ổn", và banner xanh không hiện khi còn điều chưa kiểm.
- Không thêm trường vào `RiskItem`; chỉ thêm `coverage` tùy chọn vào `ContractAnalysis`.

## Ngày 3: đầu vào
- `.doc` bị từ chối trước khi lưu (400, "chuyển sang .docx"). Trước đây `.doc` được nhận rồi python-docx thất bại.
- Tệp không đọc được (PDF ảnh quét không có lớp chữ, tệp hỏng) bị từ chối với 400 và xóa tệp đã lưu. Trước đây vẫn lưu hợp đồng trạng thái `uploaded` và giao diện đi tiếp sang bước phân tích rồi báo lỗi khó hiểu. Lỗi khi tạo chunk/embedding/ghi DB giờ lan ra (không nuốt), tệp đã lưu được xóa.
- Xóa `app/document/file_handler.py`: không nơi nào gọi.
- **Giới hạn 12.000 ký tự** (`clause_parser._LLM_GAPFILL_CHAR_LIMIT`): chỉ giới hạn đầu vào của LLM bù các trường mà regex bỏ sót; việc tách và đánh giá điều khoản chạy trên toàn văn. Báo cáo cũ nói điều khoản sau 12.000 ký tự không được kiểm là chưa đúng. Đã thêm cảnh báo log khi bị cắt. Chưa đo trên 5–10 hợp đồng: máy chỉ có 1 hợp đồng mẫu thật (3.605 ký tự, dưới ngưỡng) nên cần bạn cung cấp thêm file để đo. Cập nhật 2026-11-09: đã đo thêm 6 hợp đồng tổng hợp của gold set, 2.715 đến 3.765 ký tự, đều dưới ngưỡng; mẫu này không đại diện cho hợp đồng dài.

## Ngày 4-5: công cụ gold set và đánh giá (nhãn do người gán)
- `evaluation/gold/`: mẫu CSV, hướng dẫn gán nhãn, `prepare_units.py` (chọn Điều bằng rút ngẫu nhiên có seed, không nhìn đầu ra hệ thống, ghi băm SHA-256 hợp đồng chứ không ghi tên tệp), `kappa.py` (Cohen's kappa thuần Python, không thêm pandas/sklearn), `make_split.py` (chia dev/test theo hợp đồng), `draw_citations.py` (rút 50 trích dẫn để hai người kiểm 3 tiêu chí). Đổi tên từ `sample_citations.py` vì `.gitignore` có mẫu `sample_*`.
- `evaluation/run_eval.py`: Precision/Recall/F1/False rate ở mức Điều, bootstrap 95% (1000 lần, mức đơn vị), độ phủ, hash commit; cấu hình `rule_only` (regex luật đỏ + căn cứ pháp lý ở phần mở đầu, không LLM) và `full`. Điều chưa kiểm được tính là dự đoán "không có rủi ro" và báo riêng ở cột độ phủ.
- Đã chạy thử toàn bộ đường đi (rule_only và full) trên hai hợp đồng mẫu với nhãn giả; kết quả thử không được lưu vào repo và không có ý nghĩa thống kê.
- Chưa làm: baseline không RAG (kế hoạch cho phép cắt). Chưa có gold set thật nên chưa có số liệu đánh giá.
- Lưu ý khi chạy: hợp đồng đưa vào nên là `.docx`; tệp `.md` còn dấu `#`/`**` làm bước trích điều khoản không thấy Điều nào (nay báo lỗi 502 thay vì trả kết quả rỗng).

## Ngày 6: bảo mật nhẹ và tài liệu
- Mật khẩu đăng ký tối thiểu 8 ký tự. Đăng nhập không đặt sàn độ dài để tài khoản cũ (6 ký tự) vẫn vào được. Giao diện hiển thị được lỗi 422.
- Giới hạn đăng nhập sai: 5 lần mỗi 15 phút theo (địa chỉ, email), trả 429 kèm `Retry-After`. Trong bộ nhớ, một tiến trình; không thêm thư viện mới.
- Đăng ký trùng email: trả 400 với thông báo chung (trước là 409 "Email already registered"). Giới hạn: không có xác minh email nên người dùng vẫn phân biệt được qua việc đăng ký email mới thành công (200).
- Giới hạn tải lên 10 MB (`MAX_UPLOAD_MB`), 413. Chỉ đọc tối đa giới hạn+1 byte vào bộ nhớ của ứng dụng; máy chủ vẫn nhận phần thân yêu cầu trước đó (muốn chặn sớm hơn cần cấu hình ở proxy).
- `requirements.txt` ghim phiên bản theo container đang chạy (Python 3.12); Dockerfile ghim `torch==2.13.0` từ chỉ mục CPU. Chưa dựng lại image sau thay đổi này.
- README: đổi sang hợp đồng lao động, thêm mục Giới hạn. README trước đó không nêu đa-LLM, `as_of_date` hay HITL trên giao diện, nên không có gì cần xóa ở đó; cần rà các tuyên bố này ở slide và báo cáo (tệp của bạn).
- Credential mặc định ghi rõ chỉ dành cho phát triển (README), chưa đổi giá trị.

## Gold set nháp do AI soạn (cần người xác minh)
- Bạn không có 6-8 hợp đồng lao động thật đã ẩn danh nên AI viết 6 hợp đồng tổng hợp (`evaluation/gold/contracts/`, 10 Điều mỗi hợp đồng, 4 Điều cài lỗi và các Điều đối chứng đúng luật; hợp đồng 06 chỉ có 2 lỗi). Không dùng hợp đồng mẫu `data/demo_contracts` và `CTR-LAB-01` vì mã đã được chỉnh theo chúng.
- 30 đơn vị rút ngẫu nhiên có seed (`prepare_units`), trong đó 12 có rủi ro theo thiết kế (40%). Nhãn nháp ở cột `ai_*` kèm điều luật; các điều luật chính (Điều 17, 20, 25, 35, 48, 98, 105, 107, 113, 127, 137, 168, 187) đã đối chiếu với nội dung trong kho luật của hệ thống. Riêng cụm "chỉ được thử việc một lần đối với một công việc" (Điều 25) không tìm thấy trong kho, cần mở văn bản gốc.
- Các cột người gán (`ann1_*`, `ann2_*`, `expert_final`) để trống có chủ đích: nhãn AI không phải gold. Điền hộ cả hai người gán và chuyên gia sẽ cho kappa giả. Người xác minh dùng `adopt_ai` sau khi đã kiểm từng đơn vị.
- Hệ quả cho báo cáo: đây là bộ kiểm thử tổng hợp, đo xem hệ thống có phát hiện đúng các lỗi đã biết không; không phải độ chính xác trên hợp đồng thật. Lỗi viết ngay theo mẫu quen thuộc của 7 luật đỏ nên kết quả `rule_only` có thể cao hơn thực tế.

## Truy xuất: lượt tìm phạm vi luật lao động
- Thêm lượt tìm riêng trong Bộ luật Lao động 2019 và Nghị định 145/2020 khi truy vấn là về lao động (`RAG_LABOR_SCOPE`, mặc định bật; `PgLegalVectorSearch.search_in_doc_nums`). Đo trên bản sao cách ly: exact provision recall 0,230 lên 0,299, recall@5 0,230 lên 0,270, ba ca tốt lên, không ca nào xấu đi; số liệu và cách đọc ở `evaluation_results/reports/LABOR_EFFECTIVITY_RAG_RUN.md`.
- Đa dạng hóa hạt giống đã thử và gỡ bỏ vì không có lợi (một ca xấu đi, không ca nào tốt lên).
- Dùng lại vector embedding của cùng một truy vấn trong một lượt truy xuất (bộ nhớ đệm 64 mục), giảm độ trễ của lượt tìm phụ.
- Nhánh từ khóa FTS vẫn chưa sửa (ba cách thử đều thất bại; xem báo cáo trên).
- Lưu ý khi đọc kết quả: đây là thay đổi truy xuất, cần chạy lại các đánh giá sau này trên cấu hình mới; số liệu RAG-only cũ (0,201) là trước hai thay đổi (sửa cờ hiệu lực và lượt tìm phụ).

## 2026-11-09: rà soát độ chính xác pipeline (commit `fa71544`, nhánh `fix/pipeline-accuracy-review`)
Nguồn: 10 nhận xét về kết quả phân tích hợp đồng `CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.docx`. Nguyên nhân gốc từng lỗi, trước/sau và giới hạn: `docs/accuracy-review-contractlens-f87af2fa.md`. Gold set **chưa đóng băng** (chưa có tag `eval-frozen`), nên các thay đổi dưới đây không vi phạm nguyên tắc đóng băng; nhưng chúng đổi hành vi hệ thống, nên mọi số liệu đánh giá phải chạy lại trên mã này.
- **Trích dẫn:** truy vấn kho luật đúng Điều/khoản/điểm (trước đây lấy dòng đầu theo độ sâu `ltree`, ra sai khoản: Điều 98 K2, 127 K1, 137 K2 → nay K1, K2, K3). Quote cắt đúng khoản; thêm kiểm tra nhất quán `article`/`location`/`evidence_path`/`quote`. Căn cứ pháp lý của các luật đỏ đổi theo đối chiếu kho: bỏ Điều 141 (ốm đau) và Điều 129 khỏi `terminate_pregnancy`/`fine_deduct_wage`.
- **Luật đỏ:** thêm `training_cost_flat` (bồi thường chi phí đào tạo bằng số tháng lương cố định, Điều 62, Điều 40 K3) và tách `forfeit_wage_quit`. Còn 8 cờ (trước 7). Điều bị gán theo nội dung vi phạm thật, mỗi vi phạm là một `finding` riêng. **Ảnh hưởng gold set:** nếu cột `ai_luat_dau_ra` dùng "7 luật đỏ" thì cần ánh xạ lại cho cờ mới.
- **Điều khoản sửa đổi:** viết lại theo câu rồi kiểm lại (còn vi phạm, câu cụt, mất số liệu hợp pháp); không qua kiểm tra thì không hiển thị. Áp dụng cả cho bản sửa do LLM sinh.
- **Điều 21 BLLĐ:** 4 trạng thái `co`/`chua_day_du`/`thieu`/`khong_ap_dung`, thêm giới tính, địa điểm cụ thể, thời giờ nghỉ ngơi; `ppe` là "không áp dụng" cho việc văn phòng. Test `contract_qa_cases` đổi theo (kỳ vọng `ppe` thay đổi).
- **Phần mở đầu hợp đồng:** văn bản chỉ hết hiệu lực một phần không còn tự tạo cảnh báo.
- **Trích xuất:** `Party.id_number` tách khỏi `tax_id`; `duration` tính từ ngày; mỗi trường LLM bù bị cắt đúng chủ đề; `parse_vn_date` sửa lỗi "15 tháng 07 năm 2026" âm thầm thành ngày hôm nay.
- **Báo cáo:** `coverage.pham_vi`/`phat_hien` (độ phủ điều khoản không phải chất lượng phát hiện), `legal_as_of` (đối chiếu luật tại ngày ký), độ tin cậy theo chất lượng chứng cứ thay cho 0,9 cố định, `confidence_notes`. Chỉ thêm trường tùy chọn vào schema.
- **Giới hạn chưa đóng:** Điều 1 chưa được LLM chấm lại vì hết quota Gemini ngày; đường LLM mới kiểm bằng LLM giả; Điều bị quy tắc cờ critical vẫn bỏ qua LLM; phát hiện thiếu Điều 21 dựa trên mẫu câu; chưa có số liệu đo recall/precision.
## 2026-11-09: benchmark truy xuất pháp luật chung (dev)
- Đã chạy `coverage`, đóng băng `split` (commit `2a41124`, tag `legalqa-split-frozen`) và chạy dev cho `fts`, `vector`, `hybrid` với `--only-covered`. Không chạy test.
- **Không sửa code truy xuất, không sửa `norm_doc` / `article_from_path`.** Coverage thấp (772/3.196 câu tìm được) do văn bản gold hết hiệu lực (`status_flag=2`) hoặc chunk `is_effective=false` bị lọc, không do chuẩn hoá số hiệu. Chi tiết: `evaluation_results/legal_qa/PHAN_TICH_LOI_DEV.md`.
- Phát hiện chưa xử lý, chờ quyết định: FTS dùng `plainto_tsquery` (AND toàn câu) nên rỗng ở 50/216 câu và chen hit nhiễu vào rank 2 khi RRF; chunk mở đầu không có Điều chiếm chỗ trong top 10.
- Nguồn `data/dataset.csv` chưa xác định (xem `NGUON_DATASET.md`).

## 2026-11-09: khai báo trước 3 biến thể thử trên dev (legal QA)
Khai báo **trước khi cài đặt và trước khi chạy**. Chỉ thử đúng 3 biến thể dưới đây; **không thêm biến thể nào sau khi xem kết quả** (kể cả đổi trọng số, đổi `rrf_k`, đổi cách tách từ). Mọi biến thể là cờ cấu hình, mặc định giữ hành vi cũ, không xoá code cũ.

| Biến thể | Nội dung | Cờ (`app/core/settings.py`) |
|---|---|---|
| V1 | FTS dùng truy vấn OR: tách câu hỏi thành các từ `\w+` (không trùng), nối bằng `\|`, dùng `to_tsquery('simple', ...)` thay cho `plainto_tsquery` (AND). Không lọc stopword. | `legal_fts_query = "or"` (mặc định `"plain"`) |
| V2 | V1 + loại chunk không có Điều (path không có token `D<số>`, tức PREAMBLE, `article=None`) ngay trong SQL của cả vector và FTS (để top-k được lấp bằng chunk có Điều). | `legal_article_chunks_only = true` (mặc định `false`) |
| V3 | V2 + RRF có trọng số: vector 0,7, FTS 0,3 (`rrf_k=60` giữ nguyên). | `legal_rrf_weight_vector = 0.7`, `legal_rrf_weight_fts = 0.3` (mặc định 1,0 / 1,0) |

Cấu hình sẽ chạy (dev, `--only-covered`, n=216, cùng split đóng băng): `fts` cũ, `fts`+V1, `vector` (không đổi), `hybrid` cũ, `hybrid`+V1, `hybrid`+V2, `hybrid`+V3.

Quy tắc chọn, khai báo trước:
- Chọn biến thể (trong V1, V2, V3 ở mode hybrid) có **MRR@10 cao nhất** trên dev.
- Coi là "hơn vector rõ ràng" chỉ khi **khoảng tin cậy 95% bootstrap ghép cặp** của (MRR@10 biến thể − MRR@10 vector) trên cùng 216 câu **không chứa 0 và nằm phía dương**. Nếu không, ghi trung thực là không có biến thể nào hơn vector rõ ràng (khi đó biến thể chọn vẫn là biến thể MRR cao nhất để báo cáo, nhưng không tuyên bố cải thiện).
- Chưa chạy test. Chỉ chạy test một lần sau khi được duyệt, cho: `fts`, `vector`, `hybrid` cũ, biến thể được chọn.

Về dấu `*` (dirty) trong `RESULTS.md`: `git status` toàn repo luôn có file không liên quan (`docs/dfd.md`, báo cáo gemini, `.serena/`, ...). Không stash hay xoá chúng. `git_info()` sẽ chỉ tính dirty trên mã ảnh hưởng kết quả: `app/` và `evaluation/legal_qa_retrieval.py` (kể cả file chưa theo dõi), và ghi rõ phạm vi này vào `metrics.json`.
