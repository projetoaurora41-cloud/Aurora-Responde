"""Cache leve das agregações (dashboards + mapas) para abertura rápida.

Reaproveitado do projeto original. Usa o cache padrão do Django (LocMemCache em
desenvolvimento). As agregações varrem milhões de linhas da tabela
``sinan.VIOLBR``; cacheá-las por alguns minutos torna reaberturas instantâneas.

O cache só deve ser aplicado quando lemos a tabela externa massiva (PostgreSQL)
— nunca com a tabela local/SQLite (testes, uploads), onde os dados mudam e a
consulta já é barata. Por isso os *call sites* passam por trás de um gate
(``analytics.caching_enabled()`` / ``_has_sipiact_view()``).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from django.core.cache import cache

DEFAULT_TTL = 900  # 15 minutos


def _key(prefix: str, params: Any) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return f"aurora:{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"


def cached(prefix: str, params: Any, fn: Callable[[], Any], ttl: int = DEFAULT_TTL):
    """Retorna ``fn()`` cacheado por ``ttl`` segundos, chaveado por ``params``."""
    key = _key(prefix, params)
    val = cache.get(key)
    if val is None:
        val = fn()
        cache.set(key, val, ttl)
    return val
