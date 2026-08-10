#!/bin/sh
set -e

echo "Waiting for Postgres at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}..."
until python -c "
import os, sys, psycopg
try:
    psycopg.connect(
        host=os.environ.get('POSTGRES_HOST', 'postgres'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        dbname=os.environ.get('POSTGRES_DB', 'whatsapp_business_ai'),
        user=os.environ.get('POSTGRES_USER', 'waba_user'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        connect_timeout=3,
    )
except Exception:
    sys.exit(1)
"; do
  sleep 1
done
echo "Postgres is up."

python manage.py migrate --noinput

exec "$@"
