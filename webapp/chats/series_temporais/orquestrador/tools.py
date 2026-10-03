"""Tools exposed to the orchestrator LLM (Ollama tool-calling format).

Every tool:
  - has a JSON schema declared in `TOOLS_SCHEMA` (matches Ollama tool format)
  - is dispatched by `run_tool(name, args, ctx)`
  - returns a small dict that becomes the next `role=tool` message
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sinam import queries as sq
from sinam.models import Notificacao
from src import db

# Versão LEVE (Aurora Responde): o forecasting (torch/chronos) e o catálogo de
# consultas salvas (app `analise`) foram removidos. Mantemos os nomes com
# fallback para o módulo importar e os relatórios ficarem SQL-only.
try:
    from src.analytics import analyze_series, walk_forward_backtest
    from src.series_models import REGISTRY, get as get_forecaster
    _FORECAST = True
except Exception:  # noqa: BLE001
    analyze_series = walk_forward_backtest = None
    REGISTRY = {}
    def get_forecaster(*_a, **_k):
        raise RuntimeError("Forecasting desativado nesta versão leve.")
    _FORECAST = False

try:
    from chats.series_temporais.analise.models import SavedQuery
except Exception:  # noqa: BLE001
    SavedQuery = None


@dataclass
class ToolContext:
    forecaster: str = "chronos2"


# ---------------------------------------------------------------------------
# Schemas (Ollama tool-calling format = OpenAI function tools)
# ---------------------------------------------------------------------------

_FILTER_DOC = (
    "Dicionario de filtros estilo Django ORM. Chaves aceitas:\n"
    " GEO: uf (sigla, ex 'SE'), uf_ocorrencia, municipio_codigo (IBGE 7d),\n"
    "      municipio_nome (texto, ex 'Malhador' -- resolvido automaticamente,\n"
    "      use junto com 'uf' para desambiguar quando ha homonimos).\n"
    " PESSOA: sexo ('M'/'F'/'I'), idade_anos, idade_anos__lt/lte/gt/gte,\n"
    "      faixa_etaria ('< 1 ano'|'1-4'|'5-9'|'10-14'|'15-19'|'20-59'|'60+'),\n"
    "      raca_cor ('Branca'/'Preta'/'Amarela'/'Parda'/'Indigena').\n"
    " DATA: ano (int), ano__gte, ano__lte, data_notificacao__gte/lte (YYYY-MM-DD).\n"
    " VIOLENCIAS (boolean): violencia_fisica, violencia_psicologica,\n"
    "      violencia_sexual, tortura, trafico_pessoas, violencia_financeira,\n"
    "      negligencia, violencia_infantil, intervencao_legal, outras_violencias.\n"
    " OUTROS: lesao_autoprovocada, ocorreu_outras_vezes, local_ocorrencia,\n"
    "      autor_sexo ('M'/'F'/'I'), autor_alcool."
)

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "consultar",
            "description": (
                "[ORM] Lista notificacoes SINAM/VIOLBR limpas (~2.4M registros, 2020-2024). "
                "Use filtros estilo Django, sem SQL. Retorna ate `limit` linhas + total. "
                "Esta e a forma PADRAO de buscar dados. Substitui run_sql na maioria dos casos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": _FILTER_DOC},
                    "limit": {"type": "integer", "description": "Default 20."},
                },
                "required": ["filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "contar",
            "description": (
                "[ORM] Conta notificacoes ou agrega por grupo. Sem group_by retorna o "
                "total. Com group_by retorna a contagem por valor (ex: por UF, por sexo)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": _FILTER_DOC},
                    "group_by": {
                        "type": "string",
                        "description": "Campo OU lista separada por virgula (ex: 'uf' ou 'ano,sexo').",
                    },
                    "top": {"type": "integer", "description": "Default 20."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "serie_temporal",
            "description": (
                "[ORM] Constroi a serie temporal de contagem de notificacoes ja agregada "
                "por dia/semana/mes. Sai pronta para forecast ou plot. Substitui "
                "load_series + run_sql para preparacao de series."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": _FILTER_DOC},
                    "freq": {
                        "type": "string",
                        "description": "D (diario), W (semanal), ME (mensal), QE (trimestral), YE (anual). Default D.",
                    },
                },
                "required": ["filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analise_retrospectiva",
            "description": (
                "[ORM] ANALISE RETROSPECTIVA DA SERIE: pega notificacoes filtradas, "
                "constroi a serie temporal e VALIDA o forecaster ativo na thread "
                "(definido pelo dropdown 'Forecast') contra o passado via "
                "walk-forward backtest. Retorna: profile da serie, metricas de "
                "fidelidade (WAPE/MAPE/RMSE/MAE) e a extrapolacao opcional. NAO e "
                "previsao de futuro -- e o quao bem o modelo escolhido explica a "
                "historia. `fold_size` controla a janela testada em cada fold."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": _FILTER_DOC},
                    "freq": {"type": "string", "description": "D/W/ME/QE/YE (default ME)."},
                    "fold_size": {"type": "integer",
                        "description": "Tamanho da janela de teste em cada fold (default 6)."},
                    "context": {"type": "string"},
                },
                "required": ["filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "previsao_automatica",
            "description": (
                "[alias retrocompatibilidade] Igual a `analise_retrospectiva` mas "
                "aceita 'horizon' em vez de 'fold_size'. PREFIRA "
                "analise_retrospectiva nas conversas novas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": _FILTER_DOC},
                    "freq": {"type": "string"},
                    "horizon": {"type": "integer", "description": "Default 14."},
                    "context": {"type": "string"},
                },
                "required": ["filters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ranking_municipios",
            "description": (
                "Retorna os TOP N municipios ordenados por contagem de notificacoes. "
                "USE quando o usuario perguntar 'qual a cidade mais violenta', "
                "'top 10 cidades', 'ranking de municipios', 'cidades com mais X', "
                "'piores cidades', etc. NUNCA chame relatorio_municipio com "
                "expressoes como 'cidade mais violenta' como nome -- isso vai falhar. "
                "Pode restringir por UF e filtros extra (violencia_*, ano, sexo...)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "uf": {"type": "string",
                           "description": "Sigla da UF para restringir (opcional)."},
                    "top": {"type": "integer", "description": "Quantos retornar. Default 10."},
                    "filters_extra": {"type": "object",
                        "description": "Filtros adicionais: ano, violencia_*, sexo, etc."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relatorio_uf",
            "description": (
                "[ATALHO] Relatorio retrospectivo de um ESTADO (UF) brasileiro: "
                "contagem por ano + serie mensal + analise retrospectiva. USE quando "
                "o usuario perguntar sobre um estado pelo nome (Sergipe, Sao Paulo, "
                "Bahia, etc) ou pela sigla (SE, SP, BA). "
                "TIPOS DE VIOLENCIA disponiveis no filters_extra (escolha o que o "
                "usuario pediu, NAO use violencia_sexual por default): "
                "violencia_fisica, violencia_psicologica, violencia_sexual, tortura, "
                "negligencia, trafico_pessoas, violencia_infantil, violencia_financeira, "
                "intervencao_legal, outras_violencias."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "uf": {"type": "string", "description": "Sigla (SE, SP, ...) ou nome do estado."},
                    "filters_extra": {
                        "type": "object",
                        "description": (
                            "Filtros adicionais ALEM da UF. Escolha o tipo de violencia "
                            "que o usuario CITOU NA PERGUNTA. Exemplos: "
                            "{\"tortura\": true} para tortura, "
                            "{\"violencia_fisica\": true} para violencia fisica, "
                            "{\"negligencia\": true} para negligencia, "
                            "{\"violencia_psicologica\": true} para psicologica, "
                            "{\"trafico_pessoas\": true} para trafico/aliciamento, "
                            "{\"violencia_sexual\": true} apenas se a pergunta cita sexual/abuso/estupro. "
                            "Tambem aceita: sexo (M/F), faixa_etaria, ano__gte, ano__lte."
                        )
                    },
                },
                "required": ["uf"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relatorio_brasil",
            "description": (
                "[ATALHO] Relatorio retrospectivo do PAIS INTEIRO. USE quando o "
                "usuario perguntar sobre 'Brasil', 'pais', 'nacional' ou nao "
                "especificar localizacao. "
                "TIPOS DE VIOLENCIA disponiveis (use o que o usuario pediu): "
                "violencia_fisica, violencia_psicologica, violencia_sexual, tortura, "
                "negligencia, trafico_pessoas, violencia_infantil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters_extra": {
                        "type": "object",
                        "description": (
                            "Filtros opcionais. Escolha o tipo de violencia citado. "
                            "Ex: {\"tortura\":true}, {\"negligencia\":true}, "
                            "{\"violencia_fisica\":true}, {\"trafico_pessoas\":true}. "
                            "Tambem aceita ano__gte/ano__lte."
                        )
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relatorio_municipio",
            "description": (
                "[ATALHO] One-shot: resolve o municipio + conta por ano + roda "
                "previsao_automatica anual. USE quando o usuario perguntar 'quais "
                "casos em <cidade>', 'situacao em <cidade>', 'evolucao em <cidade>'. "
                "Substitui chamadas separadas de resolver/contar/previsao."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "municipio": {"type": "string"},
                    "uf": {"type": "string", "description": "Sigla, opcional."},
                    "horizon": {"type": "integer",
                                "description": "Horizonte para forecast anual. Default 2."},
                },
                "required": ["municipio"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolver_municipio",
            "description": (
                "Resolve nome de municipio brasileiro para codigo IBGE 7d. "
                "Se ambiguo (ex: 'Bom Jesus' em varias UFs) devolve candidatos. "
                "Geralmente NAO precisa chamar manualmente -- as outras tools "
                "aceitam 'municipio_nome' direto no filters e fazem a resolucao."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "uf": {"type": "string", "description": "Sigla opcional p/ desambiguar."},
                },
                "required": ["nome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_saved_queries",
            "description": (
                "Lista as consultas SQL salvas no catalogo (SavedQuery). Use isso "
                "quando o usuario perguntar 'quais consultas existem' ou nao souber "
                "qual ID de consulta usar."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_series",
            "description": (
                "Carrega a serie temporal de uma SavedQuery (executa a SQL no Postgres "
                "Aurola). Retorna estatisticas resumidas (n pontos, range, media, etc.) "
                "e os ultimos 30 pontos. NAO retorna toda a serie por padrao."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {"type": "integer", "description": "ID da SavedQuery"},
                    "include_full": {
                        "type": "boolean",
                        "description": "Se true, retorna toda a serie. Default: false.",
                        "default": False,
                    },
                },
                "required": ["query_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forecast",
            "description": (
                "Roda forecast em uma SavedQuery usando o modelo selecionado. "
                "Retorna os valores previstos com quantis (p10, p50, p90) quando "
                "disponiveis. Use quando o usuario pedir 'prever', 'projetar', "
                "'estimar valores futuros', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {"type": "integer", "description": "ID da SavedQuery"},
                    "horizon": {
                        "type": "integer",
                        "description": "Quantos passos prever. Default: horizon padrao da consulta.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto curto em portugues para o modelo (opcional).",
                    },
                },
                "required": ["query_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "qa_multiple_choice",
            "description": (
                "Faz uma pergunta de multipla escolha sobre uma serie temporal "
                "usando o ChatTime. SO funciona com forecaster=chattime. A pergunta "
                "deve ter alternativas explicitas (a), (b), (c). Retorna a letra "
                "mais votada e as amostras brutas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_id": {"type": "integer", "description": "ID da SavedQuery"},
                    "question": {
                        "type": "string",
                        "description": "Pergunta com alternativas (a)... (b)... (c)..."
                    },
                },
                "required": ["query_id", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Roda uma SQL SELECT ad-hoc no Postgres Aurola e retorna as primeiras "
                "50 linhas. USE COM CUIDADO: somente leitura. Nao use para INSERT/UPDATE/DELETE/DROP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL SELECT a executar."},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forecast_from_sql",
            "description": (
                "Roda forecast a partir de uma SQL ad-hoc, sem precisar de uma SavedQuery. "
                "Use isso quando o usuario perguntar sobre uma agregacao especifica que "
                "nao existe como SavedQuery (ex: 'mulheres em SP em 2023'). A SQL deve "
                "retornar duas colunas: 'data' (date) e 'valor' (numerico)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT que retorna (data, valor) ordenado por data.",
                    },
                    "horizon": {"type": "integer", "description": "Passos a prever. Default 14."},
                    "freq": {
                        "type": "string",
                        "description": "Freq pandas opcional (D, W, ME, QE, YE).",
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto curto em PT-BR para o modelo (opcional).",
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "qa_from_sql",
            "description": (
                "QA multipla escolha sobre uma serie temporal vinda de uma SQL ad-hoc. "
                "Igual a qa_multiple_choice mas com SQL no lugar de query_id. "
                "Usa ChatTime internamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT retornando (data, valor)."},
                    "question": {"type": "string", "description": "Pergunta com (a)/(b)/(c)."},
                    "freq": {"type": "string"},
                },
                "required": ["sql", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_series",
            "description": (
                "Diagnostico estrutural de uma serie temporal: comprimento, "
                "frequencia, missing, tendencia, sazonalidade (lag e ACF), "
                "outliers. Use ANTES de propor um forecast quando o usuario nao "
                "explicitou o modelo, para escolher uma estrategia justificada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string",
                            "description": "SQL retornando (data, valor). Alternativa: query_id."},
                    "query_id": {"type": "integer",
                                 "description": "ID de uma SavedQuery. Alternativa: sql."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "backtest_forecast",
            "description": (
                "Walk-forward (rolling-origin) backtest de UM modelo na serie. "
                "Retorna MAE, RMSE, MAPE, sMAPE, WAPE agregados e por fold. "
                "Use para dar confianca a uma previsao (sem backtest, qualquer "
                "afirmacao 'crescera X%' e fe)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "query_id": {"type": "integer"},
                    "model": {
                        "type": "string",
                        "description": "chronos2 | ets | seasonal_naive | drift | chattime",
                    },
                    "horizon": {"type": "integer", "description": "Default 14."},
                    "n_folds": {"type": "integer", "description": "Default 3."},
                },
                "required": ["model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_forecast",
            "description": (
                "[alias retrocompatibilidade] Igual a `analise_retrospectiva`. "
                "Mantida para nao quebrar threads antigas. PREFIRA analise_retrospectiva."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "query_id": {"type": "integer"},
                    "horizon": {"type": "integer", "description": "Default 14."},
                    "context": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "peek_table",
            "description": (
                "Mostra 5 linhas reais de uma tabela VIOLBRxx para ver o formato "
                "dos valores. Use quando voce nao tem certeza se uma coluna existe "
                "ou que valores ela contem, ANTES de tentar uma SQL que pode falhar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Nome da tabela: VIOLBR20, VIOLBR21, VIOLBR22, VIOLBR23 ou VIOLBR24.",
                    },
                    "columns": {
                        "type": "string",
                        "description": "Lista de colunas separadas por virgula. Default: as 10 mais usadas.",
                    },
                },
                "required": ["table"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_forecasters",
            "description": (
                "Lista os modelos de forecast disponiveis (Chronos-2, ChatTime, ...) e "
                "quais suportam QA. Use quando o usuario perguntar 'que modelos posso usar'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

def _series_summary(idx, values: np.ndarray) -> dict:
    v = np.asarray(values, dtype=float)
    return {
        "n_pontos": int(v.size),
        "inicio": pd.Timestamp(idx.min()).date().isoformat() if len(idx) else None,
        "fim": pd.Timestamp(idx.max()).date().isoformat() if len(idx) else None,
        "min": float(v.min()) if v.size else None,
        "max": float(v.max()) if v.size else None,
        "media": float(v.mean()) if v.size else None,
        "mediana": float(np.median(v)) if v.size else None,
        "ultimos_30": [float(x) for x in v[-30:]],
        "ultimas_datas": [pd.Timestamp(d).date().isoformat() for d in idx[-30:]],
    }


def tool_list_saved_queries(args: dict, ctx: ToolContext) -> dict:
    rows = [{
        "id": q.pk, "name": q.name, "description": q.description,
        "freq": q.freq or "D", "default_horizon": q.default_horizon,
    } for q in SavedQuery.objects.all()]
    return {"queries": rows, "total": len(rows)}


def tool_load_series(args: dict, ctx: ToolContext) -> dict:
    sq = SavedQuery.objects.filter(pk=args["query_id"]).first()
    if not sq:
        return {"error": f"SavedQuery id={args['query_id']!r} nao encontrada."}
    try:
        idx, values = db.time_series(sq.sql, date_col=sq.date_col,
                                     value_col=sq.value_col, freq=sq.freq or None)
    except Exception as exc:
        return {"error": f"Falha ao executar SQL: {type(exc).__name__}: {exc}"}

    summary = _series_summary(idx, values)
    summary["query"] = {"id": sq.pk, "name": sq.name}
    if args.get("include_full"):
        summary["serie_completa"] = [float(x) for x in values]
        summary["datas_completas"] = [pd.Timestamp(d).date().isoformat() for d in idx]
    return summary


def tool_forecast(args: dict, ctx: ToolContext) -> dict:
    sq = SavedQuery.objects.filter(pk=args["query_id"]).first()
    if not sq:
        return {"error": f"SavedQuery id={args['query_id']!r} nao encontrada."}
    horizon = int(args.get("horizon") or sq.default_horizon)
    context = args.get("context") or sq.default_context

    try:
        idx, values = db.time_series(sq.sql, date_col=sq.date_col,
                                     value_col=sq.value_col, freq=sq.freq or None)
    except Exception as exc:
        return {"error": f"Falha ao carregar serie: {type(exc).__name__}: {exc}"}
    if values.size < 8:
        return {"error": f"Serie muito curta ({values.size} pontos) para forecast."}

    t0 = time.time()
    try:
        fc = get_forecaster(_resolve_solo_forecaster(ctx.forecaster))
        out = fc.predict(values, horizon, context=context)
    except Exception as exc:
        return {"error": f"Forecast falhou: {type(exc).__name__}: {exc}"}
    elapsed = time.time() - t0

    return {
        "query": {"id": sq.pk, "name": sq.name},
        "model": ctx.forecaster,
        "horizon": horizon,
        "predicted": [float(x) for x in out.values],
        "quantiles": {k: [float(x) for x in v] for k, v in (out.quantiles or {}).items()},
        "history_last_30": [float(x) for x in values[-30:]],
        "history_dates_last_30": [pd.Timestamp(d).date().isoformat() for d in idx[-30:]],
        "elapsed_seconds": round(elapsed, 2),
    }


def tool_qa(args: dict, ctx: ToolContext) -> dict:
    sq = SavedQuery.objects.filter(pk=args["query_id"]).first()
    if not sq:
        return {"error": f"SavedQuery id={args['query_id']!r} nao encontrada."}
    try:
        fc = get_forecaster("chattime")  # QA force-routes to ChatTime
    except Exception as exc:
        return {"error": f"ChatTime indisponivel: {exc}"}
    try:
        _, values = db.time_series(sq.sql, date_col=sq.date_col,
                                   value_col=sq.value_col, freq=sq.freq or None)
    except Exception as exc:
        return {"error": f"Falha ao carregar serie: {type(exc).__name__}: {exc}"}
    if values.size < 8:
        return {"error": f"Serie muito curta ({values.size} pontos) para QA."}

    t0 = time.time()
    try:
        letter, raws = fc.analyze(values, args["question"])
    except Exception as exc:
        return {"error": f"QA falhou: {type(exc).__name__}: {exc}"}
    return {
        "query": {"id": sq.pk, "name": sq.name},
        "question": args["question"],
        "answer": letter,
        "samples": raws,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


def tool_run_sql(args: dict, ctx: ToolContext) -> dict:
    sql_in = (args.get("sql") or "").strip()
    ok, err = _is_select_sql(sql_in)
    if not ok:
        return {"error": err}
    sql, autoquoted = _auto_quote_identifiers(sql_in)
    try:
        df = db.run_query(sql)
    except Exception as exc:
        return {"error": f"Falha SQL: {type(exc).__name__}: {exc}",
                "sql_executed": sql,
                "auto_quoted_names": autoquoted}
    limited = df.head(20)
    out = {
        "columns": list(limited.columns),
        "rows": json.loads(limited.to_json(orient="records", date_format="iso")),
        "total_rows": int(len(df)),
        "truncated": len(df) > 20,
    }
    # Summary stats if the query looks like a time series (has "data"+"valor")
    if "data" in df.columns and "valor" in df.columns:
        v = df["valor"].astype(float)
        out["summary"] = {
            "n": int(len(df)),
            "min": float(v.min()), "max": float(v.max()),
            "mean": round(float(v.mean()), 2),
            "sum": float(v.sum()),
        }
        out["hint"] = ("Esta query retorna serie temporal. Para forecast, "
                       "use auto_forecast(sql=...) com a MESMA SQL.")
    return out


def tool_list_forecasters(args: dict, ctx: ToolContext) -> dict:
    return {
        "active": ctx.forecaster,
        "available": [{
            "key": k, "label": cls.label,
            "description": cls.description, "supports_qa": cls.supports_qa,
        } for k, cls in REGISTRY.items()],
    }


def _is_select_sql(sql: str) -> tuple[bool, str]:
    """Returns (ok, error_message). Mirrors the guardrails of run_sql."""
    low = sql.strip().lower()
    if not low:
        return False, "SQL vazia."
    forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "truncate ",
                 "create ", "grant ", "revoke ")
    if any(low.startswith(f) or f" {f}" in low for f in forbidden):
        return False, "Apenas SELECT/WITH e permitido."
    if not low.startswith(("select", "with")):
        return False, "SQL deve comecar com SELECT ou WITH."
    return True, ""


# Auto-quoting safety net: the LLM often forgets that Postgres lowercases
# unquoted identifiers, so we rewrite known SINAM names to be double-quoted.
import re as _re

_AUTOQ_TABLES = ["VIOLBR20", "VIOLBR21", "VIOLBR22", "VIOLBR23", "VIOLBR24"]
_AUTOQ_COLUMNS = [
    "DT_NOTIFIC", "DT_OCOR", "DT_INVEST", "DT_OBITO", "DT_DIGITA", "DT_ENCERRA",
    "SG_UF", "SG_UF_OCOR", "SG_UF_NOT", "ID_MUNICIP", "ID_MN_RESI", "ID_MN_OCOR",
    "CS_SEXO", "CS_RACA", "CS_GESTANT", "CS_ESCOL_N", "NU_IDADE_N", "NU_ANO",
    "ANO_NASC", "ID_AGRAVO", "SIT_CONJUG", "ZONA", "LOCAL_OCOR", "LES_AUTOP",
    "OUT_VEZES", "AUTOR_SEXO", "AUTOR_ALCO", "EVOLUCAO", "CLASSI_FIN",
    "VIOL_FISIC", "VIOL_PSICO", "VIOL_TORT", "VIOL_SEXU", "VIOL_TRAF",
    "VIOL_FINAN", "VIOL_NEGLI", "VIOL_INFAN", "VIOL_LEGAL", "VIOL_OUTR",
    "ORIENT_SEX", "IDENT_GEN", "VIOL_MOTIV", "CICL_VID",
]


def _auto_quote_identifiers(sql: str) -> tuple[str, list[str]]:
    """Wraps unquoted SINAM table/column names in double quotes.
    Returns (rewritten_sql, list_of_fixes)."""
    fixes: list[str] = []
    out = sql
    for name in _AUTOQ_TABLES + _AUTOQ_COLUMNS:
        # \b...\b but NOT preceded/followed by a double quote
        pattern = rf'(?<!["\w]){_re.escape(name)}(?!["\w])'
        if _re.search(pattern, out):
            new = out.replace_all if False else _re.sub(pattern, f'"{name}"', out)
            if new != out:
                fixes.append(name)
                out = new
    return out, fixes


def tool_forecast_from_sql(args: dict, ctx: ToolContext) -> dict:
    sql_in = (args.get("sql") or "").strip()
    ok, err = _is_select_sql(sql_in)
    if not ok:
        return {"error": err}
    sql, _ = _auto_quote_identifiers(sql_in)
    horizon = int(args.get("horizon") or 14)
    freq = args.get("freq") or None
    context = args.get("context") or None

    try:
        idx, values = db.time_series(sql, date_col="data", value_col="valor", freq=freq)
    except Exception as exc:
        return {"error": f"Falha ao carregar serie: {type(exc).__name__}: {exc}"}
    if values.size < 8:
        return {"error": f"Serie muito curta ({values.size} pontos) para forecast."}

    t0 = time.time()
    try:
        fc = get_forecaster(_resolve_solo_forecaster(ctx.forecaster))
        out = fc.predict(values, horizon, context=context)
    except Exception as exc:
        return {"error": f"Forecast falhou: {type(exc).__name__}: {exc}"}
    return {
        "model": ctx.forecaster,
        "horizon": horizon,
        "predicted": [float(x) for x in out.values],
        "quantiles": {k: [float(x) for x in v] for k, v in (out.quantiles or {}).items()},
        "history_last_30": [float(x) for x in values[-30:]],
        "history_dates_last_30": [pd.Timestamp(d).date().isoformat() for d in idx[-30:]],
        "elapsed_seconds": round(time.time() - t0, 2),
        "n_points": int(values.size),
        "range": [pd.Timestamp(idx.min()).date().isoformat(), pd.Timestamp(idx.max()).date().isoformat()],
    }


def tool_qa_from_sql(args: dict, ctx: ToolContext) -> dict:
    sql_in = (args.get("sql") or "").strip()
    ok, err = _is_select_sql(sql_in)
    if not ok:
        return {"error": err}
    sql, _ = _auto_quote_identifiers(sql_in)
    try:
        fc = get_forecaster("chattime")
    except Exception as exc:
        return {"error": f"ChatTime indisponivel: {exc}"}
    try:
        _, values = db.time_series(sql, date_col="data", value_col="valor",
                                   freq=args.get("freq") or None)
    except Exception as exc:
        return {"error": f"Falha ao carregar serie: {type(exc).__name__}: {exc}"}
    if values.size < 8:
        return {"error": f"Serie muito curta ({values.size} pontos) para QA."}

    t0 = time.time()
    try:
        letter, raws = fc.analyze(values, args["question"])
    except Exception as exc:
        return {"error": f"QA falhou: {type(exc).__name__}: {exc}"}
    return {
        "question": args["question"],
        "answer": letter,
        "samples": raws,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


def _resolve_series(args: dict) -> tuple[np.ndarray | None, pd.DatetimeIndex | None,
                                          str | None, dict]:
    """Accept either query_id or sql, return (values, index, freq, info_or_error)."""
    if args.get("query_id"):
        sq = SavedQuery.objects.filter(pk=args["query_id"]).first()
        if not sq:
            return None, None, None, {"error": f"SavedQuery {args['query_id']!r} nao encontrada."}
        sql = sq.sql
        freq = sq.freq or None
        date_col, value_col = sq.date_col, sq.value_col
        label = sq.name
    elif args.get("sql"):
        sql_in = args["sql"].strip()
        ok, err = _is_select_sql(sql_in)
        if not ok:
            return None, None, None, {"error": err}
        sql, _ = _auto_quote_identifiers(sql_in)
        freq = args.get("freq") or None
        date_col, value_col = "data", "valor"
        label = "ad-hoc SQL"
    else:
        return None, None, None, {"error": "Forneca query_id ou sql."}
    try:
        idx, values = db.time_series(sql, date_col=date_col, value_col=value_col, freq=freq)
    except Exception as exc:
        return None, None, None, {"error": f"Falha SQL: {type(exc).__name__}: {exc}"}
    return values, idx, freq, {"label": label}


def tool_analyze_series(args: dict, ctx: ToolContext) -> dict:
    values, idx, freq, info = _resolve_series(args)
    if values is None:
        return info
    profile = analyze_series(values, idx, freq_hint=freq)
    return {"label": info["label"], **profile.to_dict()}


def _predict_fn_for(model_name: str, profile_period: int | None):
    """Returns a callable (history, h) -> predictions for the named model."""
    if model_name == "chronos2":
        fc = get_forecaster("chronos2")
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "ets":
        from src.series_models.baselines_adapter import BaselineModel
        fc = BaselineModel(backend="ets", period=profile_period)
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "seasonal_naive":
        from src.series_models.baselines_adapter import BaselineModel
        period = profile_period or 7
        fc = BaselineModel(backend="seasonal_naive", period=period)
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "drift":
        from src.series_models.baselines_adapter import BaselineModel
        fc = BaselineModel(backend="drift")
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "chattime":
        fc = get_forecaster("chattime")
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "random_forest":
        fc = get_forecaster("random_forest")
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    if model_name == "remote_api":
        fc = get_forecaster("remote_api")
        return lambda h, horizon: fc.predict(h, int(horizon)).values
    raise ValueError(f"Modelo desconhecido: {model_name!r}")


def tool_backtest_forecast(args: dict, ctx: ToolContext) -> dict:
    values, idx, freq, info = _resolve_series(args)
    if values is None:
        return info
    model = args.get("model") or "chronos2"
    horizon = int(args.get("horizon") or 14)
    n_folds = int(args.get("n_folds") or 3)
    profile = analyze_series(values, idx, freq_hint=freq)
    try:
        predict_fn = _predict_fn_for(model, profile.seasonality_lag)
    except Exception as exc:
        return {"error": str(exc)}
    bt = walk_forward_backtest(values, predict_fn, horizon=horizon,
                               n_folds=n_folds, model_name=model)
    return {"label": info["label"], **bt.to_dict()}


_COMMITTEE_MEMBERS = ["chronos2", "chattime", "ets", "seasonal_naive"]


def _candidates_for(ctx: ToolContext) -> list[str]:
    """Forecaster selection follows the dropdown of the thread:

      - 'committee' (modo competitivo) → roda TODOS, escolhe o melhor por WAPE.
      - 'chronos2' / 'chattime' / 'ets' / 'seasonal_naive' / 'drift' → solo.
    """
    main = (ctx.forecaster or "chronos2").lower()
    if main == "committee":
        return list(_COMMITTEE_MEMBERS)
    return [main]


def _resolve_solo_forecaster(forecaster_name: str) -> str:
    """Fall-back: tools that need ONE concrete forecaster (qa, forecast direto)
    receive 'chronos2' when the thread is in committee mode."""
    name = (forecaster_name or "chronos2").lower()
    return "chronos2" if name == "committee" else name


def tool_auto_forecast(args: dict, ctx: ToolContext) -> dict:
    """End-to-end: analyze -> backtest committee -> pick winner -> final forecast."""
    values, idx, freq, info = _resolve_series(args)
    if values is None:
        return info
    horizon = int(args.get("horizon") or 14)
    context = args.get("context") or None

    profile = analyze_series(values, idx, freq_hint=freq)
    if profile.length < 30:
        return {"error": f"Serie muito curta ({profile.length} pontos) para auto-forecast.",
                "profile": profile.to_dict()}

    # Committee composition respects the forecaster picked on this thread
    # (chronos2 or chattime as main + ets/seasonal_naive as baselines).
    candidates = _candidates_for(ctx)
    # Backtest each candidate. 2 folds keeps it fast; horizon may shrink so
    # the train window stays usable.
    fold_horizon = min(horizon, max(7, profile.length // 6))
    n_folds = 2
    ranking: list[dict] = []
    for cand in candidates:
        t0 = time.time()
        try:
            pf = _predict_fn_for(cand, profile.seasonality_lag)
            bt = walk_forward_backtest(values, pf, horizon=fold_horizon,
                                       n_folds=n_folds, model_name=cand)
            ranking.append({
                "model": cand,
                "wape": bt.overall.wape,
                "mape": bt.overall.mape,
                "rmse": bt.overall.rmse,
                "mae": bt.overall.mae,
                "n_folds": bt.n_folds,
                "elapsed": round(time.time() - t0, 2),
            })
        except Exception as exc:
            ranking.append({"model": cand, "error": f"{type(exc).__name__}: {exc}",
                            "elapsed": round(time.time() - t0, 2)})

    # Pick winner: smallest finite WAPE; fall back to RMSE if WAPE is nan.
    finite = [r for r in ranking if "error" not in r and isinstance(r["wape"], (int, float))
              and r["wape"] == r["wape"]]  # NaN check
    if finite:
        winner = min(finite, key=lambda r: r["wape"])
    else:
        # WAPE all NaN — fall back to RMSE
        non_err = [r for r in ranking if "error" not in r]
        if not non_err:
            return {"error": "Todos os modelos falharam no backtest.", "ranking": ranking,
                    "profile": profile.to_dict()}
        winner = min(non_err, key=lambda r: r["rmse"])

    # Final forecast over the full series using the winning model
    t0 = time.time()
    try:
        winning_fc = get_forecaster(winner["model"]) if winner["model"] in ("chronos2", "chattime") \
            else None
        if winning_fc is not None:
            final = winning_fc.predict(values, horizon, context=context)
            preds = [float(x) for x in final.values]
            quantiles = {k: [float(x) for x in v] for k, v in (final.quantiles or {}).items()}
        else:
            pf = _predict_fn_for(winner["model"], profile.seasonality_lag)
            preds = [float(x) for x in pf(values, horizon)]
            quantiles = {}
    except Exception as exc:
        return {"error": f"Forecast final falhou: {exc}", "ranking": ranking,
                "profile": profile.to_dict()}

    return {
        "label": info["label"],
        "horizon": horizon,
        "winner": winner["model"],
        "winner_metrics": {k: winner[k] for k in ("wape", "mape", "rmse", "mae") if k in winner},
        "ranking": sorted(ranking, key=lambda r: (r.get("wape", 9e9) if isinstance(r.get("wape"), (int, float))
                                                  else 9e9)),
        "profile": profile.to_dict(),
        "predicted": preds,
        "quantiles": quantiles,
        "history_last_30": [float(x) for x in values[-30:]],
        "history_dates_last_30": [pd.Timestamp(d).date().isoformat() for d in idx[-30:]],
        "elapsed_final_forecast": round(time.time() - t0, 2),
    }


VIOLBR_TABLES_SET = {"VIOLBR20", "VIOLBR21", "VIOLBR22", "VIOLBR23", "VIOLBR24"}
_DEFAULT_PEEK_COLS = ["DT_NOTIFIC", "SG_UF", "CS_SEXO", "NU_IDADE_N", "CS_RACA",
                      "VIOL_FISIC", "VIOL_SEXU", "VIOL_PSICO", "LOCAL_OCOR", "LES_AUTOP"]


def tool_peek_table(args: dict, ctx: ToolContext) -> dict:
    table = (args.get("table") or "").strip()
    if table not in VIOLBR_TABLES_SET:
        return {"error": f"Tabela {table!r} nao existe. Disponiveis: {sorted(VIOLBR_TABLES_SET)}"}
    cols_raw = (args.get("columns") or "").strip()
    if cols_raw:
        cols = [c.strip() for c in cols_raw.split(",") if c.strip()]
    else:
        cols = _DEFAULT_PEEK_COLS
    quoted = ", ".join(f'"{c}"' for c in cols)
    sql = f'SELECT {quoted} FROM "{table}" LIMIT 5'
    try:
        df = db.run_query(sql)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}",
                "hint": "Talvez alguma coluna nao exista. Confira o schema no system prompt."}
    return {
        "table": table,
        "columns": list(df.columns),
        "rows": json.loads(df.to_json(orient="records", date_format="iso")),
    }


# ---------------------------------------------------------------------------
# ORM-based tools (preferred — talk to clean `Notificacao` model)
# ---------------------------------------------------------------------------

def tool_consultar(args: dict, ctx: ToolContext) -> dict:
    return sq.query(args.get("filters") or {}, limit=int(args.get("limit") or 20))


def tool_contar(args: dict, ctx: ToolContext) -> dict:
    group_by = args.get("group_by")
    if isinstance(group_by, str) and "," in group_by:
        group_by = [g.strip() for g in group_by.split(",") if g.strip()]
    return sq.aggregate(args.get("filters") or {}, group_by=group_by,
                        top=int(args.get("top") or 20))


def tool_serie_temporal(args: dict, ctx: ToolContext) -> dict:
    return sq.time_series(args.get("filters") or {}, freq=(args.get("freq") or "D"))


def tool_resolver_municipio(args: dict, ctx: ToolContext) -> dict:
    return sq.resolver_municipio(args.get("nome", ""), args.get("uf"))


def tool_ranking_municipios(args: dict, ctx: ToolContext) -> dict:
    """Top N municipios por contagem com nome resolvido (via Municipio IBGE)."""
    from django.db.models import Count
    from sinam.models import Municipio
    from sinam import queries as sqm

    uf = (args.get("uf") or "").strip().upper() or None
    top = int(args.get("top") or 10)
    extra = args.get("filters_extra") or {}
    filters = dict(extra)
    if uf:
        filters["uf"] = uf

    sanitized, ignored, notes = sqm._sanitize_filters(filters)
    qs = (Notificacao.objects.filter(**sanitized)
                            .exclude(municipio_codigo="")
                            .values("municipio_codigo", "uf")
                            .annotate(n=Count("id"))
                            .order_by("-n")[:top])
    rows = list(qs)

    # Resolve nome do municipio. SINAM usa 6 digitos IBGE (sem verificador).
    # Cacheia para evitar N queries.
    codes = [(r["municipio_codigo"], r["uf"]) for r in rows]
    cache = {}
    for code, uf_row in codes:
        mun = Municipio.objects.filter(codigo__startswith=code, uf=uf_row).first()
        cache[(code, uf_row)] = mun.nome if mun else f"(codigo {code})"
    for r in rows:
        r["nome"] = cache.get((r["municipio_codigo"], r["uf"]), "?")

    total_all = Notificacao.objects.filter(**sanitized).count()
    return {
        "uf": uf,
        "filtros_aplicados": sanitized,
        "filtros_ignorados": ignored,
        "notes": notes,
        "top": top,
        "total_notificacoes": total_all,
        "ranking": rows,
    }


def _normalize_uf(uf_input: str) -> str | None:
    """Aceita 'SE', 'sergipe', 'Sergipe' etc. → retorna sigla 2 letras maiúsculas."""
    if not uf_input:
        return None
    s = uf_input.strip().upper()
    if len(s) == 2:
        return s
    # Nome completo -> sigla
    import unicodedata
    norm = "".join(c for c in unicodedata.normalize("NFKD", s)
                    if not unicodedata.combining(c)).lower()
    nome_to_sigla = {
        "rondonia":"RO","acre":"AC","amazonas":"AM","roraima":"RR","para":"PA",
        "amapa":"AP","tocantins":"TO","maranhao":"MA","piaui":"PI","ceara":"CE",
        "rio grande do norte":"RN","paraiba":"PB","pernambuco":"PE","alagoas":"AL",
        "sergipe":"SE","bahia":"BA","minas gerais":"MG","espirito santo":"ES",
        "rio de janeiro":"RJ","sao paulo":"SP","parana":"PR","santa catarina":"SC",
        "rio grande do sul":"RS","mato grosso do sul":"MS","mato grosso":"MT",
        "goias":"GO","distrito federal":"DF",
    }
    return nome_to_sigla.get(norm)


def _relatorio_pipeline(filters: dict, label: str, ctx: ToolContext,
                        horizon: int = 6) -> dict:
    """Shared body: count by year + monthly series + retrospective analysis."""
    by_year = sq.aggregate(filters, group_by="ano", top=20)
    ts_monthly = sq.time_series(filters, freq="ME")
    prev = tool_previsao_automatica(
        {"filters": filters, "freq": "ME", "horizon": horizon}, ctx
    )
    return {
        "escopo": label,
        "filtros_aplicados": filters,
        "total_geral": by_year.get("total_rows", 0),
        "por_ano": by_year.get("rows", []),
        "serie_mensal": {
            "n_points": ts_monthly.get("n_points", 0),
            "dates": ts_monthly.get("dates", []),
            "values": ts_monthly.get("values", []),
        },
        "previsao_mensal": prev if not prev.get("error") else {"erro": prev["error"]},
    }


def tool_relatorio_uf(args: dict, ctx: ToolContext) -> dict:
    uf_raw = args.get("uf") or ""
    uf = _normalize_uf(uf_raw)
    if not uf:
        return {"error": f"UF '{uf_raw}' nao reconhecida. Use sigla (SE, SP, RJ, ...) ou nome."}
    extra = args.get("filters_extra") or {}
    filters = {"uf": uf, **extra}
    return _relatorio_pipeline(filters, label=f"Estado de {uf}", ctx=ctx)


def tool_relatorio_brasil(args: dict, ctx: ToolContext) -> dict:
    extra = args.get("filters_extra") or {}
    return _relatorio_pipeline(extra, label="Brasil (nacional)", ctx=ctx)


def tool_relatorio_municipio(args: dict, ctx: ToolContext) -> dict:
    """One-shot: resolve + count_by_year + serie + previsao mensal."""
    nome = args.get("municipio") or ""
    uf = args.get("uf") or None
    horizon = int(args.get("horizon") or 6)  # 6 meses pra frente por default

    resolved = sq.resolver_municipio(nome, uf)
    if not resolved.get("found"):
        return {"error": f"Municipio '{nome}' nao encontrado/ambiguo.",
                "lookup_result": resolved}
    filters = {"municipio_nome": nome}
    if uf:
        filters["uf"] = uf

    by_year = sq.aggregate(filters, group_by="ano", top=20)
    ts_monthly = sq.time_series(filters, freq="ME")

    # Previsão sobre a série mensal (mais pontos = mais confiável que anual)
    prev = tool_previsao_automatica({"filters": filters, "freq": "ME",
                                     "horizon": horizon}, ctx)

    return {
        "municipio": f"{resolved['nome']}/{resolved['uf']}",
        "codigo_ibge": resolved["codigo"],
        "codigo_sinam": resolved["codigo"][:6],
        "total_geral": by_year.get("total_rows", 0),
        "por_ano": by_year.get("rows", []),
        "serie_mensal": {
            "n_points": ts_monthly.get("n_points", 0),
            "dates": ts_monthly.get("dates", []),
            "values": ts_monthly.get("values", []),
        },
        "previsao_mensal": prev if not prev.get("error") else {"erro": prev["error"]},
    }


def tool_previsao_automatica(args: dict, ctx: ToolContext) -> dict:
    """ORM + analytics + comitê — full pipeline on the clean model."""
    if not _FORECAST:
        # Versão leve: sem Chronos/torch. Os relatórios ficam SQL-only (por_ano,
        # série, total); o bloco de análise retrospectiva é omitido.
        return {"error": "forecasting_desativado_versao_leve"}
    horizon = int(args.get("horizon") or 14)
    freq = args.get("freq") or "D"
    context_text = args.get("context") or None
    values, idx, ts_info = sq.series_for_forecast(args.get("filters") or {}, freq=freq)
    if values.size == 0:
        return {"error": "Nenhuma notificacao bate com esses filtros.",
                "filters_applied": ts_info["filters_applied"]}
    profile = analyze_series(values, idx, freq_hint=freq)
    if profile.length < 30:
        return {"error": f"Serie muito curta ({profile.length} pontos) para previsao automatica.",
                "filters_applied": ts_info["filters_applied"],
                "profile": profile.to_dict(),
                "dates": ts_info["dates"], "values": ts_info["values"]}

    candidates = _candidates_for(ctx)
    fold_horizon = min(horizon, max(7, profile.length // 6))
    n_folds = 2
    config = {
        "freq": freq, "horizon_requested": horizon,
        "fold_horizon": fold_horizon, "n_folds_attempted": n_folds,
        "candidates": list(candidates),
        "forecaster_mode": ctx.forecaster or "chronos2",
    }
    ranking: list[dict] = []
    folds_by_model: dict[str, list[dict]] = {}
    for cand in candidates:
        t0 = time.time()
        try:
            pf = _predict_fn_for(cand, profile.seasonality_lag)
            bt = walk_forward_backtest(values, pf, horizon=fold_horizon,
                                       n_folds=n_folds, model_name=cand)
            ranking.append({"model": cand,
                            "wape": bt.overall.wape, "mape": bt.overall.mape,
                            "rmse": bt.overall.rmse, "mae": bt.overall.mae,
                            "bias": bt.overall.bias,
                            "n_folds": bt.n_folds, "elapsed": round(time.time()-t0,2)})
            folds_by_model[cand] = [{
                "fold": i + 1,
                "train_end_idx": f.train_end,
                "test_window": [f.test_start, f.test_end],
                "n_test": f.metrics.n,
                "wape": f.metrics.wape, "mape": f.metrics.mape,
                "rmse": f.metrics.rmse, "mae": f.metrics.mae,
            } for i, f in enumerate(bt.folds)]
        except Exception as exc:
            ranking.append({"model": cand, "error": f"{type(exc).__name__}: {exc}",
                            "elapsed": round(time.time()-t0,2)})

    finite = [r for r in ranking
              if "error" not in r and isinstance(r["wape"], (int,float))
              and r["wape"] == r["wape"]]
    winner = (min(finite, key=lambda r: r["wape"]) if finite
              else min((r for r in ranking if "error" not in r),
                       key=lambda r: r["rmse"], default=None))
    if winner is None:
        return {"error": "Todos os modelos falharam no backtest.",
                "ranking": ranking, "profile": profile.to_dict(),
                "config": config}

    try:
        winning_fc = get_forecaster(winner["model"]) if winner["model"] in ("chronos2","chattime") else None
        if winning_fc is not None:
            final = winning_fc.predict(values, horizon, context=context_text)
            preds = [float(x) for x in final.values]
            quantiles = {k: [float(x) for x in v] for k, v in (final.quantiles or {}).items()}
        else:
            pf = _predict_fn_for(winner["model"], profile.seasonality_lag)
            preds = [float(x) for x in pf(values, horizon)]
            quantiles = {}
    except Exception as exc:
        return {"error": f"Forecast final falhou: {exc}", "ranking": ranking,
                "profile": profile.to_dict()}

    return {
        "filters_applied": ts_info["filters_applied"],
        "freq": freq, "horizon": horizon,
        "config": config,
        "winner": winner["model"],
        "winner_metrics": {k: winner[k] for k in
                           ("wape","mape","rmse","mae","bias","n_folds") if k in winner},
        "ranking": sorted(ranking, key=lambda r: (r.get("wape", 9e9)
                          if isinstance(r.get("wape"), (int,float)) else 9e9)),
        "folds_by_model": folds_by_model,
        "profile": profile.to_dict(),
        "predicted": preds,
        "quantiles": quantiles,
        "history_last_30_dates": ts_info["dates"][-30:],
        "history_last_30_values": ts_info["values"][-30:],
    }


DISPATCH = {
    "consultar":             tool_consultar,
    "contar":                tool_contar,
    "serie_temporal":        tool_serie_temporal,
    "previsao_automatica":   tool_previsao_automatica,
    "resolver_municipio":    tool_resolver_municipio,
    "relatorio_municipio":   tool_relatorio_municipio,
    "relatorio_uf":          tool_relatorio_uf,
    "relatorio_brasil":      tool_relatorio_brasil,
    "ranking_municipios":    tool_ranking_municipios,
    "list_saved_queries": tool_list_saved_queries,
    "load_series": tool_load_series,
    "forecast": tool_forecast,
    "qa_multiple_choice": tool_qa,
    "forecast_from_sql": tool_forecast_from_sql,
    "qa_from_sql": tool_qa_from_sql,
    "analyze_series": tool_analyze_series,
    "backtest_forecast": tool_backtest_forecast,
    "auto_forecast": tool_auto_forecast,
    "peek_table": tool_peek_table,
    "run_sql": tool_run_sql,
    "list_forecasters": tool_list_forecasters,
}


# ---------------------------------------------------------------------------
# Ferramentas extra do "Aurora responde" (RAG jurídico/interno + SIPIA-CT).
# Mescladas aqui para o orquestrador enxergar tudo num único conjunto de tools,
# mantendo a implementação separada em [rag_tools.py].
# ---------------------------------------------------------------------------
from .rag_tools import RAG_DISPATCH, RAG_TOOLS_SCHEMA  # noqa: E402

TOOLS_SCHEMA.extend(RAG_TOOLS_SCHEMA)
DISPATCH.update(RAG_DISPATCH)

# ---------------------------------------------------------------------------
# Curadoria do que o ROTEADOR (Qwen3) enxerga. As ferramentas legadas de SQL
# cru / SavedQuery (run_sql, *_from_sql, forecast/qa por query_id, peek_table…)
# confundem o modelo pequeno e apontam para tabelas que não existem no caminho
# limpo (ex.: run_sql em "sinan"). Elas seguem em DISPATCH (retrocompat) mas
# NÃO são anunciadas — o Qwen usa só o conjunto limpo e unificado.
# ---------------------------------------------------------------------------
_EXPOSED_TOOLS = {
    # Dados SINAM (ORM limpo)
    "consultar", "contar", "serie_temporal", "ranking_municipios", "resolver_municipio",
    "relatorio_uf", "relatorio_brasil", "relatorio_municipio",
    # Série temporal / Chronos (só quando a pergunta é de série)
    "previsao_automatica", "analise_retrospectiva",
    # Fontes do Aurora responde
    "rag_juridico", "rag_interno", "consulta_sipia_ct",
}
TOOLS_SCHEMA[:] = [t for t in TOOLS_SCHEMA
                   if t.get("function", {}).get("name") in _EXPOSED_TOOLS]


def run_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    fn = DISPATCH.get(name)
    if fn is None:
        return {"error": f"Tool desconhecida: {name!r}"}
    return fn(args or {}, ctx)
