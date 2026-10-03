# Interface web (Django)

Aplicação em [`webapp/`](../webapp/) que dá UI a tudo que a CLI faz, mais
catálogo de consultas salvas, histórico persistente e autenticação.

## Setup

```powershell
python webapp\manage.py migrate
python webapp\manage.py seed_queries        # consultas iniciais
python webapp\manage.py createsuperuser     # primeiro usuário
python webapp\manage.py runserver
```

Abre em <http://127.0.0.1:8000/>.

## URLs

| Rota                     | View                          | Descrição                              |
|--------------------------|-------------------------------|----------------------------------------|
| `/login/`                | `auth_views.LoginView`        | Login                                  |
| `/signup/`               | `forecasts.views.signup`      | Cadastro                               |
| `/logout/`               | `auth_views.LogoutView`       | Logout (POST)                          |
| `/`                      | `query_list`                  | Lista de `SavedQuery`                  |
| `/new/`                  | `query_create`                | Form para cadastrar consulta           |
| `/<id>/`                 | `query_detail`                | Detalhe: SQL, gráfico, forms F/QA      |
| `/<id>/edit/`            | `query_edit`                  | Editar consulta                        |
| `/<id>/delete/`          | `query_delete`                | Remover consulta                       |
| `/<id>/forecast/`        | `run_forecast_view`           | POST: roda forecast                    |
| `/<id>/qa/`              | `run_qa_view`                 | POST: roda QA                          |
| `/forecasts/<id>/`       | `forecast_detail`             | Resultado de um ForecastRun            |
| `/qa/<id>/`              | `qa_detail`                   | Resultado de um QARun                  |
| `/history/`              | `history`                     | Forecasts + QAs recentes               |
| `/admin/`                | Django admin                  | CRUD direto + permissões               |

Todas as views (exceto login/signup) exigem `@login_required`.

## Modelos

```python
SavedQuery(name, description, sql, date_col, value_col, freq,
           default_context, default_horizon, created_by, timestamps)
ForecastRun(query, user, horizon, context,
            history_dates, history_values, predicted_values,
            elapsed_seconds, error, created_at)
QARun(query, user, question, answer, raw_samples,
      elapsed_seconds, error, created_at)
```

`history_*`, `predicted_values`, `raw_samples` são `JSONField`, então a UI
pode plotar Chart.js direto sem nova chamada ao banco.

## Service layer

`forecasts/services.py` é a única ponte entre Django e `src/`. Mantém Django
ignorante sobre psycopg/torch e oferece tipos `dataclass` que viram JSON
naturalmente nos modelos.

```python
load_series(sql, date_col, value_col, freq) -> SeriesResult
run_forecast(sql, date_col, value_col, freq, horizon, context) -> ForecastResult
run_qa(sql, date_col, value_col, freq, question) -> QAResult
```

Erros viram campo `error: str` em vez de exceção, para o caller persistir o
fracasso no histórico sem `try/except` espalhado.

## Singleton do ChatTime

`ChatTimeRunner.get()` retorna a mesma instância em todas as chamadas. Em
produção use **1 worker gunicorn** para manter o modelo em memória:

```bash
gunicorn sinamweb.wsgi --workers 1 --timeout 600
```

`--timeout 600` cobre o load inicial em CPU (vários minutos). Múltiplos
workers carregariam ~13 GB cada — desnecessário para inferência sequencial.

## Variáveis de ambiente

Carregadas em [`webapp/sinamweb/settings.py`](../webapp/sinamweb/settings.py)
via `python-dotenv` (mesmo `.env` da CLI).

| Variável                  | Default                       | Para que serve                           |
|---------------------------|-------------------------------|------------------------------------------|
| `DJANGO_SECRET_KEY`       | `django-insecure-dev-only...` | **Trocar em produção**                   |
| `DJANGO_DEBUG`            | `1`                           | `0` em produção                          |
| `DJANGO_ALLOWED_HOSTS`    | `localhost,127.0.0.1`         | Lista separada por vírgula               |
| Resto                     | —                             | mesmas do CLI: `PG*`, `CHATTIME_MODEL`   |

## Adicionar uma consulta nova

Duas opções:

1. **UI:** `/new/` → preenche nome, SQL, `date_col`/`value_col`, `freq` opcional.
2. **Seed programático:** edite
   [`webapp/forecasts/management/commands/seed_queries.py`](../webapp/forecasts/management/commands/seed_queries.py),
   acrescente um dict em `SEEDS`, depois:
   ```powershell
   python webapp\manage.py seed_queries --overwrite
   ```
