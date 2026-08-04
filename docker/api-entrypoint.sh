#!/bin/sh
set -eu
# Local Docker: ensure bind/named volumes are writable regardless of host UID mapping.
mkdir -p /cache/huggingface/hub /app/data/uploads
chmod -R a+rwX /cache/huggingface /app/data/uploads 2>/dev/null || true
exec "$@"
