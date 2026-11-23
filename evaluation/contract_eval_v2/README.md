# Kiểm chứng cải tiến QA: dev đối chứng và kiểm tra tính bất biến

Đã hoàn thành full (18/11/2026): 369 QA + 369 judge + 117 workflow; xem [báo cáo full](../../docs/bo_test_hoi_dong/KET_QUA_FULL_QA_WORKFLOW.md) và `artifacts/full_preflight/FINAL_VALIDATION.json`. Test QA đạt 76,4%, F1 tại 93 Điều có nhãn sau full workflow là 71,2%; công khai lỗi phủ định của quy tắc và thiếu context của QA tổng quát. `python -m evaluation.contract_eval_v2.full_run check` kiểm offline dữ liệu/hash, `python -m evaluation.contract_eval_v2.validate_full` kiểm số lượng, phép tính và đóng hash kết quả. [Báo cáo chuẩn bị](../../docs/bo_test_hoi_dong/RA_SOAT_TRUOC_CHAY_FULL.md) giữ trạng thái lịch sử trước khi chạy. Không so trực tiếp điểm theo rubric mới với số v1/v4.

Vòng v3 mới hơn dùng bản v2 này làm baseline, tham khảo nghiên cứu và nguồn Chính phủ, bổ sung 32 ca regression và tám ca mới: xem [`RESEARCH_NOTES.md`](RESEARCH_NOTES.md) và [báo cáo v3](D:/contract-agent/docs/bo_test_hoi_dong/NGHIEN_CUU_V3_KET_QUA.md). Các số/artifacts v2 dưới đây giữ nguyên như một mốc lịch sử.

Đây là thí nghiệm phát triển sau khi đã xem lỗi v1, **không phải bộ test giữ kín mới**. Mục tiêu là kiểm tra một thay đổi cụ thể: giải đúng số Điều hợp đồng rồi dùng nội dung Điều để tìm luật. Không sửa dữ liệu, split, nhãn hoặc khóa test v1.

## Dữ liệu và đơn vị độc lập

Nguồn: 16 ca gốc `injection` thuộc **dev v1**, một vi phạm và một hợp lệ cho mỗi trong tám nhóm luật. Mỗi ca có năm câu: T1, T2, T3, hỏi lại bằng câu chữ khác và T1 với số Điều đổi sang 30 + số cũ. Tổng 80 câu, nhưng chỉ 16 ca gốc; các hợp đồng còn dùng chung một nền tổng hợp. Không coi 80 câu là 80 quan sát độc lập hoặc hợp đồng thực tế.

32 hợp đồng văn bản gồm 16 bản gốc và 16 bản đổi số Điều; thay đổi cả số tiểu mục trong Điều, giữ nguyên nội dung nghĩa vụ. Đổi số Điều nhằm kiểm tra khả năng bám nội dung thay vì ghi nhớ vị trí. Cách hỏi mới là paraphrase xác định trước, không dùng LLM sinh nhãn.

`inputs.jsonl` có id và đường dẫn trung tính, câu hỏi, mốc thời gian và loại biến thể; không có nhãn hay căn cứ gold. `gold.jsonl` kế thừa đáp án từ nguồn; `gold_clause_ids` được đổi theo Điều mới, còn `gold_clause_text` và các thông tin nguồn giữ nguyên trích đoạn v1 để truy vết. Trường này không được đưa vào prompt hay dùng để so khớp văn bản hợp đồng mới. Nhãn kế thừa **chưa được chuyên gia xác nhận**. Tám câu T3 trên hợp đồng hợp lệ không có Điều/luật gold để truy xuất; do đó retrieval luật chấm 72/80 câu và luôn công khai mẫu số này.

`manifest.json` ghi hash đầu vào, đáp án, hợp đồng, nguồn và quy tắc trước khi chạy. Không đổi chúng để làm đẹp kết quả. `QUALITY_AUDIT.json` tách rõ các điều kiện đã đạt và chưa đạt của v1: hash, chia tập, độ phủ dev, nhãn người, phạm vi workflow và nhóm temporal.

## Các cấu hình so sánh

| Cấu hình | Điều hợp đồng | Truy vấn tìm luật |
|---|---|---|
| `baseline` | Vector như trước thay đổi | Câu hỏi + lịch sử như trước |
| `reference_only` | Ưu tiên đúng số Điều được hỏi, trong đúng hợp đồng | Vẫn chỉ câu hỏi + lịch sử |
| `grounded` | Như `reference_only` | Thêm nội dung Điều thực lấy được |

Ba cấu hình dùng cùng tiến trình, kho luật và model embedding. Đảo thứ tự cấu hình giữa các câu để giảm ảnh hưởng thứ tự; không tuyên bố đây là phép đo độ trễ không chịu tác động cache. Không dùng Điều gold để chọn ngữ cảnh: chỉ phân tích số Điều trong câu hỏi và tra qua repository của hợp đồng đang hỏi. Tham chiếu ghi rõ tên văn bản luật không được coi là số Điều hợp đồng.

QA chạy hai cấu hình `baseline` và `grounded` trên 32 câu (T1 gốc + T1 đổi số, 16 ca gốc), tổng 64 câu trả lời. QA dùng graph thật, checkpointer trong bộ nhớ, tắt bộ nhớ dài hạn để từng câu độc lập; không đánh giá hội thoại nhiều lượt hoặc streaming. Prompt giữ nguyên. Trace lưu context thực trong trạng thái graph cuối, **bao gồm đoạn luật chèn cố định**, khác phép dựng lại context chỉ từ kết quả vector ở v1.

Judge Groq Qwen chấm câu trả lời GPT-OSS; không thấy tên cấu hình trong prompt. Correctness 0–2 được chuẩn hóa 0–1; trích xuất kết luận, chấm mức hỗ trợ bởi context và ghi lý do. Judge mới chưa được người hiệu chuẩn trên mẫu đầu ra này, nên QA là số đo tự động tạm thời. Không so trực tiếp điểm này với điểm QA toàn test v1 vì khác mẫu và rubric. Bảng `human_review.csv` để người đọc kiểm tra và điền nhãn riêng, không tự điền thay người.

## Cách tính

- Retrieval: R@5 ở mức văn bản–Điều; loại bản trùng của cùng Điều trong danh sách trả về trước khi chấm. Chỉ dùng các kết quả thực đã trả về, không mở rộng thêm ứng viên để tăng điểm.
- So sánh theo cặp trên cùng câu. CI95 của độ chênh lấy mẫu lại theo `base_case_id`, 1.000 lần, seed 42; giữ những câu cùng ca đi cùng nhau. Chưa loại được phụ thuộc do hợp đồng nền dùng chung.
- Báo số kỳ vọng, số hoàn tất, số chấm được, số sinh được đáp án hợp lệ; dữ liệu chưa có giữ `null`, không dùng số unit test làm độ chính xác pháp lý.
- Báo cả ca cải thiện và thoái lui. Không sửa nhãn, xóa ca khó hoặc lựa chọn lần chạy có điểm đẹp hơn.

## Chạy và kiểm tra

```powershell
python -m evaluation.contract_eval_v2.audit
python -m evaluation.contract_eval_v2.experiment prepare
python -m pytest tests/evaluation/test_contract_eval_v2.py -q
```

Runtime cần DB bản sao đánh giá đã có, image `contractlens-api:latest`, model embedding trong cache. Không trỏ tới DB bất kỳ ở cổng 5433: đó có thể là ứng dụng khác. Dùng mạng riêng của `evaluation/docker-compose.eval.yml`, không sửa `schema.sql` hoặc áp schema vào bản sao.

```powershell
docker start contractlens-eval-01a154eb-postgres-1
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -e LEGAL_RETRIEVAL_MODE=vector -v D:/contract-agent/evaluation/contract_eval_v2/artifacts:/workspace/evaluation/contract_eval_v2/artifacts worker python -u -m evaluation.contract_eval_v2.experiment retrieval
# qa và judge gọi Groq, dùng tài khoản đã cấu hình; chỉ chạy khi được người dùng cho phép gửi dữ liệu.
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -e LLM_PROVIDER=groq -e GROQ_MODEL=openai/gpt-oss-120b -e LEGAL_RETRIEVAL_MODE=vector -v D:/contract-agent/evaluation/contract_eval_v2/artifacts:/workspace/evaluation/contract_eval_v2/artifacts worker python -u -m evaluation.contract_eval_v2.experiment qa
docker compose -p contractlens-eval-01a154eb --env-file .env -f evaluation/docker-compose.eval.yml run --rm --no-deps -v D:/contract-agent/evaluation/contract_eval_v2/artifacts:/workspace/evaluation/contract_eval_v2/artifacts worker python -u -m evaluation.contract_eval_v2.experiment judge
python -m evaluation.contract_eval_v2.experiment score
```

Mỗi bước bỏ qua bản ghi đã có để tiếp tục lần chạy gián đoạn. Giữ nguyên mã/config giữa các lần resume; thay phương pháp phải có thí nghiệm phiên bản khác. Không xóa đầu ra để chạy lại chọn điểm. `GROQ_PAYLOAD_REVIEW.jsonl` là bản xem trước 64 prompt ở retrieval đầu tiên; graph có thể rewrite/retry theo luồng có sẵn, trace QA mới là ngữ cảnh thực dùng cuối cùng.

Dữ liệu đánh giá được nạp **vào DB bản sao** dưới user `contract-eval-v2-dev@example.invalid`, id ở `artifacts/dev_clause_grounding/contract_map.json`. Không tự xóa dữ liệu. Thư mục artifacts trong gói này chứa dữ liệu tổng hợp, kết quả dev và context luật phục vụ đối chiếu; không chứa khóa API, `.env` hoặc hợp đồng cá nhân.

Để có kết luận tổng quát hóa thuyết phục hơn, còn cần nhãn được người kiểm, hợp đồng nền đa dạng và tập test mới chưa dùng để chọn sửa. Thí nghiệm này chứng minh tác động có kiểm soát của một thay đổi trên dev, không thay thế những bước đó.
