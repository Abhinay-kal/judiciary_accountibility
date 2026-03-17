#!/usr/bin/env sh
set -eu

log() {
  echo "[bootstrap] $*"
}

if [ -z "${DATABASE_URL:-}" ]; then
  log "DATABASE_URL is not set"
  exit 1
fi

if [ -z "${REDIS_URL:-}" ]; then
  log "REDIS_URL is not set"
  exit 1
fi

log "Waiting for Postgres and Redis"
PYTHONPATH=/app python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

from sqlalchemy import create_engine, text


def wait_for_redis(url: str, timeout_seconds: int = 90) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "redis"
    port = parsed.port or 6379
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(2)
    raise SystemExit(f"Redis not reachable at {host}:{port}")


def wait_for_db(url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            time.sleep(2)
    raise SystemExit("Postgres did not become ready in time")


def ensure_alembic_table_capacity(url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(64) NOT NULL PRIMARY KEY)"))
        conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))


wait_for_redis(os.environ["REDIS_URL"])
wait_for_db(os.environ["DATABASE_URL"])
ensure_alembic_table_capacity(os.environ["DATABASE_URL"])
print("Dependencies are ready")
PY

log "Running migrations"
PYTHONPATH=/app alembic -c /app/alembic.ini upgrade head

log "Seeding sample data if database is empty"
PYTHONPATH=/app python /app/scripts/seed.py

if [ "${BOOTSTRAP_ONLY:-0}" = "1" ]; then
  log "BOOTSTRAP_ONLY=1 set; exiting after bootstrap"
  exit 0
fi

log "Starting backend API"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
