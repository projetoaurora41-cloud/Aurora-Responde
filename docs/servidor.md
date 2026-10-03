# Requisitos de servidor (vCPU · RAM · GPU/VRAM · disco)

Dimensionamento para hospedar **toda a plataforma Aurora** (webapp Django +
PostgreSQL + modelos locais). Os números são estimativas ancoradas no que o
projeto realmente carrega — em especial:

- **ChatTime-1-7B** carrega **~13 GB** na primeira inferência
  ([`docs/troubleshooting.md`](troubleshooting.md)).
- **Qwen3-8B** (orquestrador via Ollama) recomenda **GPU ≥ 12 GB**
  ([`docs/chat.md`](chat.md)).
- **Marcelo (Dados SINAN)** e **Rafael (Datas Comemorativas)** usam **LLMs por
  API** (OpenAI/Gemini/Perplexity) → **não consomem GPU local**.

---

## 1. Quem consome recurso

| Componente | Dono | Onde roda | VRAM (GPU) | CPU/RAM |
|-----------|------|-----------|-----------|---------|
| **Qwen3-8B** (orquestrador, Ollama) | Hernandison | GPU local | ~5–6 GB (Q4) | leve |
| **ChatTime-1-7B** (QA série temporal) | Hernandison | GPU local | **~13 GB** (fp16) | mmap ~13 GB RAM |
| **Chronos-2** (120M) | Hernandison | GPU local | ~0,5–1 GB | leve |
| ETS · Seasonal Naive · Drift · Random Forest | Hernandison | **CPU** | — | leve |
| **Embeddings MiniLM-L12** (RAG/pgvector) | Hernandison, Marcelo | CPU por padrão (`*_EMBED_DEVICE=cpu`) | ~0,5 GB se cuda | ~0,3 GB |
| LLM externo GPT-4o-mini/Gemini/Perplexity | Marcelo | **API (nuvem)** | — | — |
| LLM por conversa (Ollama local **ou** API) | Eduardo | GPU local **se** usar Ollama; senão API | +~5 GB por modelo Ollama | leve |
| Google Gemini (`CarnavalLLMAssistant`) | Rafael | **API (nuvem)** | — | — |
| **PostgreSQL + pgvector** (~3,1 M linhas + VIOLBR bruto) | Núcleo | CPU | — | RAM p/ cache/índice |
| Django + gunicorn (**1 worker** = 1 cópia do modelo) | Núcleo | CPU | — | leve |

> **Pico de VRAM (tudo residente ao mesmo tempo):** ChatTime (~13) + Qwen3 (~6) +
> Chronos-2 (~1) + overhead/KV (~2) ≈ **~22 GB**. Por isso o alvo recomendado é
> uma GPU de **24 GB**.

---

## 2. Perfis de servidor

### 🟢 Recomendado (produção leve — todos os modelos residentes)
Cabe ChatTime + Qwen3 + Chronos-2 + embeddings ao mesmo tempo, sem swap.

| Recurso | Especificação |
|--------|----------------|
| **GPU** | **1× 24 GB VRAM** — RTX 4090 / RTX 3090 / RTX A5000 / **NVIDIA L4** ou A10 |
| **vCPU** | **16** |
| **RAM** | **64 GB** |
| **Disco** | **200 GB NVMe SSD** (cache HuggingFace ~30 GB + banco + VIOLBR) |
| SO | **Linux** (evita o `OSError 1455` de pagefile do Windows) · driver NVIDIA + CUDA 12.x |

### 🟡 Mínimo (dev / poucos usuários, uso sequencial)
Roda tudo, mas ChatTime e Qwen3 **não** ficam residentes juntos — o Ollama
descarrega o Qwen quando ocioso (troca mais lenta).

| Recurso | Especificação |
|--------|----------------|
| **GPU** | **1× 16 GB VRAM** — RTX 4060 Ti 16 GB / RTX A4000 |
| **vCPU** | **8** |
| **RAM** | **32 GB** |
| **Disco** | **100 GB SSD** |

### 🔵 Folgado (multiusuário / LLM local grande no chat do Eduardo)
Permite modelo Ollama grande (ex.: Llama-3.x 70B Q4 ≈ 40 GB) + o resto, ou
concorrência real de forecasts (cada worker gunicorn = +~13 GB de ChatTime).

| Recurso | Especificação |
|--------|----------------|
| **GPU** | **48 GB VRAM** (RTX A6000 / **L40S**) **ou** 2× 24 GB |
| **vCPU** | **32** |
| **RAM** | **128 GB** |
| **Disco** | **500 GB NVMe** |

### ⚪ Sem GPU (só APIs — demo/econômico)
Marcelo e Rafael funcionam 100% (LLM na nuvem). Eduardo funciona apontando para
API. **Séries Temporais funciona mas fica lento**: ChatTime/Chronos em CPU levam
**minutos** por inferência (aceitável só para demonstração).

| Recurso | Especificação |
|--------|----------------|
| **GPU** | nenhuma |
| **vCPU** | 8–16 |
| **RAM** | 32–64 GB (mmap ~13 GB do ChatTime + Postgres) |
| **Disco** | 100 GB SSD |

---

## 3. Observações de dimensionamento

- **A VRAM é o fator crítico**, não o vCPU. O restante (ETS, baselines, embeddings,
  Django, Postgres) é leve. Escolha a GPU primeiro.
- **12 GB só bastam se dispensar o ChatTime**: o Qwen3-8B cabe em 12 GB, mas o
  ChatTime-7B (fp16) precisa de ~13 GB. Sem ChatTime, o forecast usa Chronos-2/ETS
  normalmente (o ChatTime só faz o QA de múltipla escolha).
- **Concorrência = múltiplos ChatTime**: o deploy usa `gunicorn --workers 1` para
  compartilhar o singleton (~13 GB). Cada worker adicional recarrega o modelo →
  some +~13 GB de VRAM por worker se quiser forecasts paralelos.
- **PostgreSQL**: ~3,1 M notificações + tabelas VIOLBR brutas (~150 colunas × 5
  anos) + índices HNSW do pgvector. Reserve alguns GB de RAM para `shared_buffers`
  e o índice vetorial. Disco do banco: ~5–15 GB.
- **ETL `.dbc`**: a importação do DataSUS (`dbc_to_dbf` + bulk insert de milhões de
  linhas) é um pico transitório de CPU/RAM — não muda o perfil permanente.
- **CUDA**: `torch>=2.7.1` exige driver NVIDIA recente + CUDA 12.x. GPU Ampere ou
  mais nova (RTX 30/40, A-series, L4/L40) é o ideal.
- **Windows vs Linux**: o projeto roda no Windows (há workarounds para pagefile e
  proxy), mas para servidor de produção o **Linux** é mais estável para as cargas
  de GPU/mmap.

---

## 4. Resumo rápido

> **Alvo recomendado:** GPU **24 GB VRAM** · **16 vCPU** · **64 GB RAM** ·
> **200 GB NVMe**, Linux com CUDA 12.x.
> **Mínimo viável:** GPU 16 GB · 8 vCPU · 32 GB RAM · 100 GB SSD.
> **Sem GPU:** só para demo (forecasts em CPU levam minutos); chats de Marcelo e
> Rafael rodam plenos via API.
