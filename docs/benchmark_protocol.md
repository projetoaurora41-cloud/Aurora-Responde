# Protocolo de Benchmark & Seleção de Modelos

Documento prescritivo. Executa-o **uma vez por candidato em cada posição**;
o vencedor de cada posição vai pro `.env` (orquestrador) ou `REGISTRY`
(forecasters). Re-executa quando: sair modelo novo, mudar requisito de
latência/VRAM, ou após 6 meses (drift).

> **Resumo do julgamento:**
> Não existe "melhor modelo absoluto" — só **melhor combinação de posições**
> dado o budget de hardware (RTX 5060 Ti 16 GB), o domínio (SINAM/violência)
> e o objetivo principal (análise retrospectiva, não prospectiva).

---

## 1. Posições e candidatos

A arquitetura tem 3 posições funcionalmente distintas. Um mesmo modelo
**pode** ocupar mais de uma, mas a avaliação trata cada slot
independentemente.

```
┌─────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────┐
│   POSIÇÃO 1         │    │  POSIÇÃO 2               │    │  POSIÇÃO 3           │
│   ORQUESTRADOR      │───▶│  RETROSPECTIVA           │───▶│  PROSPECTIVA         │
│   (LLM com tools)   │    │  ("explica o passado")   │    │  ("projeta futuro")  │
│   ex: Qwen3-8B      │    │  ex: ChatTime, RandomFor │    │  ex: Chronos-2, ETS  │
└─────────────────────┘    └──────────────────────────┘    └──────────────────────┘
```

### Matriz consolidada (candidatos × posições)

| Modelo               | Tipo            | P1 Orquest. | P2 Retrosp.  | P3 Prosp. | VRAM   | Lat./turno |
|----------------------|-----------------|:---:|:---:|:---:|--------|------------|
| **Qwen3-8B-Instruct**| LLM tool-calling | ✅ default  | ⚪ não recomendado | ❌  | 5 GB   | 5–15 s     |
| Llama 3.3 70B Q4     | LLM grande      | ⭕ teste    | ⭕ teste     | ❌  | ~38 GB | 30–90 s    |
| Qwen3 14B            | LLM médio       | ⭕ teste    | ⭕ teste     | ❌  | 9 GB   | 15–30 s    |
| Gemma 3 12B          | LLM com PT-BR   | ⭕ teste    | ⭕ teste     | ❌  | 8 GB   | 12–25 s    |
| Phi-4 14B            | LLM Microsoft   | ⭕ teste    | ⭕ teste     | ❌  | 9 GB   | 15–30 s    |
| **Chronos-2** (120M) | Foundation TS   | ❌          | ⚪ via comitê | ✅ default | 1 GB | 0.2 s     |
| **ChatTime-1-7B**    | LLM-for-series  | ❌          | ✅ candidato | ✅  | 13 GB  | 60–150 s   |
| TimesFM 500M         | Foundation TS   | ❌          | ⚪          | ⭕ teste | 1 GB   | 0.3 s      |
| Moirai 2.0           | Foundation TS   | ❌          | ⚪          | ⭕ teste | 1 GB   | 0.5 s      |
| **ETS (statsmodels)**| Estatístico     | ❌          | ✅ baseline  | ✅ baseline | 0     | <0.1 s   |
| Seasonal Naive       | Trivial         | ❌          | ✅ sanity    | ✅ sanity   | 0     | <0.01 s  |
| **Random Forest**    | Tabular ML      | ❌          | ✅ candidato | ⭕ via features | 0  | <1 s    |
| XGBoost / LightGBM   | Tabular ML      | ❌          | ✅ candidato | ⭕         | 0     | <1 s     |
| Regressão logística  | Linear          | ❌          | ✅ baseline  | ❌         | 0     | <0.1 s   |

✅ = atual ou recomendado · ⭕ = candidato a testar · ⚪ = funciona mas
fora do mainstream para a posição · ❌ = não aplicável

> **Random Forest na posição 2:** entra como candidato porque "retrospectiva"
> aqui significa **explicar o passado conhecido** com features estruturadas
> (mês, UF, sexo, etc.) — domínio onde árvores costumam dominar quando há
> tabular features. Pra ser comparado, criar um adapter que cabe no
> `src/series_models/` (ver §6.3).

---

## 2. Critérios de avaliação por posição

Cada critério é normalizado em **0–100** e ponderado conforme a tabela.

### Posição 1: Orquestrador

| Critério                                           | Peso | Como medir |
|----------------------------------------------------|:----:|------------|
| **Tool-calling correctness**                       | 35%  | % de cases onde a sequência de tools chamadas = `expected_tool_chain` (allowing reordering of independent steps). Mede em conjunto de 50 perguntas SINAM (§4). |
| **Routing geográfico**                             | 15%  | % de cases onde município/UF/Brasil foi corretamente identificado (sem o `_maybe_rewrite_tool_call` precisar entrar). |
| **Latência por turno**                             | 15%  | Mediana p50 + p95 em GPU local. Penaliza p95 > 30 s. |
| **Qualidade conversacional PT-BR**                 | 15%  | Eval humano (2 avaliadores) numa escala 1–5: clareza, ausência de jargão (WAPE/MAPE etc.), prosa narrativa. Inter-annotator agreement (Cohen κ ≥ 0.6). |
| **Resistência a alucinação**                       | 10%  | Detector regex no output: % de afirmações numéricas que constam no `tool_payload.result` (não inventadas). |
| **Robustez multi-turno**                           | 10%  | Em conversas de 3+ rodadas, % onde mantém o filtro/contexto correto. |

### Posição 2: Modelo Retrospectivo

"Retrospectivo" = explicar/classificar/sumarizar **o que já aconteceu** numa
série ou conjunto de notificações.

| Critério                                       | Peso | Como medir |
|------------------------------------------------|:----:|------------|
| **WAPE retrospectivo (walk-forward)**          | 30%  | Backtest com 3 folds, horizonte 6, na bateria de 30 séries SINAM (§4.2). |
| **Calibração de incerteza**                    | 15%  | Cobertura empírica do intervalo p10–p90 (alvo: 80% ± 5%). |
| **Interpretabilidade**                         | 15%  | Categórico (0/50/100): explica decisões? RF dá feature importance, ETS dá decomposição, LLM dá narrativa. |
| **Robustez a outliers / regimes**              | 10%  | WAPE em séries com mudança de regime conhecida (5 séries marcadas). |
| **Latência por série**                         | 10%  | p95 do tempo de backtest+treino. |
| **Custo (memória)**                            | 10%  | VRAM/RAM pico. |
| **Capacidade de dar diagnóstico estrutural**   | 10%  | Identifica sazonalidade lag certo? Tendência? Outlier? Comparado a `analyze_series` (gold). |

### Posição 3: Modelo Prospectivo

"Prospectivo" = projetar para o futuro. **Hoje não é o caso de uso primário**
do projeto, mas a posição é avaliada para casos legítimos.

| Critério                                       | Peso | Como medir |
|------------------------------------------------|:----:|------------|
| **WAPE / MAPE prospectivo (out-of-sample real)** | 30%  | Treina até cut-off histórico, prevê N pontos, compara com realização posterior conhecida. |
| **Calibração de quantis (p10/p50/p90)**        | 20%  | Cobertura empírica. |
| **Cold-start (séries curtas n<60)**            | 15%  | WAPE em 8 séries curtas marcadas. |
| **Robustez a regimes mistos**                  | 15%  | WAPE em séries com pandemia 2020-22 (mudança de regime). |
| **Latência**                                   | 10%  | p95. |
| **Manutenção / facilidade de adapter**         | 10%  | Pacote ativo? Última release < 12 meses? API estável? |

---

## 3. Categorias de benchmark (3 famílias)

Aplicar **as três** complementarmente. Nenhuma é suficiente sozinha.

### 3.1 Preferência humana (qualidade conversacional)

Apenas Posição 1. Janela curta (10–20 perguntas SINAM blindadas).

- **Procedimento:** duas saídas A vs B do mesmo prompt, ordem cega, dois
  avaliadores votam. Win-rate computado por modelo. **Inspiração:**
  [Chatbot Arena](https://lmarena.ai/).
- **Custo:** ~3 h de pessoa para 50 votos × 2 avaliadores.
- **Métrica:** Bradley-Terry score normalizado 0–100.

### 3.2 Correção objetiva pública

Sanity check que o modelo não regrediu em capacidade genérica.

| Categoria               | Benchmark recomendado          | Posição |
|-------------------------|--------------------------------|---------|
| Tool calling            | **BFCL v3** (Berkeley)         | P1      |
| Raciocínio              | ARC-AGI (mini-set), GSM8K (PT-BR translation) | P1 |
| Long-context            | LongBench v2 (subset PT-BR)    | P1      |
| Forecast zero-shot      | **GIFT-Eval**, fev-bench       | P3      |
| QA fechado              | TruthfulQA (PT-BR)             | P1      |

Cada um roda **uma vez por modelo** com seu protocolo oficial. Resultado
serve apenas pra eliminar candidatos catastroficamente piores que o
incumbent — não pra ranking primário.

### 3.3 Domínio (SINAM) — **prioridade #1**

O dataset proprietário de 50 perguntas + 30 séries é o que decide.
Detalhado na §4.

---

## 4. Conjunto de avaliação (golden dataset)

### 4.1 Tipologia de perguntas (Posição 1, total 60)

Salvar em `tests/benchmark/perguntas_orquestrador.csv`.

| Categoria                                | N  | Exemplo |
|------------------------------------------|----|---------|
| Contagem factual nacional                | 6  | "Quantos casos de violência infantil no Brasil em 2024?" |
| Contagem factual UF (sigla)              | 6  | "Casos em SE em 2023" |
| Contagem factual UF (nome estendido)     | 6  | "Notificações em Pernambuco" |
| Contagem município (não ambíguo)         | 5  | "Casos em Aracaju" |
| Contagem município (ambíguo)             | 5  | "Bom Jesus" (existe em 11 UFs) |
| Filtros demográficos (sexo + idade)      | 6  | "Crianças do sexo feminino vítimas em SP" |
| Filtros de tipo de violência             | 6  | "Tortura por UF em 2024" |
| Comparação temporal (anos)               | 4  | "2020 vs 2024 em violência sexual" |
| Análise retrospectiva (forecast)         | 6  | "Evolução de violência psicológica em RJ" |
| Edge case: sem dado                      | 4  | "Sequestro em Sergipe" (não existe no SINAM) |
| Edge case: vazio/short circuit           | 4  | "" / "oi" / "schema" |
| Multi-turno (depende de turno anterior)  | 2  | "E em 2024?" após pergunta sobre 2023 |

Cada pergunta tem schema:

```jsonc
{
  "id": "q-001",
  "category": "uf_nome",
  "question": "É correto afirmar que em Sergipe os casos de abuso sexual diminuíram?",
  "expected_tool_chain": ["relatorio_uf"],
  "forbidden_tools": ["relatorio_municipio", "relatorio_brasil"],
  "expected_args_contain": {"relatorio_uf": {"uf": "SE"}},
  "expected_filters_contain": {"violencia_sexual": true},
  "gold_numbers": [291, 321, 424, 643, 721, 796],   // por ano
  "gold_answer_keywords": ["crescente", "aumento", "não diminuíram"],
  "forbidden_keywords": ["diminuíram", "queda", "redução"],
  "max_latency_seconds": 30
}
```

### 4.2 Bateria de séries (Posições 2 e 3, total 30)

Salvar em `tests/benchmark/series_sinam.json`.

| Tipo de série            | N  | Exemplo `filters` |
|--------------------------|----|-------------------|
| UF mensal (5 anos+)      | 8  | `{uf: SP}`, `{uf: SE}`, ... |
| Tipo de violência mensal | 5  | `{violencia_sexual: true}` |
| Cruzamento UF + tipo     | 5  | `{uf: SP, violencia_fisica: true}` |
| Município capital        | 4  | `{municipio_nome: Aracaju}` |
| Município pequeno        | 3  | `{municipio_nome: Malhador}` (escasso) |
| Demográfico              | 3  | `{sexo: F, faixa_etaria: 10-14}` |
| Regime com pandemia      | 2  | série diária 2019-2021 com quebra COVID |

Cada série armazena: `dates`, `values`, freq, e **um cut-off** após o qual os valores ficam reservados como ground truth (não vistos pelo modelo durante treino).

### 4.3 Eval humano (Posição 1)

20 perguntas selecionadas das 60. Saídas A vs B mostradas em ordem aleatória.
Use template em `tests/benchmark/human_eval_template.md`.

---

## 5. Harness reprodutível

### 5.1 Estrutura de pastas

```
tests/benchmark/
├── perguntas_orquestrador.csv   # 60 cases p/ P1
├── series_sinam.json            # 30 séries p/ P2 e P3
├── human_eval_template.md
├── runners/
│   ├── run_orquestrador.py      # roda P1
│   ├── run_retrospectiva.py     # roda P2
│   └── run_prospectiva.py       # roda P3
├── results/
│   └── <YYYY-MM-DD>_<modelo>/
│       ├── per_question.csv
│       ├── per_series.csv
│       └── summary.json
└── reports/
    └── <YYYY-MM-DD>_benchmark.md
```

### 5.2 Orquestrador (P1)

`tests/benchmark/runners/run_orquestrador.py`:

```python
"""Orchestrator benchmark: roda 60 perguntas em N candidatos LLM."""
import csv, json, time
from pathlib import Path
from chat.orchestrator import chat as run_chat   # reusa o orquestrador real

CANDIDATES = [
    ("qwen3:8b",      {}),               # baseline (atual)
    ("qwen3:14b",     {}),
    ("llama3.3:70b-instruct-q4_K_M", {}),
    ("gemma3:12b",    {}),
    ("phi4:14b",      {}),
]

def evaluate_question(case: dict, model: str) -> dict:
    t0 = time.time()
    r = run_chat([{"role":"user","content": case["question"]}],
                 forecaster="chronos2", model=model)
    elapsed = time.time() - t0

    tools_called = [e.name for e in r.tool_events]
    # critérios
    correct_chain   = set(tools_called) >= set(case["expected_tool_chain"])
    no_forbidden    = all(t not in tools_called for t in case.get("forbidden_tools", []))
    args_ok         = _args_match(r.tool_events, case.get("expected_args_contain", {}))
    has_gold_nums   = _check_numbers_in_text(r.final_text, case.get("gold_numbers", []))
    no_forbidden_kw = not any(kw.lower() in r.final_text.lower()
                              for kw in case.get("forbidden_keywords", []))
    has_gold_kw     = any(kw.lower() in r.final_text.lower()
                          for kw in case.get("gold_answer_keywords", []))

    return {
        "id": case["id"],
        "model": model,
        "elapsed_s": round(elapsed, 2),
        "rounds": r.rounds,
        "tools_called": "|".join(tools_called),
        "correct_chain": correct_chain,
        "no_forbidden": no_forbidden,
        "args_ok": args_ok,
        "gold_nums_present": has_gold_nums,
        "gold_kw_present": has_gold_kw,
        "no_forbidden_kw": no_forbidden_kw,
        "final_text": r.final_text,
    }

def score(rows: list[dict]) -> dict:
    """Aggregate as percentages 0-100 per criterion."""
    n = len(rows)
    return {
        "tool_correctness": 100 * sum(r["correct_chain"] for r in rows) / n,
        "no_hallucination": 100 * sum(r["no_forbidden_kw"] for r in rows) / n,
        "gold_numbers":     100 * sum(r["gold_nums_present"] for r in rows) / n,
        "p50_latency_s":    sorted(r["elapsed_s"] for r in rows)[n//2],
        "p95_latency_s":    sorted(r["elapsed_s"] for r in rows)[int(n*0.95)],
    }

def main():
    cases = list(csv.DictReader(open("tests/benchmark/perguntas_orquestrador.csv")))
    for model, _ in CANDIDATES:
        rows = [evaluate_question(c, model) for c in cases]
        outdir = Path(f"tests/benchmark/results/{date.today()}_{model.replace(':','_')}")
        outdir.mkdir(parents=True, exist_ok=True)
        with open(outdir/"per_question.csv","w",newline="") as f:
            csv.DictWriter(f, rows[0].keys()).writeheader()
            csv.DictWriter(f, rows[0].keys()).writerows(rows)
        json.dump(score(rows), open(outdir/"summary.json","w"), indent=2)
```

### 5.3 Retrospectivo (P2) e Prospectivo (P3)

`run_retrospectiva.py`: itera 30 séries × N candidatos via
`walk_forward_backtest` reutilizando `src/analytics/metrics.py`. Output:
`per_series.csv` com `wape, mape, rmse, mae, n_folds` por (modelo, série).

`run_prospectiva.py`: igual mas com cut-off **fixo** e prevê o "futuro real"
(período reservado em `series_sinam.json`).

### 5.4 Random Forest como forecaster (P2/P3)

Para entrar no mesmo harness, criar:

```python
# src/series_models/random_forest_adapter.py
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor
from .base import ForecastOutput

class RandomForestForecaster:
    label = "Random Forest (features mês + lag1-12)"
    description = "Tabular ML com features sazonais. Rápido e interpretável."
    supports_qa = False

    def __init__(self, n_estimators=400, max_depth=10):
        self.kw = dict(n_estimators=n_estimators, max_depth=max_depth,
                       random_state=0, n_jobs=-1)

    def _features(self, idx, lookback=12):
        df = pd.DataFrame(index=idx)
        df["month"] = df.index.month
        df["year"]  = df.index.year
        df["weekday"] = df.index.weekday
        return df

    def predict(self, series, horizon, context=None):
        v = np.asarray(series, dtype=float)
        n = len(v)
        # Build training table: rows are timesteps t >= lookback
        lb = 12
        if n < lb + horizon:
            return ForecastOutput(values=np.full(horizon, v.mean()), model="random_forest")
        X, y = [], []
        for t in range(lb, n):
            X.append(v[t-lb:t])
            y.append(v[t])
        X = np.array(X); y = np.array(y)
        rf = RandomForestRegressor(**self.kw).fit(X, y)
        # iterative one-step-ahead
        history = list(v)
        preds = []
        for _ in range(horizon):
            x_new = np.array(history[-lb:]).reshape(1, -1)
            yhat = float(rf.predict(x_new)[0])
            preds.append(yhat); history.append(yhat)
        return ForecastOutput(values=np.array(preds), model="random_forest")

    def analyze(self, series, question):
        return "", []
```

Registrar em `src/series_models/__init__.py`:

```python
"random_forest": RandomForestForecaster,
```

Pronto — entra no `walk_forward_backtest` automaticamente.

### 5.5 Como rodar tudo

```powershell
# pré-requisitos
.\venv\Scripts\Activate.ps1
ollama pull qwen3:14b llama3.3:70b-instruct-q4_K_M gemma3:12b phi4:14b
pip install scikit-learn  # se for testar Random Forest

# orquestrador
python tests/benchmark/runners/run_orquestrador.py

# retrospectivo + prospectivo
python tests/benchmark/runners/run_retrospectiva.py
python tests/benchmark/runners/run_prospectiva.py

# relatório final consolida
python tests/benchmark/runners/build_report.py
```

`build_report.py` lê tudo de `results/`, ranqueia por posição usando pesos
de §2, e gera `reports/<data>_benchmark.md` com:
- Tabela do ranking por posição
- Gráficos de WAPE por modelo × série
- Win-rate Bradley-Terry do eval humano
- Recomendação final

---

## 6. Metodologia de pontuação

### 6.1 Normalização

Cada critério **bruto** → escala 0–100:

```
score(c) = 100 * (max(c) - obs(c)) / (max(c) - min(c))     # se "menor é melhor" (latência, WAPE)
score(c) = 100 * (obs(c) - min(c)) / (max(c) - min(c))     # se "maior é melhor" (correctness)
```

### 6.2 Score ponderado por posição

```
score_position(modelo) = Σ peso_critério × score_critério_normalizado
```

Exemplo concreto (Orquestrador):
```
score_P1(model) = 0.35 * tool_correctness
                + 0.15 * routing_geo
                + 0.15 * latency_p95
                + 0.15 * qualidade_PTBR
                + 0.10 * anti_hallucination
                + 0.10 * multi_turn
```

### 6.3 Confidence interval

Bootstrap de 1000 amostras sobre o conjunto de perguntas/séries dá um IC 95%
em cada score. Para declarar **vencedor**: o limite inferior do IC do
candidato precisa ser maior que o limite superior do IC do incumbente.
Caso contrário, é empate → mantém o atual (princípio de Occam).

---

## 7. Critério de **adoção** (gatilho de mudança)

Em cada posição, adotar o candidato vencedor SE:

1. **Posição 1 (Orquestrador)**: score > incumbente + 10 pts E latência p95 ≤ 2× incumbente.
2. **Posição 2 (Retrospectivo)**: WAPE médio ≥ 3 pts melhor no IC 95% E interpretabilidade ≥ incumbente − 10.
3. **Posição 3 (Prospectivo)**: WAPE médio ≥ 5 pts melhor no IC 95% E cobertura p10–p90 dentro de 75–85%.

Senão, **mantém o atual** mesmo que um critério individual seja melhor.

---

## 8. Checklist de execução (passo a passo)

Marque cada item conforme avança.

### Setup (1×)
- [ ] Clonar dataset gold (`tests/benchmark/perguntas_*.csv`, `series_sinam.json`)
- [ ] `ollama pull` de todos candidatos LLM
- [ ] `pip install scikit-learn xgboost lightgbm` se for testar tabular ML
- [ ] Criar `src/series_models/random_forest_adapter.py` (§5.4)
- [ ] Pinar versões em `requirements.benchmark.txt`

### Posição 1 — Orquestrador (~1 dia)
- [ ] Rodar `run_orquestrador.py` para cada candidato
- [ ] Verificar logs: `results/<data>_<modelo>/per_question.csv`
- [ ] Eval humano (20 perguntas, 2 avaliadores, votos cegos)
- [ ] Calcular score ponderado por candidato
- [ ] Verificar IC 95% via bootstrap
- [ ] Aplicar gatilho de adoção (§7.1)
- [ ] Documentar decisão em `reports/<data>_p1_orquestrador.md`

### Posição 2 — Retrospectivo (~4 h)
- [ ] Rodar `run_retrospectiva.py` para Chronos-2, ChatTime, ETS, Random Forest, XGBoost
- [ ] Conferir cobertura p10–p90 nas 30 séries
- [ ] Avaliar interpretabilidade (rubrica em `tests/benchmark/interp_rubric.md`)
- [ ] Score ponderado
- [ ] Aplicar gatilho (§7.2)
- [ ] Documentar em `reports/<data>_p2_retrospectivo.md`

### Posição 3 — Prospectivo (~3 h)
- [ ] Rodar `run_prospectiva.py` para Chronos-2, ChatTime, TimesFM, Moirai, ETS
- [ ] Comparar WAPE out-of-sample real
- [ ] Avaliar cobertura quantil
- [ ] Score ponderado
- [ ] Aplicar gatilho (§7.3)
- [ ] Documentar em `reports/<data>_p3_prospectivo.md`

### Consolidação
- [ ] Rodar `build_report.py` para gerar `reports/<data>_benchmark.md`
- [ ] Comparar com benchmarks públicos (BFCL, GIFT-Eval) como sanity
- [ ] Atualizar `.env` (`OLLAMA_MODEL`) se P1 mudou
- [ ] Atualizar `_AUTO_BASELINES` em `chat/tools.py` se P2/P3 mudaram
- [ ] Atualizar `docs/architecture.svg` se houve troca
- [ ] Commit: `benchmark <YYYY-MM-DD>: <vencedores ou "sem mudança">`

### Re-execução periódica
- [ ] A cada release nova de Qwen/Llama/Chronos: rodar §Posição correspondente
- [ ] A cada 6 meses: rodar checklist completo (drift do domínio SINAM)
- [ ] A cada novo modelo "candidato sério" na comunidade: incluir em CANDIDATES

---

## 9. Apêndice: como interpretar resultados ambíguos

### "Modelo A vence latência, B vence acurácia"
Use o gatilho de adoção (§7) — ele penaliza trade-off ruim com regras
duras. Se ambos passam, vence o de menor latência (operação local = recurso
escasso).

### "Score igual no bootstrap"
Mantém o incumbente. Empate ≠ motivo para mudar (custo de troca > ganho).

### "Random Forest bate Chronos-2 retrospectivamente"
É plausível: RF com features sazonais (lag-1..12, mês, ano) explica
quase tudo de séries com tendência+sazonalidade clara, que é o caso
SINAM. Adote para P2 **se** interpretabilidade também ganhar. Mantenha
Chronos-2 em P3 (prospectivo) — RF extrapola mal.

### "Llama 70B Q4 ganha em qualidade mas perde latência"
70B em RTX 5060 Ti 16 GB roda swap → 60–120 s/turno. Inaceitável pra chat
interativo. Adote apenas se houver hardware ≥ 24 GB ou se o caso de uso
mudar para batch (não tempo real).

---

## 10. Como rodar **hoje** (estado do código)

A infra-estrutura para o benchmark **já está pronta** (forecasters pluggable
+ analytics + walk_forward_backtest). O que falta é o conjunto gold de
perguntas/séries. Estado atual:

| Item                                       | Status |
|--------------------------------------------|--------|
| `src/series_models/` com 7 backends pluggable | ✅ pronto |
| `src/analytics/walk_forward_backtest`      | ✅ pronto |
| Adapter Random Forest                      | ✅ adicionado nessa rodada |
| Adapter Remote API (OpenAI/custom HTTP)    | ✅ stub adicionado |
| Tools de teste no orchestrator             | ✅ `analyze_series`, `backtest_forecast`, `previsao_automatica` |
| Pasta `tests/benchmark/` com cases gold    | ❌ falta — você popula |
| Runners `run_orquestrador.py` etc.         | ❌ falta — pseudo-código pronto na §5 |
| `build_report.py`                          | ❌ falta — esqueleto pronto |

### Modo mais simples (sem montar o gold ainda) — comparação ad-hoc

Funciona já. Abre o chat, faz a mesma pergunta com cada forecaster do
dropdown, anota o WAPE de cada uma na página `/chat/relatorio/`. Não é
estatisticamente rigoroso mas dá um senso direcional rápido.

### Modo benchmark (passo a passo) — gera resultados auditáveis

1. **Criar a pasta**:
   ```powershell
   mkdir tests\benchmark\runners
   mkdir tests\benchmark\results
   ```

2. **Popular o gold dataset**. Comece pequeno (15-20 perguntas) baseado nas
   que você já testou na thread. Salve em
   `tests/benchmark/perguntas_orquestrador.csv` no schema da §4.1.

3. **Bateria de séries** (`tests/benchmark/series_sinam.json`) — pode ser
   gerada por script a partir do próprio Postgres/SQLite, capturando 30
   filtros distintos.

4. **Copiar os runners** dos pseudo-códigos da §5 para arquivos `.py`
   correspondentes.

5. **Rodar**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   python tests\benchmark\runners\run_orquestrador.py
   python tests\benchmark\runners\run_retrospectiva.py
   python tests\benchmark\runners\run_prospectiva.py
   ```

6. **Consolidar e decidir** com o gatilho de adoção da §7.


## 11. Adicionar um modelo externo (API online) à stack

A pasta `src/series_models/remote_api_adapter.py` foi adicionada para isso. Ele
delega a um endpoint HTTP qualquer que retorne JSON `{"predicted":[...],
"p10":[...], "p50":[...], "p90":[...]}`. Funciona com:

- **OpenAI/Anthropic** via wrapper próprio (você expõe um endpoint que chama a
  API deles internamente e devolve o JSON).
- **Replicate / Together / Modal** hospedando Chronos/TimesFM/Moirai.
- **TimesFM Google Cloud** (Vertex AI) com wrapper.
- **Endpoint próprio** rodando em outro servidor.

### Configuração via `.env`

```ini
REMOTE_FORECASTER_URL=https://meu-endpoint.com/forecast
REMOTE_FORECASTER_API_KEY=sk-...
REMOTE_FORECASTER_LABEL=TimesFM @ Vertex AI
REMOTE_FORECASTER_TIMEOUT=60
```

Restart o servidor. A opção **"TimesFM @ Vertex AI"** (o label que você setou)
aparece no dropdown "Forecast" da thread. Selecione-a e qualquer
`relatorio_uf`/`previsao_automatica` vai chamar o seu endpoint em vez dos
modelos locais.

### Para LLMs orquestradores online (Claude, GPT-4)

O Ollama Python client aceita endpoints OpenAI-compatible diretamente. Para
trocar pro Claude/GPT-4, ajuste `OLLAMA_HOST` no `.env` para um
**gateway/proxy OpenAI-compatible** (ex: LiteLLM, OpenRouter). O orquestrador
nem percebe a troca. Modelos no Anthropic API direto exigem um wrapper porque
o formato de tool calling difere — passa pelo LiteLLM.


## 12. Referências e benchmarks externos

- BFCL v3: <https://gorilla.cs.berkeley.edu/leaderboard.html> — tool calling
- GIFT-Eval: <https://huggingface.co/spaces/Salesforce/GIFT-Eval> — séries temporais
- Chatbot Arena: <https://lmarena.ai/> — preferência humana
- ARC-AGI: <https://arcprize.org/> — raciocínio
- LongBench v2: <https://github.com/THUDM/LongBench> — long context
- M5 / M4: clássicos de TS forecasting
- fev-bench: paper Chronos-2 (Amazon, 2025)
