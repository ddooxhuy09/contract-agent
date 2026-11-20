# Vòng nghiên cứu và cải tiến v3 — 18/11/2026

V4 mới hơn: `review_round.py`, `review_report.py` và [báo cáo v4](D:/contract-agent/docs/bo_test_hoi_dong/CAI_THIEN_V4_KET_QUA.md). Dùng thêm một lượt cùng model kiểm chứng bản nháp theo nguồn (không phải judge/gold), bỏ nguồn vector lệch phạm vi khi có căn cứ chính xác và bổ sung bối cảnh hợp đồng. V4 đo lại 40 ca đã chẩn đoán và 16 validation không dùng sửa v4, cùng rubric; tác động là của tổ hợp thay đổi, chưa có ablation riêng cho từng phần.

Mục tiêu: tăng chất lượng câu trả lời bằng code và nguồn luật thực, giữ nguyên nhãn, model sinh, judge và rubric của phép đo trước. Dữ liệu và cấu hình nằm trong `artifacts/research_evidence_v3/protocol.json`, đóng băng trước kết quả candidate.

## Nguồn nghiên cứu và cách áp dụng

| Nguồn sơ cấp | Ý tưởng dùng trong đồ án | Giới hạn |
|---|---|---|
| Yan et al., [Corrective Retrieval Augmented Generation](https://arxiv.org/abs/2401.15884) | Không tin mặc định rằng vector đã tìm đủ căn cứ; bổ sung truy xuất chính xác và tinh lọc phần luật đưa vào prompt | Đây là cách triển khai riêng bằng chỉ mục chủ đề và repository, không phải tái lập toàn bộ CRAG hay mô hình evaluator của paper |
| Gao et al., [Enabling Large Language Models to Generate Text with Citations / ALCE](https://aclanthology.org/2023.emnlp-main.398/) | Phân biệt đúng câu trả lời với chất lượng viện dẫn; lưu ngữ cảnh thực và kiểm số Điều hợp đồng riêng với Điều luật | Giữ rubric đang dùng để so trước/sau; chưa triển khai bộ đo NLI của ALCE |
| Asai et al., [Self-RAG](https://arxiv.org/abs/2310.11511) | Tham khảo việc kiểm lại bằng chứng trước kết luận | Không huấn luyện reflection tokens, không tuyên bố hệ thống là Self-RAG |

## Nguồn luật Việt Nam

- [Bộ luật Lao động 45/2019/QH14 — Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=198540&lang=vi&pageid=27160).
- [Văn bản hợp nhất 125/VBHN-VPQH — Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=215248&pageid=27160), [PDF chính thức có thể tìm kiếm](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/9/125-vbhn-vpqh.pdf). Đã kiểm các Điều 17, 25, 26, 40, 62, 113, 127 và 190 cho các thay đổi/trường hợp mới liên quan.
- Trang VBPL của Bộ luật trả 403 trong công cụ truy cập phiên này. Không có MCP chuyên trang luật Việt Nam được kết nối; đã dùng web và MCP Search để xác định nguồn Chính phủ công khai, cùng corpus Postgres hiện có. Không tuyên bố đọc được trang bị chặn, không crawl toàn bộ website hay sửa DB luật.

Chỉ mục chủ đề dùng để **chọn văn bản cần đọc**, không quyết định vi phạm. Cùng chủ đề giấy tờ hoặc kỷ luật, câu hợp lệ/phủ định và câu vi phạm đều được đọc cùng các Điều liên quan. Nội dung pháp luật lấy từ repository thật, kèm path nguồn thật và kiểm văn bản theo ngày; không chép đáp án benchmark vào ứng dụng. Ánh xạ Điều của phiên bản 2019 không áp cho bộ luật đời trước.

## Thay đổi code

1. Loại số thứ tự Điều/tiểu mục hợp đồng khỏi truy vấn luật, giữ số Điều luật được nêu đích danh. Giữ chữ số đơn trong truy vấn pháp luật thay vì làm mất Điều 4/5…
2. `qa_evidence.py`: nhận diện chủ đề trong phạm vi lao động; tra trực tiếp Điều trong kho, ghép đúng thứ tự, loại dòng lặp và phần tràn sang Điều kế tiếp. Đặt căn cứ cốt lõi trước các kết quả vector bổ sung. Không kết luận nhãn bằng regex.
3. Khi có căn cứ chính xác theo chủ đề, không chèn thêm đoạn luật cố định có thể bắt nhầm chủ đề từ Điều khác trong nền hợp đồng.
4. Prompt QA phân biệt thiếu dữ kiện vụ việc với thiếu luật; cấm suy “không thấy điều cấm” thành “được phép”; yêu cầu kiểm chủ thể, hành vi, điều kiện, phủ định, ngoại lệ và viện dẫn đúng nội dung.
5. Chuẩn hóa số Điều hợp đồng LLM trả về từ int/string, xác minh thuộc ngữ cảnh, không tự thêm nguồn mà model chưa dẫn.

Không đổi API/schema, auth, node/cạnh LangGraph, retry, streaming hoặc checkpointer. Không thêm dependency. Các câu hỏi ngoài phạm vi lao động hoặc thiếu căn cứ chính xác giữ retrieval thông thường.

## Phép đo thật và cách tránh làm đẹp số

| Nhóm | Quy mô | Cách sử dụng |
|---|---:|---|
| Dev từ vòng trước | 80 câu / 16 ca gốc | So lại v2 grounded với candidate; không coi là test độc lập |
| Regression từ test v1 | 32 câu / 32 ca gốc | Chọn trước bằng seed 20261118: mỗi nguồn injection/injection_v2, mỗi chủ đề, một vi phạm và một hợp lệ; không trùng ca gốc dev |
| Ca mới đối chiếu nguồn | 8 câu / 8 ca | Thử việc và nghỉ hằng năm, nhãn từ điều kiện trong nguồn Chính phủ; do tác giả code soạn nên không phải benchmark độc lập do chuyên gia xây |

QA chọn T1 và biến thể đổi số của dev (32 câu), toàn bộ 32 regression và 8 ca mới: **72 câu mỗi cấu hình, 144 câu trả lời**, chấm thật từng câu. Không lấy ca gold để chọn evidence lúc inference. `inputs.jsonl` không có nhãn/căn cứ gold; runner không phân tích gold để sinh câu trả lời (bước integrity đọc bytes để kiểm hash). Judge không nhận tên cấu hình. Các đầu ra lỗi, câu hỏi ngược, ca kém đi đều được giữ và báo.

Baseline được nạp lại từ snapshot query/prompt/format/citation behavior của vòng v2. Candidate dùng cùng model GPT-OSS và embedding BGE-M3; judge Qwen và prompt chấm của `experiment.py` không đổi. Các sửa đổi prompt/hydration là thứ cần đo, không phải chỉnh người chấm để nâng điểm. Báo riêng từng nhóm, từng mẫu số, CI theo ca gốc và số ca tăng/giảm; không trộn các nhóm thành một điểm “độ chính xác hệ thống”.

Các kết quả v1 và vòng dev trước được giữ nguyên. Không xóa `test.lock`, không ghi đè dự đoán cũ, không sửa nhãn tranh cãi để khớp model. Nhãn người và hiệu chuẩn judge trên câu trả lời thật vẫn là giới hạn; kết quả phải được trình bày là số đo tự động trên dữ liệu tổng hợp.

## Tái lập

Sau khi protocol đã tồn tại, `prepare` chỉ xác minh và từ chối thay code/data trong cùng vòng. Dùng image và DB bản sao như README của v2, mount artifacts ghi được; truyền `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-120b`, `LEGAL_RETRIEVAL_MODE=vector`.

```powershell
python -m evaluation.contract_eval_v2.research_round prepare
# Ba bước runtime trong worker; qa/judge gọi Groq đã được người dùng cho phép.
python -m evaluation.contract_eval_v2.research_round retrieval
python -m evaluation.contract_eval_v2.research_round qa
python -m evaluation.contract_eval_v2.research_round judge
python -m evaluation.contract_eval_v2.research_round score
```

`--split dev|regression_test|fresh_source_checked` cho phép tiếp tục đúng phần gián đoạn. Không xóa output để chạy lại chọn điểm cao. Token và ngữ cảnh thực được lưu cùng từng câu; chi phí tiền phụ thuộc tài khoản Groq, không suy từ số unit test.
