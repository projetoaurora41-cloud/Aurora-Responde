# Aurora Responde

Assistente conversacional (chat único) em Django sobre **violência contra
crianças e adolescentes no Brasil**. É um **fork leve** do Projeto Aurora: usa
**um só LLM — o Jurema-7B** (via Ollama) — para redigir **todas** as respostas,
sobre quaisquer temas (dados, legislação, SIPIA-CT ou funcionamento da
plataforma). **Não há orquestrador Qwen3** nem modelos de forecasting.

## Arquitetura

![Arquitetura do Aurora Responde (só Jurema)](docs/arquitetura_aurora_responde.svg)

1. **Guardrails (entrada)** — risco a uma criança → encaminhamentos (Conselho
   Tutelar / Disque 100 / Boletim de Ocorrência) sem LLM; detecção de injeção;
   mascaramento de PII.
2. **Roteador determinístico** identifica o tema (dados / legislação / SIPIA-CT /
   produto), o nível geográfico, o tipo de violência e o ano — sem um LLM decidindo.
3. A **fonte** é consultada: **PostgreSQL ao vivo** para números exatos
   (SINAM/VIOLBR e SIPIA-CT), um **corpus jurídico curado** para a legislação, e a
   **documentação** (`docs/`) para perguntas sobre a plataforma.
4. O **Jurema-7B** redige a resposta a partir desses dados. Nunca inventa números;
   se estiver indisponível, há *fallback* para a narrativa pronta do payload.

Detalhes em [docs/arquitetura.md](docs/arquitetura.md).

## Estrutura do projeto

```
Aurora-Responde/
├── webapp/                         ← aplicação Django 6
│   ├── aurora/                       settings.py (lê o .env da raiz), urls.py
│   ├── core/                         base + autenticação + home/registry
│   ├── sinam/                        camada semântica: Notificacao + filtros geo/violência
│   ├── guardrails/                   segurança (risco, injeção, PII, limites)
│   └── chats/series_temporais/
│       └── orquestrador/             O CHAT: roteador determinístico + Jurema
│           ├── orchestrator.py        roteador + narração (_narrar_com_jurema)
│           ├── tools.py               relatórios SQL (SINAM) ao vivo
│           ├── rag_tools.py           rag_juridico / rag_interno / consulta_sipia_ct
│           ├── leis_corpus.py         corpus jurídico curado (ECA, leis, ...)
│           └── sipia_ct.py            fonte SQL do SIPIA-CT
├── src/                            ← núcleo sem Django: src/db.py (acesso ao Postgres)
├── docs/                           ← documentação + diagrama + corpus RAG (docs/rag/)
└── requirements.txt                ← 8 pacotes (Django, psycopg, pandas, ollama, ...)
```

URLs: a home (chat) fica em `/`; endpoints do chat sob `/series-temporais/chat/`;
admin em `/admin/`.

## Pré-requisitos

- **Python 3.12+**
- **PostgreSQL** com o banco do projeto (dados SINAM/VIOLBR + SIPIA-CT já
  carregados). Config via `.env` (variáveis `PG*`).
- **[Ollama](https://ollama.com/download)** rodando localmente, com o modelo
  **Jurema-7B** instalado (ver passo 3 abaixo). Sem ele o chat não responde.

> Leve: **não** precisa de GPU dedicada, PyTorch, modelos HuggingFace nem pgvector.

## Como clonar e rodar

### Windows (PowerShell)

```powershell
git clone https://github.com/projetoaurora41-cloud/Aurora-Responde.git
cd Aurora-Responde
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1) Configurar o ambiente (editar o .env com as credenciais do Postgres)
Copy-Item .env.example .env
notepad .env   # defina PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD

# 2) Instalar o Jurema-7B no Ollama (único LLM)
ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
ollama cp  hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b

# 3) Migrar o Django e subir
python webapp\manage.py migrate
python webapp\manage.py runserver
# abra http://127.0.0.1:8000/
```

### Linux / macOS (bash)

```bash
git clone https://github.com/projetoaurora41-cloud/Aurora-Responde.git
cd Aurora-Responde
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # edite PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD

ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
ollama cp  hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b

python webapp/manage.py migrate
python webapp/manage.py runserver
```

> **Banco já populado?** Se o Postgres do `.env` já tem as tabelas (dados + ORM),
> o `migrate` é praticamente no-op e você pode ir direto ao `runserver`.
> Para criar um admin: `python webapp/manage.py createsuperuser`.

## Variáveis de ambiente (.env)

| Variável | Para que serve |
|----------|----------------|
| `PGHOST` `PGPORT` `PGDATABASE` `PGUSER` `PGPASSWORD` | Conexão PostgreSQL (dados + ORM). |
| `OLLAMA_HOST` | Host do Ollama (default `http://127.0.0.1:11434`). |
| `OLLAMA_MODEL` / `JUREMA_MODEL` | Nome do modelo gerador — ambos `jurema-7b`. |
| `JUREMA_NUM_PREDICT` | Máx. de tokens da resposta (default 520). |
| `SIPIA_CT_TABLE` / `SIPIA_CT_VALUE_COL` | View do SIPIA-CT e coluna numérica. |
| `AURORA_MAX_DATA_YEAR` | Último ano com dados (default 2024). |
| `DJANGO_DEBUG` `DJANGO_ALLOWED_HOSTS` | Dev local. |

> O `.env` **nunca** é versionado (está no `.gitignore`). Use o `.env.example`
> como modelo — ele só tem placeholders.

## Exemplos de perguntas

- **Dados:** "Quantos casos de violência sexual em São Paulo em 2023?"
- **Ranking:** "Quais os 5 estados com mais notificações de negligência?"
- **Legislação:** "O que diz a Lei Menino Bernardo sobre castigo físico?"
- **SIPIA-CT:** "No Conselho Tutelar, qual a distribuição por sexo?"
- **Produto:** "Como o Aurora Responde funciona?"
- **Risco:** "Meu vizinho bate no filho, o que faço?" → orienta Conselho Tutelar / Disque 100 / BO.

## Comandos comuns

| Tarefa | Windows | Linux/macOS |
|--------|---------|-------------|
| Ativar venv | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| Migrações | `python webapp\manage.py migrate` | `python webapp/manage.py migrate` |
| Superusuário | `python webapp\manage.py createsuperuser` | `python webapp/manage.py createsuperuser` |
| Servidor | `python webapp\manage.py runserver` | `python webapp/manage.py runserver` |
| Servidor na rede | `python webapp\manage.py runserver 0.0.0.0:8000` | idem (inclua o IP em `DJANGO_ALLOWED_HOSTS`) |
| Carregar SIPIA-CT | `python webapp\manage.py load_sipia_ct` | `python webapp/manage.py load_sipia_ct` |

## Documentação

| Documento | O que cobre |
|-----------|-------------|
| [docs/arquitetura.md](docs/arquitetura.md) | Arquitetura só-Jurema + diagrama |
| [docs/chat.md](docs/chat.md) | Como o chat funciona (roteador + Jurema) |
| [docs/semantic_layer.md](docs/semantic_layer.md) | Camada semântica `Notificacao` + filtros |
| [docs/database.md](docs/database.md) | Schema do banco (VIOLBR / SIPIA-CT) |
| [docs/docker.md](docs/docker.md) | Subir com Docker Compose |
| [docs/rag/](docs/rag/) | Corpus do RAG interno (dicionário SINAM, sobre o produto) |

## Licença

Projeto de pesquisa — PROCC/UFS · MJSP.
