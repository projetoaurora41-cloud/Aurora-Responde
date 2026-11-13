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
    """Soma tolerante a valores inválidos na origem (texto, vazio, '-')."""
    v = value_col()
    if not v:
        return "COUNT(*)"
    c = _ident(v)
    return (f"SUM(CASE WHEN {c}::text ~ '^[0-9]+(\\.[0-9]+)?$' "
            f"THEN {c}::text::numeric ELSE 0 END)")


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


_UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
        "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
        "SE", "SP", "TO")

NOME_SISTEMA = "SIPIA-CT (Sistema de Informação para a Infância e Adolescência — Conselho Tutelar)"
FONTE = "SIPIA-CT (Conselho Tutelar)"

# Dimensão usada para o TOTAL de registros quando o usuário não escolhe uma: cada
# registro tem exatamente um sexo, então a soma de "Sexo" é o universo. Somar
# todas as dimensões contava o mesmo registro 3–4 vezes (ex.: Sergipe 2023:
# 964 + 964 + 964 + 28 = 2.920, quando o certo é 964).
_DIM_TOTAL = os.getenv("SIPIA_CT_DIM_TOTAL", "Sexo")


def consultar(filtros: dict, group_by: str | None = None, top: int = 15) -> dict:
    """Total de registros do SIPIA-CT + distribuição.

    - Sem ``indicador``: o total vem da dimensão ``Sexo`` (universo único) e a
      distribuição é por ano (sem filtro de ano), por UF (com ano e sem UF) ou
      por direito violado (com UF e ano).
    - Com ``indicador``: total e distribuição por categoria daquela dimensão.
    """
    tbl = table_name()
    if not tbl:
        return {"disponivel": False, "fonte": FONTE,
                "mensagem": ("A base do SIPIA-CT não está conectada nesta instalação.")}
    if not table_exists():
        return {"disponivel": False, "fonte": FONTE,
                "mensagem": "A base do SIPIA-CT não está disponível no momento."}

    cols = allowed_columns()
    tq = _ident_table(tbl)
    agg = _agg_expr()
    filtros = dict(filtros or {})
    indicador = None
    for k in list(filtros):
        if k.split("__")[0] == "indicador":
            indicador = str(filtros.pop(k))
    dim = indicador or _DIM_TOTAL

    where, params, descr = _build_where(filtros, cols)
    extra, extra_p = [], []
    if "indicador" in cols:
        extra.append(f"{_ident('indicador')} ILIKE %s")
        extra_p.append(dim)
    tem_categoria_filtro = any(k.split("__")[0] == "categoria" for k in filtros)
    if ("categoria" in cols and not tem_categoria_filtro
            and os.getenv("SIPIA_CT_EXCLUDE_TOTAL", "1") == "1"):
        catq = _ident("categoria")
        extra.append(f"({catq} NOT ILIKE %s AND {catq} NOT ILIKE %s)")
        extra_p += ["Total", "coluna%"]
    if "uf" in cols and not any(k.split("__")[0] == "uf" for k in filtros):
        extra.append(f"upper({_ident('uf')}) IN ({', '.join(['%s'] * len(_UFS))})")
        extra_p += list(_UFS)
    if extra:
        where = (where + " AND " if where else " WHERE ") + " AND ".join(extra)
        params = list(params) + extra_p

    try:
        total = int(_run(f"SELECT COALESCE({agg}, 0) FROM {tq}{where}", list(params))[0][0] or 0)
    except Exception:  # noqa: BLE001
        return {"disponivel": False, "fonte": FONTE,
                "mensagem": ("Não consegui consultar o SIPIA-CT para esse recorte agora. "
                             "Tente informar o estado e o ano (ex.: Sergipe em 2023).")}

    out = {
        "disponivel": True,
        "fonte": FONTE,
        "sistema": NOME_SISTEMA,
        "filtros_aplicados": "; ".join(descr) if descr else "nenhum (todos os estados e anos)",
        "uf": str(filtros.get("uf") or "").upper() or None,
        "ano": filtros.get("ano"),
        "indicador": indicador,
        "dimensao_total": dim,
        "soma_registros": total,
    }

    tem_ano = any(k.split("__")[0] == "ano" for k in filtros)
    tem_uf = bool(out["uf"])
    if group_by and group_by in cols and group_by != "indicador":
        gb = group_by
    elif indicador:
        gb = "categoria"
    elif not tem_ano:
        gb = "ano"
    elif not tem_uf:
        gb = "uf"
    else:
        gb = "categoria"

    if gb == "categoria" and not indicador:
        # Distribuição por direito violado (o mesmo universo, outra dimensão).
        dim_dist = "Direito Violado"
        w2 = where
        p2 = [dim_dist if (p == dim) else p for p in params]
        out["distribuicao_dimensao"] = dim_dist
    else:
        w2, p2 = where, params
    if gb in cols:
        gq = _ident(gb)
        try:
            rows = _run(
                f"SELECT {gq} AS dim, COALESCE({agg},0) AS n FROM {tq}{w2} "
                f"GROUP BY 1 ORDER BY n DESC NULLS LAST LIMIT 200",
                list(p2),
            )
            dist: dict[str, int] = {}
            for r in rows:
                valor = r[0] if r[0] not in (None, "") else "Não informado"
                valor = _normalizar_categoria(gb, str(valor))
                dist[valor] = dist.get(valor, 0) + int(r[1] or 0)
            if gb == "ano":
                ordenado = sorted(dist.items(), key=lambda kv: str(kv[0]))
            else:
                ordenado = sorted(dist.items(), key=lambda kv: -kv[1])[:int(top)]
            out["distribuicao_por"] = gb
            out["distribuicao"] = [{"valor": v, "n": n} for v, n in ordenado if n]
        except Exception:  # noqa: BLE001
            pass
    return out


# Correções de categorias conhecidas da origem (typos/variações nos CSVs do
# SIPIA-CT). Chave e valor comparados sem acento/caixa; o valor é o rótulo final.
_CATEGORIA_FIX = {
    "femenino": "Feminino",
    "feminino": "Feminino",
    "masculino": "Masculino",
}


def _normalizar_categoria(dimensao: str, valor: str) -> str:
    """Normaliza rótulos de categoria só para a dimensão 'Sexo' (onde há o typo
    'Femenino'). Nas demais dimensões devolve o valor como veio."""
    if (dimensao or "").strip().lower() != "categoria":
        return valor
    chave = _norm_txt(valor)
    return _CATEGORIA_FIX.get(chave, valor)


def _norm_txt(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()
