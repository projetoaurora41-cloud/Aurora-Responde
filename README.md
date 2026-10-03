# Aurora Responde

Assistente conversacional (chat único) em Django sobre **violência contra
crianças e adolescentes no Brasil**. É um **fork leve** do Projeto Aurora: usa
**um só LLM — o Jurema-7B** (via Ollama) — para redigir **todas** as respostas,
sobre quaisquer temas (dados, legislação, SIPIA-CT ou funcionamento da
plataforma). **Não há orquestrador Qwen3** nem modelos de forecasting.

## Como responde

1. **Roteador determinístico** identifica o tipo da pergunta (dados / legislação /
   SIPIA-CT / produto) e escolhe a fonte certa — sem um LLM decidindo.
2. A fonte é consultada: **PostgreSQL ao vivo** para números exatos (SINAM/VIOLBR
   e SIPIA-CT), um **corpus jurídico curado** para a legislação, e a
   **documentação** (`docs/`) para perguntas sobre a plataforma.
3. O **Jurema-7B** redige a resposta a partir desses dados. O modelo nunca
   inventa números — ele narra o que o banco retornou. Se o Jurema estiver
   indisponível, há *fallback* para a narrativa pronta do payload.

Uma camada de **guardrails** roda antes do modelo (risco → Conselho Tutelar /
Disque 100 / Boletim de Ocorrência; detecção de injeção; mascaramento de PII).

Toda a aplicação usa um **único banco PostgreSQL** (`Aurola`): dados SINAM e
estado do Django ficam juntos. Sem embeddings, sem torch, sem APIs externas.

## Estrutura do projeto

```
Projeto-Aurora/
├── webapp/
│   ├── manage.py
│   ├── aurora/                       ← projeto Django (settings, urls)
│   │
│   ├── core/                         ← COMPARTILHADO por todos os chats
│   │   ├── models.py                   bases abstratas (BaseChatThread/Message)
│   │   ├── registry.py                 registro de tipos de chat (alimenta a home)
│   │   ├── views.py                    home/landing + signup/login
│   │   ├── management/commands/        migrate_sqlite_to_pg (SQLite legado → Postgres)
│   │   └── templates/core/home.html
│   │
│   ├── sinam/                        ← COMPARTILHADO: dados VIOLBR (Notificacao + ETL)
│   │
│   └── chats/                        ← um pacote por pesquisador
│       ├── series_temporais/        ← Chat de Séries Temporais (Hernandison)
│       │   ├── orquestrador/          chat conduzido por LLM   (namespace url: chat)
│       │   ├── analise/               consultas + análise retrospectiva + QA (namespace: queries)
│       │   └── benchmark/             benchmark orquestradores x modelos (namespace: benchmark)
│       │
│       └── dados_sinam/             ← Chat Dados SINAN — RAG + SQL (Marcelo West)
│           ├── services.py            gera/valida/executa SQL + RAG + LLMs (GPT/Gemini/Perplexity)
│           ├── embeddings.py          embeddings locais (sentence-transformers, CPU)
│           ├── models.py              ChatThread/ChatMessage + SentencaEmbedding (pgvector)
│           └── management/commands/   seed_embeddings (popula a busca vetorial)
│
├── src/                             ← núcleo: acesso ao Postgres, modelos de série, CLI
├── ChatTime/                        ← modelo ChatTime (vendored)
└── docs/                            ← documentação detalhada
```

URLs: a home fica em `/`; tudo do chat de séries temporais fica sob
`/series-temporais/...`; o Chat Dados SINAN em `/dados-sinam/...`; os dados SINAM
em `/sinam/...`; o admin em `/admin/`.

## Como adicionar o seu tipo de chat (para os colegas)

Segue o fluxo **oficial do Django** ([startapp](https://docs.djangoproject.com/en/stable/ref/django-admin/#startapp)
+ [tutorial parte 1](https://docs.djangoproject.com/en/stable/intro/tutorial01/)),
adaptado para que cada chat viva dentro do pacote `webapp/chats/`. Use `geoespacial`
como exemplo do seu nome.

**1. Crie o app com o `manage.py`** (o `startapp` exige que a pasta de destino já
exista, e `chats/` já é um pacote Python):

```bash
cd webapp
mkdir chats/geoespacial                              # Windows: mkdir chats\geoespacial
python manage.py startapp geoespacial chats/geoespacial
```

Isso gera o esqueleto padrão do Django: `apps.py`, `models.py`, `views.py`,
`admin.py`, `tests.py` e `migrations/`.

**2. Ajuste o `apps.py`** — como o app está num pacote, o `name` precisa ser o
caminho pontilhado completo (a [documentação do Django](https://docs.djangoproject.com/en/stable/ref/applications/#for-application-authors)
recomenda isso para apps fora da raiz). Aproveite para definir um `label` curto:

```python
# webapp/chats/geoespacial/apps.py
from django.apps import AppConfig

class GeoespacialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chats.geoespacial"          # caminho completo do pacote
    label = "geoespacial"               # rótulo curto (prefixo das tabelas)
    verbose_name = "Chat Geoespacial"
```

**3. Registre o app em `INSTALLED_APPS`** ([docs](https://docs.djangoproject.com/en/stable/ref/applications/#configuring-applications)) —
em `webapp/aurora/settings.py` use o caminho do `AppConfig`:

```python
INSTALLED_APPS = [
    # ...
    "chats.geoespacial.apps.GeoespacialConfig",
]
```

**4. Escreva seus modelos e migre** ([tutorial parte 2](https://docs.djangoproject.com/en/stable/intro/tutorial02/)).
Opcionalmente herde as bases abstratas de `core` para padronizar conversa/mensagem:

```python
# webapp/chats/geoespacial/models.py
from django.db import models

from core.models import BaseChatThread, BaseChatMessage

class Conversa(BaseChatThread):
    pass

class Mensagem(BaseChatMessage):
    thread = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="mensagens")
```

```bash
python manage.py makemigrations geoespacial
python manage.py migrate
```

**5. Crie as URLs** ([tutorial parte 1 — URLconf](https://docs.djangoproject.com/en/stable/intro/tutorial01/#write-your-first-view)).
No app, `webapp/chats/geoespacial/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
]
```

E inclua no `webapp/aurora/urls.py` com [`include()`](https://docs.djangoproject.com/en/stable/ref/urls/#include)
e um namespace próprio:

```python
path("geoespacial/", include(("chats.geoespacial.urls", "geo"), namespace="geo")),
```

**6. Apareça na home** — registre o chat no `ready()` do seu `AppConfig`
(o método [`ready()`](https://docs.djangoproject.com/en/stable/ref/applications/#django.apps.AppConfig.ready)
é o lugar canônico para inicialização de app):

```python
def ready(self):
    from core.registry import ChatType, register
    register(ChatType(
        key="geoespacial", name="Chat Geoespacial",
        url_name="geo:home", owner="Fulano", icon="🗺️",
        description="...",
    ))
```

> **Pontos compartilhados que você toca:** apenas `INSTALLED_APPS` e `aurora/urls.py`.
> **Regra de ouro:** trabalhe só dentro da sua pasta em `chats/`. Não edite o app de
> outro pesquisador. `core` e `sinam` são compartilhados — combine no grupo antes de
> alterá-los.

## Início rápido

### Windows (PowerShell)

```powershell
git clone https://github.com/projetoaurora41-cloud/Projeto-Aurora.git
cd Projeto-Aurora
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env             # ajustar PGPASSWORD
python webapp\manage.py migrate
python webapp\manage.py seed_queries    # consultas SQL de exemplo
python webapp\manage.py createsuperuser
python webapp\manage.py runserver
# http://127.0.0.1:8000/
```

### Linux / macOS (bash)

```bash
git clone https://github.com/projetoaurora41-cloud/Projeto-Aurora.git
cd Projeto-Aurora
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # ajustar PGPASSWORD
python webapp/manage.py migrate
python webapp/manage.py seed_queries
python webapp/manage.py createsuperuser
python webapp/manage.py runserver
```

## Requisitos

- Python 3.14 — Windows 10/11 (também roda em Linux/macOS)
- PostgreSQL 16+ com banco `Aurola` — **banco único do projeto**: dados
  SINAM/VIOLBR (`VIOLBR20`..`VIOLBR24`) + todo o estado do Django (via ORM)
- Extensão [pgvector](https://github.com/pgvector/pgvector) no PostgreSQL — para
  a busca vetorial (embeddings) do Chat Dados SINAN
- ~13 GB de disco livre para o cache do modelo HuggingFace (CPU-only suportado)

## URLs principais

| Caminho | App | O que é |
|---------|-----|---------|
| `/` | `core` | Home: lista os tipos de chat registrados |
| `/login/` · `/signup/` | `core` | Autenticação |
| `/series-temporais/` | `analise` | Catálogo de consultas + análise retrospectiva + QA |
| `/series-temporais/chat/` | `orquestrador` | Chat conduzido por LLM |
| `/series-temporais/benchmark/` | `benchmark` | Benchmark de modelos |
| `/dados-sinam/` | `dados_sinam` | Chat Dados SINAN: consulta em linguagem natural (RAG + SQL) |
| `/sinam/importar/` | `sinam` | Importar dados SINAM (.dbc) |
| `/admin/` | Django | Admin |

## Comandos comuns

| Tarefa | Windows | Linux/macOS |
|--------|---------|-------------|
| Ativar venv | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| Migrações | `python webapp\manage.py migrate` | `python webapp/manage.py migrate` |
| Consultas de exemplo | `python webapp\manage.py seed_queries` | `python webapp/manage.py seed_queries` |
| Importar municípios (IBGE) | `python webapp\manage.py seed_municipios` | `python webapp/manage.py seed_municipios` |
| ETL VIOLBR (→ banco padrão) | `python webapp\manage.py etl_violbr` | `python webapp/manage.py etl_violbr` |
| Migrar SQLite legado → Postgres | `python webapp\manage.py migrate_sqlite_to_pg` | `python webapp/manage.py migrate_sqlite_to_pg` |
| Embeddings do Chat Dados SINAN | `python webapp\manage.py seed_embeddings` | `python webapp/manage.py seed_embeddings` |
| Superusuário | `python webapp\manage.py createsuperuser` | `python webapp/manage.py createsuperuser` |
| Servidor | `python webapp\manage.py runserver` | `python webapp/manage.py runserver` |
| Servidor na rede | `python webapp\manage.py runserver 0.0.0.0:8000` | idem (inclua o IP em `ALLOWED_HOSTS`) |

## CLI (`src/main.py`)

Para tarefas fora do Django (testes rápidos de banco e modelos de série):

```powershell
python -m src.main ping                          # confirma o Postgres
python -m src.main describe VIOLBR24              # inspeciona uma tabela
python -m src.main forecast --sql "..." --horizon 14
python -m src.main ask "Tendência (a)/(b)/(c)?" --sql "..."
```

## Recursos do chat de Séries Temporais

- Catálogo de consultas SQL salvas (CRUD) e visualização em Chart.js
- Análise retrospectiva e QA via formulários
- Chat com orquestrador LLM local (Ollama)
- Benchmark de orquestradores × modelos de série temporal em `/series-temporais/benchmark/`
- Histórico persistente por usuário

## Recursos do Chat Dados SINAN

- Geração automática de SQL a partir de perguntas em português (com validação)
- Busca semântica via embeddings locais (sentence-transformers) + **pgvector**,
  com fallback para busca textual (ILIKE)
- Respostas por GPT/Gemini/Perplexity ou por regras determinísticas (sem chave)
- Chaves de API por sessão (nunca persistidas) e histórico por usuário
- Popular embeddings: `python webapp/manage.py seed_embeddings`

## Documentação

A pasta [`docs/`](docs/) tem documentação detalhada e os diagramas:

| Documento | O que cobre |
|-----------|-------------|
| [docs/django_layout.svg](docs/django_layout.svg) | Estrutura dos apps (atualizado para o Aurora) |
| [docs/architecture.svg](docs/architecture.svg) | Fluxo de dados ingestão → chat → análise |
| [docs/models_roles.svg](docs/models_roles.svg) | Papéis dos modelos (orquestrador, série, QA) |
| [docs/arquitetura.md](docs/arquitetura.md) | Camadas e fluxo de dados |
| [docs/cli.md](docs/cli.md) | Referência da CLI `python -m src.main` |
| [docs/chat.md](docs/chat.md) | Chat com orquestrador local |
| [docs/semantic_layer.md](docs/semantic_layer.md) | Camada semântica `Notificacao` + ETL |
| [docs/database.md](docs/database.md) · [docs/troubleshooting.md](docs/troubleshooting.md) | Schema VIOLBR · erros comuns |

> Os diagramas SVG já refletem o Aurora. Os `.md` detalhados ainda podem citar a
> estrutura anterior (`sinamweb/`, app `forecasts`) em alguns pontos — em migração.

## Licença

Uso interno do grupo de pesquisa. O código upstream do ChatTime mantém sua
licença original (ver `ChatTime/`).
