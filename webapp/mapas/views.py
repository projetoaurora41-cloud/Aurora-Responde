"""Endpoints do mapa SIPIA-CT usados na distribuição geográfica."""

from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import queries


@require_GET
def sipiact_filtros(request):
    return JsonResponse(queries.sipiact_filtros())


@require_GET
def sipiact_uf(request):
    indicador = request.GET.get("indicador") or None
    ano_raw = request.GET.get("ano") or None
    ano = None
    if ano_raw:
        try:
            ano = int(ano_raw)
        except (TypeError, ValueError):
            ano = None
    return JsonResponse(queries.sipiact_uf_totals(indicador, ano))
