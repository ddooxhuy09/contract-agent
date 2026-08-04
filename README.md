# ContractLens — AI rà soát hợp đồng tiếng Việt

Stack: FastAPI · Postgres/pgvector · Neo4j · Gemini · BAAI/bge-m3 · React (Vite)

## Chạy bằng Docker

Cần [Docker Desktop](https://www.docker.com/products/docker-desktop/). Không cần cài Python/Node trên máy.

```powershell
# 1) Cấu hình
copy .env.example .env
# Điền GEMINI_API_KEY và JWT_SECRET (không để giá trị mặc định)

# 2) Build & chạy toàn bộ stack
docker compose up --build -d
```

Mở:

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| API      | http://localhost:8010/health |

Lần đầu API sẽ tải model embedding (`BAAI/bge-m3`) — có thể mất vài phút.

### Nạp database từ dump (tuỳ chọn)

Đặt file `contractlens_backup.dump` ở root repo, rồi:

```powershell
docker compose up -d postgres
# đợi postgres healthy
powershell -File scripts\restore_db.ps1
docker compose up -d
```

### Lệnh thường dùng

```powershell
docker compose up --build -d    # build lại & chạy
docker compose logs -f api      # xem log API
docker compose down             # dừng stack
```

## API chính

- `POST /api/v1/auth/register` · `login`
- `POST /api/v1/upload` · `analyze` · `chat`
- `GET /api/v1/contracts`
- `GET /health`
