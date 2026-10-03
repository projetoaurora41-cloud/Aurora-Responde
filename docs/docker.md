# Docker — rodando o Aurora Responde em containers

Guia para subir o fork **leve** com **Docker Compose**. O **banco é externo**
(fora do Docker): o app conecta ao PostgreSQL definido no seu `.env`. O compose
sobe a aplicação, o **Ollama** e instala o **Jurema-7B** (único LLM).

```
        ┌────────────────────────────────────────────┐
        │                docker compose               │
        │   ┌──────────┐        ┌──────────┐          │
        │   │   web    │──────▶ │  ollama  │          │
        │   │  Django  │        │ Jurema-7B│          │
        │   │  :8000   │        │  :11434  │          │
        │   └────┬─────┘        └────▲─────┘          │
        │        │      provisiona   │ (uma vez)       │
        │        │            ┌──────┴──────┐          │
        │        │            │ ollama-pull │ jurema-7b│
        │        │            └─────────────┘          │
        │   ┌──────────┐                               │
        │   │  valkey  │  cache / rate limit            │
        │   └──────────┘                               │
        └────────┼────────────────────────────────────┘
                 │ via .env (variáveis PG*)
                 ▼
         PostgreSQL EXTERNO  (host / remoto — NÃO está no Docker)
```

| Serviço | Imagem | Papel |
|---------|--------|-------|
| **web** | build local (`Dockerfile`) | App Django (webapp + `src/`), porta `8000` |
| **ollama** | `ollama/ollama` | LLM local — **Jurema-7B**, porta `11434` |
| **ollama-pull** | `ollama/ollama` | Baixa o Jurema-7B (GGUF) e sai |
| **valkey** | `valkey/valkey` | Cache / contadores de limite (guardrails) |

> **Banco externo:** não há serviço de Postgres no compose. Se o banco roda na
> **sua máquina** (host), use `PGHOST=host.docker.internal` no `.env`; se é
> **remoto**, use o host/IP real.

## Pré-requisitos

- **Docker Desktop** (Windows/Mac) ou Docker Engine + Compose v2 (Linux).
- Um **PostgreSQL externo** com os dados (SINAM/VIOLBR + SIPIA-CT) já carregados.
- Um **`.env`** na raiz com as variáveis do banco (`PGHOST`, `PGPORT`,
  `PGDATABASE`, `PGUSER`, `PGPASSWORD`). Sem chaves de API — o fork não usa.

## Início rápido

1. No `.env`, aponte o banco externo (exemplo p/ banco no host):
   ```dotenv
   PGHOST=host.docker.internal
   PGPORT=5432
   PGDATABASE=Aurora
   PGUSER=postgres
   PGPASSWORD=sua-senha
   JUREMA_MODEL=jurema-7b
   OLLAMA_MODEL=jurema-7b
   ```
2. Suba tudo (na 1ª vez, faz build e baixa o Jurema ~4,7 GB):
   ```bash
   docker compose up --build
   ```
3. Abra <http://localhost:8000>.

> A 1ª subida baixa o Jurema-7B (~4,7 GB), guardado no volume `ollama-models`;
> as próximas subidas são rápidas.

## Arquivos

| Arquivo | Para que serve |
|---------|-----------------|
| `Dockerfile` | Imagem leve da app (Python 3.12 + `requirements.txt`, **sem** PyTorch) |
| `docker-compose.yml` | Orquestra `web` + `ollama` + `ollama-pull` + `valkey` |
| `docker/entrypoint.sh` | Espera o banco → aplica migrations → sobe o servidor |
| `.dockerignore` | Mantém a imagem enxuta (exclui `venv/`, `.git/`, `.env`, ...) |

## Comandos úteis

```bash
docker compose up --build            # sobe tudo (build + baixa o Jurema)
docker compose up -d                 # em segundo plano
docker compose logs -f web           # logs da app
docker compose logs -f ollama-pull   # progresso do download do Jurema
docker compose exec web python manage.py createsuperuser   # 1º usuário admin
docker compose exec ollama ollama list                     # modelos do Ollama
docker compose down                  # derruba (mantém volumes/modelos)
```

Produção (gunicorn):
```bash
docker compose run --rm --service-ports web gunicorn
```

## GPU (opcional)

O Ollama usa CPU por padrão (em CPU a 1ª resposta é mais lenta). Para GPU,
requer `nvidia-container-toolkit` (no Windows, WSL2 + driver NVIDIA): descomente
o bloco `deploy.resources` do serviço `ollama` no `docker-compose.yml`.

## Solução de problemas

| Sintoma | Causa / solução |
|--------|------------------|
| `Cannot connect to the Docker daemon` | Serviço do Docker parado: `sudo systemctl enable --now docker`. Sem sudo: `sudo usermod -aG docker $USER && newgrp docker`. |
| `Temporary failure resolving 'deb.debian.org'` no build | DNS dos contêineres. `echo '{"dns":["8.8.8.8","1.1.1.1"]}' \| sudo tee /etc/docker/daemon.json` e `sudo systemctl restart docker`. |
| `connection refused` ao banco | `PGHOST` errado. Banco no host → `host.docker.internal`; remoto → host/IP real. |
| App "trava" na 1ª resposta | Esperado: o Jurema carrega na memória. Veja `docker compose logs -f ollama`. |
| Ollama "Failed to connect" | O `OLLAMA_HOST` aponta para `http://ollama:11434`. Confirme o serviço `ollama` no ar e o `ollama-pull` concluído. |
| `entrypoint.sh: not found` / `bad interpreter` | Fim de linha CRLF. O `.gitattributes` força LF; garanta que foi salvo assim. |

## Limitações

- **Dados moram no banco externo.** O compose não popula dados; usa o seu banco
  já carregado.
- **1 worker.** O deploy usa 1 processo (suficiente para o chat).
