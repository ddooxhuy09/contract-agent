# Lần chạy bị hủy (22/11/2026)

Dừng sau vài câu đầu, trước khi judge. Hai lỗi phát hiện từ trace:
1. Code: sau nhánh rewrite của graph QA, câu hỏi bị viết lại thành từ khóa nên lượt retrieve sau quay về top-k vector.
   Sửa: quyết định "câu hỏi toàn hợp đồng" theo câu hỏi gốc của người dùng (`_retrieve_node`).
2. Đo: `context_contract_clauses` lấy từ lời gọi `retrieve_contract` nên sai/trống ở cấu hình candidate.
   Sửa: đọc `_valid_clause_numbers` / `_contract_context` từ state cuối của graph.
Code đổi nên protocol (hash code) không còn khớp; chạy lại toàn bộ ở `whole_contract_20261122b` với protocol mới. Không dùng số của lần này.
