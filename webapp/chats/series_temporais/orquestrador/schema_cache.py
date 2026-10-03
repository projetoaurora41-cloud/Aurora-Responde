"""Introspect the SINAM Postgres schema once and cache it as a prompt-friendly
text block. Injected into the system prompt so the LLM knows what tables and
columns exist before it tries to call tools.

Pulled lazily on first use, then memoised. To refresh after a schema change,
restart the Django process.
"""
from __future__ import annotations

import functools
import logging

from src import db


log = logging.getLogger(__name__)

VIOLBR_TABLES = ["VIOLBR20", "VIOLBR21", "VIOLBR22", "VIOLBR23", "VIOLBR24"]

# Columns known to be categorical with low cardinality. For each, we fetch the
# top-5 most common values so the LLM can write `"CS_SEXO" = 'F'` literally
# instead of guessing.
CATEGORICAL_HINTS: dict[str, str] = {
    "CS_SEXO":     "sexo da vitima",
    "SG_UF":       "UF residencia (codigo IBGE: 35=SP, 33=RJ, 31=MG, 41=PR, 43=RS)",
    "SG_UF_OCOR":  "UF da ocorrencia (mesmo codigo IBGE)",
    "SG_UF_NOT":   "UF da notificacao (mesmo codigo IBGE)",
    "CS_RACA":     "raca/cor (codigo IBGE)",
    "CS_ESCOL_N":  "escolaridade",
    "CS_GESTANT":  "gestante",
    "ZONA":        "zona (urbana/rural)",
    "SIT_CONJUG":  "situacao conjugal",
    "LOCAL_OCOR":  "local da ocorrencia",
    "LES_AUTOP":   "lesao auto-provocada",
    "OUT_VEZES":   "ocorreu outras vezes",
    "VIOL_FISIC":  "violencia fisica (S/N)",
    "VIOL_PSICO":  "violencia psicologica (S/N)",
    "VIOL_SEXU":   "violencia sexual (S/N)",
    "VIOL_TORT":   "tortura (S/N)",
    "VIOL_FINAN":  "violencia financeira (S/N)",
    "VIOL_NEGLI":  "negligencia (S/N)",
    "VIOL_INFAN":  "violencia infanto-juvenil (S/N)",
    "VIOL_LEGAL":  "intervencao legal (S/N)",
}


def _top_values(table: str, col: str, k: int = 5) -> list[str]:
    sql = f'''
        SELECT "{col}" AS v, COUNT(*) AS c
          FROM "{table}"
         WHERE "{col}" IS NOT NULL AND "{col}" != ''
         GROUP BY 1
         ORDER BY c DESC
         LIMIT {k}
    '''
    df = db.run_query(sql)
    return [str(v) for v in df["v"].tolist()]


@functools.lru_cache(maxsize=1)
def get_sinam_schema_text() -> str:
    """Build the schema cheat-sheet that goes into the SYSTEM_PROMPT.

    Cheap on first call: ~25 small SELECTs against VIOLBR24, totals < 1s.
    """
    try:
        cols_df = db.describe_table("VIOLBR24")
    except Exception as exc:
        log.warning("schema_cache: falha ao descrever VIOLBR24: %s", exc)
        return "(Falha ao introspectar schema SINAM. Banco indisponivel?)"

    all_cols = cols_df["column_name"].tolist()
    cat_values: dict[str, list[str]] = {}
    for col in CATEGORICAL_HINTS:
        if col not in all_cols:
            continue
        try:
            cat_values[col] = _top_values("VIOLBR24", col)
        except Exception as exc:
            log.debug("schema_cache: %s: %s", col, exc)

    # Compose the prompt block. Keep it compact -- this goes into every chat turn.
    lines: list[str] = []
    lines.append("BANCO DE DADOS DISPONIVEL (Postgres 'Aurola', schema=public):")
    lines.append(f"  Tabelas: {', '.join(f'\"{t}\"' for t in VIOLBR_TABLES)}")
    lines.append("  (uma por ano de notificacao SINAM; mesmo schema entre elas)")
    lines.append("")
    lines.append("COLUNAS (todas TEXT; nomes case-sensitive, use sempre entre aspas duplas):")
    # Wrap to keep lines reasonable
    line, current = [], 0
    for c in all_cols:
        if current + len(c) + 2 > 100:
            lines.append("  " + ", ".join(line))
            line, current = [], 0
        line.append(c)
        current += len(c) + 2
    if line:
        lines.append("  " + ", ".join(line))

    lines.append("")
    lines.append("REGRAS DE QUERY:")
    lines.append('  - DT_NOTIFIC e TEXT no formato YYYY-MM-DD. Sempre filtre antes do cast:')
    lines.append("    WHERE \"DT_NOTIFIC\" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'")
    lines.append("  - Para series temporais use SELECT data, COUNT(*)::int AS valor ... GROUP BY 1 ORDER BY 1")
    lines.append("  - SUBSTRING(\"DT_NOTIFIC\",1,4) = '2023' filtra por ano sem cast.")
    lines.append("  - Para combinar varios anos use UNION ALL entre VIOLBR20..24.")
    lines.append("  - SG_UF e codigo IBGE NUMERICO, nao sigla. Sergipe=28, SP=35, RJ=33,")
    lines.append("    MG=31, BA=29, PB=25, CE=23, PR=41, RS=43, AM=13, PA=15, GO=52, DF=53.")
    lines.append("")
    lines.append("VIOLENCIAS REGISTRADAS (todas com flag S=sim / N=nao):")
    lines.append("  VIOL_FISIC  -- violencia fisica")
    lines.append("  VIOL_PSICO  -- violencia psicologica")
    lines.append("  VIOL_SEXU   -- violencia sexual")
    lines.append("  VIOL_TORT   -- tortura")
    lines.append("  VIOL_TRAF   -- trafico de pessoas (mais proximo de 'sequestro/rapto')")
    lines.append("  VIOL_FINAN  -- violencia financeira")
    lines.append("  VIOL_NEGLI  -- negligencia/abandono")
    lines.append("  VIOL_INFAN  -- violencia contra crianca/adolescente")
    lines.append("  VIOL_LEGAL  -- intervencao legal")
    lines.append("  VIOL_OUTR   -- outros tipos")
    lines.append("  NAO HA categoria 'sequestro', 'roubo', 'homicidio' -- so violencia notificada por")
    lines.append("  servico de saude. Se o usuario perguntar algo que nao bate, EXPLIQUE a limitacao.")
    lines.append("")
    if cat_values:
        lines.append("VALORES TIPICOS DE COLUNAS CATEGORICAS (top-5 em VIOLBR24):")
        for col, vals in cat_values.items():
            desc = CATEGORICAL_HINTS[col]
            pretty = ", ".join(repr(v) for v in vals)
            lines.append(f"  \"{col}\" ({desc}): {pretty}")
    return "\n".join(lines)
