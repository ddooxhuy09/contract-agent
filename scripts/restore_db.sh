#!/usr/bin/env sh
# Restore contractlens_backup.dump into the running postgres service.
# Usage (from repo root, Docker up):
#   docker compose exec postgres sh /backup/../..   # prefer:
#   sh scripts/restore_db.sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DUMP="${DUMP_PATH:-/backup/contractlens_backup.dump}"
USER_NAME="${POSTGRES_USER:-contractlens}"
DB_NAME="${POSTGRES_DB:-contractlens}"

echo "Terminating connections to ${DB_NAME}..."
docker compose exec -T postgres psql -U "$USER_NAME" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();"

echo "Recreating database ${DB_NAME}..."
docker compose exec -T postgres psql -U "$USER_NAME" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
  -c "CREATE DATABASE ${DB_NAME} OWNER ${USER_NAME};"

echo "Restoring ${DUMP} (this can take several minutes for multi-GB dumps)..."
docker compose exec -T postgres pg_restore \
  -U "$USER_NAME" \
  -d "$DB_NAME" \
  --no-owner \
  --no-acl \
  --verbose \
  "$DUMP"

echo "Done. Sample table check:"
docker compose exec -T postgres psql -U "$USER_NAME" -d "$DB_NAME" -c "\dt"
