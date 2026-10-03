# Interface web (Django)

Aplicação em [`webapp/`](../webapp/) — o chat único do Aurora Responde, com
autenticação e histórico de conversas por usuário.

## Setup

```bash
python webapp/manage.py migrate        # Windows: python webapp\manage.py migrate
python webapp/manage.py createsuperuser   # opcional (1º admin)
python webapp/manage.py runserver
```

Abre em <http://127.0.0.1:8000/>. (Requer o Ollama com o `jurema-7b` — ver
[chat.md](chat.md).)

## URLs

| Rota | View | Descrição |
|------|------|-----------|
| `/` | `orquestrador.views.aurora_home` | O chat (abre a conversa mais recente) |
| `/login/` · `/signup/` · `/logout/` | auth / `core.views.signup` | Autenticação |
| `/series-temporais/chat/` | `thread_list` | Lista de conversas |
| `/series-temporais/chat/new/` | `new_thread` | Nova conversa (POST) |
| `/series-temporais/chat/<id>/` | `thread` | Abre uma conversa |
| `/series-temporais/chat/<id>/send/` | `send_message` | Envia mensagem (POST) |
| `/series-temporais/chat/<id>/delete/` | `delete_thread` | Remove conversa (POST) |
| `/admin/` | Django admin | CRUD + permissões |

O chat funciona para visitantes anônimos (por sessão) e logados (por usuário).

## Modelos

Em [`orquestrador/models.py`](../webapp/chats/series_temporais/orquestrador/models.py):

```python
ChatThread(user|session_key, title, model="jurema-7b", temperature, timestamps)
ChatMessage(thread, role, content, tool_name, tool_payload (JSON),
            tokens_prompt, tokens_completion, elapsed_seconds, created_at)
ChatAttachment(message, file, ...)   # anexos opcionais
```

`tool_payload` guarda o resultado completo da ferramenta (para a UI); o texto
final é redigido pelo Jurema (ver [chat.md](chat.md)).

## Fluxo de uma mensagem

1. `send_message` aplica os **guardrails de entrada** (limite de uso, risco,
   injeção, PII) antes de qualquer processamento.
2. Persiste a mensagem do usuário e chama `orchestrator.chat(...)`.
3. O orquestrador roteia determinadamente, roda **uma** ferramenta e o
   **Jurema** redige a resposta.
4. **Guardrails de saída**, persiste a resposta e redireciona para a conversa.

## Variáveis de ambiente

Carregadas em [`webapp/aurora/settings.py`](../webapp/aurora/settings.py) via
`python-dotenv` (o `.env` da raiz).

| Variável | Default | Para que serve |
|----------|---------|----------------|
| `DJANGO_SECRET_KEY` | dev-only | **Trocar em produção** |
| `DJANGO_DEBUG` | `1` | `0` em produção |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos |
| `PG*` | — | Conexão PostgreSQL |
| `OLLAMA_MODEL` / `JUREMA_MODEL` | `jurema-7b` | Modelo gerador |

Ver a lista completa no [README](../README.md#variáveis-de-ambiente-env).
