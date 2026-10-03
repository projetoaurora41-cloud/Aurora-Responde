"""Controle de requisições por chave (sessão/IP) — stub com cache Django.

Usa ``CACHES["default"]`` (Valkey via django-redis quando ``VALKEY_URL`` está
definido; LocMemCache no dev). Se o cache falhar, **permite** e registra
warning (degrada limpo — o chat não deve cair por falha de limite).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class LimiteResult:
    ok: bool
    motivo: str = ""
    retry_after_seconds: int | None = None
    contagem_min: int = 0
    contagem_dia: int = 0


def _limits() -> tuple[int, int]:
    per_min = int(getattr(settings, "GUARDRAILS_RATE_LIMIT_PER_MIN", 10))
    per_day = int(getattr(settings, "GUARDRAILS_RATE_LIMIT_PER_DAY", 200))
    return per_min, per_day


def verificar_limite(chave: str) -> LimiteResult:
    """Incrementa contadores minuto/dia para ``chave`` e aplica o teto.

    Chaves de cache: ``guardrails:rl:min:{chave}`` (TTL 60s) e
    ``guardrails:rl:day:{chave}`` (TTL 86400s).
    """
    if not chave:
        return LimiteResult(ok=True, motivo="chave_vazia")

    per_min, per_day = _limits()
    key_min = f"guardrails:rl:min:{chave}"
    key_day = f"guardrails:rl:day:{chave}"

    try:
        # add só cria se não existir; depois incr.
        if cache.add(key_min, 0, timeout=60):
            pass
        if cache.add(key_day, 0, timeout=86400):
            pass
        contagem_min = int(cache.incr(key_min))
        contagem_dia = int(cache.incr(key_day))
    except Exception as exc:  # noqa: BLE001 — degrada limpo
        logger.warning(
            "guardrails.limites: cache indisponível (%s) — permitindo %r",
            exc, chave,
        )
        return LimiteResult(ok=True, motivo=f"cache_indisponivel:{type(exc).__name__}")

    if contagem_min > per_min:
        return LimiteResult(
            ok=False,
            motivo="limite_por_minuto",
            retry_after_seconds=60,
            contagem_min=contagem_min,
            contagem_dia=contagem_dia,
        )
    if contagem_dia > per_day:
        return LimiteResult(
            ok=False,
            motivo="limite_por_dia",
            retry_after_seconds=3600,
            contagem_min=contagem_min,
            contagem_dia=contagem_dia,
        )
    return LimiteResult(
        ok=True,
        contagem_min=contagem_min,
        contagem_dia=contagem_dia,
    )
