# ERROR ANALYSIS

Các category tự động dưới đây dựa trên output/trace. Không tự kết luận hallucination, unsupported legal conclusion hay incorrect abstention khi chưa có review nội dung.

Lỗi pipeline có thể sinh fallback/analysis rỗng; những trường hợp đó được tách khỏi dự đoán nhãn risk hợp lệ. Có cạnh trong corpus không có nghĩa cạnh được dùng trong answer.

## MIX-017

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

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

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-006

Invalid/Unverified Ground Truth

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-012

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Incorrect Risk Classification

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## TEMP-009

Invalid/Unverified Ground Truth, Unsupported Capability, Retrieval Missing Evidence

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-019

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-005

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-003

Invalid/Unverified Ground Truth

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-004

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-008

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point, Incorrect Risk Classification

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## TEMP-011

Invalid/Unverified Ground Truth, Unsupported Capability, Retrieval Missing Evidence

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-020

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."
