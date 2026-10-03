"""ETL: read raw VIOLBRxx tables from Postgres and populate sinam.Notificacao.

Usage:
    python manage.py etl_violbr                  # all years (VIOLBR20..24)
    python manage.py etl_violbr --year 2024      # only one year
    python manage.py etl_violbr --clear          # truncate first
    python manage.py etl_violbr --limit 10000    # for testing
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Iterable

from django.core.management.base import BaseCommand

from sinam.lookups import (
    CS_ESCOL, CS_GESTANTE, CS_RACA, LOCAL_OCOR, SIM_NAO, UF_CODE_TO_SIGLA,
    faixa_etaria, parse_flag, parse_nu_idade,
)
from sinam.models import Notificacao
from src import db


VIOLBR_TABLES = ["VIOLBR20", "VIOLBR21", "VIOLBR22", "VIOLBR23", "VIOLBR24"]

# Columns we actually read from the source table.
SRC_COLUMNS = [
    "DT_NOTIFIC", "DT_OCOR", "NU_ANO", "SEM_NOT",
    "CS_SEXO", "NU_IDADE_N", "CS_RACA", "CS_ESCOL_N", "CS_GESTANT",
    "SG_UF", "SG_UF_OCOR", "ID_MN_RESI",
    "LOCAL_OCOR",
    "VIOL_FISIC", "VIOL_PSICO", "VIOL_SEXU", "VIOL_TORT", "VIOL_TRAF",
    "VIOL_FINAN", "VIOL_NEGLI", "VIOL_INFAN", "VIOL_LEGAL", "VIOL_OUTR",
    "LES_AUTOP", "OUT_VEZES",
    "AUTOR_SEXO", "AUTOR_ALCO",
]


def _parse_date(s: str | None) -> dt.date | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if len(s) < 10:
        return None
    try:
        return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def _row_to_notificacao(row: dict, source_table: str) -> Notificacao | None:
    data_not = _parse_date(row.get("DT_NOTIFIC"))
    if data_not is None:
        return None  # Skip rows without a valid notification date.

    idade = parse_nu_idade(row.get("NU_IDADE_N"))
    uf = UF_CODE_TO_SIGLA.get((row.get("SG_UF") or "").strip(), "")
    uf_ocor = UF_CODE_TO_SIGLA.get((row.get("SG_UF_OCOR") or "").strip(), "")

    try:
        sem_epi = int(str(row.get("SEM_NOT") or "")[-2:])
    except ValueError:
        sem_epi = None

    return Notificacao(
        source_table=source_table,
        data_notificacao=data_not,
        data_ocorrencia=_parse_date(row.get("DT_OCOR")),
        ano=int(row.get("NU_ANO") or data_not.year),
        semana_epi=sem_epi,

        sexo=(row.get("CS_SEXO") or "I").strip()[:1] or "I",
        idade_anos=idade,
        faixa_etaria=faixa_etaria(idade),
        raca_cor=CS_RACA.get((row.get("CS_RACA") or "").strip(), ""),
        escolaridade=CS_ESCOL.get((row.get("CS_ESCOL_N") or "").strip(), ""),
        gestante=CS_GESTANTE.get((row.get("CS_GESTANT") or "").strip(), ""),

        uf=uf,
        uf_ocorrencia=uf_ocor,
        municipio_codigo=(row.get("ID_MN_RESI") or "").strip()[:7],
        local_ocorrencia=LOCAL_OCOR.get((row.get("LOCAL_OCOR") or "").strip(), ""),
        zona="",  # coluna ZONA nao existe no schema; mantido por compatibilidade

        violencia_fisica=parse_flag(row.get("VIOL_FISIC")),
        violencia_psicologica=parse_flag(row.get("VIOL_PSICO")),
        violencia_sexual=parse_flag(row.get("VIOL_SEXU")),
        tortura=parse_flag(row.get("VIOL_TORT")),
        trafico_pessoas=parse_flag(row.get("VIOL_TRAF")),
        violencia_financeira=parse_flag(row.get("VIOL_FINAN")),
        negligencia=parse_flag(row.get("VIOL_NEGLI")),
        violencia_infantil=parse_flag(row.get("VIOL_INFAN")),
        intervencao_legal=parse_flag(row.get("VIOL_LEGAL")),
        outras_violencias=parse_flag(row.get("VIOL_OUTR")),

        lesao_autoprovocada=parse_flag(row.get("LES_AUTOP")),
        ocorreu_outras_vezes=parse_flag(row.get("OUT_VEZES")),
        autor_sexo=(row.get("AUTOR_SEXO") or "").strip()[:1],
        autor_alcool=SIM_NAO.get((row.get("AUTOR_ALCO") or "").strip(), ""),
    )


def _stream_table(table: str, limit: int | None) -> Iterable[dict]:
    """Yield rows of the given VIOLBR table as dicts. Streams from psycopg."""
    cols_quoted = ", ".join(f'"{c}"' for c in SRC_COLUMNS)
    sql = f'SELECT {cols_quoted} FROM "{table}"'
    if limit:
        sql += f" LIMIT {int(limit)}"
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colnames = [d.name for d in cur.description]
            while True:
                batch = cur.fetchmany(5000)
                if not batch:
                    break
                for row in batch:
                    yield dict(zip(colnames, row))


class Command(BaseCommand):
    help = "Popula sinam.Notificacao a partir das tabelas VIOLBRxx do Postgres."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, choices=[2020, 2021, 2022, 2023, 2024],
                            help="Apenas um ano (default: todos).")
        parser.add_argument("--clear", action="store_true",
                            help="Apaga Notificacao antes de inserir.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Limite de linhas por tabela (debug).")
        parser.add_argument("--batch", type=int, default=2000,
                            help="Tamanho do bulk_create (default 2000).")

    def handle(self, *args, **opts):
        tables = [f"VIOLBR{opts['year'] - 2000:02d}"] if opts.get("year") else VIOLBR_TABLES

        if opts["clear"]:
            if opts.get("year"):
                n = Notificacao.objects.filter(source_table=tables[0]).count()
                Notificacao.objects.filter(source_table=tables[0]).delete()
                self.stdout.write(f"Removidas {n} linhas de {tables[0]}.")
            else:
                n = Notificacao.objects.count()
                Notificacao.objects.all().delete()
                self.stdout.write(f"Removidas {n} linhas (TODAS).")

        batch_size = opts["batch"]
        for table in tables:
            self.stdout.write(self.style.NOTICE(f"\n[{table}] importando..."))
            t0 = time.time()
            buf: list[Notificacao] = []
            ok = skipped = 0
            try:
                for row in _stream_table(table, opts["limit"]):
                    obj = _row_to_notificacao(row, table)
                    if obj is None:
                        skipped += 1
                        continue
                    buf.append(obj)
                    if len(buf) >= batch_size:
                        Notificacao.objects.bulk_create(buf, batch_size=batch_size)
                        ok += len(buf); buf = []
                        if ok % (batch_size * 10) == 0:
                            self.stdout.write(f"  {ok:>8} importadas  ({(ok / (time.time()-t0)):.0f}/s)")
                if buf:
                    Notificacao.objects.bulk_create(buf, batch_size=batch_size)
                    ok += len(buf)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  ERRO em {table}: {exc}"))
                continue
            elapsed = time.time() - t0
            self.stdout.write(self.style.SUCCESS(
                f"  {table}: {ok} importadas, {skipped} puladas em {elapsed:.1f}s"
                f" ({ok / max(elapsed,0.01):.0f}/s)"
            ))

        total = Notificacao.objects.count()
        self.stdout.write(self.style.SUCCESS(f"\nTotal na base limpa: {total} notificacoes."))
