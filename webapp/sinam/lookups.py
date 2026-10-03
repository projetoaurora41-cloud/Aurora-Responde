"""Code → human label mappings for SINAM categorical columns.

These are stable IBGE / DataSUS dictionaries; reproduced inline to keep the ETL
self-contained.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Geographic — IBGE state codes
# ---------------------------------------------------------------------------

UF_CODE_TO_SIGLA: dict[str, str] = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
UF_SIGLA_TO_CODE = {v: k for k, v in UF_CODE_TO_SIGLA.items()}


# ---------------------------------------------------------------------------
# Person attributes
# ---------------------------------------------------------------------------

CS_SEXO: dict[str, str] = {
    "M": "Masculino",
    "F": "Feminino",
    "I": "Ignorado",
}

CS_RACA: dict[str, str] = {
    "1": "Branca",
    "2": "Preta",
    "3": "Amarela",
    "4": "Parda",
    "5": "Indigena",
    "9": "Ignorada",
}

# SINAM education codes (CS_ESCOL_N). Simplified to readable labels.
CS_ESCOL: dict[str, str] = {
    "00": "Analfabeto",
    "01": "1a-4a serie incompleta (fundamental)",
    "02": "4a serie completa (fundamental)",
    "03": "5a-8a serie incompleta (fundamental)",
    "04": "Fundamental completo",
    "05": "Medio incompleto",
    "06": "Medio completo",
    "07": "Superior incompleto",
    "08": "Superior completo",
    "09": "Ignorado",
    "10": "Nao se aplica",
}

CS_GESTANTE: dict[str, str] = {
    "1": "1o trimestre",
    "2": "2o trimestre",
    "3": "3o trimestre",
    "4": "Idade gestacional ignorada",
    "5": "Nao",
    "6": "Nao se aplica",
    "9": "Ignorado",
}

ZONA: dict[str, str] = {
    "1": "Urbana",
    "2": "Rural",
    "3": "Periurbana",
    "9": "Ignorado",
}

# Local da ocorrencia (LOCAL_OCOR)
LOCAL_OCOR: dict[str, str] = {
    "01": "Residencia",
    "02": "Habitacao coletiva",
    "03": "Escola",
    "04": "Local pratica esportiva",
    "05": "Bar / similar",
    "06": "Via publica",
    "07": "Comercio / servicos",
    "08": "Industria / construcao",
    "09": "Outros",
    "99": "Ignorado",
}

SIT_CONJUG: dict[str, str] = {
    "1": "Solteiro",
    "2": "Casado / uniao estavel",
    "3": "Viuvo",
    "4": "Separado / divorciado",
    "9": "Ignorado",
}

# SINAM boolean-like fields use "1" = Sim, "2" = Nao, "9" = Ignorado.
SIM_NAO: dict[str, str] = {"1": "Sim", "2": "Nao", "9": "Ignorado"}


def parse_nu_idade(value: str | None) -> int | None:
    """Decode SINAM's NU_IDADE_N format.

    Layout: 4 digits where the leading digit is the unit:
      1 -> hora, 2 -> dia, 3 -> mes, 4 -> ano
    Followed by 3 digits with the numeric value (zero-padded).
    Returns idade em ANOS (rounded down), or None if undecodable.

    Examples:
      '4012' -> 12 anos
      '4005' -> 5 anos
      '3010' -> 0 anos (10 meses)
      '1023' -> 0 anos (23 horas)
      '0000' / '' / None -> None
    """
    if not value:
        return None
    s = str(value).strip()
    if not s.isdigit() or len(s) < 4:
        return None
    unit = s[0]
    try:
        n = int(s[1:4])
    except ValueError:
        return None
    if unit == "4":
        return n
    if unit in ("1", "2", "3"):  # hora, dia, mes
        return 0
    return None


def faixa_etaria(anos: int | None) -> str:
    if anos is None:
        return "Ignorada"
    if anos < 1:    return "< 1 ano"
    if anos < 5:    return "1-4"
    if anos < 10:   return "5-9"
    if anos < 15:   return "10-14"
    if anos < 20:   return "15-19"
    if anos < 60:   return "20-59"
    return "60+"


def parse_flag(value: str | None) -> bool | None:
    """Decode SINAM boolean: '1' Sim, '2' Nao, '9' Ignorado/None."""
    if value in (None, "", "9"):
        return None
    return value == "1"
