"""Score heurístico de prompt injection (0–1). Bloquear se >= limiar (default 0.70)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# (padrão, peso) — pesos somam e são saturados em 1.0
_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"), 0.85),
    (re.compile(r"ignor[ae]\s+(todas?\s+)?(as\s+)?(instruc[oõ]es|regras)"), 0.85),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions?|rules?)"), 0.8),
    (re.compile(r"\bjailbreak\b|\bdan\s+mode\b|\bdeveloper\s+mode\b"), 0.75),
    (re.compile(r"system\s*prompt|prompt\s+do\s+sistema|reveal\s+(your\s+)?(system|hidden)\s+prompt"), 0.7),
    (re.compile(r"finja\s+ser|finja\s+que\s+voce|pretend\s+(you\s+are|to\s+be)|roleplay\s+as"), 0.55),
    (re.compile(r"voce\s+(agora\s+)?e\s+(um\s+)?(admin|administrador|root|hacker)"), 0.6),
    (re.compile(r"override\s+(your\s+)?(safety|rules|guardrails)|bypass\s+(your\s+)?(filters?|safety)"), 0.8),
    (re.compile(r"esqueca\s+(tudo|suas\s+regras)|forget\s+(everything|your\s+rules)"), 0.75),
    (re.compile(r"new\s+instructions?\s*:|novas?\s+instruc[oõ]es\s*:"), 0.5),
    (re.compile(r"<\s*/?\s*system\s*>|\[system\]|<<\s*sys\s*>>"), 0.65),
]


@dataclass
class InjecaoResult:
    score: float
    motivos: list[str]


def score_injecao(texto: str) -> InjecaoResult:
    """Retorna score em [0, 1] e lista de padrões que bateram."""
    if not texto or not texto.strip():
        return InjecaoResult(score=0.0, motivos=[])
    n = _norm(texto)
    score = 0.0
    motivos: list[str] = []
    for pat, peso in _PATTERNS:
        if pat.search(n):
            score += peso
            motivos.append(pat.pattern[:60])
    return InjecaoResult(score=min(1.0, round(score, 3)), motivos=motivos)
