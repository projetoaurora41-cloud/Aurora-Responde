# Docker — rodando o Aurora em containers

Guia para subir a plataforma com **Docker Compose**. O **banco é externo** (fora
do Docker): o app conecta ao PostgreSQL definido no seu `.env`. O compose sobe a
aplicação, o servidor de LLM local e **instala os modelos automaticamente**.

```
        ┌────────────────────────────────────────────────┐
        │                 docker compose                  │
        │                                                 │
        │   ┌──────────┐        ┌──────────┐              │
        │   │   web    │──────▶ │  ollama  │  (Qwen3 /     │
        │   │  Django  │        │ LLM local│   chat        │
        │   │  :8000   │        │  :11434  │   Eduardo)    │
        │   └────┬─────┘        └────▲─────┘              │
        │        │        provisiona │  (uma vez, no up)   │
        │        │            ┌──────┴──────┐             │
        │        │            │ ollama-pull │  qwen3:8b    │
        │        │            └─────────────┘             │
        │        │            ┌─────────────┐             │
        │        │            │ models-init │  ChatTime +  │
        │        │            └─────────────┘  Chronos (HF)│
        └────────┼────────────────────────────────────────┘
                 │ via .env (variáveis PG*)
                 ▼
         PostgreSQL EXTERNO  (host / remoto — NÃO está no Docker)
```

| Serviço | Imagem | Papel |
|---------|--------|-------|
| **web** | build local (`Dockerfile`) | App Django (webapp + `src/` + ChatTime), porta `8000` |
| **ollama** | `ollama/ollama` | LLM local — orquestrador Qwen3 e chat do Eduardo, porta `11434` |
| **ollama-pull** | `ollama/ollama` | Baixa o modelo `qwen3:8b` e sai (provisionamento) |
| **models-init** | `aurora-web` | Baixa os modelos HuggingFace (ChatTime/Chronos) e sai |

> **Banco externo:** não há serviço de Postgres no compose. O app usa o `.env`
> que você já tem. Se o banco roda na **sua máquina** (host), use
> `PGHOST=host.docker.internal` no `.env`; se é **remoto**, use o host/IP real.

---

## Pré-requisitos

- **Docker Desktop** (Windows/Mac) ou Docker Engine + Compose v2 (Linux).
- Um **PostgreSQL externo acessível**, com a extensão **pgvector** habilitada
  (`CREATE EXTENSION IF NOT EXISTS vector;`) — usada pelos índices do RAG.
- Um **`.env`** na raiz com as variáveis do banco (`PGHOST`, `PGPORT`,
  `PGDATABASE`, `PGUSER`, `PGPASSWORD`) e, se usar, as chaves de API
  (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY`).

---

## Arquivos

| Arquivo | Para que serve |
|---------|-----------------|
| `Dockerfile` | Imagem da app (Python 3.12 + PyTorch **CPU** + dependências) |
| `docker-compose.yml` | Orquestra `web` + `ollama` + provisionamento dos modelos |
| `docker/entrypoint.sh` | Espera o banco → aplica migrations → sobe o servidor |
| `docker/fetch_models.py` | Baixa ChatTime/Chronos para o cache (`models-init`) |
| `deploy.sh` / `deploy.ps1` | **Clone automático** do repo + sobe os containers (servidor) |
| `.dockerignore` | Mantém a imagem enxuta (exclui `venv/`, `.git/`, `.env`, ...) |

---

## Início rápido

1. No `.env`, garanta o host do banco externo (exemplo p/ banco no host):

   ```dotenv
   PGHOST=host.docker.internal
   PGPORT=5432
   PGDATABASE=Aurola
   PGUSER=postgres
   PGPASSWORD=sua-senha
   ```

2. Suba tudo (na 1ª vez, faz build e baixa os modelos):

   ```bash
   docker compose up --build
   ```

3. Abra <http://localhost:8000>.

> **Primeira execução baixa ~20 GB** de modelos (qwen3:8b ~5 GB + ChatTime ~13 GB
> + Chronos ~0,5 GB). Fica tudo em volumes; as próximas subidas são rápidas. A
> app já responde enquanto os modelos terminam de baixar.

### Instalar só parte dos modelos

O download do ChatTime é o mais pesado. Para subir **sem** ele:

```bash
# só app + Ollama + modelo do orquestrador (sem os modelos HuggingFace)
docker compose up --build web ollama ollama-pull

# ou nem o Ollama — só a aplicação
docker compose up --build web
```

Depois, se quiser, provisione os modelos HuggingFace sob demanda:

```bash
docker compose run --rm models-init
```

---

## Deploy no servidor (clone automático)

Num servidor novo, o script [`deploy.sh`](../deploy.sh) (Linux) /
[`deploy.ps1`](../deploy.ps1) (Windows) faz **tudo**: instala o Docker (se
faltar), **clona** o repositório, cria o `.env` e sobe todos os recursos (build
da app + Ollama + download dos modelos).

**Pré-requisitos no servidor:** acesso `sudo` e a credencial do repositório
privado (PAT). O próprio `deploy.sh` instala `git`, `curl` e o **Docker**.

### Passo a passo (Linux)

**1 — Leve o bootstrap para o servidor** (só estes 2 arquivos; o resto ele clona):
```bash
scp deploy.sh deploy.env.example  usuario@servidor:~/
```

**2 — Coloque a "key do GitHub" no `deploy.env`** (arquivo local, não versionado):
```bash
cp deploy.env.example deploy.env
nano deploy.env
# preencha AURORA_REPO_URL com um PAT (escopo 'repo'):
# AURORA_REPO_URL=https://SEU_TOKEN@github.com/projetoaurora41-cloud/Projeto-Aurora.git
```

**3 — Rode o bootstrap** — instala o Docker (se faltar), clona, cria o `.env` e sobe:
```bash
bash deploy.sh
```
> Na 1ª vez ele instala o Docker via `get.docker.com` (pode pedir a senha do
> sudo) e usa `sudo docker` nesta sessão; no próximo login você já usa `docker`
> sem sudo.

**4 — Ajuste o `.env` do projeto** (banco EXTERNO + chaves de API) — o script para
e avisa enquanto o `.env` estiver com valores de exemplo:
```bash
nano Projeto-Aurora/.env
# PGHOST=host.docker.internal   (ou o host/IP real do banco)
# PGDATABASE / PGUSER / PGPASSWORD ; OPENAI_API_KEY / GEMINI_API_KEY / ...
```

**5 — Rode de novo e crie o admin:**
```bash
bash deploy.sh                       # sobe os containers com o .env correto
cd Projeto-Aurora
docker compose exec web python manage.py createsuperuser
```

**6 — Acesse** <http://localhost:8000> (ou `http://IP-DO-SERVIDOR:8000`).

> **Atualizar depois:** rode `bash deploy.sh` (de onde ficam o `deploy.sh` e o
> `deploy.env`) — ele faz `git pull` e recria os containers com o código novo.

### Passo a passo (Windows / Docker Desktop)

```powershell
Copy-Item deploy.env.example deploy.env
notepad deploy.env      # preencha AURORA_REPO_URL com o token (PAT escopo 'repo')
powershell -ExecutionPolicy Bypass -File deploy.ps1
# depois edite Projeto-Aurora\.env (banco externo + chaves) e rode o deploy.ps1 de novo
```

### Autenticação do repositório privado

**Onde colocar a "key do GitHub"?** Nunca em arquivo versionado. A credencial é
usada para *clonar* o repo, então vive **fora** dele. Duas formas:

- **Arquivo `deploy.env`** (recomendado) — copie de
  [`deploy.env.example`](../deploy.env.example) para `deploy.env` (já no
  `.gitignore`) e preencha `AURORA_REPO_URL` com o token. O `deploy.sh`/`deploy.ps1`
  carregam esse arquivo automaticamente.
- **Variável de ambiente** — `export AURORA_REPO_URL="https://<TOKEN>@github.com/..."`
  antes de rodar o script.

| Método | Como |
|--------|------|
| **PAT (HTTPS)** | Gere um token com escopo `repo` e use na URL: `https://<TOKEN>@github.com/.../Projeto-Aurora.git` |
| **Deploy key (SSH)** | Cadastre a chave **pública** como *Deploy key* no repo; a **privada** fica em `~/.ssh/` (fora do repo). Use `AURORA_REPO_URL="git@github.com:projetoaurora41-cloud/Projeto-Aurora.git"` |

> **Alternativa (imagem autocontida):** em vez de clonar no host, é possível clonar
> dentro do build (um `Dockerfile` que roda `git clone`). O bootstrap acima é
> preferível: separa código de imagem e facilita `git pull` + rebuild.

---

## Banco externo (detalhes)

- **`PGHOST`** é o ponto-chave:
  - banco na sua máquina (host) → `host.docker.internal`
  - banco remoto → o host/IP real (ex.: `diinftic-es01`)
- O `entrypoint` **espera o banco** e roda `python manage.py migrate` contra ele
  ao subir. Portanto o usuário do `.env` precisa ter permissão de criar/alterar
  tabelas do Django nesse banco.
- **pgvector** precisa existir no banco externo. Uma vez:

  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

---

## Provisionamento dos modelos

- **`ollama-pull`** — espera o `ollama` subir e roda `ollama pull qwen3:8b`. Para
  adicionar outro modelo (ex.: o que o Eduardo usa), rode manualmente:

  ```bash
  docker compose exec ollama ollama pull llama3.1
  ```

- **`models-init`** — roda [`docker/fetch_models.py`](../docker/fetch_models.py),
  que baixa `CHATTIME_MODEL` e `CHRONOS2_MODEL` (definidos no `.env`, com defaults
  `ChengsenWang/ChatTime-1-7B-Chat` e `amazon/chronos-2`) para o volume `hf-cache`
  (`HF_HOME=/models/huggingface`). É idempotente: se já está no cache, apenas
  confere e sai.

---

## GPU (opcional)

O `Dockerfile` usa **PyTorch CPU** por padrão — roda em qualquer máquina, mas os
forecasts do ChatTime/Chronos ficam lentos (minutos). Duas frentes:

1. **Ollama na GPU** (mais fácil): requer `nvidia-container-toolkit` (no Windows,
   WSL2 + driver NVIDIA). Descomente o bloco `deploy.resources` do serviço
   `ollama` no `docker-compose.yml`.
2. **PyTorch na GPU** (ChatTime/Chronos): troque a base do `Dockerfile` por uma
   imagem CUDA e instale o torch com índice CUDA (em vez de `.../whl/cpu`).
   Adicione o mesmo bloco `deploy.resources` ao serviço `web`. Ver
   [`servidor.md`](servidor.md) para o dimensionamento de VRAM.

---

## Comandos úteis

```bash
docker compose up --build            # sobe tudo (build + provisiona modelos)
docker compose up -d                 # em segundo plano
docker compose logs -f web           # logs da app
docker compose logs -f models-init   # progresso do download dos modelos HF
docker compose exec web bash         # shell no container da app
docker compose exec web python manage.py createsuperuser   # 1º usuário admin
docker compose exec ollama ollama list                     # modelos do Ollama
docker compose down                  # derruba (mantém volumes/modelos)
docker compose down -v               # derruba E apaga volumes/modelos (cuidado!)

# modo produção (gunicorn, 1 worker p/ o singleton do modelo):
docker compose run --rm --service-ports web gunicorn
```

---

## Como a imagem funciona

- **Base**: `python:3.12-slim`. Instala **PyTorch CPU** primeiro (wheel menor) e
  depois o `requirements.txt` + `gunicorn`.
- **Código**: copia `webapp/`, `src/` e `ChatTime/`. O `settings.py` insere a raiz
  do projeto no `sys.path`, então `import src...` funciona.
- **Entrypoint**: espera o banco (externo), roda `migrate` e inicia o servidor.
  Modo padrão `web` = `runserver --noreload` (serve estáticos em DEBUG e mantém
  **1 processo**, necessário para o singleton do ChatTime ~13 GB). Modo `gunicorn`
  para produção.
- **Volumes**: `hf-cache` (modelos HuggingFace) e `ollama-models` (modelos do
  Ollama). Nenhum volume de banco — o banco é externo.

---

## Solução de problemas

| Sintoma | Causa / solução |
|--------|------------------|
| `Cannot connect to the Docker daemon` | O serviço do Docker não está rodando: `sudo systemctl enable --now docker` (ou `sudo snap start docker`). Sem sudo: `sudo usermod -aG docker $USER && newgrp docker`. |
| daemon "não respondeu mesmo após a instalação" | O `dockerd` não subiu **ou** a checagem caiu no meio de um restart. Diagnostique: `sudo journalctl -u docker --no-pager -n 50` (procure `API listen on /run/docker.sock` = está no ar) e `ps -p 1 -o comm=`. Sem systemd (WSL/LXC) → `sudo service docker start`. VPS **OpenVZ/LXC** → Docker não roda (precisa KVM). **Não** rode um 2º `dockerd` manual. |
| `iptables: No chain/target/match by that name` (ao subir containers) | A chain `DOCKER` do iptables sumiu (comum quando um firewall recarrega/*flush* o iptables com o Docker no ar). Recrie reiniciando o Docker: `sudo systemctl restart docker`. Persistiu? conflito nft×legacy ou firewall → `sudo reboot`. |
| `docker: docker: É um diretório` | Você rodou `bash docker compose ...`. Tire o `bash`: o comando é `docker compose ...` (ou `bash deploy.sh`). |
| Build falha sem `webapp/`/`src/` | Rodou `docker compose up` de dentro do **zip** (que só tem a config). Num servidor novo rode `bash deploy.sh` — ele clona o projeto completo e builda de lá. |
| `Temporary failure resolving 'deb.debian.org'` / `Could not resolve host` no build (apt ou pip) | **DNS dos contêineres.** Em muitos VPS o `/etc/resolv.conf` do host aponta para `127.0.0.53` (stub do systemd-resolved), inalcançável de dentro do build. O `deploy.sh` já corrige automaticamente (grava `"dns"` em `/etc/docker/daemon.json` e reinicia o Docker). Manual: `echo '{"dns":["8.8.8.8","1.1.1.1"]}' \| sudo tee /etc/docker/daemon.json` e `sudo systemctl restart docker`. Desativar a correção automática: `AURORA_SKIP_DNS_FIX=1 bash deploy.sh`. |
| `connection refused` ao banco | `PGHOST` errado. Banco no host → `host.docker.internal`; remoto → host/IP real. Confirme que o Postgres externo aceita conexões. |
| `type "vector" does not exist` | Extensão pgvector ausente no banco externo. Rode `CREATE EXTENSION vector;` nele. |
| App demora / "trava" no 1º forecast | Esperado: carrega o modelo (~13 GB). Veja `docker compose logs -f web`. |
| `models-init` falhou | Sem internet ou repositório HF indisponível. Reexecute `docker compose run --rm models-init`. |
| Ollama "Failed to connect" | O `OLLAMA_HOST` já aponta para `http://ollama:11434`. Confirme o serviço `ollama` no ar e o `ollama-pull` concluído. |
| `entrypoint.sh: not found` / `bad interpreter` | Fim de linha CRLF. O `.gitattributes` força LF; garanta que foi salvo assim. |
| Build grande/lento | Normal — PyTorch + transformers pesam alguns GB. Fica em cache nas próximas builds. |

---

## Limitações

- **Dados moram no banco externo.** O compose não popula dados; usa o seu banco já
  carregado (ETL `.dbc` continua sendo um passo à parte, fora do container).
- **CPU por padrão.** Sem a variante CUDA, os forecasts locais são lentos. Os
  chats de Marcelo e Rafael (API) e o Ollama funcionam normalmente.
- **1 worker.** O deploy usa 1 processo para compartilhar o modelo em memória;
  forecasts são sequenciais (ver [`arquitetura.md`](arquitetura.md)).
