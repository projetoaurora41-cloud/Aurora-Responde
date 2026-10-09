"""IBGE municipality code → name lookup.

The JSON file at ``core/data/municipios_ibge.json`` was produced once from
``https://servicodados.ibge.gov.br/api/v1/localidades/municipios`` and ships
with the project so the dashboards work offline. SINAN VIOL stores the
6-digit IBGE code (no check digit), so we key the lookup by the first six
digits of the official 7-digit code.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "municipios_ibge.json"


# IBGE numeric UF code → 2-letter sigla. Some SINAN extracts use the numeric
# code in SG_UF_OCOR; we want the dropdown to show "SE" instead of "28".
_UF_NUM_TO_SIGLA: dict[str, str] = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

_UF_FULL_NAME: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}


def uf_sigla(value: str) -> str:
    """Resolve any SINAN UF representation to the 2-letter sigla."""
    if not value:
        return ""
    v = str(value).strip().upper()
    if v in _UF_NUM_TO_SIGLA:
        return _UF_NUM_TO_SIGLA[v]
    return v  # already a sigla


def uf_label(value: str) -> str:
    """Friendly UF label, e.g. ``"SE — Sergipe"``."""
    sigla = uf_sigla(value)
    name = _UF_FULL_NAME.get(sigla)
    return f"{sigla} — {name}" if name else sigla


def uf_candidates(value: str) -> list[str]:
    """All string forms of a UF that may appear in SINAN data.

    Resolving "SE" from a dropdown should match rows whose
    ``SG_UF_OCOR`` is either ``"SE"`` (alphabetic) or ``"28"`` (the
    matching IBGE numeric code).
    """
    sigla = uf_sigla(value)
    if not sigla:
        return []
    nums = [num for num, sg in _UF_NUM_TO_SIGLA.items() if sg == sigla]
    return [sigla, *nums]


@cache
def _load() -> dict[str, dict[str, str]]:
    if not _DATA_PATH.exists():
        return {}
    with _DATA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def lookup(code: str) -> dict[str, str] | None:
    """Return ``{"n": name, "uf": "SE"}`` or ``None`` if unknown."""
    if not code:
        return None
    return _load().get(str(code).strip())


def label(code: str, *, with_uf: bool = True) -> str:
    """Human label for a SINAN municipality code.

    Falls back to the bare code when no match is found in the IBGE list, so
    the UI never shows a blank entry.
    """
    info = lookup(code)
    if not info:
        return code
    if with_uf and info.get("uf"):
        return f"{info['n']} ({info['uf']})"
    return info["n"]


def names_for_codes(codes: list[str]) -> list[dict[str, Any]]:
    """Bulk lookup helper used by the filter endpoint.

    Returns a list of ``{"codigo": ..., "nome": ..., "label": ...}`` dicts
    in the same order as ``codes``.
    """
    table = _load()
    out = []
    for code in codes:
        info = table.get(code)
        nome = info["n"] if info else code
        uf = info["uf"] if info else ""
        out.append(
            {
                "codigo": code,
                "nome": nome,
                "uf": uf,
                "label": f"{nome} ({uf})" if uf else nome,
            }
        )
    return out
