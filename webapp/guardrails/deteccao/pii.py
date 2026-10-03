"""Detecção e máscara de CPF / CNPJ / CNS (com validação de dígitos)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def _only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _cpf_valido(digs: str) -> bool:
    if len(digs) != 11 or digs == digs[0] * 11:
        return False
    nums = [int(c) for c in digs]
    s1 = sum(nums[i] * (10 - i) for i in range(9))
    d1 = (s1 * 10) % 11
    d1 = 0 if d1 == 10 else d1
    if d1 != nums[9]:
        return False
    s2 = sum(nums[i] * (11 - i) for i in range(10))
    d2 = (s2 * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return d2 == nums[10]


def _cnpj_valido(digs: str) -> bool:
    if len(digs) != 14 or digs == digs[0] * 14:
        return False
    nums = [int(c) for c in digs]
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = sum(nums[i] * w1[i] for i in range(12)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    if d1 != nums[12]:
        return False
    d2 = sum(nums[i] * w2[i] for i in range(13)) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    return d2 == nums[13]


def _cns_valido(digs: str) -> bool:
    """CNS: 15 dígitos; validação simplificada (módulo 11 / padrões oficiais comuns)."""
    if len(digs) != 15 or not digs.isdigit():
        return False
    if digs[0] in "127":
        # Definitivo: soma ponderada
        s = sum(int(digs[i]) * (15 - i) for i in range(15))
        return s % 11 == 0
    if digs[0] in "89":
        # Provisório
        s = sum(int(digs[i]) * (15 - i) for i in range(15))
        return s % 11 == 0
    return False


_CPF_RE = re.compile(r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b")
_CNPJ_RE = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b")
_CNS_RE = re.compile(r"\b(\d{3}\s?\d{4}\s?\d{4}\s?\d{4})\b")


@dataclass
class PiiResult:
    texto_mascarado: str
    campos: list[str] = field(default_factory=list)


def mascarar_pii(texto: str) -> PiiResult:
    """Substitui CPF/CNPJ/CNS válidos por máscaras; não bloqueia a mensagem."""
    if not texto:
        return PiiResult(texto_mascarado="")
    out = texto
    campos: list[str] = []

    def _sub_cpf(m: re.Match[str]) -> str:
        digs = _only_digits(m.group(1))
        if _cpf_valido(digs):
            campos.append("cpf")
            return "***.***.***-**"
        return m.group(0)

    def _sub_cnpj(m: re.Match[str]) -> str:
        digs = _only_digits(m.group(1))
        if _cnpj_valido(digs):
            campos.append("cnpj")
            return "**.***.***/****-**"
        return m.group(0)

    def _sub_cns(m: re.Match[str]) -> str:
        digs = _only_digits(m.group(1))
        if _cns_valido(digs):
            campos.append("cns")
            return "*** **** **** ****"
        return m.group(0)

    # CNPJ antes de CPF (mais dígitos) para evitar matches parciais.
    out = _CNPJ_RE.sub(_sub_cnpj, out)
    out = _CPF_RE.sub(_sub_cpf, out)
    out = _CNS_RE.sub(_sub_cns, out)
    return PiiResult(texto_mascarado=out, campos=campos)
