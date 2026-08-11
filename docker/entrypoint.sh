#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time, socket

host = os.getenv("POSTGRES_HOST", "")
port = int(os.getenv("POSTGRES_PORT") or 5432)
if host:
    for _ in range(60):
        try:
            with socket.create_connection((host, port), timeout=2):
                break
        except OSError:
            time.sleep(1)
    else:
        raise SystemExit(f"Database at {host}:{port} not reachable")
PY

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"
