"""Carrega dados do SIPIA-CT (Conselho Tutelar) de um CSV para a tabela SQL
consultada pela tool ``consulta_sipia_ct`` do "Aurora responde".

Uso:
    python manage.py load_sipia_ct caminho.csv --table sipia_ct [--truncate]

Depois, aponte o .env para a tabela:  SIPIA_CT_TABLE=sipia_ct

Cabeçalho CSV esperado (colunas extras são ignoradas):
    uf, municipio, ano, sexo, faixa_etaria, direito_violado, medida_aplicada
`ano` é inteiro; as demais colunas são texto.
"""
from __future__ import annotations

import csv
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

COLUMNS = ["uf", "municipio", "ano", "sexo", "faixa_etaria",
           "direito_violado", "medida_aplicada"]


class Command(BaseCommand):
    help = "Carrega um CSV do SIPIA-CT na tabela consultada pela tool consulta_sipia_ct."

    def add_arguments(self, parser):
        parser.add_argument("csv", help="Caminho do arquivo CSV.")
        parser.add_argument("--table", default="sipia_ct", help="Tabela destino (default: sipia_ct).")
        parser.add_argument("--truncate", action="store_true", help="Zera a tabela antes de carregar.")

    def handle(self, *args, **opts):
        table = opts["table"]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise CommandError(f"Nome de tabela inválido: {table!r}")
        try:
            fh = open(opts["csv"], newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(str(exc))
        with fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise CommandError("CSV vazio ou sem cabeçalho.")

        tq = f'"{table}"'
        coldefs = ", ".join(
            (f'"{c}" integer' if c == "ano" else f'"{c}" text') for c in COLUMNS)
        collist = ", ".join(f'"{c}"' for c in COLUMNS)
        placeholders = ", ".join(["%s"] * len(COLUMNS))

        n = 0
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(f"CREATE TABLE IF NOT EXISTS {tq} (id bigserial PRIMARY KEY, {coldefs})")
                if opts["truncate"]:
                    cur.execute(f"TRUNCATE {tq}")
                for r in rows:
                    vals = []
                    for c in COLUMNS:
                        v = (r.get(c) or "").strip()
                        if c == "ano":
                            vals.append(int(v) if v.isdigit() else None)
                        else:
                            vals.append(v or None)
                    cur.execute(f"INSERT INTO {tq} ({collist}) VALUES ({placeholders})", vals)
                    n += 1
        self.stdout.write(self.style.SUCCESS(f"Carregado {n} linha(s) em {table}."))
