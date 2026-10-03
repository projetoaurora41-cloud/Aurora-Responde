"""Copia todos os dados do SQLite legado para o banco PostgreSQL padrão.

Uso típico (uma vez, ao mudar o projeto de SQLite para Postgres)::

    python manage.py migrate            # cria o schema no Postgres
    python manage.py migrate_sqlite_to_pg

O comando lê da conexão ``legacy_sqlite`` (exposta automaticamente pelo
settings enquanto o arquivo ``db.sqlite3`` existir) e grava na conexão
``default`` (Postgres). Os PKs são preservados (cópia 1:1). As restrições de
chave estrangeira são desativadas durante a carga (``session_replication_role
= replica``) para não depender da ordem das tabelas, e as sequences são
resetadas ao final.

Tabelas geridas automaticamente pelo ``migrate`` (content types, permissões,
log do admin e sessões) não são copiadas — são recriadas no Postgres e os
dados que as referenciam estão vazios.
"""
from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connections

# (app_label, model_name) que NÃO devem ser copiados — recriados pelo migrate.
EXCLUIR = {
    ("contenttypes", "contenttype"),
    ("auth", "permission"),
    ("admin", "logentry"),
    ("sessions", "session"),
}

LEGACY = "legacy_sqlite"
DEST = "default"


class Command(BaseCommand):
    help = "Copia os dados do SQLite legado (legacy_sqlite) para o Postgres (default)."

    # Acima deste nº de linhas, usa COPY (streaming, leve em memória) em vez de
    # INSERT multi-linha do ORM — evita estourar a memória do Postgres.
    COPY_LIMIAR = 50_000

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch", type=int, default=1000,
            help="Tamanho do lote (default 1000).")
        parser.add_argument(
            "--no-truncate", action="store_true",
            help="Não limpar (TRUNCATE) as tabelas de destino antes de copiar.")

    def handle(self, *args, **opts):
        if LEGACY not in connections.databases:
            raise CommandError(
                "Conexão 'legacy_sqlite' indisponível — o arquivo db.sqlite3 não "
                "existe. Nada a migrar.")

        batch = opts["batch"]
        dest = connections[DEST]

        # Confere que o schema já existe no destino (migrate rodou).
        with dest.cursor() as cur:
            cur.execute("SELECT to_regclass('public.django_migrations')")
            if cur.fetchone()[0] is None:
                raise CommandError(
                    "Schema não encontrado no Postgres. Rode `manage.py migrate` antes.")
            # Desliga checagem de FK/triggers durante a carga (requer superuser).
            cur.execute("SET session_replication_role = replica;")

        modelos = [
            m for m in apps.get_models()
            if m._meta.managed
            and (m._meta.app_label, m._meta.model_name) not in EXCLUIR
        ]

        # Limpa o destino antes de copiar (evita PKs duplicados de execuções
        # parciais anteriores). Só toca tabelas do Django que TÊM linhas — as
        # tabelas-fonte VIOLBR* não são models e nunca entram aqui.
        if not opts["no_truncate"]:
            with dest.cursor() as cur:
                for model in modelos:
                    tabela = model._meta.db_table
                    cur.execute(f'SELECT EXISTS (SELECT 1 FROM "{tabela}" LIMIT 1)')
                    if cur.fetchone()[0]:
                        cur.execute(f'TRUNCATE TABLE "{tabela}" CASCADE;')
                        self.stdout.write(self.style.WARNING(f"  limpa: {tabela}"))

        total_copiado = 0
        for model in modelos:
            origem = model._base_manager.using(LEGACY)
            try:
                total = origem.count()
            except Exception as exc:  # tabela inexistente no SQLite
                self.stdout.write(self.style.WARNING(
                    f"  {model._meta.label}: ignorado ({exc})"))
                continue
            if total == 0:
                continue

            self.stdout.write(f"{model._meta.label}: {total} linhas")
            if total > self.COPY_LIMIAR:
                copiado = self._copiar_via_copy(model, dest, batch, total)
            else:
                copiado = self._copiar_via_orm(model, batch, total)
            total_copiado += copiado
            self.stdout.write(self.style.SUCCESS(f"  OK {copiado}/{total}"))

        # Reabilita FK/triggers e reseta as sequences (PKs foram preservados).
        with dest.cursor() as cur:
            cur.execute("SET session_replication_role = DEFAULT;")
        style = no_style()
        with dest.cursor() as cur:
            for app_config in apps.get_app_configs():
                for sql in dest.ops.sequence_reset_sql(style, list(app_config.get_models())):
                    cur.execute(sql)

        self.stdout.write(self.style.SUCCESS(
            f"\nConcluído: {total_copiado} linhas copiadas para o Postgres '{dest.settings_dict['NAME']}'. "
            "Sequences resetadas."))

    # ----------------------------------------------------------------- #
    def _copiar_via_orm(self, model, batch, total):
        """Tabelas pequenas: ORM bulk_create (preserva PK, converte tipos/JSON)."""
        origem = model._base_manager.using(LEGACY)
        buffer, copiado = [], 0
        for obj in origem.iterator(chunk_size=batch):
            buffer.append(obj)
            if len(buffer) >= batch:
                model._base_manager.using(DEST).bulk_create(buffer, batch_size=batch)
                copiado += len(buffer)
                buffer.clear()
        if buffer:
            model._base_manager.using(DEST).bulk_create(buffer, batch_size=batch)
            copiado += len(buffer)
        return copiado

    def _copiar_via_copy(self, model, dest, batch, total):
        """Tabelas grandes: COPY via streaming (leve em memória no servidor).

        Lê valores crus do SQLite e os repassa ao COPY do Postgres em modo
        texto — o Postgres faz o parse final por coluna (aceita 0/1 p/ boolean,
        'YYYY-MM-DD' p/ date, etc.).
        """
        table = model._meta.db_table
        legacy = connections[LEGACY]
        copiado = 0
        with legacy.cursor() as scur:
            scur.execute(f'SELECT * FROM "{table}"')
            colnames = [d[0] for d in scur.description]
            collist = ", ".join(f'"{c}"' for c in colnames)
            pg_conn = dest.connection
            with pg_conn.cursor() as pcur:
                with pcur.copy(f'COPY "{table}" ({collist}) FROM STDIN') as cp:
                    while True:
                        rows = scur.fetchmany(batch)
                        if not rows:
                            break
                        for r in rows:
                            cp.write_row(r)
                        copiado += len(rows)
                        self.stdout.write(f"  {copiado}/{total}", ending="\r")
        return copiado
