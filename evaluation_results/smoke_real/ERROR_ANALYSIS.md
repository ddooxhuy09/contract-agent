# ERROR ANALYSIS

Các category tự động dưới đây dựa trên output/trace. Không tự kết luận hallucination, unsupported legal conclusion hay incorrect abstention khi chưa có review nội dung.

Lỗi pipeline có thể sinh fallback/analysis rỗng; những trường hợp đó được tách khỏi dự đoán nhãn risk hợp lệ. Có cạnh trong corpus không có nghĩa cạnh được dùng trong answer.

## MIX-017

Invalid/Unverified Ground Truth, Pipeline Execution Failure

"No clauses extracted; the workflow may have swallowed extraction errors."

## TEMP-006

Invalid/Unverified Ground Truth, Unsupported Capability, Retrieval Missing Evidence

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-018

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## TEMP-014

Invalid/Unverified Ground Truth, Unsupported Capability, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-007

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."
