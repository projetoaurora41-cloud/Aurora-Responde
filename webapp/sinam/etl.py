"""Reusable ETL primitives.

Two callers today:
  - management command `etl_violbr` (reads from Postgres VIOLBRxx tables)
  - upload view in `sinam.views.upload_dbc` (reads from a .dbc file)
Both produce `Notificacao` instances via `row_to_notificacao()`.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import tempfile
import time

from .lookups import (
    CS_ESCOL, CS_GESTANTE, CS_RACA, LOCAL_OCOR, SIM_NAO, UF_CODE_TO_SIGLA,
    faixa_etaria, parse_flag, parse_nu_idade,
)
from .models import Notificacao


log = logging.getLogger(__name__)


def _parse_date(s) -> dt.date | None:
    """Parse date from either a string ('YYYY-MM-DD') or a datetime.date."""
    if isinstance(s, dt.date):
        return s
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if len(s) < 10:
        return None
    try:
        return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except (ValueError, IndexError):
        return None


def _raw_val(v):
    """Normaliza um valor do DBF para texto (as brutas VIOLBR sao 100% text)."""
    if v is None:
        return None
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v).strip()


def load_raw_violbr_table(dbf_path: str, source_table: str,
                          replace: bool = True, progress_cb=None,
                          copy_batch: int = 50000) -> dict:
    """Carrega o DBF cru (todas as colunas) na tabela ``public."<source_table>"``.

    Essa tabela bruta (colunas originais do DATASUS) alimenta a view ``VIOLBR``,
    consumida pelo chatbot de datas comemorativas (Carnaval) e pelo QA geral.
    Usa COPY (psycopg) — rápido para centenas de milhares de linhas.
    """
    import dbfread
    from src import db

    def _emit(stage, current, total=None, **extra):
        if progress_cb:
            try:
                progress_cb(stage, current, total, extra)
            except Exception:
                log.exception("progress_cb falhou")

    table = dbfread.DBF(dbf_path, encoding="latin-1", load=False)
    fields = list(table.field_names)
    cols_ddl = ", ".join(f'"{f}" text' for f in fields)
    col_idents = ", ".join(f'"{f}"' for f in fields)

    t0 = time.time()
    n = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # A view VIOLBR depende das tabelas brutas; remova-a antes de mexer
            # na tabela (é recriada ao final por refresh_violbr_view()).
            cur.execute('DROP VIEW IF EXISTS public."VIOLBR"')
            if replace:
                cur.execute(f'DROP TABLE IF EXISTS public."{source_table}" CASCADE')
            cur.execute(f'CREATE TABLE IF NOT EXISTS public."{source_table}" ({cols_ddl})')
            copy_sql = f'COPY public."{source_table}" ({col_idents}) FROM STDIN'
            with cur.copy(copy_sql) as cp:
                for rec in table:
                    cp.write_row([_raw_val(rec.get(f)) for f in fields])
                    n += 1
                    if n % copy_batch == 0:
                        _emit("raw_loading", n, None)
        conn.commit()
    elapsed = round(time.time() - t0, 1)
    _emit("raw_loaded", n, n, raw_rows=n, raw_seconds=elapsed)
    return {"rows": n, "cols": len(fields), "seconds": elapsed}


def refresh_violbr_view() -> dict:
    """(Re)cria a view ``public."VIOLBR"`` = UNION ALL das brutas VIOLBR<YY>.

    Dinâmico: detecta as tabelas ``VIOLBR<YY>`` presentes e projeta as colunas
    explicitamente (ordem da 1ª tabela) para o UNION casar por nome. Idempotente.
    """
    from src import db
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
             WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
               AND table_name ~ '^VIOLBR[0-9]{2}$'
             ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            return {"tables": [], "cols": 0}
        cur.execute("""
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s
             ORDER BY ordinal_position
        """, (tables[0],))
        cols = [r[0] for r in cur.fetchall()]
        col_list = ", ".join(f'"{c}"' for c in cols)
        union_sql = "\nUNION ALL\n".join(
            f'SELECT {col_list} FROM public."{t}"' for t in tables)
        cur.execute(f'CREATE OR REPLACE VIEW public."VIOLBR" AS\n{union_sql}')
        conn.commit()
    return {"tables": tables, "cols": len(cols)}


def row_to_notificacao(row: dict, source_table: str) -> Notificacao | None:
    """Build a `Notificacao` from a dict-like row of raw VIOLBR data.

    Works for rows coming from Postgres `cursor.fetchall()` (all str) OR from
    dbfread (mixed types including `datetime.date`).
    """
    data_not = _parse_date(row.get("DT_NOTIFIC"))
    if data_not is None:
        return None

    idade = parse_nu_idade(row.get("NU_IDADE_N"))
    uf = UF_CODE_TO_SIGLA.get(str(row.get("SG_UF") or "").strip(), "")
    uf_ocor = UF_CODE_TO_SIGLA.get(str(row.get("SG_UF_OCOR") or "").strip(), "")

    sem_raw = str(row.get("SEM_NOT") or "")
    try:
        sem_epi = int(sem_raw[-2:]) if sem_raw else None
    except ValueError:
        sem_epi = None

    nu_ano = str(row.get("NU_ANO") or "").strip()
    try:
        ano = int(nu_ano)
    except (ValueError, TypeError):
        ano = data_not.year

    return Notificacao(
        source_table=source_table,
        data_notificacao=data_not,
        data_ocorrencia=_parse_date(row.get("DT_OCOR")),
        ano=ano,
        semana_epi=sem_epi,

        sexo=str(row.get("CS_SEXO") or "I").strip()[:1] or "I",
        idade_anos=idade,
        faixa_etaria=faixa_etaria(idade),
        raca_cor=CS_RACA.get(str(row.get("CS_RACA") or "").strip(), ""),
        escolaridade=CS_ESCOL.get(str(row.get("CS_ESCOL_N") or "").strip(), ""),
        gestante=CS_GESTANTE.get(str(row.get("CS_GESTANT") or "").strip(), ""),

        uf=uf,
        uf_ocorrencia=uf_ocor,
        municipio_codigo=str(row.get("ID_MN_RESI") or "").strip()[:7],
        local_ocorrencia=LOCAL_OCOR.get(str(row.get("LOCAL_OCOR") or "").strip(), ""),
        zona="",

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
        autor_sexo=str(row.get("AUTOR_SEXO") or "").strip()[:1],
        autor_alcool=SIM_NAO.get(str(row.get("AUTOR_ALCO") or "").strip(), ""),
    )


def import_dbc_file(dbc_path: str, source_table: str,
                    progress_cb=None, replace: bool = True,
                    batch_size: int = 2000) -> dict:
    """Read a DataSUS .dbc, translate codes, bulk-insert into Notificacao.

    progress_cb(stage: str, current: int, total: int|None, extra: dict) is
    called periodically — used by the upload view to update the DB record.

    Returns a dict with counts and timings.
    """
    import dbctodbf
    import dbfread

    def _emit(stage: str, current: int, total=None, **extra):
        if progress_cb:
            try:
                progress_cb(stage, current, total, extra)
            except Exception:
                log.exception("progress_cb falhou")

    t_global = time.time()

    # 1) DBC -> DBF (pure python, slow but reliable)
    _emit("decompressing", 0, None)
    tmp_dbf = tempfile.NamedTemporaryFile(suffix=".dbf", delete=False)
    tmp_dbf.close()
    dbf_path = tmp_dbf.name
    t0 = time.time()
    dbctodbf.DBCDecompress().decompressFile(dbc_path, dbf_path)
    decompress_seconds = round(time.time() - t0, 1)
    _emit("decompressed", 0, None, decompress_seconds=decompress_seconds,
          dbf_size_mb=round(os.path.getsize(dbf_path) / 1e6, 1))

    # 1b) Carrega a tabela BRUTA (todas as colunas) — alimenta a view VIOLBR
    #     consumida pelo chatbot Carnaval / QA geral. Sem isso, só o orquestrador
    #     (que lê a base limpa) enxergaria a importação.
    raw_stats = load_raw_violbr_table(dbf_path, source_table,
                                      replace=replace, progress_cb=progress_cb)

    # 2) Replace existing rows for this source_table if requested
    if replace:
        n_old = Notificacao.objects.filter(source_table=source_table).count()
        Notificacao.objects.filter(source_table=source_table).delete()
        _emit("cleared_existing", 0, None, rows_removed=n_old)

    # 3) Stream DBF, build Notificacao, bulk_create
    table = dbfread.DBF(dbf_path, encoding="latin-1", load=False)
    ok = skipped = 0
    buf: list[Notificacao] = []
    t0 = time.time()
    try:
        for rec in table:
            obj = row_to_notificacao(rec, source_table)
            if obj is None:
                skipped += 1
                continue
            buf.append(obj)
            if len(buf) >= batch_size:
                Notificacao.objects.bulk_create(buf, batch_size=batch_size)
                ok += len(buf); buf = []
                if ok % (batch_size * 10) == 0:
                    _emit("inserting", ok, None,
                          rows_per_sec=int(ok / max(time.time() - t0, 0.01)))
        if buf:
            Notificacao.objects.bulk_create(buf, batch_size=batch_size)
            ok += len(buf)
    finally:
        try:
            os.unlink(dbf_path)
        except OSError:
            pass

    elapsed_insert = round(time.time() - t0, 1)

    # 4) (Re)cria a view VIOLBR para incluir esta tabela bruta (novo ano) e
    #    refletir os dados recém-carregados no chatbot Carnaval / QA geral.
    view_info = refresh_violbr_view()

    # 5) Materializa as tabelas do Carnaval (best-effort). Se falhar, o chatbot
    #    ainda funciona pelo fallback que recalcula da view VIOLBR.
    try:
        import os as _os

        from src.carnaval.materialize import rebuild_forecast_tables
        _url = (_os.getenv("CHATBOT_DATABASE_URL", "").strip()
                or _os.getenv("DATABASE_URL", "").strip())
        if _url:
            _emit("materializing", ok, None)
            rebuild_forecast_tables(_url)
    except Exception:
        log.exception("Falha ao materializar tabelas do Carnaval (segue via fallback).")

    total_elapsed = round(time.time() - t_global, 1)
    _emit("done", ok, ok,
          inserted=ok, skipped=skipped,
          raw_rows=raw_stats["rows"],
          decompress_seconds=decompress_seconds,
          insert_seconds=elapsed_insert,
          total_seconds=total_elapsed)
    return {
        "inserted": ok,
        "skipped": skipped,
        "raw_rows": raw_stats["rows"],
        "view_tables": view_info.get("tables", []),
        "decompress_seconds": decompress_seconds,
        "insert_seconds": elapsed_insert,
        "total_seconds": total_elapsed,
    }
