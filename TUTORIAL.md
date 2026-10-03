# Tutorial — SINAM + ChatTime

Guia passo-a-passo do zero, no Windows. Para visão geral do projeto, leia o
[README](README.md). Para detalhes por componente, veja [`docs/`](docs/).

---

## 1. Pré-requisitos

Instalar uma única vez:

| Ferramenta       | Onde                                                |
|------------------|------------------------------------------------------|
| Python 3.14      | <https://www.python.org/downloads/> *(marcar "Add to PATH")* |
| Git for Windows  | <https://git-scm.com/download/win>                   |
| PostgreSQL 16+   | <https://www.postgresql.org/download/windows/>       |

Conferir no PowerShell:

```powershell
python --version
git --version
psql --version
```

Você também precisa do banco **`Aurola`** rodando localmente, com as tabelas
`VIOLBR20` … `VIOLBR24` populadas (uma por ano). Veja
[docs/database.md](docs/database.md) para detalhes do schema.

---

## 2. Clonar o projeto

```powershell
cd C:\Users\herna
git clone https://github.com/Hernandison/projeto-sinam-chattime.git Projeto_Sinam
cd Projeto_Sinam
```

Se a pasta já existe, apenas `cd C:\Users\herna\Projeto_Sinam`.

---

## 3. Criar e ativar o venv

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Se o PowerShell barrar a ativação:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

e reative. O prompt deve ficar com o prefixo `(venv)`.

---

## 4. Instalar dependências

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Aproximadamente 3 GB e alguns minutos (torch CPU, transformers, Django, etc.).

---

## 5. Criar o arquivo `.env`

Na raiz, copie de [`.env.example`](.env.example) e ajuste:

```ini
PGHOST=localhost
PGPORT=5432
PGDATABASE=Aurola
PGUSER=postgres
PGPASSWORD=SUA_SENHA_AQUI
CHATTIME_MODEL=ChengsenWang/ChatTime-1-7B-Chat
```

---

## 6. Testar a conexão com o banco

```powershell
python -m src.main ping
```

Saída esperada (exemplo):

```
PostgreSQL 18.3 on x86_64-windows, compiled by msvc-19.44.35225, 64-bit
```

> **Importante:** sempre execute como módulo (`-m src.main`). Rodar
> `python src/main.py` direto gera `ModuleNotFoundError: No module named 'db'`
> porque o arquivo usa imports relativos. Veja
> [docs/troubleshooting.md](docs/troubleshooting.md).

---

## 7. Smoke test (primeira execução baixa ~13 GB)

```powershell
python scripts\smoke_chattime.py
```

O que acontece:

1. Consulta `VIOLBR24` e monta uma série diária.
2. Baixa `ChengsenWang/ChatTime-1-7B-Chat` em `%USERPROFILE%\.cache\huggingface`
   (somente na primeira vez).
3. Roda forecast de 14 dias e imprime `t+1` … `t+14`.

Em CPU-only o load demora vários minutos — é esperado.

---

## 8. Configurar a interface web (Django)

A interface gerencia consultas salvas, executa forecast/QA e mantém histórico
por usuário.

```powershell
python webapp\manage.py migrate
python webapp\manage.py seed_queries
python webapp\manage.py createsuperuser
```

Subir o servidor:

```powershell
python webapp\manage.py runserver
```

Acessar:

| URL                              | O que faz                                |
|----------------------------------|------------------------------------------|
| <http://127.0.0.1:8000/login/>   | login                                    |
| <http://127.0.0.1:8000/signup/>  | criar conta                              |
| <http://127.0.0.1:8000/>         | lista de consultas salvas                |
| `/<id>/`                         | detalhe + gráfico + botões forecast/QA   |
| <http://127.0.0.1:8000/history/> | histórico de execuções                   |
| <http://127.0.0.1:8000/admin/>   | admin Django (cadastros, super-usuário)  |

Detalhes em [docs/webapp.md](docs/webapp.md).

---

## 9. Usar a CLI

| Comando                                                        | O que faz                            |
|----------------------------------------------------------------|--------------------------------------|
| `python -m src.main ping`                                      | testa conexão com o banco            |
| `python -m src.main tables`                                    | lista tabelas no schema `public`     |
| `python -m src.main describe VIOLBR24`                         | colunas e tipos da tabela            |
| `python -m src.main query --sql "SELECT ..."`                  | roda SQL e imprime tabela            |
| `python -m src.main forecast --sql "..." --horizon 14`         | série → forecast com ChatTime        |
| `python -m src.main ask "(a)... (b)... (c)..." --sql "..."`    | QA múltipla escolha sobre a série    |

Referência completa: [docs/cli.md](docs/cli.md).

---

## 10. Chat com IA (requer o Jurema-7B no Ollama)

A interface é um chat conversacional onde o **Jurema-7B** (via **Ollama**) é o
**único LLM**: ele redige todas as respostas em PT-BR a partir dos dados ao vivo
(PostgreSQL), da legislação e da documentação. Um roteador determinístico escolhe
a fonte — não há orquestrador Qwen3 nem modelos de forecast.

Instalação adicional (necessária para o chat):

1. **Baixar e instalar o Ollama**: <https://ollama.com/download/windows>
2. **Puxar o Jurema-7B** (~4,7 GB, primeira vez) e apelidá-lo como `jurema-7b`:
   ```powershell
   ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
   ollama cp hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b
   ```
3. Abrir `http://127.0.0.1:8000/`, clicar **+ Nova conversa**.

Detalhes em [docs/chat.md](docs/chat.md). Sem GPU dedicada o chat ainda
funciona, mas as respostas são mais lentas.

---

## 11. Próximos terminais

Em todo terminal novo:

```powershell
cd C:\Users\herna\Projeto_Sinam
.\venv\Scripts\Activate.ps1
```

Sem isso, `python` usará o interpretador global e dará `ModuleNotFoundError`
nas dependências.

---

## 12. Problemas comuns

Lista resumida — completa em [docs/troubleshooting.md](docs/troubleshooting.md).

- `ModuleNotFoundError: No module named 'db'` → use `python -m src.main`.
- `OperationalError: connection refused` → Postgres parado ou `.env` errado.
- `OSError 1455 (paging file too small)` → use sempre `ChatTimeRunner.get()`,
  nunca `ChatTime(...)` direto.
- PowerShell barrando o venv → `Set-ExecutionPolicy -Scope Process Bypass`.
