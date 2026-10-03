"""Helpers used by the chat tools to query the cleaned `Notificacao` model.

Keeps Django ORM specifics out of `webapp/chat/tools.py` so the same helpers
can be reused by other layers (CLI, scripts, etc.).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from django.db.models import Count, Q

import unicodedata

from .models import Municipio, Notificacao


def _normalize(s: str) -> str:
    nkfd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nkfd if not unicodedata.combining(c)).lower().strip()


def resolver_municipio(nome: str, uf: str | None = None) -> dict:
    """Encontra município pelo nome (com tolerância a acentos/case).

    Retorna {found: bool, codigo, nome, uf, candidates: [...]} ou erro.
    `uf` opcional restringe a busca.
    """
    nome_n = _normalize(nome)
    if not nome_n:
        return {"found": False, "error": "Nome vazio."}
    qs = Municipio.objects.filter(nome_normalizado=nome_n)
    if uf:
        qs = qs.filter(uf=uf.upper())
    exact = list(qs[:5])
    if len(exact) == 1:
        m = exact[0]
        return {"found": True, "codigo": m.codigo, "nome": m.nome, "uf": m.uf}
    if len(exact) > 1:
        # ambiguity (e.g. "Bom Jesus" exists in 11 UFs)
        return {
            "found": False,
            "ambiguous": True,
            "candidates": [{"codigo": m.codigo, "nome": m.nome, "uf": m.uf} for m in exact],
            "hint": "Forneca 'uf' para desambiguar.",
        }
    # Fallback: contains
    qs = Municipio.objects.filter(nome_normalizado__contains=nome_n)
    if uf:
        qs = qs.filter(uf=uf.upper())
    cand = list(qs[:10])
    if not cand:
        return {"found": False, "error": f"Nenhum municipio bate com '{nome}'."}
    return {
        "found": False,
        "ambiguous": True,
        "candidates": [{"codigo": m.codigo, "nome": m.nome, "uf": m.uf} for m in cand],
        "hint": "Multiplos candidatos por busca parcial; refine.",
    }


# Whitelist of filter keys accepted from outside (LLM). Anything else is dropped.
# Each key maps to the Django ORM lookup expression.
ALLOWED_FILTERS: dict[str, str] = {
    # Geography
    "uf":                  "uf",
    "uf_ocorrencia":       "uf_ocorrencia",
    "municipio_codigo":    "municipio_codigo",
    # Person
    "sexo":                "sexo",
    "idade_anos":          "idade_anos",
    "idade_anos__lt":      "idade_anos__lt",
    "idade_anos__lte":     "idade_anos__lte",
    "idade_anos__gt":      "idade_anos__gt",
    "idade_anos__gte":     "idade_anos__gte",
    "faixa_etaria":        "faixa_etaria",
    "raca_cor":            "raca_cor",
    "escolaridade":        "escolaridade",
    # Dates
    "ano":                 "ano",
    "ano__gte":            "ano__gte",
    "ano__lte":            "ano__lte",
    "data_notificacao__gte": "data_notificacao__gte",
    "data_notificacao__lte": "data_notificacao__lte",
    "semana_epi":          "semana_epi",
    # Violences
    "violencia_fisica":      "violencia_fisica",
    "violencia_psicologica": "violencia_psicologica",
    "violencia_sexual":      "violencia_sexual",
    "tortura":               "tortura",
    "trafico_pessoas":       "trafico_pessoas",
    "violencia_financeira":  "violencia_financeira",
    "negligencia":           "negligencia",
    "violencia_infantil":    "violencia_infantil",
    "intervencao_legal":     "intervencao_legal",
    "outras_violencias":     "outras_violencias",
    # Other
    "lesao_autoprovocada":   "lesao_autoprovocada",
    "ocorreu_outras_vezes":  "ocorreu_outras_vezes",
    "local_ocorrencia":      "local_ocorrencia",
    "autor_sexo":            "autor_sexo",
    "autor_alcool":          "autor_alcool",
}

# Fields safe to expose in result rows (no PII, all already aggregated/coded).
RESULT_FIELDS = [
    "id", "data_notificacao", "ano", "uf", "uf_ocorrencia",
    "sexo", "idade_anos", "faixa_etaria", "raca_cor", "escolaridade",
    "municipio_codigo", "local_ocorrencia",
    "violencia_fisica", "violencia_psicologica", "violencia_sexual",
    "tortura", "trafico_pessoas", "negligencia", "violencia_infantil",
    "lesao_autoprovocada", "ocorreu_outras_vezes",
]


def _sanitize_filters(raw: dict | None) -> tuple[dict, list[str], list[str]]:
    """Keep only allowed keys; coerce sigla→sigla, booleans, ints.

    Returns (filters, ignored_keys, notes). `municipio_nome` is resolved here
    into `municipio_codigo` so the caller doesn't need to.

    IMPORTANT: works on a copy of `raw` — never mutates the caller's dict.
    """
    if not raw:
        return {}, [], []
    raw = dict(raw)
    out: dict[str, Any] = {}
    ignored: list[str] = []
    notes: list[str] = []

    # Resolve municipio_nome (+ optional uf hint) → municipio_codigo before the loop.
    # SINAM stores municipality as the 6-digit IBGE code WITHOUT the check digit,
    # so we drop the trailing digit when filtering Notificacao.
    if raw.get("municipio_nome"):
        uf_hint = raw.get("uf") or None
        res = resolver_municipio(str(raw.pop("municipio_nome")), uf_hint)
        if res.get("found"):
            codigo_sinam = res["codigo"][:6]
            out["municipio_codigo"] = codigo_sinam
            notes.append(f"municipio resolvido: {res['nome']}/{res['uf']} "
                         f"(IBGE {res['codigo']} -> SINAM {codigo_sinam})")
        else:
            cands = res.get("candidates", [])
            cand_txt = "; ".join(f"{c['nome']}/{c['uf']}({c['codigo']})" for c in cands[:5])
            notes.append(f"municipio NAO encontrado/ambiguo. Candidatos: {cand_txt}"
                         if cands else f"municipio NAO encontrado: {res.get('error','?')}")
            # leave out — caller sees no rows + the note

    for k, v in raw.items():
        if k not in ALLOWED_FILTERS:
            ignored.append(k); continue
        if isinstance(v, str) and v.lower() in ("true", "false"):
            v = (v.lower() == "true")
        if k.startswith("uf") and isinstance(v, str):
            v = v.strip().upper()
        # SINAM municipio = first 6 digits of IBGE 7d code.
        if k == "municipio_codigo" and isinstance(v, str):
            v = v.strip()
            if len(v) == 7 and v.isdigit():
                v = v[:6]
        out[ALLOWED_FILTERS[k]] = v
    return out, ignored, notes


def query(filters: dict | None, limit: int = 50) -> dict:
    sanitized, ignored, notes = _sanitize_filters(filters)
    qs = Notificacao.objects.filter(**sanitized).order_by("-data_notificacao")
    total = qs.count()
    rows = list(qs.values(*RESULT_FIELDS)[:limit])
    for r in rows:
        if isinstance(r.get("data_notificacao"), date):
            r["data_notificacao"] = r["data_notificacao"].isoformat()
    return {
        "total_rows": total, "shown": len(rows),
        "filters_applied": sanitized, "filters_ignored": ignored,
        "notes": notes, "rows": rows,
    }


def aggregate(filters: dict | None, group_by: str | list[str] | None = None,
              top: int = 20) -> dict:
    sanitized, ignored, notes = _sanitize_filters(filters)
    qs = Notificacao.objects.filter(**sanitized)
    total = qs.count()
    if group_by:
        if isinstance(group_by, str):
            group_by = [group_by]
        safe_fields = {f.name for f in Notificacao._meta.fields}
        group_by = [g for g in group_by if g in safe_fields]
        if not group_by:
            return {"error": f"group_by inválido. Campos válidos: {sorted(safe_fields)}",
                    "filters_applied": sanitized, "notes": notes}
        rows = list(qs.values(*group_by).annotate(n=Count("id"))
                       .order_by("-n")[:top])
        return {"total_rows": total,
                "filters_applied": sanitized, "filters_ignored": ignored,
                "notes": notes, "group_by": group_by, "rows": rows}
    return {"total_rows": total, "filters_applied": sanitized,
            "filters_ignored": ignored, "notes": notes}


def time_series(filters: dict | None, freq: str = "D") -> dict:
    sanitized, ignored, notes = _sanitize_filters(filters)
    qs = (Notificacao.objects.filter(**sanitized)
                            .values("data_notificacao")
                            .annotate(valor=Count("id"))
                            .order_by("data_notificacao"))
    rows = list(qs)
    if not rows:
        return {"total_rows": 0, "n_points": 0,
                "filters_applied": sanitized, "filters_ignored": ignored,
                "notes": notes, "dates": [], "values": []}

    df = pd.DataFrame(rows)
    df["data_notificacao"] = pd.to_datetime(df["data_notificacao"])
    df = df.set_index("data_notificacao").sort_index()

    if freq:
        freq = {"M": "ME", "Q": "QE", "Y": "YE", "A": "YE"}.get(freq, freq)
        df = df["valor"].resample(freq).sum().to_frame()
    else:
        df = df.asfreq("D", fill_value=0)

    return {
        "total_rows": int(df["valor"].sum()),
        "n_points": int(len(df)),
        "filters_applied": sanitized, "filters_ignored": ignored,
        "notes": notes, "freq": freq,
        "dates": [d.date().isoformat() for d in df.index],
        "values": [float(v) for v in df["valor"].to_numpy()],
    }


def series_for_forecast(filters: dict | None, freq: str = "D") -> tuple[np.ndarray, pd.DatetimeIndex, dict]:
    """Compact accessor used by forecasting tools."""
    ts = time_series(filters, freq=freq)
    if not ts["dates"]:
        return np.array([]), pd.DatetimeIndex([]), ts
    idx = pd.DatetimeIndex(pd.to_datetime(ts["dates"]))
    values = np.array(ts["values"], dtype=float)
    return values, idx, ts
