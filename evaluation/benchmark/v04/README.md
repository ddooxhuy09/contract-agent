# ContractLens Mixed Legal Evaluation v0.4 (DEMO)

**34 câu hỏi trộn**: 20 câu của v0.3 có provenance + phân loại Easy/Medium/Hard; 14 tình huống mới về mốc thời gian, văn bản cũ/mới, quy định chuyển tiếp và sửa đổi/bổ sung (gồm Expert).

## File chính
- `MIXED_34_TEST_CASES_V04.json`: một file chứa toàn bộ corpus metadata, định danh điều khoản, danh sách văn bản, cạnh quan hệ, trạng thái phiên bản và 34 câu hỏi có gold.
- `MIXED_34_TEST_CASES_V04.jsonl`: chỉ các test case, dùng cho Python runner.
- `QUESTIONS_ONLY_NO_GOLD.json`: chỉ đầu vào, tránh rò rỉ gold vào prompt.
- `LEGAL_DOCUMENTS_STATUS.json`: mốc hiệu lực + status trên cấp văn bản.
- `LEGAL_RELATION_GRAPH.json`: quan hệ REPLACES, AMENDS_CLAUSE, ADDS_CLAUSE, REPLACES_WITH_TRANSITION.
- `PROVISION_VERSION_TIMELINE.json`: các phiên bản khoản 2, khoản 4 Điều 4 Nghị định 145/2020.
- `LEGAL_PROVISIONS.json`: trích đoạn minh họa (KHÔNG phải toàn bộ điều luật).
- `RETRIEVAL_CORPUS_MIXED_UNLABELED.jsonl`: các chunk có cả nguồn cũ và nguồn mới, không lộ nhãn gold.
- `contracts/`: 7 DOCX giả lập giữ lại từ v0.3.
- `PREVIEW_34_MIXED_TEMPORAL_CASES.md`: xem nhanh 34 case và giải thích 14 tình huống temporal.
- `PREDICTIONS_TEMPLATE.jsonl`: file dự đoán trống.

## Chạy
```bash
python validate_schema.py
python score_temporal_predictions.py --pred PREDICTIONS_TEMPLATE.jsonl
```

Các phép chấm script chỉ là kiểm tra **cấu trúc retrieval/citation/relation/temporal selection**. Phải chấm nội dung câu trả lời thủ công hoặc LLM-as-a-Judge đã hiệu chuẩn mới đo được legal correctness / faithfulness. **Không dùng kết quả file dự đoán trống để báo cáo độ chính xác của ContractLens**.

## Quy tắc quan trọng về thời gian
- `as_of_date`: ngày đánh giá/tìm luật; `transaction_date`: ngày sự kiện giao kết/thực hiện. Cả hai đều cần khi có quy định chuyển tiếp.
- `effective_until_exclusive`: ngày luật cũ **không còn hiệu lực chung**, không phủ định các ngoại lệ chuyển tiếp.
- `partially_amended_or_expired` là trạng thái cả nghị định. Không thay bằng kết luận rằng mọi khoản đều hết hiệu lực.
- Edge là quan hệ **có hướng** và có phạm vi `affected_scope`. Nghị định sửa khoản 2 Điều 4 không đồng nghĩa sửa mọi khoản của Điều 4.
- `difficulty.level` là easy/medium/hard/expert nhất quán trên cả 34 case; `difficulty_legacy` lưu phân loại cũ để truy vết.

## Trạng thái kiểm chứng
Tất cả case là synthetic draft. Đã đối chiếu các sự kiện chính với cơ sở văn bản nhà nước; đoạn trích vẫn phải kiểm tra với toàn văn từng phiên bản và chuyên gia trước khi dùng làm ground truth pháp lý chính thức. Riêng Nghị định 145/2020 có các thay đổi về sau (ví dụ 129/2025/NĐ-CP được CSDL VBPL liệt kê) chưa được map toàn bộ đến từng khoản.

## Có thể chạy trong hệ thống hiện tại không?
ContractLens v3 có retrieval với `is_effective`, status và graph expansion; chức năng hỏi đáp hiện chủ yếu truy xuất luật hiện hành. Vì vậy bài test lịch sử **có thể thất bại đúng với giới hạn thiết kế hiện tại**. Chưa được tuyên bố hệ thống hỗ trợ time-travel retrieval hay bản hợp nhất tại mọi mốc nếu chưa thực sự triển khai.

**Lưu ý chất lượng corpus:** Những chunk phiên bản lịch sử không có trích dẫn gốc đầy đủ được đánh dấu placeholder chưa xác minh (ví dụ N145 khoản 2 Điều 4 bản 2021). Không được tính điểm retrieval text/citation chuẩn cho placeholder này cho đến khi nhập và kiểm tra tài liệu chính thức. Các ID `provision@effective_from` ngăn đánh đồng hai phiên bản của cùng khoản.
