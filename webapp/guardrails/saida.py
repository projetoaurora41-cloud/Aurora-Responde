"""Filtros de saída: vazamento, supressão estatística, número sem fonte."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings

from .mensagens import MSG_SAIDA_BLOQUEADA, MSG_SUPRESSAO


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


_LEAK_RE = re.compile(
    r"traceback\s*\(most recent call last\)|"
    r'file\s+"[^"]+",\s*line\s+\d+|'
    r"\bselect\s+.+\s+from\s+\w+|"
    r"\binsert\s+into\s+\w+|"
    r"\bupdate\s+\w+\s+set\s+|"
    r"\bdelete\s+from\s+\w+|"
    r"\bpassword\s*=\s*\S+|"
    r"\bapi[_-]?key\s*=\s*\S+|"
    r"begin\s+rsa\s+private\s+key|"
    r"-----begin\s+(rsa\s+)?private\s+key-----",
    re.IGNORECASE | re.DOTALL,
)

# "apenas 3 casos", "2 notificações", "foram 1 registro"
_LOW_COUNT_RE = re.compile(
    r"\b(?:apenas|somente|so|foram|ha|existem?|total\s+de)\s+"
    r"(\d{1,2})\s+"
    r"(?:casos?|notificac(?:ao|oes)|registros?|ocorrencias?)\b",
    re.IGNORECASE,
)

_BIG_NUMBER_RE = re.compile(r"\b(\d{3,}(?:\.\d{3})*|\d{4,})\b")

_FONTE_RE = re.compile(
    r"\bsinan\b|\bsipia\b|\beca\b|\bfonte\b|\[j\d+\]|\[d\d+\]|"
    r"segundo\s+(?:o|a)\s+|conforme\s+(?:o|a)\s+|base\s+jurid",
    re.IGNORECASE,
)


@dataclass
class FiltroSaidaResult:
    ok: bool = True
    bloqueio: bool = False
    texto: str = ""
    mensagem_usuario: str = ""
    eventos: list[dict] = field(default_factory=list)


def _suppress_below() -> int:
    return int(getattr(settings, "GUARDRAILS_SUPPRESS_BELOW", 5))


def filtrar_saida(texto: str) -> FiltroSaidaResult:
    """Aplica filtros de vazamento, supressão e marca número sem fonte."""
    raw = texto or ""
    eventos: list[dict] = []

    if _LEAK_RE.search(raw):
        return FiltroSaidaResult(
            ok=False,
            bloqueio=True,
            texto="",
            mensagem_usuario=MSG_SAIDA_BLOQUEADA,
            eventos=[{"tipo": "vazamento", "acao": "bloqueio"}],
        )

    limiar = _suppress_below()
    for m in _LOW_COUNT_RE.finditer(raw):
        n = int(m.group(1))
        if n < limiar:
            return FiltroSaidaResult(
                ok=True,
                bloqueio=False,
                texto=MSG_SUPRESSAO,
                mensagem_usuario="",
                eventos=[{
                    "tipo": "supressao",
                    "n": n,
                    "limiar": limiar,
                }],
            )

    # Número "grande" sem menção a fonte → evento de revisão (não bloqueia).
    if _BIG_NUMBER_RE.search(raw) and not _FONTE_RE.search(_norm(raw)):
        eventos.append({"tipo": "numero_sem_fonte"})

    return FiltroSaidaResult(
        ok=True,
        bloqueio=False,
        texto=raw,
        mensagem_usuario="",
        eventos=eventos,
    )
