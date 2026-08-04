# ContractLens — AI rà soát hợp đồng tiếng Việt

## Stack
- FastAPI + Clean Architecture (`domain` / `application` / `infrastructure` / `api`)
- Postgres + pgvector (`schema.sql`)
- Neo4j GraphRAG (`schema.cypher`)
- JWT local auth
- Gemini + BAAI/bge-m3 embeddings (LangChain HuggingFaceEmbeddings)
- Full local stack via Docker Compose (api + frontend + postgres + neo4j)

## Chạy trên máy mới (không cần cài Python/Node)

```bash
cp .env.example .env
# Điền GEMINI_API_KEY và JWT_SECRET (không để default)

docker compose up --build -d
```

Mặc định:
- Frontend: http://localhost:5173
- API: http://localhost:8010/health
- Postgres host port: `5433`
- Neo4j Bolt host port: `7688`

### Nạp database từ dump

File `contractlens_backup.dump` (custom `pg_restore`) phải nằm ở root repo (đã mount sẵn vào postgres).

```powershell
docker compose up -d postgres
# đợi healthy
powershell -File scripts/restore_db.ps1
docker compose up -d
```

## Dev workflow

| Việc | Lệnh |
|------|------|
| Sửa frontend/backend | Không rebuild — hot reload qua bind mount |
| Thêm package Node | `docker compose exec frontend npm install <pkg>` |
| Thêm package Python | Sửa `requirements.txt` → `docker compose build api && docker compose up -d api` |
| Đổi Dockerfile | `docker compose build <service> && docker compose up -d <service>` |
| Reset DB | `docker compose stop api; docker volume rm contractlens_pgdata; docker compose up -d` |
| Cleanup | `docker compose down; docker image prune -f` |

## API chính
- `POST /api/v1/auth/register` / `login`
- `POST /api/v1/upload` · `analyze` · `chat`
- `GET /api/v1/contracts`
- `GET /health`

## Ingest luật mẫu (trong container api)

```bash
docker compose exec api python -m scripts.ingest_legal_sample
```

## Tài liệu
- [docs/refactor-report.md](docs/refactor-report.md)
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
- [schema.sql](schema.sql) · [schema.cypher](schema.cypher)
