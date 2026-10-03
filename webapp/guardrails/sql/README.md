# Scripts SQL do pacote real de guardrails
# ========================================
#
# A apresentação de segurança menciona **2 scripts SQL** a rodar no Postgres
# (vocabulário/dashboard etc.) depois do `manage.py migrate`.
#
# Quando o pacote chegar:
# 1. Cole os `.sql` nesta pasta.
# 2. Rode-os no banco do `.env` (mesmo search_path do Django — schema `django`
#    por padrão, ver `DJANGO_DB_SCHEMA` em settings).
#
# Exemplos:
#
#   psql "postgresql://$PGUSER:$PGPASSWORD@$PGHOST:$PGPORT/$PGDATABASE" \
#     -c "SET search_path TO django,sinan,public;" \
#     -f webapp/guardrails/sql/01_....sql
#
# Ou, de dentro do container:
#
#   docker compose exec web bash
#   # use psql apontando para o Postgres externo do .env
#
# Checklist completo: docs/guardrails_integracao.md
