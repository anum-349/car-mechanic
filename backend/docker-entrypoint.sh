#!/bin/sh
set -eu

python - <<'PY'
import os
import time
import psycopg2

for attempt in range(60):
    try:
        connection = psycopg2.connect(
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ.get("DB_HOST", "db"),
            port=os.environ.get("DB_PORT", "5432"),
            connect_timeout=3,
        )
        connection.close()
        break
    except Exception:
        if attempt == 59:
            raise SystemExit("Database did not become ready within 120 seconds.")
        time.sleep(2)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

case "${RUN_LAUNCH_CHECK:-1}" in
    1|true|True|yes|YES)
        python manage.py launch_check --production
        ;;
esac

exec "$@"
