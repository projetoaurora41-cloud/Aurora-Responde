# Troubleshooting

## `ModuleNotFoundError: No module named 'db'`

Você rodou `python src/main.py` direto. O arquivo usa imports relativos
(`from . import db`), então só funciona como módulo:

```powershell
python -m src.main ping
```

## `ModuleNotFoundError: No module named 'django'` (ou outra dep)

O venv não está ativo. Em todo terminal novo:

```powershell
cd C:\Users\herna\Projeto_Sinam
.\venv\Scripts\Activate.ps1
```

Confirme com `(venv)` no prompt.

## `OperationalError: connection refused` / `password authentication failed`

Postgres não está rodando ou o `.env` está com host/porta/usuário/senha
errados. Verifique:

```powershell
Get-Service postgresql*           # status do serviço
psql -U postgres -d Aurola -c "SELECT 1"
```

## `OSError 1455 (paging file too small)` ao carregar o modelo

O `LlamaForCausalLM.from_pretrained(..., device_map="auto")` original tenta
mmap todos os shards de uma vez e estoura o pagefile do Windows. O wrapper
em [`src/chattime_runner.py`](../src/chattime_runner.py) evita isso ao
fixar o device.

**Nunca** instancie `ChatTime(...)` direto. Use:

```python
from src.chattime_runner import ChatTimeRunner
runner = ChatTimeRunner.get(hist_len=N, pred_len=H)
```

## PowerShell barrando o `Activate.ps1`

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\venv\Scripts\Activate.ps1
```

A política `Bypass` vale só para essa sessão.

## Servidor Django "trava" no primeiro forecast

Esperado. A primeira chamada carrega o modelo (~13 GB de mmap + dezenas de
segundos de inicialização). Em CPU pode levar vários minutos. As próximas
inferências usam o singleton em memória.

Para produção:

```bash
gunicorn sinamweb.wsgi --workers 1 --timeout 600
```

`--workers 1` mantém o singleton. `--timeout 600` cobre cold start.

## `TemplateDoesNotExist: registration/login.html`

Confira que [`webapp/templates/`](../webapp/templates/) existe e que
`TEMPLATES.DIRS` em `webapp/sinamweb/settings.py` aponta para
`BASE_DIR / "templates"`. Se você apagou e recriou a pasta, talvez tenha
sumido o diretório `registration/`.

## Forecast retorna valores estranhos / negativos

ChatTime trabalha com discretização interna; valores fora da escala
histórica podem aparecer. Verifique:

- A série tem pelo menos ~100 pontos? (séries muito curtas dão lixo)
- `--freq` bate com a granularidade dos dados?
- `--context` descreve o que a série representa? O modelo é sensível a isso.

## QA sempre devolve vazio

`analyze_verbose` extrai a letra via três regex em ordem
([`src/chattime_runner.py`](../src/chattime_runner.py)). Se as amostras do
modelo não contêm `(a)`, `a)`, ou começam com `a`/`b`/`c`, a função
retorna `""`. Cheque as `raw_samples` salvas — formate a pergunta como
"... (a) ... (b) ... (c) ...?" para aumentar a chance de match.

## Resetar o banco do Django

O banco do Django agora é o **PostgreSQL `Aurola`** (não mais o SQLite). Para
recriar o schema da aplicação sem tocar nos dados VIOLBR brutos, apague as
tabelas do Django (ou recrie o banco) e rode:

```powershell
python webapp\manage.py migrate
python webapp\manage.py seed_queries
python webapp\manage.py createsuperuser
```

> O `webapp\db.sqlite3` é apenas o backup legado. Para recopiá-lo para o
> Postgres, use `python webapp\manage.py migrate_sqlite_to_pg`.
