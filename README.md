# ContractLens — AI rà soát hợp đồng tiếng Việt

## Stack
- FastAPI + Clean Architecture (`domain` / `application` / `infrastructure` / `api`)
- Postgres + pgvector (`schema.sql`)
- Neo4j GraphRAG (`schema.cypher`)
- JWT local auth (không Supabase)
- Gemini + Vietnamese embeddings

## Chạy hạ tầng

```bash
docker compose up -d
cp .env.example .env   # điền GEMINI_API_KEY, JWT_SECRET
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## API chính
- `POST /api/v1/auth/register` / `login`
- `POST /api/v1/upload` · `analyze` · `chat`
- `GET /api/v1/contracts`
- `GET /health`

## Ingest luật mẫu (không dump)

```bash
python -m scripts.ingest_legal_sample
```

## Tài liệu
- [docs/refactor-report.md](docs/refactor-report.md) — báo cáo refactor
- [schema.sql](schema.sql) · [schema.cypher](schema.cypher)
