# Tutorial — Aurora Responde

Guia passo-a-passo do zero (Windows e Linux/macOS) para clonar e rodar o **Aurora
Responde**: o chat único que usa **só o Jurema-7B** para responder. Para a visão
geral, veja o [README](README.md); para detalhes por componente, [`docs/`](docs/).

---

## 1. Pré-requisitos

Instalar uma vez:

| Ferramenta | Onde |
|------------|------|
| Python 3.12+ | <https://www.python.org/downloads/> *(marque "Add to PATH")* |
| Git | <https://git-scm.com/downloads> |
| Ollama | <https://ollama.com/download> |

Você também precisa de acesso a um **PostgreSQL** com os dados do projeto
(SINAM/VIOLBR + SIPIA-CT) já carregados. As credenciais vão no `.env` (passo 4).

Conferir:
```bash
python --version
git --version
ollama --version
```

---

## 2. Clonar o projeto

**Windows (PowerShell):**
```powershell
cd C:\Users\<voce>\Aurora
git clone https://github.com/projetoaurora41-cloud/Aurora-Responde.git
cd Aurora-Responde
```

**Linux/macOS:**
```bash
git clone https://github.com/projetoaurora41-cloud/Aurora-Responde.git
cd Aurora-Responde
```

---

## 3. Criar o venv e instalar dependências

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1          # se barrar: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

São **8 pacotes leves** (Django, psycopg, pandas/numpy, ollama, markdown,
pypdf, python-dotenv) — segundos, não gigabytes. Sem PyTorch.

---

## 4. Criar o `.env`

Na raiz, copie de [`.env.example`](.env.example) e ajuste as credenciais do banco:

```ini
PGHOST=187.127.34.12
PGPORT=5433
PGDATABASE=Aurora
PGUSER=postgres
PGPASSWORD=SUA_SENHA_AQUI

OLLAMA_MODEL=jurema-7b
JUREMA_MODEL=jurema-7b
SIPIA_CT_TABLE=sipiact.vw_sipiact_long
SIPIA_CT_VALUE_COL=quantidade
```

> O `.env` **nunca** é versionado (está no `.gitignore`). Ele guarda segredos —
> não compartilhe nem faça commit.

---

## 5. Instalar o Jurema-7B no Ollama

O Jurema é o **único LLM** — redige todas as respostas. Baixe uma vez (~4,7 GB) e
apelide como `jurema-7b`:

```bash
ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
ollama cp  hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b
ollama list        # deve listar "jurema-7b"
```

Deixe o Ollama rodando (ele inicia como serviço no Windows/macOS).

---

## 6. Migrar e subir o servidor

```bash
python webapp/manage.py migrate        # Windows: python webapp\manage.py migrate
python webapp/manage.py runserver
```

> Se o banco do `.env` já tem as tabelas (dados + ORM), o `migrate` é
> praticamente no-op. Para criar um admin: `python webapp/manage.py createsuperuser`.

Acesse:

| URL | O que é |
|-----|---------|
| <http://127.0.0.1:8000/> | O chat (home) |
| <http://127.0.0.1:8000/login/> · `/signup/` | Autenticação |
| <http://127.0.0.1:8000/admin/> | Admin Django |

---

## 7. Testar o chat

Abra <http://127.0.0.1:8000/>, clique **+ Nova conversa** e pergunte, por exemplo:

- *"Quantos casos de violência sexual em São Paulo em 2023?"* (dados)
- *"O que diz a Lei Menino Bernardo?"* (legislação)
- *"No Conselho Tutelar, qual a distribuição por sexo?"* (SIPIA-CT)
- *"Como o Aurora Responde funciona?"* (sobre a plataforma)

> A **1ª resposta** demora mais (~1 min) enquanto o Jurema carrega na memória; as
> seguintes são rápidas. Sem GPU funciona, só mais lento.

---

## 8. Problemas comuns

| Sintoma | Solução |
|--------|---------|
| `Ollama indisponível` no rodapé do chat | O Ollama não está rodando, ou o `jurema-7b` não foi instalado (passo 5). |
| `connection ... failed` / `no password supplied` | Credenciais do banco erradas no `.env` (passo 4). |
| Resposta genérica sem números | O Jurema caiu no *fallback* (indisponível) — confira o Ollama. |
| PowerShell barra o `Activate.ps1` | `Set-ExecutionPolicy -Scope Process Bypass` e reative o venv. |

Mais em [docs/troubleshooting.md](docs/troubleshooting.md) e [docs/chat.md](docs/chat.md).
