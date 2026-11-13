"""Consultas SINAN do Aurora Responde lidas da MESMA fonte do Painel.

Antes, o assistente contava a tabela ``sinam.Notificacao`` (ETL próprio, UF de
residência, ano da data de notificação, só até 2024) enquanto o Painel lê
``sinan.VIOLBR`` (UF/município de ocorrência, ``NU_ANO``, 2020–2025). Os
números divergiam para o mesmo filtro (ex.: São Paulo 33.586 x 32.821).

Este módulo traduz os filtros do roteador para os do Painel e usa
``painel.services.analytics`` — assim assistente e Painel devolvem o mesmo
número para o mesmo recorte.
"""
from __future__ import annotations

from typing import Any

from django.db.models import CharField, Count
from django.db.models.functions import Cast, Substr

# Filtros de tipo de violência do roteador -> coluna SINAN (marcador '1' = Sim).
VIOL_COLS: dict[str, str] = {
    "violencia_sexual": "VIOL_SEXU",
    "violencia_fisica": "VIOL_FISIC",
    "violencia_psicologica": "VIOL_PSICO",
    "tortura": "VIOL_TORT",
    "negligencia": "VIOL_NEGLI",
    "trafico_pessoas": "VIOL_TRAF",
    "violencia_financeira": "VIOL_FINAN",
    "violencia_infantil": "VIOL_INFAN",   # trabalho infantil no SINAN
    "intervencao_legal": "VIOL_LEGAL",
    "outras_violencias": "VIOL_OUTR",
    "exploracao_sexual": "SEX_EXPLO",
}

VIOL_ROTULO: dict[str, str] = {
    "violencia_sexual": "violência sexual",
    "violencia_fisica": "violência física",
    "violencia_psicologica": "violência psicológica",
    "tortura": "tortura",
    "negligencia": "negligência/abandono",
    "trafico_pessoas": "tráfico de pessoas",
    "violencia_financeira": "violência financeira",
    "violencia_infantil": "trabalho infantil",
    "intervencao_legal": "intervenção legal",
    "outras_violencias": "outras violências",
    "exploracao_sexual": "exploração sexual",
}


def _an():
    from painel.services import analytics
    return analytics


def _cached(prefix: str, params: Any, fn):
    an = _an()
    if an.caching_enabled():
        from painel.services.cache import cached
        return cached(f"ar:{prefix}", params, fn)
    return fn()


def painel_filters(filters: dict | None) -> dict:
    """Filtros do roteador (uf, municipio_codigo, ano, ano__gte/lte, sexo) ->
    filtros do Painel (uf, municipio, ano, ano_inicio, ano_fim, sexo)."""
    f = dict(filters or {})
    out: dict[str, Any] = {}
    if f.get("uf"):
        out["uf"] = str(f["uf"]).strip().upper()
    mc = str(f.get("municipio_codigo") or "").strip()
    if mc:
        out["municipio"] = mc[:6]
    if f.get("ano"):
        out["ano"] = str(f["ano"])
    if f.get("ano__gte"):
        out["ano_inicio"] = str(f["ano__gte"])
    if f.get("ano__lte"):
        out["ano_fim"] = str(f["ano__lte"])
    if f.get("sexo"):
        out["sexo"] = str(f["sexo"]).upper()[:1]
    return out


def violencias(filters: dict | None) -> list[str]:
    return [k for k in VIOL_COLS if (filters or {}).get(k)]


def queryset(filters: dict | None):
    an = _an()
    qs = an.apply_filters(an.base_queryset(), painel_filters(filters))
    for k in violencias(filters):
        qs = qs.filter(**{VIOL_COLS[k]: "1"})
    return qs


def _key(filters: dict | None) -> dict:
    return {k: v for k, v in sorted((filters or {}).items()) if v not in (None, "", False)}


def por_ano(filters: dict | None) -> list[dict]:
    def _c():
        rows = (queryset(filters).exclude(NU_ANO="")
                .values("NU_ANO").annotate(n=Count("id")).order_by("NU_ANO"))
        out = []
        for r in rows:
            a = str(r["NU_ANO"] or "").strip()
            if a.isdigit():
                out.append({"ano": int(a), "n": int(r["n"] or 0)})
        return out
    return _cached("por_ano", _key(filters), _c)


def total(filters: dict | None) -> int:
    return _cached("total", _key(filters), lambda: queryset(filters).count())


def serie_mensal(filters: dict | None) -> list[dict]:
    def _c():
        rows = (queryset(filters).exclude(DT_NOTIFIC__isnull=True)
                .annotate(mes=Substr(Cast("DT_NOTIFIC", output_field=CharField()), 1, 7))
                .values("mes").annotate(n=Count("id")).order_by("mes"))
        return [{"mes": r["mes"], "n": int(r["n"] or 0)}
                for r in rows if r["mes"] and len(r["mes"]) == 7]
    return _cached("mensal", _key(filters), _c)


def ano_mais_recente() -> int | None:
    """Último ano presente na base do painel (independe do filtro)."""
    an = _an()
    anos = _cached("anos_base", "all", an.available_years)
    return int(anos[-1]) if anos else None


def nota_preliminar(mensal: list[dict], ultimo_ano: int | None) -> str | None:
    """Aviso quando o último ano da série é o mais recente da base (preliminar)."""
    if not ultimo_ano or ultimo_ano != ano_mais_recente():
        return None
    meses = [m for m in mensal if m["mes"].startswith(str(ultimo_ano))]
    if len(meses) < 4:
        return (f"Os dados de {ultimo_ano} são preliminares e ainda incluem "
                f"poucos meses do ano.")
    ultimo = meses[-1]
    anteriores = [m["n"] for m in meses[-4:-1]]
    media = sum(anteriores) / len(anteriores) if anteriores else 0
    if media and ultimo["n"] < 0.6 * media:
        mes_nome = _MESES.get(ultimo["mes"][5:7], ultimo["mes"])
        return (f"Os dados de {ultimo_ano} são preliminares: {mes_nome} tem "
                f"{br(ultimo['n'])} notificações, contra cerca de {br(media)} por mês "
                f"nos meses anteriores, o que indica registro ainda incompleto.")
    return (f"Os dados de {ultimo_ano} ainda são preliminares e podem mudar "
            f"com as atualizações do SINAN.")


_MESES = {"01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
          "05": "maio", "06": "junho", "07": "julho", "08": "agosto",
          "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro"}


def ranking(filters: dict | None, top: int = 10) -> dict:
    """Top municípios por notificações, sem os códigos de município ignorado."""
    an = _an()

    def _c():
        qs = (queryset(filters).exclude(ID_MN_OCOR="")
              .values("SG_UF_OCOR", "ID_MN_OCOR").annotate(n=Count("id"))
              .order_by("-n"))
        rows, ignorados = [], 0
        for r in qs[: top + 80]:
            if an.municipio_ignorado(r["ID_MN_OCOR"]):
                ignorados += int(r["n"] or 0)
                continue
            if len(rows) < top:
                rows.append({
                    "codigo": r["ID_MN_OCOR"],
                    "nome": an._municipio_label(r["ID_MN_OCOR"], r["SG_UF_OCOR"]),
                    "n": int(r["n"] or 0),
                })
        return {"ranking": rows, "sem_municipio": ignorados}
    return _cached("ranking", {"f": _key(filters), "t": top}, _c)


def perfil(filters: dict | None) -> dict:
    """Perfil das vítimas (sexo, raça/cor) com as categorias já unificadas."""
    an = _an()

    def _c():
        qs = queryset(filters)

        def _agg(field, labels, default):
            acc: dict[str, int] = {}
            for r in qs.values(field).annotate(n=Count("id")):
                lab = labels.get((r[field] or "").strip(), default)
                acc[lab] = acc.get(lab, 0) + int(r["n"] or 0)
            tot = sum(acc.values()) or 1
            return [{"categoria": k, "n": v, "pct": round(100 * v / tot, 1)}
                    for k, v in sorted(acc.items(), key=lambda kv: -kv[1])]
        return {
            "sexo": _agg("CS_SEXO", an._SEXO_LABELS, "Ignorado"),
            "raca": _agg("CS_RACA", an._RACA_LABELS, "Ignorada"),
        }
    return _cached("perfil", _key(filters), _c)


def br(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def pct_br(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")
