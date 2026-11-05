# API request lifecycle

Hai luồng đại diện: phân tích hợp đồng và chat streaming. Các route còn lại theo cùng khuôn (JWT → use case → repository). Ánh xạ route: [`../CODEBASE_MAP.md`](../CODEBASE_MAP.md).

```mermaid
sequenceDiagram
    actor U as Client
    participant R as routes.py
    participant D as deps.py
    participant UC as AnalyzeContract
    participant P as AnalyzePipeline
    participant DB as contracts repo

    U->>R: POST /api/v1/analyze (Bearer JWT)
    R->>D: get_current_user_id
    D-->>R: user_id
    R->>UC: execute(contract_id, user_id, provider)
    UC->>DB: get_owned(contract_id, user_id)
    DB-->>UC: contract or none
    UC->>P: run(full_text, contract_id, provider)
    P-->>UC: analysis, risks
    UC->>DB: save_analysis
    UC-->>R: result
    R-->>U: AnalyzeResponse or error via _http_error
```

```mermaid
sequenceDiagram
    actor U as Client
    participant R as routes.py chat_stream
    participant DB as contracts repo
    participant Q as QaPipeline
    participant G as qa_agent graph

    U->>R: POST /api/v1/chat/stream
    R->>DB: get_owned(contract_id, user_id)
    alt not owned
        R-->>U: 404
    else owned
        R-->>U: 200 text/event-stream
        R->>Q: stream(contract_id, question, provider, checkpoint_id)
        Q->>G: stream_answer_events
        G-->>U: SSE frames
    end
```

## Evidence
- `app/api/routes.py`: `analyze`, `chat_stream`, `_http_error`; `app/api/deps.py`.
- `app/application/use_cases/contracts.py`: `AnalyzeContract.execute` (`get_owned`, `_pipeline.run` / `run_review`, `save_analysis`).
- `app/infrastructure/agents/pipelines.py`: `LangGraphQaPipeline.stream`.

## Giả định chưa xác minh
- Với `review_mode`, `AnalyzeContract` gọi `run_review` và trả bản nháp thay vì `save_analysis`; nhánh này không vẽ và chưa đọc hết thân hàm.
- Khuôn frame SSE nằm trong `stream_answer_events`, không vẽ ở đây.
- Trong luồng stream, tại route 404 xảy ra trước khi mở stream (đúng theo comment trong `chat_stream`).
