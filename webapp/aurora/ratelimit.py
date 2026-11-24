"""Limite de requisições por IP para todo o site (proteção contra abuso/DoS).

Complementa o limite do chat (``guardrails.limites``), que só vale para o envio
de mensagens. Aqui cada IP tem um teto por minuto em duas faixas:

* ``AURORA_RATE_LIMIT_API_PER_MIN``   — rotas ``/aurora/api/`` (JSON pesado dos
  painéis e mapas). Padrão: 120/min.
* ``AURORA_RATE_LIMIT_PAGE_PER_MIN``  — demais páginas. Padrão: 240/min.

Estáticos, admin e ``/series-temporais/chat/`` (já limitado pelos guardrails)
ficam de fora. Ao estourar o teto a resposta é HTTP 429 com ``Retry-After``.
Usa o cache padrão do Django (Valkey em produção, se configurado); se o cache
falhar, a requisição passa e um aviso é registrado (o site não cai por isso).

Atrás de proxy reverso, defina ``AURORA_TRUST_X_FORWARDED_FOR=1`` para usar o
IP real do cliente (último endereço do ``X-Forwarded-For``, o que o proxy
acrescentou).
"""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse

logger = logging.getLogger(__name__)

_ISENTOS = ("/static/", "/admin/", "/series-temporais/chat/", "/favicon")


def client_ip(request) -> str:
    if getattr(settings, "AURORA_TRUST_X_FORWARDED_FOR", False):
        fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if fwd:
            # O proxy acrescenta o IP real no FIM da lista; os anteriores podem ter
            # sido forjados pelo cliente, então usamos o último.
            return fwd.split(",")[-1].strip()
        real = request.META.get("HTTP_X_REAL_IP", "").strip()
        if real:
            return real
    return request.META.get("REMOTE_ADDR", "") or "desconhecido"


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bloqueio = self._verificar(request)
        if bloqueio is not None:
            return bloqueio
        return self.get_response(request)

    def _verificar(self, request):
        if not getattr(settings, "AURORA_RATE_LIMIT_ENABLED", True):
            return None
        path = request.path
        if path.startswith(_ISENTOS):
            return None
        api = path.startswith("/aurora/api/")
        teto = int(getattr(settings, "AURORA_RATE_LIMIT_API_PER_MIN" if api
                           else "AURORA_RATE_LIMIT_PAGE_PER_MIN", 120 if api else 240))
        if teto <= 0:
            return None
        janela = int(time.time() // 60)
        chave = f"rl:site:{'api' if api else 'page'}:{client_ip(request)}:{janela}"
        try:
            cache.add(chave, 0, timeout=70)
            contagem = int(cache.incr(chave))
        except Exception as exc:  # noqa: BLE001 — degrada sem derrubar o site
            logger.warning("ratelimit: cache indisponível (%s) — permitindo", exc)
            return None
        if contagem <= teto:
            return None
        espera = max(1, 60 - int(time.time()) % 60)
        logger.warning("ratelimit: %s excedeu %s req/min em %s", client_ip(request), teto, path)
        msg = "Muitas requisições em pouco tempo. Aguarde alguns segundos e tente novamente."
        if api or "application/json" in request.headers.get("Accept", ""):
            resp = JsonResponse({"error": msg, "retry_after_seconds": espera}, status=429)
        else:
            resp = HttpResponse(msg, status=429, content_type="text/plain; charset=utf-8")
        resp["Retry-After"] = str(espera)
        return resp
