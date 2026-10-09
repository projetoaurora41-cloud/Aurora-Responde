"""Agregações do mapa coroplético SIPIA-CT.

Duas fontes de dados, escolhidas automaticamente:

1. **PostgreSQL** — se o banco for Postgres e existir a view
   ``sipiact.vw_sipiact_totais`` (mesma fonte do projeto original), os totais
   são lidos diretamente dela (dados reais do SIPIA-CT).
2. **Fallback (modelo)** — caso contrário (ex.: SQLite local), usa o modelo
   ``SipiactTotal``, alimentado pelo dataset agregado embutido.

Em ambos os casos o formato de saída dos endpoints é idêntico, então o
front-end (``mapa_sipiact.js``) não muda.

O SIPIA-CT só chega ao nível estadual — não há detalhamento por município.
"""
from __future__ import annotations

from django.db import connection
from django.db.models import Sum

from painel.services.cache import cached
from .models import SipiactTotal
from .ufs import UF_NOME, to_sigla

SIPIACT_VIEW = "sipiact.vw_sipiact_totais"


def _has_sipiact_view() -> bool:
    """True se estamos em Postgres e a view real do SIPIA-CT existe."""
    if connection.vendor != "postgresql":
        return False
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [SIPIACT_VIEW])
            return cur.fetchone()[0] is not None
    except Exception:  # noqa: BLE001 - qualquer erro → usa fallback
        return False


def usando_dados_reais() -> bool:
    """True quando o mapa lê a fonte oficial (view Postgres), não o dataset embutido."""
    return _has_sipiact_view()


# --------------------------------------------------------------------------- #
# Filtros (indicadores + anos)                                                #
# --------------------------------------------------------------------------- #


def sipiact_filtros() -> dict:
    """Opções de filtro: indicadores e anos distintos presentes na base."""
    if _has_sipiact_view():
        return cached("sipiact_filtros", "all", _sipiact_filtros_view)
    return _sipiact_filtros_model()


def _sipiact_filtros_view() -> dict:
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT DISTINCT indicador FROM {SIPIACT_VIEW} "
            f"WHERE indicador IS NOT NULL ORDER BY 1"
        )
        indicadores = [str(r[0]) for r in cur.fetchall()]
        cur.execute(
            f"SELECT DISTINCT ano FROM {SIPIACT_VIEW} "
            f"WHERE ano IS NOT NULL ORDER BY 1"
        )
        anos = [int(r[0]) for r in cur.fetchall()]
    return {"indicadores": indicadores, "anos": anos}


def _sipiact_filtros_model() -> dict:
    indicadores = list(
        SipiactTotal.objects.values_list("indicador", flat=True)
        .distinct()
        .order_by("indicador")
    )
    anos = sorted(
        {a for a in SipiactTotal.objects.values_list("ano", flat=True).distinct() if a}
    )
    return {"indicadores": indicadores, "anos": anos}


# --------------------------------------------------------------------------- #
# Totais por UF                                                               #
# --------------------------------------------------------------------------- #


def _totals_from_view(indicador: str | None, ano: int | None) -> list[dict]:
    conds, params = [], []
    if indicador:
        conds.append("indicador = %s")
        params.append(indicador)
    if ano:
        conds.append("ano = %s")
        params.append(int(ano))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = f"SELECT uf, SUM(total)::bigint AS total FROM {SIPIACT_VIEW}{where} GROUP BY uf"
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return [{"uf": r[0], "total": r[1]} for r in cur.fetchall()]


def _totals_from_model(indicador: str | None, ano: int | None) -> list[dict]:
    qs = SipiactTotal.objects.all()
    if indicador:
        qs = qs.filter(indicador=indicador)
    if ano:
        qs = qs.filter(ano=ano)
    return list(qs.values("uf").annotate(total=Sum("total")).order_by())


def sipiact_uf_totals(indicador: str | None, ano: int | None) -> dict:
    """Totais por UF (sigla) para um indicador SIPIA-CT, opcionalmente por ano."""
    view = _has_sipiact_view()

    def _compute():
        rows = (
            _totals_from_view(indicador, ano)
            if view
            else _totals_from_model(indicador, ano)
        )
        totals: dict[str, int] = {}
        grand = 0
        for r in rows:
            sigla = to_sigla(r["uf"])
            if sigla not in UF_NOME:  # ignora linhas agregadas (ex.: 'Brasil')
                continue
            t = int(r["total"] or 0)
            totals[sigla] = totals.get(sigla, 0) + t
            grand += t
        return {"indicador": indicador, "ano": ano, "grand": grand, "totals": totals}

    if view:
        return cached("sipiact_uf", {"i": indicador, "a": ano}, _compute)
    return _compute()
