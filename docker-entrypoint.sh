#!/bin/sh
# docker-entrypoint.sh
# Runs as the container's ENTRYPOINT. Applies Alembic migrations then
# hands off to the CMD (uvicorn). Keeps the same image deployable to
# any environment — the DB URL comes from the environment, not this script.
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Starting application..."
exec "$@"
