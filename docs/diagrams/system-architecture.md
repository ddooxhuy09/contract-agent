# System architecture

Thành phần runtime và các kết nối thật trong mã. Giải thích: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

```mermaid
flowchart LR
    FE["Frontend React/Vite"]
    subgraph API["FastAPI app/main.py"]
        R["api/routes.py (prefix /api/v1)"]
        UC["application/use_cases"]
        C["AppContainer"]
    end
    subgraph AG["app/agents"]
        WF["workflow.py - phan tich"]
        QA["qa_agent.py - hoi dap"]
    end
    PL["infrastructure/agents/pipelines.py"]
    RET["infrastructure/retrieval + vector"]
    PG[("Postgres + pgvector")]
    N4[("Neo4j")]
    FS[["data/uploads"]]
    GM["Gemini"]
    HF["BAAI/bge-m3 embedder"]

    FE -->|HTTP, SSE| R
    R --> UC
    UC --> C
    C --> PL
    PL --> WF
    PL --> QA
    UC -->|repositories| PG
    UC -->|storage| FS
    UC -->|embed| HF
    WF --> GM
    QA --> GM
    WF --> RET
    QA --> RET
    RET --> PG
    RET --> N4
    RET --> HF
    WF -->|checkpoint| PG
    QA -->|checkpoint, memory| PG
```

## Evidence
- `app/main.py`: `lifespan` dựng `build_container()`, `LangGraphAnalyzePipeline`, `LangGraphQaPipeline`, `bind_retrieval`, `init_checkpointer`; `include_router(router)`; mount `frontend/dist`.
- `app/infrastructure/container.py`: `AppContainer` gồm repository Pg, `LocalObjectStorage`, `HuggingFaceEmbedder`, `GeminiChatModel`, `Neo4jGraphRepository`, `PgLegalVectorSearch`.
- `app/infrastructure/agents/pipelines.py`: import `qa_agent`, `workflow`.
- `app/agents/memory.py`: docstring ghi bộ nhớ dài hạn dùng `AsyncPostgresStore`.

## Giả định chưa xác minh
- Checkpointer lưu vào Postgres: suy từ `memory.py` và tên `init_checkpointer`; chưa đọc thân `checkpointer.py`.
- Frontend gọi API trực tiếp theo `VITE_API_BASE_URL`; chưa mở `frontend/src/api.js`.
- Luồng embed từ `UC` vẽ chung cho upload; truy vấn embed của retrieval vẽ riêng qua `RET`.
