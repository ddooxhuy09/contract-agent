# ERROR ANALYSIS

Các category tự động dưới đây dựa trên output/trace. Không tự kết luận hallucination, unsupported legal conclusion hay incorrect abstention khi chưa có review nội dung.

Lỗi pipeline có thể sinh fallback/analysis rỗng; những trường hợp đó được tách khỏi dự đoán nhãn risk hợp lệ. Có cạnh trong corpus không có nghĩa cạnh được dùng trong answer.

## MIX-017

Invalid/Unverified Ground Truth, Pipeline Execution Failure

{"type": "PipelineExtractionFailure", "message": "No clauses extracted; the workflow may have swallowed extraction errors."}

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

## MIX-006

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-012

Invalid/Unverified Ground Truth, Pipeline Execution Failure

{"type": "PipelineExtractionFailure", "message": "No clauses extracted; the workflow may have swallowed extraction errors."}

## TEMP-009

Invalid/Unverified Ground Truth, Unsupported Capability, Retrieval Missing Evidence

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-019

Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document

"Last actual retrieval attempt; graph stage is ranked before final filtering/truncation. LLM stage includes only full chunks confirmed in the actual prompt."

## MIX-005

Invalid/Unverified Ground Truth, Pipeline Execution Failure

{"type": "PipelineExtractionFailure", "message": "No clauses extracted; the workflow may have swallowed extraction errors."}

## MIX-003

Invalid/Unverified Ground Truth, Pipeline Execution Failure

{"type": "PipelineExtractionFailure", "message": "No clauses extracted; the workflow may have swallowed extraction errors."}

## MIX-004

Invalid/Unverified Ground Truth, Pipeline Execution Failure

{"type": "InterruptedAfterProviderQuotaExhaustion", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-008

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-011

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-020

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-013

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-014

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-010

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-003

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-009

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-002

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-001

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-013

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-011

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-012

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-016

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-015

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-005

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-008

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-001

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## MIX-010

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-007

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-004

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}

## TEMP-002

Invalid/Unverified Ground Truth, Environment/Dependency Block

{"type": "ProviderQuotaBlocked", "message": "Observed Gemini daily request quota exhausted (limit 20 for configured model). Dedicated worker stopped during retry; model unchanged."}
