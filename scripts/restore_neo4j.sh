#!/usr/bin/env sh
# Restore neo4j.dump into the Neo4j Docker volume (offline load).
# Usage (repo root, macOS / Linux):
#   chmod +x scripts/restore_neo4j.sh   # once
#   ./scripts/restore_neo4j.sh
#   # or: sh scripts/restore_neo4j.sh
#
# Neo4j MUST be stopped while loading (neo4j-admin offline). Script starts it again after.

set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"

DUMP="$(pwd)/neo4j.dump"
if [ ! -f "$DUMP" ]; then
  echo "Missing neo4j.dump at repo root: $DUMP" >&2
  exit 1
fi

PROJECT="${COMPOSE_PROJECT_NAME:-contractlens}"
VOLUME="${PROJECT}_neo4jdata"
USER_NAME="${NEO4J_USER:-neo4j}"
PASS="${NEO4J_PASSWORD:-contractlens}"

bring_up() {
  echo "Trying to bring neo4j back up..."
  docker compose up -d neo4j >/dev/null 2>&1 || true
}

trap 'bring_up' INT TERM
# On failure after stop, still try to start neo4j again
on_err() {
  echo "ERROR: restore failed." >&2
  bring_up
  exit 1
}
trap 'on_err' EXIT

echo "1/4 Stopping neo4j (required for offline load)..."
docker compose stop neo4j

if ! docker volume ls -q --filter "name=${VOLUME}" | grep -q .; then
  echo "Volume ${VOLUME} missing - creating via compose..."
  docker compose up -d neo4j
  sleep 8
  docker compose stop neo4j
fi

echo "2/4 Loading dump into volume ${VOLUME} (overwrite)..."
docker run --rm \
  -v "${VOLUME}:/data" \
  -v "${DUMP}:/backups/neo4j.dump:ro" \
  --entrypoint neo4j-admin \
  neo4j:5 \
  database load neo4j \
  --from-path=/backups \
  --overwrite-destination=true

echo "3/4 Starting neo4j again..."
docker compose up -d neo4j

echo "4/4 Waiting for healthy..."
ok=0
i=0
while [ "$i" -lt 40 ]; do
  i=$((i + 1))
  sleep 3
  status="$(docker compose ps neo4j --format '{{.Status}}' 2>/dev/null || true)"
  case "$status" in
    *healthy*) ok=1; break ;;
  esac
  echo "  status: ${status}"
done
if [ "$ok" -ne 1 ]; then
  echo "WARNING: Neo4j not healthy yet - check: docker compose ps neo4j / docker compose logs neo4j" >&2
fi

echo "Node counts:"
docker compose exec -T neo4j cypher-shell -u "$USER_NAME" -p "$PASS" \
  "MATCH (n) RETURN labels(n) AS labels, count(*) AS cnt ORDER BY cnt DESC LIMIT 15;"

trap - EXIT INT TERM
echo "Done."
