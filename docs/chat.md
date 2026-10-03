# Chat (orquestrador + ferramentas + pipeline inteligente)

Interface conversacional sobre as séries SINAM. Um LLM local (Qwen3 via
**Ollama**) recebe a pergunta em PT-BR, **conhece o schema do banco** (pré-injetado
no system prompt) e tem ferramentas que cobrem desde análise estrutural até
previsão com seleção automática de modelo.

```
Usuário ──► chat ──► orchestrator ──┬─ Ollama (Qwen3-8B)
                                    │
                                    └─ Tools (11):
                                       list_saved_queries, list_forecasters
                                       load_series, run_sql           (Postgres)
                                       analyze_series                 (Analytics)
                                       backtest_forecast              (Analytics + Forecasters)
                                       auto_forecast       ◄── pipeline completo
                                       forecast_from_sql, qa_from_sql,
                                       forecast, qa_multiple_choice    (Forecasters)
```

Tudo local. Nenhuma chamada externa.

## Pré-requisitos manuais

1. **Instalar Ollama** (Windows): <https://ollama.com/download/windows>
2. **Baixar o modelo orquestrador** (~5 GB):
   ```powershell
   ollama pull qwen3:8b
   ```
3. **GPU recomendada**: RTX com >= 12 GB.

## Forecasters disponíveis

Listados em [`src/series_models/__init__.py`](../src/series_models/__init__.py).

| Chave            | Backend                        | Tamanho | GPU | QA  | Uso típico                                  |
|------------------|--------------------------------|---------|-----|-----|----------------------------------------------|
| `chronos2`       | Amazon Chronos-2               | 120M    | ✅  | ❌  | Forecast SOTA, intervalos calibrados.       |
| `chattime`       | ChatTime-1-7B (vendored)       | 7B      | ✅  | ✅  | QA múltipla escolha (a)/(b)/(c).            |
| `ets`            | Holt-Winters (statsmodels)     | <1 MB   | ❌  | ❌  | Baseline forte com tendência/sazonalidade.  |
| `seasonal_naive` | Repete o último ciclo          | —       | ❌  | ❌  | Sanity check obrigatório em séries sazonais.|
| `drift`          | Linear entre 1º e último ponto | —       | ❌  | ❌  | Sanity check em séries tendenciosas.        |

## Pipeline `auto_forecast` (recomendado)

A tool **`auto_forecast`** encapsula análise + comitê + seleção + previsão em
uma única chamada. O LLM aciona ela toda vez que o usuário pede uma previsão
sem citar modelo específico.

```
auto_forecast(sql ou query_id, horizon)
   ├─ analyze_series           → SeriesProfile (sazonalidade, tendência, missing, ...)
   ├─ walk-forward backtest    → MAE/RMSE/MAPE/WAPE para cada candidato
   │     ├─ Chronos-2
   │     ├─ ETS
   │     └─ Seasonal Naive
   ├─ vencedor = argmin(WAPE)
   └─ forecast final com o vencedor → mediana + p10/p90 (quando disponível)
```

Output devolvido ao LLM:

```jsonc
{
  "winner": "chronos2",
  "winner_metrics": { "wape": 14.04, "mape": 15.2, "rmse": 7415.7 },
  "ranking": [
    { "model": "chronos2",       "wape": 14.04, "elapsed": 12.3 },
    { "model": "seasonal_naive", "wape": 15.00, "elapsed": 0.0  },
    { "model": "ets",            "wape": 15.86, "elapsed": 0.3  }
  ],
  "profile": {
    "length": 60, "inferred_freq": "ME",
    "seasonality_lag": 3, "trend_slope": 609.8,
    "notes": ["serie curta (n<100) — prefira foundation",
              "tendencia crescente forte (slope=+610/mes)",
              "sazonalidade clara em lag=3 (acf=0.83)"]
  },
  "predicted": [55040, 56832, ...],
  "quantiles": { "p10": [...], "p50": [...], "p90": [...] }
}
```

O LLM transforma isso numa resposta estruturada (modelo escolhido + métricas +
previsão + interpretação em prosa).

## Analytics (`src/analytics/`)

Componente reutilizável (não depende de Django).

### `analyze_series(values, idx, freq_hint)`

Retorna um `SeriesProfile` com:

- comprimento, range, frequência inferida, % missing, % zeros
- estatísticas (mean, median, std, CV)
- **tendência** (slope da regressão linear + strength)
- **sazonalidade** (ACF nos lags candidatos de acordo com a freq)
- **outliers** (regra IQR)
- flags `has_negatives`, `is_count_like`
- `notes`: lista de observações em PT-BR

### `walk_forward_backtest(values, predict_fn, horizon, n_folds=3)`

Rolling-origin com N folds. Para cada fold treina em `values[:cut]` e mede em
`values[cut:cut+horizon]`. Retorna `BacktestResult` com:

- `overall`: métricas agregadas
- `folds`: cada fold com cut-point, predição, verdadeiro, métricas

### `metrics(y_true, y_pred)`

MAE · RMSE · MAPE · sMAPE · **WAPE** · bias.

WAPE (`sum |err| / sum |y|`) é o critério primário do comitê — robusto a zeros
e outliers, é a métrica padrão para previsão em saúde pública.

## Tools (lista completa)

| Tool                  | Quando usar                                                       |
|-----------------------|-------------------------------------------------------------------|
| `auto_forecast`       | **Previsão sem citar modelo.** Pipeline completo.                |
| `analyze_series`      | Só o diagnóstico estrutural, sem prever.                          |
| `backtest_forecast`   | Comparar UM modelo específico (não comitê).                       |
| `forecast_from_sql`   | Usuário citou um modelo específico ("usa o ETS").                 |
| `qa_from_sql`         | Pergunta múltipla escolha sobre série ad-hoc.                     |
| `forecast`            | Usar SavedQuery do catálogo.                                      |
| `qa_multiple_choice`  | QA sobre SavedQuery.                                              |
| `load_series`         | Resumo de uma SavedQuery (sem rodar nada).                        |
| `run_sql`             | Contagem, ranking, agregação. Apenas SELECT/WITH.                 |
| `list_saved_queries`  | Listar atalhos disponíveis.                                       |
| `list_forecasters`    | Listar modelos disponíveis.                                       |

## Schema injetado no system prompt

Em [`webapp/chat/schema_cache.py`](../webapp/chat/schema_cache.py). Carregado
uma vez por processo. O LLM começa cada conversa **já sabendo**:

- Quais tabelas existem (`VIOLBR20`..`VIOLBR24`).
- Todas as colunas (~150) com tipo (todas TEXT).
- Top-5 valores das colunas categóricas (`CS_SEXO`, `SG_UF`, `VIOL_FISIC`, ...).
- Regras de SQL: aspas duplas, regex em `DT_NOTIFIC`, padrão para séries.

Isso evita que o LLM "chute" nomes de tabela/coluna e elimina a maioria das
respostas do tipo "não tenho consulta salva pra isso".

## Variáveis de ambiente

| Variável         | Default                              |
|------------------|---------------------------------------|
| `OLLAMA_HOST`    | `http://127.0.0.1:11434`              |
| `OLLAMA_MODEL`   | `qwen3:8b`                            |
| `CHRONOS2_MODEL` | `amazon/chronos-2`                    |
| `CHATTIME_MODEL` | `ChengsenWang/ChatTime-1-7B-Chat`     |

## Exemplos de pergunta

- *"Quantas vítimas femininas em 2023? Prevê 14 dias."*  
  → `auto_forecast(sql, 14)` → mostra ranking + previsão + métrica
- *"Compara Chronos-2 e ETS na consulta 1 com horizonte de 30."*  
  → 2× `backtest_forecast` + interpretação
- *"A tendência é (a) crescente (b) estável (c) decrescente?"*  
  → `qa_from_sql` (rota fixa via ChatTime)
- *"Quais consultas existem?"*  
  → `list_saved_queries`
- *"Quantos registros de mulheres em SP no carnaval de 2024?"*  
  → `run_sql`

## Limitações conhecidas

- **Sem streaming**: resposta vem inteira após todos os tool calls. Tempo
  típico por turno: 5–15 s; com `auto_forecast` chega a 20–40 s
  (3 modelos no backtest).
- **Backtest custa GPU**: cada fold do Chronos-2 leva 5–15 s. O `auto_forecast`
  usa 2 folds por padrão.
- **Sem cancelamento**: fechar a aba não interrompe o servidor.
- **`statsmodels` pode warnar** sobre convergência em séries muito curtas (n<24).
  O adapter cai pra simple exponential smoothing sem trend nesse caso.
