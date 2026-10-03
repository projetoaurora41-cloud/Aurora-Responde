# Modelos e projetos por pesquisador

Visão **por pessoa** — destacando o projeto (chat) de cada pesquisador, os
modelos que cada um usa e o tipo de saída. Todos compartilham a mesma base de
dados (PostgreSQL `Aurola`).

> Complementa o diagrama transversal em [`modelos_diagrama.md`](modelos_diagrama.md)
> (entrada → organização → saída). Dono de cada chat vem do campo `owner` do
> `ChatType` registrado em cada `apps.py`.

![Modelos e projetos por pesquisador](modelos_por_pesquisador.svg)

<sub>Imagem: [`modelos_por_pesquisador.svg`](modelos_por_pesquisador.svg) (vetorial)
· [`img/modelos_por_pesquisador.png`](img/modelos_por_pesquisador.png) (alta
resolução). Fonte editável (Mermaid) abaixo.</sub>

---

## Diagrama

```mermaid
flowchart TB
  DB[("PostgreSQL Aurola — base compartilhada<br/>VIOLBR20-24 brutos · sinam_notificacao ~3.1M<br/>views · tabelas materializadas · embeddings pgvector")]

  %% ===================== HERNANDISON =====================
  subgraph H["Hernandison · Séries Temporais Retrospectiva"]
    direction TB
    HP["PROJETO: Chat Séries Temporais<br/>(orquestrador + 11 ferramentas)"]
    HQ{{"Qwen3-8B · Ollama (local)<br/>PAPEL: orquestrador (decide e narra)"}}
    HC["Comitê de forecasters · REGISTRY<br/>Chronos-2 · ChatTime-7B · ETS<br/>Seasonal Naive · Drift · Random Forest"]
    HA["Analytics (sem IA)<br/>analyze_series · backtest walk-forward · WAPE"]
    HE["Embeddings MiniLM-L12<br/>busca semântica no catálogo de SavedQuery"]
    HO["SAÍDA: previsão p10/p50/p90 + WAPE + badge<br/>· QA (a)(b)(c) via ChatTime · consulta factual"]
    HP --> HQ
    HQ -->|auto_forecast| HA --> HC --> HO
    HQ -->|catálogo| HE
    HQ -->|factual| HO
  end

  %% ===================== MARCELO =====================
  subgraph M["Marcelo West · Dados SINAN (RAG + SQL)"]
    direction TB
    MP["PROJETO: Chat Dados SINAN"]
    ME["Embeddings MiniLM-L12 · 384d · pgvector<br/>RAG — top-8 sentenças de contexto"]
    ML{{"LLM externo (escolha do usuário):<br/>GPT-4o-mini · Gemini 2.0-flash · Perplexity sonar-pro<br/>ou regras determinísticas (sem API)"}}
    MO["SAÍDA: SQL gerado + tabela de resultados<br/>+ resposta textual"]
    MP --> ME --> ML --> MO
  end

  %% ===================== EDUARDO =====================
  subgraph E["Eduardo · Dados Jurídicos (estilo Open WebUI)"]
    direction TB
    EP["PROJETO: Chat Dados Jurídicos"]
    EL{{"LLM plugável por conversa (model_id):<br/>Ollama local (llama3.1…) · Gemini · OpenAI<br/>· Conexões próprias (Groq/OpenRouter/vLLM/Ollama remoto)"}}
    ER["RAG por documento anexado (FTS/keywords)<br/>+ enriquecimento SINAM (sinam_service:<br/>ano, UF, região, mês, idade_anos)"]
    EO["SAÍDA: resposta jurídica em prosa<br/>(markdown, streaming) citando base legal"]
    EP --> EL
    ER --> EL --> EO
  end

  %% ===================== RAFAEL =====================
  subgraph R["Rafael · Datas Comemorativas (eventos)"]
    direction TB
    RP["PROJETO: Chatbot IA geral VIOLBR/SINAM<br/>foco em datas comemorativas (Carnaval)"]
    RL{{"Google Gemini<br/>CarnavalLLMAssistant"}}
    RF["Análise de eventos:<br/>daily_forecasts + event_forecasts<br/>(tabelas materializadas, com fallback)"]
    RG["General Analytics QA<br/>view + RAG de sentenças · LLM-SQL opcional"]
    RO["SAÍDA: resposta sobre padrões de violência<br/>em datas comemorativas / eventos"]
    RP --> RL
    RF --> RL
    RG --> RL --> RO
  end

  DB --> HP
  DB --> MP
  DB --> EP
  DB --> RP

  classDef db fill:#0b3b3b,stroke:#22d3ee,color:#e0f2fe;
  classDef llm fill:#312e81,stroke:#818cf8,color:#e6e8eb;
  classDef out fill:#14532d,stroke:#22c55e,color:#dcfce7;
  classDef proj fill:#3b2f0b,stroke:#fbbf24,color:#fef3c7;
  class DB db;
  class HQ,ML,EL,RL llm;
  class HO,MO,EO,RO out;
  class HP,MP,EP,RP proj;
```

---

## Tabela-resumo

| Pesquisador     | Projeto (app Django)        | Modelos usados                                                                                           | Entrada                                   | Saída                                                        |
|-----------------|-----------------------------|----------------------------------------------------------------------------------------------------------|-------------------------------------------|-------------------------------------------------------------|
| **Hernandison** | `series_temporais`          | Qwen3-8B (orquestrador) · Chronos-2 · ChatTime-7B · ETS · Seasonal Naive · Drift · Random Forest · Embeddings MiniLM · Analytics | Pergunta PT-BR + série temporal (Postgres) | Previsão `p10/p50/p90` + WAPE · QA `(a)(b)(c)` · factual     |
| **Marcelo West**| `dados_sinam`               | Embeddings MiniLM (RAG/pgvector) · GPT-4o-mini / Gemini 2.0-flash / Perplexity sonar-pro (ou regras)     | Pergunta PT-BR + contexto RAG + schema     | SQL gerado + tabela + resposta textual                      |
| **Eduardo**     | `dados_juridicos`           | LLM por conversa: Ollama local (llama3.1…) / Gemini / OpenAI / conexões próprias · RAG de documentos     | Pergunta + documentos anexados + SINAM     | Resposta jurídica em prosa (markdown, streaming) c/ base legal |
| **Rafael**      | `datas_comemorativas`       | Google Gemini (`CarnavalLLMAssistant`) · análise de eventos (forecasts) · General Analytics QA           | Pergunta + previsões de eventos + views    | Resposta sobre padrões em datas comemorativas / eventos     |

Todos leem e escrevem no **mesmo PostgreSQL `Aurola`**. As diferenças estão na
**estratégia de cada projeto**: Hernandison orquestra um comitê de modelos de
série temporal; Marcelo faz NL→SQL com RAG e LLM externo; Eduardo oferece um chat
plugável (qualquer LLM) com RAG de documentos; Rafael foca análise de eventos com
Gemini.
