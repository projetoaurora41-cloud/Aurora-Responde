"""Helpers de UF (estado) — código IBGE numérico <-> sigla de 2 letras."""
from __future__ import annotations

UF_NUM_TO_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}
SIGLA_TO_NUM = {s: n for n, s in UF_NUM_TO_SIGLA.items()}

UF_NOME = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima",
    "PA": "Pará", "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão",
    "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte", "PB": "Paraíba",
    "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe", "BA": "Bahia",
    "MG": "Minas Gerais", "ES": "Espírito Santo", "RJ": "Rio de Janeiro",
    "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal",
}


def to_sigla(value: str | None) -> str:
    """Aceita código IBGE numérico ('28') ou sigla ('SE'/'se') → sigla maiúscula."""
    if not value:
        return ""
    v = str(value).strip().upper()
    return UF_NUM_TO_SIGLA.get(v, v)


def uf_label(sigla: str) -> str:
    nome = UF_NOME.get(sigla)
    return f"{sigla} — {nome}" if nome else sigla
