#!/usr/bin/env bash
# Entrypoint da aplicação Aurora dentro do container.
#   1. espera o PostgreSQL responder;
#   2. aplica as migrations do Django;
#   3. inicia o servidor (runserver por padrão, ou gunicorn).
set -e

cd /app/webapp

echo "[entrypoint] aguardando o PostgreSQL em ${PGHOST:-db}:${PGPORT:-5432} ..."
python - <<'PY'
import os, sys, time
import psycopg

dsn = (
    f"host={os.getenv('PGHOST','db')} port={os.getenv('PGPORT','5432')} "
    f"dbname={os.getenv('PGDATABASE','Aurola')} user={os.getenv('PGUSER','postgres')} "
    f"password={os.getenv('PGPASSWORD','')}"
)
for i in range(30):
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
        print("[entrypoint] banco acessível.")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] ({i+1}/30) banco indisponível: {exc}")
        time.sleep(2)
else:
    print("[entrypoint] ERRO: PostgreSQL não respondeu a tempo.", file=sys.stderr)
    sys.exit(1)
PY

echo "[entrypoint] aplicando migrations..."
python manage.py migrate --noinput

case "$1" in
  web)
    echo "[entrypoint] iniciando runserver em 0.0.0.0:8000 (DEBUG serve estáticos)"
    exec python manage.py runserver 0.0.0.0:8000 --noreload
    ;;
  gunicorn)
    echo "[entrypoint] iniciando gunicorn (1 worker — singleton do modelo)"
    exec gunicorn aurora.wsgi:application \
        --chdir /app/webapp --bind 0.0.0.0:8000 \
        --workers 1 --timeout 600
    ;;
  *)
    # Qualquer outro comando: executa direto (ex.: manage.py etl_violbr, bash, ...)
    exec "$@"
    ;;
esac
