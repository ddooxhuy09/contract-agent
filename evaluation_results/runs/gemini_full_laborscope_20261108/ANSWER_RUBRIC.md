# Rubric review nội dung pháp lý

Tất cả điểm sau phải do chuyên gia hoặc judge đã hiệu chuẩn thực hiện trên câu hỏi, facts đầu vào, prompt/evidence thực tế và nguồn pháp luật đúng phiên bản. Nhãn nháp không được dùng như xác minh pháp lý.

- QA: kiểm tra từng claim về chủ thể, điều kiện, ngoại lệ và nghĩa vụ; 0=sai trọng yếu, 1=đúng một phần/cần điều kiện, 2=đúng và đủ trong phạm vi facts.
- Multi-hop: ngoài QA, phải kết nối đủ căn cứ/quan hệ đúng hướng và phạm vi; không cho điểm chỉ vì kể tên nhiều luật.
- Risk: so đúng clause được hỏi, severity theo critical/warning/ok và giải thích mâu thuẫn/nguy cơ; không coi mọi missing evidence là vi phạm luật.
- Classification: dựa trên facts quản lý/tiền lương/độc lập và điều kiện áp dụng; chấp nhận kết luận có điều kiện khi thiếu facts.
- Temporal: xác định as_of và transaction, phiên bản, thời điểm và ngoại lệ chuyển tiếp. Không gán mọi văn bản hết hiệu lực là forbidden citation.

Faithfulness: mỗi claim có được evidence thực sự trong prompt hỗ trợ không (0=không, 1=một phần, 2=đầy đủ). Relevance: có trả lời đúng câu hỏi và facts không. Citation support: câu trích có thật, đúng Điều/Khoản/Điểm/phiên bản và hỗ trợ claim không. Legal grounding: căn cứ có đủ hiệu lực/phạm vi không. Abstention: từ chối/làm rõ có đúng với phần thiếu dữ kiện hay không.

Hallucination rate cần denominator số claim đã review và số claim bị xác nhận bịa/sai; không dùng số chunk không thuộc gold làm số hallucination. Mọi điểm tự động, điểm human và số mẫu phải báo cáo riêng. HUMAN_REVIEW_TEMPLATE.csv để trống đến khi có review thật.
