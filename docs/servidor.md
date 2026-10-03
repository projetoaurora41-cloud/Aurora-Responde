# Requisitos de servidor (Aurora Responde)

Dimensionamento para hospedar o **fork leve**: webapp Django + Ollama (Jurema-7B).
O **PostgreSQL é externo** (não entra na conta do servidor de aplicação). Como
não há forecasting (torch/Chronos/ChatTime) nem embeddings, os requisitos são
modestos.

## O que roda

| Componente | Onde | Custo |
|------------|------|-------|
| **Jurema-7B** (GGUF Q4, via Ollama) | GPU **ou** CPU | ~5 GB de VRAM/RAM |
| **webapp Django** | CPU | leve (~0,3 GB) |
| **Valkey** (cache/limites, opcional) | CPU | leve |
| **PostgreSQL** | **externo** | fora do servidor de app |

> Não há PyTorch, modelos HuggingFace nem pgvector. O único modelo é o Jurema-7B.

## Recomendações

| Cenário | CPU | RAM | GPU/VRAM | Disco |
|---------|-----|-----|----------|-------|
| **Com GPU** (respostas rápidas) | 4 vCPU | 8–16 GB | ≥ 6 GB (cabe o Jurema Q4) | ~15 GB |
| **Só CPU** (funciona, mais lento) | 8 vCPU | 16 GB | — | ~15 GB |

- A **VRAM** só importa para o Jurema; 6 GB já acomodam o Q4. Sem GPU, ele roda
  em CPU/RAM — a **1ª resposta** carrega o modelo (mais lenta); as seguintes são
  rápidas.
- **Disco**: ~5 GB do Jurema + a imagem/venv. O banco (grande) fica no servidor
  de PostgreSQL externo.
- **1 worker**: o deploy usa 1 processo de aplicação; o Ollama serve o modelo.

## Rede

- A aplicação (`:8000`) precisa alcançar o **Ollama** (`:11434`) e o
  **PostgreSQL** externo (host/porta do `.env`).
- Para expor na rede, inclua o IP em `DJANGO_ALLOWED_HOSTS` e rode
  `runserver 0.0.0.0:8000` (ou gunicorn em produção).
