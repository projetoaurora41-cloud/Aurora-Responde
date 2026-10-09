"""Analytics queries that power the Aurora dashboards.

Each public function returns a JSON-serialisable dict ready to feed Chart.js.
Filters are applied uniformly via :func:`apply_filters` so the front-end can
drive every dashboard from one shared filter form.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from django.db import connection
from django.db.models import CharField, Count, IntegerField, Q
from django.db.models.functions import Cast, Coalesce, Substr

from painel.models import ViolbrExterno, ViolenceNotification
from painel.services import municipios as municipios_lookup

# --------------------------------------------------------------------------- #
# Fonte de dados VIOLBR                                                        #
# --------------------------------------------------------------------------- #

# A disponibilidade da tabela externa não muda durante a vida do processo, mas
# depende do banco/alias — cacheamos por alias de conexão.
_external_violbr_cache: dict[str, bool] = {}


def _external_violbr_available() -> bool:
    """True se o PostgreSQL atual expõe a tabela bruta ``sinan.VIOLBR``."""
    if connection.vendor != "postgresql":
        return False
    alias = connection.alias
    if alias not in _external_violbr_cache:
        try:
            with connection.cursor() as cur:
                cur.execute('SELECT to_regclass(%s)', ['sinan."VIOLBR"'])
                _external_violbr_cache[alias] = cur.fetchone()[0] is not None
        except Exception:  # noqa: BLE001 - qualquer falha → usa tabela própria
            _external_violbr_cache[alias] = False
    return _external_violbr_cache[alias]


def violbr_model():
    """Modelo que respalda as leituras VIOLBR.

    No PostgreSQL com ``sinan.VIOLBR`` presente, usa o modelo *não gerenciado*
    :class:`~core.models.ViolbrExterno` (dados reais, como o projeto original).
    Caso contrário (SQLite local, banco de teste, upload manual), usa a tabela
    própria :class:`~core.models.ViolenceNotification`.
    """
    return ViolbrExterno if _external_violbr_available() else ViolenceNotification


def caching_enabled() -> bool:
    """Só cacheia agregações quando lemos a tabela externa massiva (Postgres).

    Com a tabela local/SQLite (testes, uploads) os dados mudam e a consulta é
    barata, então o cache é dispensável (e atrapalharia os testes).
    """
    return _external_violbr_available()

# --------------------------------------------------------------------------- #
# Filter handling                                                             #
# --------------------------------------------------------------------------- #

# Maps incoming filter keys to the model field they constrain. Multi-value
# filters (lists) are translated to ``__in`` lookups automatically.
_DIRECT_FILTERS: dict[str, str] = {
    "uf": "SG_UF_OCOR",
    "municipio": "ID_MN_OCOR",
    "ano": "NU_ANO",
    "sexo": "CS_SEXO",
}

# Marker filters use the SINAN convention ``'1' = Sim``.
_MARKER_FILTERS: dict[str, str] = {
    "viol_sexu": "VIOL_SEXU",
    "viol_traf": "VIOL_TRAF",
    "viol_fisic": "VIOL_FISIC",
    "viol_psico": "VIOL_PSICO",
    "viol_negli": "VIOL_NEGLI",
    "sex_explo": "SEX_EXPLO",
    "sex_estupr": "SEX_ESTUPR",
    "sex_assedi": "SEX_ASSEDI",
    "sex_porno": "SEX_PORNO",
}


def base_queryset():
    """Notifications restricted to children/adolescents (0–17 years).

    Reads from the external ``sinan.VIOLBR`` table when available (PostgreSQL),
    otherwise from the uploaded :class:`ViolenceNotification` table. Both expose
    the same field names, so the rest of this module is backend-agnostic.
    """
    qs = violbr_model().objects.all()
    # NU_IDADE_N follows the SINAN unit-prefixed encoding: <4000 = under 1 year,
    # 4000–4017 = 0–17 years. Keep records without a parseable age so the
    # dashboards still surface them when no demographic filter is applied.
    return qs.exclude(NU_IDADE_N="")


def apply_filters(qs, filters: dict[str, Any] | None):
    if not filters:
        return qs

    for key, field in _DIRECT_FILTERS.items():
        value = filters.get(key)
        if value in (None, "", []):
            continue
        if key == "uf":
            # Match the UF whether the source stored "SE" or "28".
            candidates = municipios_lookup.uf_candidates(value)
            qs = qs.filter(**{f"{field}__in": candidates}) if candidates else qs
            continue
        if isinstance(value, (list, tuple)):
            qs = qs.filter(**{f"{field}__in": list(value)})
        else:
            qs = qs.filter(**{field: value})

    for key, field in _MARKER_FILTERS.items():
        if filters.get(key):
            qs = qs.filter(**{field: "1"})

    ano_inicio = filters.get("ano_inicio")
    ano_fim = filters.get("ano_fim")
    if ano_inicio:
        qs = qs.filter(NU_ANO__gte=str(ano_inicio))
    if ano_fim:
        qs = qs.filter(NU_ANO__lte=str(ano_fim))

    faixa = filters.get("faixa_etaria")
    if faixa:
        qs = _filter_age_band(qs, faixa)

    return qs


def period_label(filters: dict[str, Any] | None = None) -> str:
    """Texto amigável do período analítico (filtros ou anos da base)."""
    filters = filters or {}
    ai = str(filters.get("ano_inicio") or "").strip()
    af = str(filters.get("ano_fim") or "").strip()
    if ai and af:
        return f"Período: {ai}" if ai == af else f"Período: {ai}–{af}"
    if ai:
        return f"Período: a partir de {ai}"
    if af:
        return f"Período: até {af}"

    years = sorted(
        a
        for a in violbr_model()
        .objects.exclude(NU_ANO="")
        .values_list("NU_ANO", flat=True)
        .distinct()
        if a and str(a).isdigit()
    )
    if not years:
        return "Período: não disponível"
    lo, hi = years[0], years[-1]
    return f"Período: {lo}" if lo == hi else f"Período: {lo}–{hi}"


def _filter_age_band(qs, band: str):
    # NU_IDADE_N values are 4-digit strings; for the 4xxx range the last two
    # digits encode the age in years.
    bands = {
        "00-04": ("4000", "4004"),
        "05-09": ("4005", "4009"),
        "10-13": ("4010", "4013"),
        "14-17": ("4014", "4017"),
    }
    if band not in bands:
        return qs
    lo, hi = bands[band]
    return qs.filter(NU_IDADE_N__gte=lo, NU_IDADE_N__lte=hi)


# Convenient aggregate templates ------------------------------------------- #

VIOLENCE_AGGREGATES: dict[str, Q] = {
    "violencia_sexual": Q(VIOL_SEXU="1"),
    "trafico": Q(VIOL_TRAF="1"),
    "exploracao_sexual": Q(SEX_EXPLO="1"),
    "violencia_fisica": Q(VIOL_FISIC="1"),
    "violencia_psicologica": Q(VIOL_PSICO="1"),
    "tortura": Q(VIOL_TORT="1"),
    "violencia_financeira": Q(VIOL_FINAN="1"),
    "negligencia": Q(VIOL_NEGLI="1"),
    "trabalho_infantil": Q(VIOL_INFAN="1"),
    "intervencao_legal": Q(VIOL_LEGAL="1"),
    "outras": Q(VIOL_OUTR="1"),
}


def _violence_count_kwargs() -> dict[str, Count]:
    return {key: Count("id", filter=q) for key, q in VIOLENCE_AGGREGATES.items()}


def _municipio_label(codigo: str, uf_raw: str = "") -> str:
    """Rótulo amigável no formato ``São Paulo (SP)``.

    Usa a tabela IBGE embarcada. Se o código não for encontrado, cai para o
    código original acompanhado da sigla da UF (quando disponível).
    """
    info = municipios_lookup.lookup(codigo)
    if info:
        return municipios_lookup.label(codigo, with_uf=True)
    sigla = municipios_lookup.uf_sigla(uf_raw)
    return f"{codigo} ({sigla})" if sigla else codigo


# --------------------------------------------------------------------------- #
# Dashboard 1 — Mapa coroplético por UF                                       #
# --------------------------------------------------------------------------- #


def dashboard_uf_map(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters).exclude(SG_UF_OCOR="")
    raw = list(
        qs.values("SG_UF_OCOR")
        .annotate(total=Count("id"), **_violence_count_kwargs())
        .order_by("-total")
    )
    # Unifica códigos IBGE numéricos ("35") e siglas ("SP") na mesma UF.
    metric_keys = ["total", *VIOLENCE_AGGREGATES.keys()]
    merged: dict[str, dict[str, Any]] = {}
    for r in raw:
        sigla = municipios_lookup.uf_sigla(r["SG_UF_OCOR"]) or r["SG_UF_OCOR"]
        if sigla not in merged:
            merged[sigla] = {"SG_UF_OCOR": sigla, **{k: 0 for k in metric_keys}}
        for k in metric_keys:
            merged[sigla][k] += r.get(k) or 0
    rows = sorted(merged.values(), key=lambda r: r["total"], reverse=True)
    return {
        "labels": [r["SG_UF_OCOR"] for r in rows],
        "rows": [_normalize_row(r, key="SG_UF_OCOR", label="uf") for r in rows],
        "datasets": _violence_datasets(rows),
    }


# --------------------------------------------------------------------------- #
# Dashboard 2 — Ranking de municípios                                         #
# --------------------------------------------------------------------------- #


def dashboard_municipality_ranking(filters=None, limit: int = 25) -> dict[str, Any]:
    qs = (
        apply_filters(base_queryset(), filters)
        .exclude(ID_MN_OCOR="")
        .values("SG_UF_OCOR", "ID_MN_OCOR")
        .annotate(total=Count("id"), **_violence_count_kwargs())
        .order_by("-total")[:limit]
    )
    rows = list(qs)
    return {
        "labels": [_municipio_label(r["ID_MN_OCOR"], r["SG_UF_OCOR"]) for r in rows],
        "rows": rows,
        "datasets": _violence_datasets(rows),
    }


# --------------------------------------------------------------------------- #
# Dashboard 3 — Série temporal mensal                                          #
# --------------------------------------------------------------------------- #


def dashboard_monthly_series(filters=None) -> dict[str, Any]:
    # DT_NOTIFIC é uma data ISO ('AAAA-MM-DD') tanto na tabela externa
    # sinan.VIOLBR (texto) quanto no SQLite (data armazenada como texto ISO),
    # então agrupar pelo prefixo 'AAAA-MM' funciona nos dois backends — e evita
    # ``date_trunc`` sobre coluna de texto, que quebraria no PostgreSQL.
    qs = (
        apply_filters(base_queryset(), filters)
        .exclude(DT_NOTIFIC__isnull=True)
        # Cast garante texto tanto para o CharField externo quanto para o
        # DateField local (SQLite guarda datas como texto ISO), então Substr(1,7)
        # devolve 'AAAA-MM' nos dois casos.
        .annotate(mes=Substr(Cast("DT_NOTIFIC", output_field=CharField()), 1, 7))
        .values("mes")
        .annotate(
            total=Count("id"),
            violencia_sexual=Count("id", filter=Q(VIOL_SEXU="1")),
            trafico=Count("id", filter=Q(VIOL_TRAF="1")),
            exploracao_sexual=Count("id", filter=Q(SEX_EXPLO="1")),
        )
        .order_by("mes")
    )
    rows = [r for r in qs if r["mes"] and len(r["mes"]) == 7]
    labels = [r["mes"] for r in rows]
    return {
        "labels": labels,
        "rows": [
            {
                "mes": r["mes"],
                "total": r["total"],
                "violencia_sexual": r["violencia_sexual"],
                "trafico": r["trafico"],
                "exploracao_sexual": r["exploracao_sexual"],
            }
            for r in rows
        ],
        "datasets": [
            {"label": "Violência sexual", "data": [r["violencia_sexual"] for r in rows]},
            {"label": "Tráfico", "data": [r["trafico"] for r in rows]},
            {"label": "Exploração sexual", "data": [r["exploracao_sexual"] for r in rows]},
        ],
    }


# --------------------------------------------------------------------------- #
# Dashboard 4 — Subtipos de violência sexual                                   #
# --------------------------------------------------------------------------- #


def dashboard_sexual_subtypes(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters).filter(VIOL_SEXU="1")
    aggregates = qs.aggregate(
        assedio=Count("id", filter=Q(SEX_ASSEDI="1")),
        estupro=Count("id", filter=Q(SEX_ESTUPR="1")),
        pornografia=Count("id", filter=Q(SEX_PORNO="1")),
        exploracao=Count("id", filter=Q(SEX_EXPLO="1")),
        outro=Count("id", filter=Q(SEX_OUTRO="1")),
    )
    pairs = [
        ("Assédio sexual", aggregates["assedio"]),
        ("Estupro", aggregates["estupro"]),
        ("Pornografia infantil", aggregates["pornografia"]),
        ("Exploração sexual", aggregates["exploracao"]),
        ("Outro", aggregates["outro"]),
    ]
    pairs.sort(key=lambda p: p[1], reverse=True)
    return {
        "labels": [p[0] for p in pairs],
        "datasets": [{"label": "Casos", "data": [p[1] for p in pairs]}],
        "rows": [{"subtipo": label, "total": value} for label, value in pairs],
    }


# --------------------------------------------------------------------------- #
# Dashboard 5A — Encaminhamentos da rede de proteção                           #
# --------------------------------------------------------------------------- #


_ENC_LABELS: list[tuple[str, str]] = [
    ("ENC_SAUDE", "Rede da Saúde"),
    ("ASSIST_SOC", "Assistência Social"),
    ("REDE_EDUCA", "Educação"),
    ("ATEND_MULH", "Atendimento à Mulher"),
    ("CONS_TUTEL", "Conselho Tutelar"),
    ("DIR_HUMAN", "Centro de Referência DH"),
    ("MPU", "Ministério Público"),
    ("DELEG_CRIA", "Delegacia Criança/Adolescente"),
    ("DELEG_MULH", "Delegacia da Mulher"),
    ("DELEG", "Outras delegacias"),
    ("INFAN_JUV", "Justiça Infância e Juventude"),
    ("DEFEN_PUBL", "Defensoria Pública"),
]


def dashboard_protection_network(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)
    aggregates = qs.aggregate(
        **{field: Count("id", filter=Q(**{field: "1"})) for field, _ in _ENC_LABELS}
    )
    pairs = [(label, aggregates[field]) for field, label in _ENC_LABELS]
    pairs.sort(key=lambda p: p[1], reverse=True)
    return {
        "labels": [p[0] for p in pairs],
        "datasets": [{"label": "Encaminhamentos", "data": [p[1] for p in pairs]}],
        "rows": [{"encaminhamento": label, "total": value} for label, value in pairs],
    }


# --------------------------------------------------------------------------- #
# Dashboard 5B — Encaminhamentos por tipo de violência                         #
# --------------------------------------------------------------------------- #


_VIOL_TYPE_GROUPS: list[tuple[str, str]] = [
    ("VIOL_SEXU", "Sexual"),
    ("VIOL_TRAF", "Tráfico"),
    ("VIOL_FISIC", "Física"),
    ("VIOL_PSICO", "Psicológica"),
    ("VIOL_NEGLI", "Negligência"),
    ("VIOL_TORT", "Tortura"),
    ("VIOL_INFAN", "Trabalho infantil"),
]


def dashboard_protection_by_violence(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)
    enc_fields = [f for f, _ in _ENC_LABELS]
    matrix: list[dict[str, Any]] = []
    for viol_field, viol_label in _VIOL_TYPE_GROUPS:
        sub = qs.filter(**{viol_field: "1"})
        agg = sub.aggregate(
            **{
                enc: Count("id", filter=Q(**{enc: "1"}))
                for enc in enc_fields
            }
        )
        matrix.append({"tipo_violencia": viol_label, **agg})
    return {
        "labels": [m["tipo_violencia"] for m in matrix],
        "datasets": [
            {"label": label, "data": [row[field] for row in matrix]}
            for field, label in _ENC_LABELS
        ],
        "rows": matrix,
    }


# --------------------------------------------------------------------------- #
# Dashboard 6 — Barras empilhadas por tipo de violência                        #
# --------------------------------------------------------------------------- #


def dashboard_violence_types(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters).exclude(NU_ANO="")
    rows = (
        qs.values("NU_ANO")
        .annotate(
            fisica=Count("id", filter=Q(VIOL_FISIC="1")),
            psicologica=Count("id", filter=Q(VIOL_PSICO="1")),
            tortura=Count("id", filter=Q(VIOL_TORT="1")),
            sexual=Count("id", filter=Q(VIOL_SEXU="1")),
            trafico=Count("id", filter=Q(VIOL_TRAF="1")),
            negligencia=Count("id", filter=Q(VIOL_NEGLI="1")),
            trabalho_infantil=Count("id", filter=Q(VIOL_INFAN="1")),
            outras=Count("id", filter=Q(VIOL_OUTR="1")),
        )
        .order_by("NU_ANO")
    )
    rows = list(rows)
    labels = [r["NU_ANO"] for r in rows]
    keys = [
        ("Física", "fisica"),
        ("Psicológica", "psicologica"),
        ("Tortura", "tortura"),
        ("Sexual", "sexual"),
        ("Tráfico", "trafico"),
        ("Negligência", "negligencia"),
        ("Trabalho infantil", "trabalho_infantil"),
        ("Outras", "outras"),
    ]
    return {
        "labels": labels,
        "datasets": [{"label": label, "data": [r[k] for r in rows]} for label, k in keys],
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Dashboard 7 — Pirâmide etária                                                #
# --------------------------------------------------------------------------- #


_AGE_BANDS = (
    ("00-04", "4000", "4004"),
    ("05-09", "4005", "4009"),
    ("10-13", "4010", "4013"),
    ("14-17", "4014", "4017"),
)


def dashboard_age_pyramid(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)
    rows = []
    for band, lo, hi in _AGE_BANDS:
        sub = qs.filter(NU_IDADE_N__gte=lo, NU_IDADE_N__lte=hi)
        agg_m = sub.filter(CS_SEXO="M").count()
        agg_f = sub.filter(CS_SEXO="F").count()
        rows.append({"faixa_etaria": band, "masculino": agg_m, "feminino": agg_f})
    return {
        "labels": [r["faixa_etaria"] for r in rows],
        "datasets": [
            {"label": "Masculino", "data": [-r["masculino"] for r in rows]},
            {"label": "Feminino", "data": [r["feminino"] for r in rows]},
        ],
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# Dashboard 8 — Perfil das vítimas                                             #
# --------------------------------------------------------------------------- #


_RACA_LABELS = {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena"}
_SEXO_LABELS = {"M": "Masculino", "F": "Feminino", "I": "Ignorado"}
_ESCOL_LABELS = {
    "00": "Analfabeto",
    "01": "1ª-4ª incompleto",
    "02": "4ª completo",
    "03": "5ª-8ª incompleto",
    "04": "Fundamental completo",
    "05": "Médio incompleto",
    "06": "Médio completo",
    "07": "Superior incompleto",
    "08": "Superior completo",
    "09": "Ignorado",
    "10": "Não se aplica",
}


def dashboard_victim_profile(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)

    raca_rows = (
        qs.values("CS_RACA").annotate(total=Count("id")).order_by("-total")
    )
    sexo_rows = (
        qs.values("CS_SEXO").annotate(total=Count("id")).order_by("-total")
    )
    escol_rows = (
        qs.values("CS_ESCOL_N").annotate(total=Count("id")).order_by("-total")
    )

    return {
        "raca": {
            "labels": [_RACA_LABELS.get(r["CS_RACA"] or "", "Ignorada") for r in raca_rows],
            "data": [r["total"] for r in raca_rows],
        },
        "sexo": {
            "labels": [_SEXO_LABELS.get(r["CS_SEXO"] or "", "Ignorado") for r in sexo_rows],
            "data": [r["total"] for r in sexo_rows],
        },
        "escolaridade": {
            "labels": [_ESCOL_LABELS.get(r["CS_ESCOL_N"] or "", "Ignorada") for r in escol_rows],
            "data": [r["total"] for r in escol_rows],
        },
    }


# --------------------------------------------------------------------------- #
# Dashboard 9 — Local de ocorrência                                            #
# --------------------------------------------------------------------------- #


_LOCAL_LABELS = {
    "01": "Residência",
    "02": "Habitação coletiva",
    "03": "Escola",
    "04": "Local esportivo",
    "05": "Bar ou similar",
    "06": "Via pública",
    "07": "Comércio/Serviços",
    "08": "Indústria/Construção",
    "09": "Outro",
    "99": "Ignorado",
}


def _classify_hour(hora: str) -> str:
    if not hora:
        return "Sem registro"
    digits = "".join(ch for ch in hora if ch.isdigit())
    if len(digits) < 2:
        return "Sem registro"
    try:
        h = int(digits[:2])
    except ValueError:
        return "Sem registro"
    if 0 <= h <= 5:
        return "00-05 (madrugada)"
    if 6 <= h <= 11:
        return "06-11 (manhã)"
    if 12 <= h <= 17:
        return "12-17 (tarde)"
    if 18 <= h <= 23:
        return "18-23 (noite)"
    return "Sem registro"


def dashboard_occurrence_context(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)

    by_local = (
        qs.values("LOCAL_OCOR").annotate(total=Count("id")).order_by("-total")
    )
    local_rows = [
        {
            "local": _LOCAL_LABELS.get(r["LOCAL_OCOR"] or "", "Ignorado"),
            "total": r["total"],
        }
        for r in by_local
    ]

    hour_buckets: dict[str, int] = OrderedDict(
        (k, 0)
        for k in (
            "00-05 (madrugada)",
            "06-11 (manhã)",
            "12-17 (tarde)",
            "18-23 (noite)",
            "Sem registro",
        )
    )
    for row in qs.values_list("HORA_OCOR", flat=True):
        hour_buckets[_classify_hour(row or "")] += 1

    return {
        "local": {
            "labels": [r["local"] for r in local_rows],
            "data": [r["total"] for r in local_rows],
            "rows": local_rows,
        },
        "horario": {
            "labels": list(hour_buckets.keys()),
            "data": list(hour_buckets.values()),
        },
    }


# --------------------------------------------------------------------------- #
# Dashboard 10 — Concentração por local de ocorrência                          #
# --------------------------------------------------------------------------- #


def dashboard_heatmap_by_local(filters=None) -> dict[str, Any]:
    qs = apply_filters(base_queryset(), filters)
    rows = (
        qs.values("LOCAL_OCOR")
        .annotate(
            total=Count("id"),
            violencia_sexual=Count("id", filter=Q(VIOL_SEXU="1")),
            exploracao_sexual=Count("id", filter=Q(SEX_EXPLO="1")),
        )
        .order_by("-total")
    )
    rows = list(rows)
    return {
        "labels": [_LOCAL_LABELS.get(r["LOCAL_OCOR"] or "", "Ignorado") for r in rows],
        "datasets": [
            {"label": "Total", "data": [r["total"] for r in rows]},
            {"label": "Violência sexual", "data": [r["violencia_sexual"] for r in rows]},
            {"label": "Exploração sexual", "data": [r["exploracao_sexual"] for r in rows]},
        ],
        "rows": [
            {
                "local": _LOCAL_LABELS.get(r["LOCAL_OCOR"] or "", "Ignorado"),
                **{k: v for k, v in r.items() if k != "LOCAL_OCOR"},
            }
            for r in rows
        ],
    }


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _violence_datasets(rows) -> list[dict[str, Any]]:
    return [
        {"label": "Total", "data": [r["total"] for r in rows]},
        {"label": "Violência sexual", "data": [r["violencia_sexual"] for r in rows]},
        {"label": "Tráfico", "data": [r["trafico"] for r in rows]},
        {"label": "Exploração sexual", "data": [r["exploracao_sexual"] for r in rows]},
    ]


def _normalize_row(row, *, key: str, label: str) -> dict[str, Any]:
    out = {label: row[key]}
    out.update({k: v for k, v in row.items() if k != key})
    return out


# --------------------------------------------------------------------------- #
# KPIs de destaque (cartões do topo do painel)                                #
# --------------------------------------------------------------------------- #


def overview_kpis(filters=None) -> dict[str, int]:
    """Indicadores-resumo exibidos como cartões no topo dos dashboards."""
    qs = apply_filters(base_queryset(), filters)
    agg = qs.aggregate(
        total=Count("id"),
        violencia_sexual=Count("id", filter=Q(VIOL_SEXU="1")),
        exploracao_sexual=Count("id", filter=Q(SEX_EXPLO="1")),
    )
    municipios = (
        qs.exclude(ID_MN_OCOR="").values("ID_MN_OCOR").distinct().count()
    )
    return {
        "total": agg["total"] or 0,
        "violencia_sexual": agg["violencia_sexual"] or 0,
        "exploracao_sexual": agg["exploracao_sexual"] or 0,
        "municipios": municipios,
    }


# --------------------------------------------------------------------------- #
# Catalogue used by views/templates to render every dashboard uniformly.       #
# --------------------------------------------------------------------------- #

DASHBOARDS: list[dict[str, Any]] = [
    {
        "key": "uf_map",
        "title": "Notificações por UF",
        "priority": "Alta",
        "chart": "bar",
        "fn": dashboard_uf_map,
    },
    {
        "key": "municipality_ranking",
        "title": "Ranking de Municípios",
        "priority": "Alta",
        "chart": "bar",
        "fn": dashboard_municipality_ranking,
    },
    {
        "key": "monthly_series",
        "title": "Distribuição Mensal",
        "priority": "Alta",
        "chart": "line",
        "fn": dashboard_monthly_series,
    },
    {
        "key": "sexual_subtypes",
        "title": "Tipos de Violência",
        "priority": "Alta",
        "chart": "bar",
        "fn": dashboard_sexual_subtypes,
    },
    {
        "key": "protection_network",
        "title": "Encaminhamentos por Rede de Proteção",
        "priority": "Alta",
        "subtitle": "Resposta institucional acionada após a notificação.",
        "chart": "bar",
        "fn": dashboard_protection_network,
    },
    {
        "key": "protection_by_violence",
        "title": "Encaminhamentos por Tipo de Violência",
        "priority": "Alta",
        "subtitle": "Cobertura institucional cruzada com tipo de violência.",
        "chart": "stacked",
        "fn": dashboard_protection_by_violence,
    },
    {
        "key": "violence_types",
        "title": "Tipos de Violência por Ano",
        "priority": "Alta",
        "chart": "stacked",
        "fn": dashboard_violence_types,
    },
    {
        "key": "age_pyramid",
        "title": "Faixa Etária",
        "priority": "Média",
        "chart": "pyramid",
        "fn": dashboard_age_pyramid,
    },
    {
        "key": "victim_profile",
        "title": "Perfil das Vítimas",
        "priority": "Média",
        "chart": "multi",
        "fn": dashboard_victim_profile,
    },
    {
        "key": "heatmap_by_local",
        "title": "Notificações por Local de Ocorrência",
        "priority": "Média",
        "chart": "bar",
        "fn": dashboard_heatmap_by_local,
    },
]


def get_dashboard(key: str) -> dict[str, Any] | None:
    for d in DASHBOARDS:
        if d["key"] == key:
            return d
    return None
