# Troubleshooting

## `ModuleNotFoundError: No module named 'django'` (ou outra dep)

O venv não está ativo. Em todo terminal novo:

```powershell
cd C:\Users\<voce>\Aurora\Aurora-Responde
.\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
```

Confirme com `(venv)` no prompt. Se faltar algo: `pip install -r requirements.txt`.

## PowerShell barrando o `Activate.ps1`

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\venv\Scripts\Activate.ps1
```

A política `Bypass` vale só para essa sessão.

## `connection ... failed` / `no password supplied` / `password authentication failed`

O `.env` está com host/porta/usuário/senha errados, ou o PostgreSQL não aceita a
conexão. Verifique as variáveis `PG*` no `.env` e teste:

```bash
python webapp/manage.py check          # carrega settings e valida
```

Lembre: o banco é **externo** — confirme `PGHOST`/`PGPORT` e que ele aceita
conexões da sua máquina.

## O chat responde "Ollama indisponível" ou cai no fallback

O Jurema é o único LLM. Verifique:

```bash
ollama list          # deve listar "jurema-7b"
```

Se não listar, instale:

```bash
ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
ollama cp  hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b
```

Confirme também que o Ollama está rodando e que `OLLAMA_HOST` no `.env` aponta
para ele (`http://127.0.0.1:11434` por padrão). Sem o Jurema, o chat ainda
responde, mas cai no *fallback* (narrativa pronta, sem reescrita do modelo).

## A primeira resposta demora muito (~1 min)

Esperado: a 1ª chamada carrega o Jurema na memória. As seguintes são rápidas.
Em CPU (sem GPU) o carregamento é mais lento. Suba o `JUREMA_NUM_PREDICT` só se
precisar de respostas mais longas (custa tempo).

## O chat responde com números "redondos" ou genéricos

Sinal de que o Jurema caiu no *fallback* (Ollama indisponível) **ou** que a
pergunta não casou com nenhum filtro. Confira o Ollama e reformule citando
estado, ano e tipo de violência. Os números vêm sempre do PostgreSQL — o modelo
não os inventa.

## `TemplateDoesNotExist: registration/login.html`

Confira que [`webapp/templates/`](../webapp/templates/) existe e que
`TEMPLATES.DIRS` em `webapp/aurora/settings.py` aponta para `BASE_DIR / "templates"`.

## "You have N unapplied migration(s)"

No fork, as migrações pendentes `guardrails.0001` e `orquestrador.0005` são
**no-op** (não alteram o banco). O aviso é cosmético; se quiser silenciá-lo e o
banco for seu, rode `python webapp/manage.py migrate`.

## Resetar o banco do Django

O estado do Django vive no **PostgreSQL** do `.env`. Para recriar o schema da
aplicação sem tocar nos dados brutos, apague as tabelas do Django (ou recrie o
banco) e rode:

```bash
python webapp/manage.py migrate
python webapp/manage.py createsuperuser
```
