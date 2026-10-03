"""Template tags used by the chat thread UI."""
from __future__ import annotations

import html
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def render_markdown(text) -> str:
    """Render assistant prose as safe HTML (tables, lists, headers, code).

    Escapa `<`/`>`/`&` do texto ANTES do markdown: a lib `markdown` deixa HTML
    cru passar, então uma resposta que contivesse `<div>`/`<h1>` injetaria
    elementos reais e QUEBRAVA o layout do chat. Escapar preserva a formatação
    markdown (negrito, listas, tabelas) sem permitir HTML bruto.
    """
    import markdown as md  # lazy
    if not text:
        return ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_out = md.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    # Limit header sizes: h1/h2/h3 → h4/h5/h6 (consistent com o resto da UI)
    return mark_safe(html_out
        .replace("<h1>", "<h4>").replace("</h1>", "</h4>")
        .replace("<h2>", "<h5>").replace("</h2>", "</h5>")
        .replace("<h3>", "<h6>").replace("</h3>", "</h6>"))


@register.filter
def json_attr(value) -> str:
    """Serialise to JSON and escape for safe use inside an HTML attribute.

    Use as: <canvas data-payload="{{ obj|json_attr }}">
    """
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = "null"
    # Escape quote characters etc. for HTML attribute context.
    return mark_safe(html.escape(text, quote=True))


@register.filter
def jsonpretty(value, max_chars: int = 4000) -> str:
    """Render any JSON-serialisable value as a pretty string.

    Truncates very long payloads at `max_chars` so the thread doesn't break
    when a tool returns a multi-megabyte result.
    """
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [truncado em {max_chars} chars]"
    return text


@register.filter
def wape_grade(wape) -> dict:
    """Classifica a acurácia de um forecast com base no WAPE.

    Retorna {label, level, color} — usado nos badges.
    WAPE = Weighted Absolute Percentage Error (sum|err|/sum|y|).
    """
    try:
        w = float(wape)
    except (TypeError, ValueError):
        return {"label": "—", "level": "n/a", "color": "muted"}
    if w != w:  # NaN
        return {"label": "—", "level": "n/a", "color": "muted"}
    if w < 10:
        return {"label": f"alta · WAPE {w:.1f}%", "level": "alta", "color": "success"}
    if w < 25:
        return {"label": f"boa · WAPE {w:.1f}%", "level": "boa", "color": "accent"}
    if w < 50:
        return {"label": f"média · WAPE {w:.1f}%", "level": "media", "color": "warning"}
    return {"label": f"baixa · WAPE {w:.1f}%", "level": "baixa", "color": "danger"}


@register.filter
def tool_label(name: str) -> str:
    """Human-readable label for tool icon row."""
    return {
        "consultar": "Consultar (ORM)",
        "contar": "Contar (ORM)",
        "serie_temporal": "Série temporal (ORM)",
        "previsao_automatica": "Previsão automática (comitê)",
        "resolver_municipio": "Resolver município (IBGE)",
        "list_saved_queries": "Listar consultas salvas",
        "list_forecasters": "Listar modelos disponíveis",
        "load_series": "Carregar série (catálogo)",
        "forecast": "Forecast (catálogo)",
        "qa_multiple_choice": "QA múltipla escolha (catálogo)",
        "forecast_from_sql": "Forecast (SQL livre)",
        "qa_from_sql": "QA (SQL livre)",
        "analyze_series": "Analisar série",
        "backtest_forecast": "Backtest de 1 modelo",
        "run_sql": "SQL livre (legado)",
        "peek_table": "Espiar tabela bruta",
    }.get(name, name)


@register.filter
def is_forecast_tool(name: str) -> bool:
    return name in {"previsao_automatica", "forecast", "forecast_from_sql",
                    "backtest_forecast"}
