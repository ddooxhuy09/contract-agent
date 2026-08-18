#!/usr/bin/env sh
# Restore contractlens_backup.dump into the running postgres service.
# Place dump at repo root, then: sh scripts/restore_db.sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST_DUMP="${ROOT}/contractlens_backup.dump"
CONTAINER_DUMP="/tmp/contractlens_backup.dump"
USER_NAME="${POSTGRES_USER:-contractlens}"
DB_NAME="${POSTGRES_DB:-contractlens}"

if [ ! -f "$HOST_DUMP" ]; then
  echo "Missing dump file at repo root: $HOST_DUMP" >&2
  exit 1
fi

echo "Copying dump into postgres container..."
docker compose cp "$HOST_DUMP" "postgres:${CONTAINER_DUMP}"

echo "Terminating connections to ${DB_NAME}..."
docker compose exec -T postgres psql -U "$USER_NAME" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();"

echo "Recreating database ${DB_NAME}..."
docker compose exec -T postgres psql -U "$USER_NAME" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
  -c "CREATE DATABASE ${DB_NAME} OWNER ${USER_NAME};"

echo "Restoring ${CONTAINER_DUMP} (this can take several minutes for multi-GB dumps)..."
docker compose exec -T postgres pg_restore \
  -U "$USER_NAME" \
  -d "$DB_NAME" \
  --no-owner \
  --no-acl \
  --verbose \
  "$CONTAINER_DUMP"

echo "Done. Sample table check:"
docker compose exec -T postgres psql -U "$USER_NAME" -d "$DB_NAME" -c "\dt"
