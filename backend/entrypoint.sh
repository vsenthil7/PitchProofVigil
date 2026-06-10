#!/usr/bin/env bash
# Run migrations then start the server. Migrations are idempotent.
set -euo pipefail
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head || echo "Migration step skipped/failed (continuing)."
fi
exec uvicorn app.api.app:app --host 0.0.0.0 --port 8000
