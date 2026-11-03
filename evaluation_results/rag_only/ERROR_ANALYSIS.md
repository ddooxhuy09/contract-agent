# RAG-only error analysis

Các nhãn lỗi dưới đây chỉ là so khớp cấu trúc với ground truth draft. Không có answer generation để chấm hallucination hoặc citation support.

- Invalid/Unverified Ground Truth: 34 case
- Retrieval Missing Evidence: 32 case
- Unsupported Temporal Capability: 14 case
- Wrong Legal Document: 21 case
- Wrong Article/Clause/Point: 3 case

| Case | Final required coverage | Required provisions | Categories |
|---|---:|---|---|
| MIX-017 | 1.000 | CON-25.1 | Invalid/Unverified Ground Truth |
| TEMP-006 | 0.500 | E23-53.1, E23-52.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| MIX-018 | 0.000 | E-36.3, CON-25.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-014 | 0.000 | L12-20.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| MIX-007 | 0.000 | LAB-13.1, SI-2.1.a | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-006 | 0.000 | LAB-13.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-012 | 0.000 | COM-301 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-009 | 0.333 | C23-80.1.a, C23-79.2, C10-16.1.b | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| MIX-019 | 0.000 | CON-24 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-005 | 0.000 | SAFE-7.2.b | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-003 | 0.000 | LAB-98.1.b | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-004 | 0.000 | LAB-168.1, SI-2.1.a, SI-13.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence |
| MIX-008 | 0.000 | LAB-13.1, LAB-17.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-011 | 0.500 | N35-73.1, N145-4.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| MIX-020 | 0.000 | CON-25.2, E-36.3 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-013 | 0.500 | E-35.1, COM-24.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence |
| MIX-014 | 0.000 | E-36.3, COM-301 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-010 | 0.000 | N145-4.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| TEMP-003 | 0.000 | E05-33, E05-34 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| MIX-009 | 0.000 | CIV-328.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-002 | 0.000 | LAB-17.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-001 | 0.000 | SI14-2.1.a | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| TEMP-013 | 0.000 | N35-73.1, N10-49.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| MIX-011 | 0.000 | COM-301 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| TEMP-012 | 0.333 | N10-49.1, N145-4.4, N35-73.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| MIX-016 | 1.000 | CON-25.3 | Invalid/Unverified Ground Truth |
| MIX-015 | 0.000 | CON-25.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point |
| TEMP-005 | 0.000 | E23-53.1, E05-34, E23-52.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point, Unsupported Temporal Capability |
| TEMP-008 | 0.500 | C23-25.2, C23-79.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| MIX-001 | 0.000 | LAB-17.1 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document |
| MIX-010 | 0.000 | LAB-13.1, CIV-385 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Article/Clause/Point |
| TEMP-007 | 0.000 | C10-16.1.b | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
| TEMP-004 | 0.500 | E23-52.1, E23-52.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Unsupported Temporal Capability |
| TEMP-002 | 0.000 | SI24-2.1.a, SI24-13.1, SI24-140.1, SI24-140.2 | Invalid/Unverified Ground Truth, Retrieval Missing Evidence, Wrong Legal Document, Unsupported Temporal Capability |
