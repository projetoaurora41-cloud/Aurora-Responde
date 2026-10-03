# 🗂️ Kanban — Projeto Aurora

Quadros do que foi feito no projeto, organizados por **frente de trabalho**.
Atualizado em **2026-07-11**.

- **✅ Concluído** — ancorado no histórico do Git (hash do commit entre parênteses).
- **🔄 Em andamento** — inferido do cluster de commits mais recente.
- **📋 Backlog** — sugestões derivadas das limitações documentadas em `docs/`.
  Não são compromissos; o time deve revisar/priorizar.

> As colunas **Em andamento** e **Backlog** são um ponto de partida derivado da
> documentação e do histórico — ajuste conforme o planejamento real.

---

## 📊 Visão geral

| Frente                              | ✅ | 🔄 | 📋 | Responsável       |
|-------------------------------------|----|----|----|-------------------|
| 1 · Plataforma & Infraestrutura     | 5  | 0  | 2  | Núcleo            |
| 2 · Séries Temporais (orquestrador) | 6  | 0  | 4  | Hernandison       |
| 3 · Benchmark & LLM-as-judge        | 7  | 0  | 1  | Núcleo            |
| 4 · Dados SINAN (RAG + SQL)         | 4  | 0  | 1  | Marcelo West      |
| 5 · Dados Jurídicos                 | 7  | 1  | 1  | Eduardo           |
| 6 · Datas Comemorativas             | 4  | 0  | 1  | Rafael            |
| 7 · ETL SINAM (.dbc)                | 1  | 0  | 1  | Núcleo            |
| 8 · Documentação                    | 5  | 0  | 0  | Núcleo            |

---

## 1 · Plataforma & Infraestrutura

**✅ Concluído**
- [x] Estrutura inicial multi-chat do Aurora (`620e6ad`)
- [x] Consolidação em **um único PostgreSQL** + busca vetorial `pgvector` (`7d53fa4`)
- [x] Busca semântica no catálogo de consultas + embeddings compartilhados (`c2cf002`)
- [x] Registry de chats + fluxo oficial para criar novo chat Django (`636b7fe`)
- [x] `.gitignore` (protege `.env` e artefatos) (`9c29fd2`)

**📋 Backlog**
- [ ] Deploy: `gunicorn --workers 1` (singleton do modelo em memória) — `docs/arquitetura.md`
- [ ] Remover legado SQLite após validação da migração (`migrate_sqlite_to_pg`)

---

## 2 · Séries Temporais — orquestrador + forecasters  ·  _Hernandison_

**✅ Concluído**
- [x] Orquestrador LLM (Qwen3 via Ollama) + 11 ferramentas (`620e6ad`)
- [x] Comitê pluggable via REGISTRY/Protocol: Chronos-2, ChatTime, ETS, Seasonal Naive, Drift, Random Forest
- [x] Pipeline `auto_forecast`: análise → backtest walk-forward → seleção `argmin(WAPE)` → previsão `p10/p50/p90`
- [x] Camada Analytics sem IA (`analyze_series`, `walk_forward_backtest`, `metrics`)
- [x] Refino do orquestrador: enforcement de filtro de violência + geo + anti-jargão (`ecb3533`)
- [x] Refino (parte 2): cidade em `relatorio_brasil` + limpa filtro genérico (`3a9636c`)

**📋 Backlog**
- [ ] Adicionar TimesFM / Moirai / Prophet (novo adapter + registrar chave) — `docs/arquitetura.md`
- [ ] Streaming de resposta no chat — `docs/chat.md` (limitações)
- [ ] Cancelamento de requisição (fechar aba não interrompe o servidor)
- [ ] Tratar convergência do `statsmodels` em séries muito curtas (n < 24)

---

## 3 · Benchmark & LLM-as-judge

**✅ Concluído**
- [x] Feature de juiz (LLM-as-judge) portada do Projeto_Sinam (`7d0d5cf`)
- [x] Juiz Claude lendo `ANTHROPIC_API_KEY` do `.env` (`d2ad807`)
- [x] Juiz Gemini + tratamento de rate-limit (`f9da4c0`)
- [x] `seed_judges`: grava a rubrica completa no system prompt (`e3549da`)
- [x] Benchmark rodável: traz `tests/benchmark` + corrige paths (`9eea297`)
- [x] Corrige 404 do `run_detail` (BASE aponta pra raiz do repo) (`3c88010`)
- [x] Estabiliza benchmark: subprocesso isolado + polling do `run_status` (`ca4b0c6`)

**📋 Backlog**
- [ ] Relatório comparativo automático entre execuções (histórico de benchmark)

---

## 4 · Dados SINAN — RAG + SQL  ·  _Marcelo West_

**✅ Concluído**
- [x] Chat Dados SINAN (RAG + SQL) como app Django (`381f89e`, PR #1)
- [x] Debug visível, aviso de API e filtro por estado (`977f612`)
- [x] Correção de bug do Marcelo (`8656ffd`)
- [x] Correção de bug (`59162e0`)

**📋 Backlog**
- [ ] Cache de contexto RAG por pergunta recorrente

---

## 5 · Dados Jurídicos  ·  _Eduardo_

**✅ Concluído**
- [x] Novo chat estilo Open WebUI (`e58c637`)
- [x] Detecta Ollama local (SDK ≥ 0.4); remove Ollama do `dados_sinam` (`7db4c9b`)
- [x] Conecta ao Ollama ignorando proxy (`trust_env=False`) (`31880d0`)
- [x] Busca no banco consulta o SINAM e enriquece o contexto (`fd974a7`)
- [x] Entende intervalos de idade na pergunta (`idade_anos`) (`0c14939`)
- [x] SINAM entende região e mês; reduz alucinação de período (`352b05e`)
- [x] Melhorias gerais no projeto do Eduardo (`6f10382`)

**🔄 Em andamento**
- [ ] Refino da compreensão de linguagem natural / anti-alucinação de período

**📋 Backlog**
- [ ] Cobrir mais dimensões da pergunta (sexo, tipo de violência, raça)

---

## 6 · Datas Comemorativas (eventos)  ·  _Rafael_

**✅ Concluído**
- [x] Migra chatbot de eventos para o projeto (`ab999ce`, PR #2)
- [x] Renomeia app `carnaval` → `datas_comemorativas` (`10e2676`)
- [x] Ajuste do nome do módulo (`8e100f5`)
- [x] Ajustes de dependências do banco pós-rebase (`a4266d6`)

**📋 Backlog**
- [ ] Ampliar catálogo de datas comemorativas além do Carnaval

---

## 7 · ETL SINAM (.dbc)

**✅ Concluído**
- [x] Importação `.dbc` popula todos os chats: tabela bruta + limpa + view + materializadas (`85eaceb`)

**📋 Backlog**
- [ ] Agendar/automatizar reimportação incremental do DataSUS

---

## 8 · Documentação

**✅ Concluído**
- [x] Estrutura inicial de docs + diagramas de arquitetura (`1bb8a52`)
- [x] Docs para banco único Postgres + Chat Dados SINAN (`0778957`)
- [x] Instruções para novo chat seguindo o fluxo oficial do Django (`636b7fe`)
- [x] Diagrama alto nível dos modelos — entrada → organização → saída (`docs/modelos_diagrama.md` + SVG/PNG)
- [x] Este quadro Kanban (`KANBAN.md`)

---

## 🔧 Transversal — UI/UX

**✅ Concluído**
- [x] Corrige layout dos chatbots (`5df0f1c`)
- [x] Diversos ajustes e correções de bugs (`28cb457`, `42d8e8f`, `2e49607`, `547d53b`, `3c1baba`)
