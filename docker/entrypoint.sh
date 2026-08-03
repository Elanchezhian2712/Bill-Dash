#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time, socket
from urllib.parse import urlparse

url = os.getenv("DATABASE_URL", "")
if url:
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or 5432
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
