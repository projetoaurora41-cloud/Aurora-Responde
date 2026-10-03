# Banco de dados (`Aurola`)

PostgreSQL local — **banco único do projeto**. Contém tanto os dados
SINAM/VIOLBR (`VIOLBR*` brutos + `sinam_notificacao` limpo) quanto o estado da
aplicação Django (usuários, consultas salvas, histórico, conversas dos chats e
os embeddings vetoriais via pgvector).

- A **CLI** (`src/db.py`) lê os dados VIOLBR brutos.
- O **Django** lê e grava via ORM (é o `DATABASES["default"]`).

## Conexão

| Parâmetro     | `.env`         | Default      |
|---------------|----------------|--------------|
| Host          | `PGHOST`       | `localhost`  |
| Porta         | `PGPORT`       | `5432`       |
| Database      | `PGDATABASE`   | `Aurola`     |
| Usuário       | `PGUSER`       | `postgres`   |
| Senha         | `PGPASSWORD`   | —            |

Conferir:

```powershell
python -m src.main ping
```

## Tabelas SINAM

Cinco tabelas, uma por ano, com nomes case-sensitive (sempre entre aspas):

| Ano   | Tabela       |
|-------|--------------|
| 2020  | `"VIOLBR20"` |
| 2021  | `"VIOLBR21"` |
| 2022  | `"VIOLBR22"` |
| 2023  | `"VIOLBR23"` |
| 2024  | `"VIOLBR24"` |

Schema: `public`.

## Colunas-chave (referência rápida)

| Coluna          | Tipo  | Conteúdo                                         |
|-----------------|-------|---------------------------------------------------|
| `DT_NOTIFIC`    | text  | Data da notificação no formato `YYYY-MM-DD`       |
| `CS_SEXO`       | text  | `F`/`M`/`I`                                       |
| `NU_IDADE_N`    | text  | Idade com prefixo de unidade                      |
| `CS_RACA`       | text  | Código IBGE de raça/cor                           |
| `SG_UF`         | text  | UF do município de residência                     |
| `ID_MUNICIP`    | text  | Código IBGE do município                          |

> `DT_NOTIFIC` é `text`, não `date`. Sempre filtrar com regex antes de
> converter: `WHERE "DT_NOTIFIC" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'`. Caso
> contrário, valores corrompidos quebram `::date`.

Lista completa via:

```powershell
python -m src.main describe VIOLBR24
```

## Padrão de consulta para séries temporais

ChatTime espera uma série numérica regular. Recomendação:

```sql
SELECT "DT_NOTIFIC"::date AS data,
       COUNT(*)::int AS valor
  FROM "VIOLBR24"
 WHERE "DT_NOTIFIC" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
 GROUP BY 1
 ORDER BY 1;
```

- O alias `data` é o default do `--date-col`.
- O alias `valor` é o default do `--value-col`.
- Para mensal, troque `"DT_NOTIFIC"::date` por
  `date_trunc('month', "DT_NOTIFIC"::date)::date` e passe `--freq ME`.

Veja
[`webapp/forecasts/management/commands/seed_queries.py`](../webapp/forecasts/management/commands/seed_queries.py)
para mais exemplos prontos.

## Helpers em `src/db.py`

| Função                                   | O que faz                                        |
|------------------------------------------|--------------------------------------------------|
| `ping()`                                 | `SELECT version()`                               |
| `list_tables(schema)`                    | Lista tabelas do schema                          |
| `describe_table(table, schema)`          | Colunas/tipos                                    |
| `run_query(sql, params)`                 | SQL → `pd.DataFrame`                             |
| `time_series(sql, date_col, value_col, freq)` | DataFrame → `(DatetimeIndex, np.ndarray)`     |
| `violbr_daily_counts(year, where)`       | Atalho para `VIOLBR<YY>` diário                  |
