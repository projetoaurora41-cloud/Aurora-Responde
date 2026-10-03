# Banco de dados (`Aurola`)

PostgreSQL — **banco único do projeto** (externo, definido no `.env`). Contém
tanto os dados SINAM/VIOLBR (`VIOLBR*` brutos + `sinam_notificacao` limpo) e o
SIPIA-CT (`sipiact.vw_sipiact_long`) quanto o estado da aplicação Django
(usuários e conversas dos chats).

- O módulo **`src/db.py`** acessa os dados (consultas SQL ao vivo).
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

```bash
python webapp/manage.py check
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

## Padrão de consulta para séries temporais

Os relatórios (`relatorio_*`) montam séries regulares assim:

```sql
SELECT "DT_NOTIFIC"::date AS data,
       COUNT(*)::int AS valor
  FROM "VIOLBR24"
 WHERE "DT_NOTIFIC" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
 GROUP BY 1
 ORDER BY 1;
```

- Para mensal, troque `"DT_NOTIFIC"::date` por
  `date_trunc('month', "DT_NOTIFIC"::date)::date`.

Os helpers de agregação/série ficam na camada semântica (`sinam.queries`) e em
`src/db.py`.

## Helpers em `src/db.py`

| Função                                   | O que faz                                        |
|------------------------------------------|--------------------------------------------------|
| `ping()`                                 | `SELECT version()`                               |
| `list_tables(schema)`                    | Lista tabelas do schema                          |
| `describe_table(table, schema)`          | Colunas/tipos                                    |
| `run_query(sql, params)`                 | SQL → `pd.DataFrame`                             |
| `time_series(sql, date_col, value_col, freq)` | DataFrame → `(DatetimeIndex, np.ndarray)`     |
| `violbr_daily_counts(year, where)`       | Atalho para `VIOLBR<YY>` diário                  |
