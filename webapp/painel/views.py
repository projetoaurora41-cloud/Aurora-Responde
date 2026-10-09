"""Início, painel Aurora e distribuição geográfica."""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import number_format
from django.views.decorators.http import require_GET

from mapas import queries as mapas_queries
from painel.forms import DashboardFilterForm
from painel.services import analytics, cache as agg_cache, municipios as municipios_lookup


def _fmt_int_pt(n) -> str:
    return number_format(int(n or 0), decimal_pos=0, force_grouping=True)


@require_GET
def inicio(request):
    return render(request, "painel/inicio.html")


@require_GET
def dashboards(request):
    filter_form = DashboardFilterForm(request.GET or None)
    Model = analytics.violbr_model()
    has_data = Model.objects.exists()
    filters = filter_form.to_filters() if request.GET else {}
    kpis = analytics.overview_kpis(filters) if has_data else {
        "total": 0, "violencia_sexual": 0, "exploracao_sexual": 0, "municipios": 0,
    }
    kpis = {key: _fmt_int_pt(val) for key, val in kpis.items()}
    return render(request, "painel/dashboards.html", {
        "filter_form": filter_form,
        "dashboards": analytics.DASHBOARDS,
        "has_data": has_data,
        "total_rows": Model.objects.count(),
        "kpis": kpis,
    })


def _parse_geo_fonte(request) -> str:
    fonte = (request.GET.get("fonte") or "brasil").strip().lower()
    if fonte not in {"brasil", "sinan", "sipia-ct"}:
        return "brasil"
    return fonte


@require_GET
def distribuicao_geografica(request):
    fonte = _parse_geo_fonte(request)
    filter_form = DashboardFilterForm(request.GET or None)
    Model = analytics.violbr_model()
    has_data = Model.objects.exists()
    return render(request, "painel/distribuicao_geografica.html", {
        "fonte": fonte,
        "filter_form": filter_form,
        "has_data": has_data,
        "usando_dados_reais": mapas_queries.usando_dados_reais(),
    })


@require_GET
def mapa(request):
    qs = request.META.get("QUERY_STRING", "")
    url = reverse("distribuicao_geografica") + "?fonte=brasil"
    if qs:
        parts = [p for p in qs.split("&") if p and not p.startswith("fonte=")]
        if parts:
            url += "&" + "&".join(parts)
    return redirect(url)


@require_GET
def filter_options(request):
    def _compute():
        Model = analytics.violbr_model()
        qs = Model.objects.exclude(SG_UF_OCOR="")
        pairs = (
            qs.exclude(ID_MN_OCOR="")
            .values_list("SG_UF_OCOR", "ID_MN_OCOR")
            .distinct()
            .order_by("SG_UF_OCOR", "ID_MN_OCOR")
        )
        municipios_por_uf: dict[str, list[dict[str, str]]] = defaultdict(list)
        seen_codes: dict[str, set[str]] = defaultdict(set)
        for uf_raw, codigo in pairs:
            sigla = municipios_lookup.uf_sigla(uf_raw)
            if codigo in seen_codes[sigla]:
                continue
            seen_codes[sigla].add(codigo)
            info = municipios_lookup.lookup(codigo)
            nome = info["n"] if info else codigo
            municipios_por_uf[sigla].append({
                "codigo": codigo,
                "nome": nome,
                "label": f"{nome} ({sigla})" if sigla else nome,
            })
        for lst in municipios_por_uf.values():
            lst.sort(key=lambda m: m["nome"].lower())
        ufs = sorted(municipios_por_uf.keys())
        anos = sorted(
            a for a in Model.objects.exclude(NU_ANO="").values_list("NU_ANO", flat=True).distinct() if a
        )
        return {
            "ufs": ufs,
            "ufs_meta": [{"sigla": s, "label": municipios_lookup.uf_label(s)} for s in ufs],
            "municipios_por_uf": dict(municipios_por_uf),
            "anos": anos,
        }

    payload = agg_cache.cached("filters", "all", _compute) if analytics.caching_enabled() else _compute()
    return JsonResponse(payload)


@require_GET
def map_municipalities(request, uf: str):
    sigla = municipios_lookup.uf_sigla(uf)
    if " — " not in municipios_lookup.uf_label(sigla):
        return JsonResponse({"error": "UF invalida"}, status=400)

    filter_form = DashboardFilterForm(request.GET or None)
    filters = filter_form.to_filters() if request.GET else {}
    filters["uf"] = sigla

    def _compute():
        qs = (
            analytics.apply_filters(analytics.base_queryset(), filters)
            .exclude(ID_MN_OCOR="")
            .values("ID_MN_OCOR")
            .annotate(
                total=Count("id"),
                violencia_sexual=Count("id", filter=Q(VIOL_SEXU="1")),
                trafico=Count("id", filter=Q(VIOL_TRAF="1")),
                exploracao_sexual=Count("id", filter=Q(SEX_EXPLO="1")),
            )
            .order_by("-total")
        )
        municipios: dict[str, dict] = {}
        total_uf = 0
        for row in qs:
            codigo = row["ID_MN_OCOR"]
            info = municipios_lookup.lookup(codigo)
            nome = info["n"] if info else codigo
            municipios[codigo] = {
                "codigo": codigo,
                "nome": nome,
                "total": row["total"],
                "violencia_sexual": row["violencia_sexual"],
                "trafico": row["trafico"],
                "exploracao_sexual": row["exploracao_sexual"],
            }
            total_uf += row["total"]
        return municipios, total_uf

    if analytics.caching_enabled():
        municipios, total_uf = agg_cache.cached("mapa_muni", {"uf": sigla, "f": filters}, _compute)
    else:
        municipios, total_uf = _compute()
    return JsonResponse({
        "uf": sigla,
        "uf_label": municipios_lookup.uf_label(sigla),
        "total": total_uf,
        "municipios": municipios,
    })


@require_GET
def dashboard_data(request, key: str):
    dash = analytics.get_dashboard(key)
    if dash is None:
        return JsonResponse({"error": f"Unknown dashboard '{key}'"}, status=404)

    filter_form = DashboardFilterForm(request.GET or None)
    filters = filter_form.to_filters() if request.GET else {}

    def _compute():
        return dash["fn"](filters=filters)

    payload = agg_cache.cached(f"dash:{key}", filters, _compute) if analytics.caching_enabled() else _compute()
    response = {
        "key": dash["key"],
        "title": dash["title"],
        "chart": dash["chart"],
        "period": analytics.period_label(filters),
        "data": payload,
    }
    if dash.get("subtitle"):
        response["subtitle"] = dash["subtitle"]
    return JsonResponse(response)
