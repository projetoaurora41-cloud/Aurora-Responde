"""Fonte SQL do SIPIA-CT (Conselho Tutelar) para o "Aurora responde".

Consulta uma tabela/view do Postgres do Aurora — configurável por ``.env`` — com
agregações seguras. É uma fonte DISTINTA do SINAM (notificações de saúde): aqui
são registros do Conselho Tutelar (SIPIA-CT).

Base real do projeto (schema ``sipiact``): a view ``vw_sipiact_long`` é
UF-level e PRÉ-AGREGADA — cada linha é uma combinação
(indicador, categoria, uf, ano, mês) com uma coluna numérica ``quantidade``.
Por isso o total é ``SUM(quantidade)`` (e não ``COUNT(*)``).

  indicador  -> dimensão: "Sexo" | "Cor" | "Faixa Etária" | "Direito Violado"
                | "Agente Violador"
  categoria  -> valor (código) dentro da dimensão
  quantidade -> contagem de registros

Config (.env / compose):
    SIPIA_CT_TABLE      -> nome da tabela/view (aceita ``schema.tabela``)
    SIPIA_CT_VALUE_COL  -> coluna numérica a somar (ex.: ``quantidade``);
                           vazio => usa COUNT(*)
    SIPIA_CT_COLUMNS    -> dimensões filtráveis/agrupáveis (csv)
    SIPIA_CT_TIMEOUT_MS

Segurança: identificadores (schema/tabela/colunas) validados por regex; valores
sempre parametrizados; ``statement_timeout`` evita travar a request. Sem tabela
configurada/existente, degrada limpo.
"""
from __future__ import annotations

import os
import re

_DEFAULT_COLUMNS = "uf,ano,indicador,categoria,mes,mes_numero,periodo"
_TIMEOUT_MS = int(os.getenv("SIPIA_CT_TIMEOUT_MS", "4000"))


def table_name() -> str:
    return os.getenv("SIPIA_CT_TABLE", "").strip()


def value_col() -> str:
    return os.getenv("SIPIA_CT_VALUE_COL", "").strip()


def allowed_columns() -> set[str]:
    raw = os.getenv("SIPIA_CT_COLUMNS", _DEFAULT_COLUMNS)
    return {c.strip() for c in raw.split(",") if c.strip()}


def _ident(name: str) -> str:
    """Valida/quota UM identificador SQL simples (evita injeção via .env/args)."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
        raise ValueError(f"Identificador SQL inválido: {name!r}")
    return f'"{name}"'


def _ident_table(name: str) -> str:
    """Quota tabela, aceitando ``schema.tabela`` (cada parte validada)."""
    return ".".join(_ident(p) for p in name.split("."))


def _agg_expr() -> str:
    v = value_col()
    return f"SUM({_ident(v)}::numeric)" if v else "COUNT(*)"


def _run(sql: str, params: list):
    from django.db import connection, transaction
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", [_TIMEOUT_MS])
            cur.execute(sql, params)
            return cur.fetchall()


def table_exists() -> bool:
    tbl = table_name()
    if not tbl:
        return False
    try:
        rows = _run("SELECT to_regclass(%s) IS NOT NULL", [tbl])
        return bool(rows and rows[0][0])
    except Exception:
        return False


def _build_where(filtros: dict, cols: set[str]) -> tuple[str, list, list]:
    """WHERE parametrizado a partir de filtros whitelistados.

    `uf` compara em maiúsculas; `ano`/`mes_numero` numéricos (com __gte/__lte);
    demais dimensões por igualdade case-insensitive (ILIKE)."""
    cond, params, descr = [], [], []
    numeric = {"ano", "mes_numero"}
    for key, val in (filtros or {}).items():
        base, _, op = key.partition("__")
        if base not in cols:
            continue
        col = _ident(base)
        if base in numeric:
            try:
                v = int(val)
            except (TypeError, ValueError):
                continue
            sqlop = {"gte": ">=", "lte": "<=", "lt": "<", "gt": ">"}.get(op, "=")
            cond.append(f"{col} {sqlop} %s")
            params.append(v)
            descr.append(f"{base}{sqlop if op else '='}{v}")
        elif base == "uf":
            cond.append(f"upper({col}) = %s")
            params.append(str(val).upper())
            descr.append(f"uf={str(val).upper()}")
        else:
            cond.append(f"{col} ILIKE %s")
            params.append(str(val))
            descr.append(f"{base}={val}")
    where = (" WHERE " + " AND ".join(cond)) if cond else ""
    return where, params, descr


def consultar(filtros: dict, group_by: str | None = None, top: int = 15) -> dict:
    """Soma de registros do SIPIA-CT + distribuição por uma dimensão.

    Sem `indicador` no filtro, agrupa por `indicador` por padrão (as dimensões
    NÃO são somáveis entre si — cada uma é um recorte do mesmo universo)."""
    tbl = table_name()
    if not tbl:
        return {
            "disponivel": False,
            "fonte": "SIPIA-CT (Conselho Tutelar)",
            "mensagem": ("A base do SIPIA-CT ainda não está conectada (defina "
                         "SIPIA_CT_TABLE no .env). Responda com o SINAM e diga, de "
                         "forma transparente, que o Conselho Tutelar (SIPIA-CT) não "
                         "está integrado nesta versão."),
        }
    if not table_exists():
        return {"disponivel": False, "fonte": f"SIPIA-CT ({tbl})",
                "erro": f"Tabela '{tbl}' não encontrada no banco."}

    cols = allowed_columns()
    tq = _ident_table(tbl)
    agg = _agg_expr()
    where, params, descr = _build_where(filtros or {}, cols)

    # A view tem uma categoria 'Total' (linha-resumo) que duplicaria a soma.
    # Exclui por padrão, exceto quando o usuário filtra explicitamente categoria.
    tem_categoria_filtro = any(k.split("__")[0] == "categoria" for k in (filtros or {}))
    if ("categoria" in cols and not tem_categoria_filtro
            and os.getenv("SIPIA_CT_EXCLUDE_TOTAL", "1") == "1"):
        clause = f'{_ident("categoria")} NOT ILIKE %s'
        where = (where + " AND " + clause) if where else (" WHERE " + clause)
        params = list(params) + ["Total"]

    filtros_txt = "; ".join(descr) if descr else "nenhum (base completa)"

    try:
        total = int(_run(f"SELECT COALESCE({agg}, 0) FROM {tq}{where}", list(params))[0][0] or 0)
    except Exception as exc:  # noqa: BLE001
        # A base SIPIA-CT tem alguns valores inválidos na origem que só quebram
        # em varreduras amplas — orienta a refinar (queries com UF/ano funcionam).
        return {"disponivel": False, "fonte": f"SIPIA-CT ({tbl})",
                "mensagem": ("Não consegui agregar esse recorte do SIPIA-CT (há "
                             "registros com valor inválido na origem quando a busca é "
                             "muito ampla). Refine por ESTADO e/ou ANO — ex.: Sergipe "
                             "em 2023 — que a consulta funciona."),
                "detalhe_tecnico": f"{type(exc).__name__}: {str(exc).splitlines()[0]}"}

    out = {
        "disponivel": True,
        "fonte": f"SIPIA-CT · Conselho Tutelar ({tbl})",
        "filtros_aplicados": filtros_txt,
        "soma_registros": total,
    }
    tem_indicador = any(k.split("__")[0] == "indicador" for k in (filtros or {}))
    if not tem_indicador:
        out["nota"] = ("As dimensões (Sexo, Cor, Faixa Etária, Direito Violado, "
                       "Agente Violador) são recortes do MESMO universo — não some "
                       "umas com as outras. Filtre por 'indicador' para um total limpo.")

    gb = (group_by or "").strip() or ("indicador" if not tem_indicador else "")
    if gb and gb in cols:
        gq = _ident(gb)
        try:
            rows = _run(
                f"SELECT {gq} AS dim, COALESCE({agg},0) AS n FROM {tq}{where} "
                f"GROUP BY 1 ORDER BY n DESC NULLS LAST LIMIT %s",
                list(params) + [int(top)],
            )
            out["distribuicao_por"] = gb
            out["distribuicao"] = [
                {"valor": (r[0] if r[0] not in (None, "") else "Ignorado"), "n": int(r[1] or 0)}
                for r in rows
            ]
        except Exception as exc:  # noqa: BLE001
            out["aviso"] = f"Falha ao agrupar por {gb}: {type(exc).__name__}: {exc}"
    return out
