# Camada Semântica (`webapp/sinam/`)

Representação higienizada das notificações SINAM/VIOLBR para uso direto pelo
chat e por análises. Mantém o Postgres `Aurola` como **source-of-truth**
imutável; replica os dados num modelo Django com vocabulário humano.

## Por que existe

O schema bruto VIOLBR tem ~150 colunas TEXT com nomes crípticos (`SG_UF`,
`NU_IDADE_N`, `VIOL_TORT`, `CS_RACA`) e valores codificados (`'28'`=Sergipe,
`'4012'`=12 anos, `'1'`=Sim). Pedir pro LLM construir SQL nesse schema gera:

- nomes em português alucinados (`UF`, `ano`, `IDADE`)
- tabelas inexistentes (`VIOLBR21_viols`)
- siglas onde precisava de código IBGE
- regex e SUBSTRING toda vez que precisa idade ou ano

A camada semântica resolve isso: o LLM passa a falar em filtros estilo Django
(`{"uf": "SE", "ano": 2023, "idade_anos__lt": 13, "violencia_sexual": True}`) e
não precisa decorar nada do schema raw.

## Modelo: `Notificacao` (~25 campos)

Definido em [`webapp/sinam/models.py`](../webapp/sinam/models.py). Cada linha
é uma notificação SINAM, com códigos já traduzidos:

| Grupo            | Campos                                                                  |
|------------------|--------------------------------------------------------------------------|
| Datas            | `data_notificacao` (Date) · `data_ocorrencia` · `ano` · `semana_epi`     |
| Vítima           | `sexo` (M/F/I) · `idade_anos` · `faixa_etaria` · `raca_cor` · `escolaridade` · `gestante` |
| Localização      | `uf` (sigla) · `uf_ocorrencia` · `municipio_codigo` (IBGE 7d) · `local_ocorrencia` |
| Violências (10)  | `violencia_fisica` · `violencia_psicologica` · `violencia_sexual` · `tortura` · `trafico_pessoas` · `violencia_financeira` · `negligencia` · `violencia_infantil` · `intervencao_legal` · `outras_violencias` (todas `Boolean`/null) |
| Outros           | `lesao_autoprovocada` · `ocorreu_outras_vezes` · `autor_sexo` · `autor_alcool` |

Storage: **PostgreSQL** — o banco padrão do projeto (`.env` `PG*`, base
`Aurola`), tabela `sinam_notificacao` (~3 M notificações). Índices em
`data_notificacao`, `ano`, `uf`, `sexo`, `idade_anos`, `faixa_etaria` e nas 8
violências mais usadas.

## ETL: `etl_violbr`

[`webapp/sinam/management/commands/etl_violbr.py`](../webapp/sinam/management/commands/etl_violbr.py)

```powershell
# Importa tudo (2020-2024) ~ 10 min em CPU comum
python webapp\manage.py etl_violbr

# Só um ano
python webapp\manage.py etl_violbr --year 2024

# Reset antes de importar
python webapp\manage.py etl_violbr --clear

# Smoke (5k linhas por tabela)
python webapp\manage.py etl_violbr --limit 5000
```

O comando lê via `psycopg.cursor.fetchmany(5000)` (streaming) e popula em
`bulk_create` de 2000 linhas. Performance observada: ~4000 linhas/s. Idempotente
quando combinado com `--clear`.

### Tradução de códigos

Tabelas em [`webapp/sinam/lookups.py`](../webapp/sinam/lookups.py):

| Origem                   | Destino                                                            |
|--------------------------|---------------------------------------------------------------------|
| `SG_UF = '28'`           | `uf = 'SE'`                                                         |
| `CS_RACA = '4'`          | `raca_cor = 'Parda'`                                                |
| `NU_IDADE_N = '4012'`    | `idade_anos = 12` (prefixo 4 = anos)                                |
| `NU_IDADE_N = '3010'`    | `idade_anos = 0` (10 meses → arredondado para zero ano)             |
| `VIOL_FISIC = '1'`       | `violencia_fisica = True`                                           |
| `VIOL_FISIC = '2'`       | `violencia_fisica = False`                                          |
| `VIOL_FISIC = '9'/null`  | `violencia_fisica = None`                                           |
| `LOCAL_OCOR = '03'`      | `local_ocorrencia = 'Escola'`                                       |

`faixa_etaria` é derivada de `idade_anos`: `< 1 ano | 1-4 | 5-9 | 10-14 |
15-19 | 20-59 | 60+ | Ignorada`.

## API: `webapp/sinam/queries.py`

Helpers ORM acessados pelas tools do chat. Toda função aceita um dict
`filters` que passa por uma **whitelist** (`ALLOWED_FILTERS`) — chaves não
reconhecidas são descartadas e devolvidas em `filters_ignored`.

| Função                                       | Retorno                                              |
|----------------------------------------------|------------------------------------------------------|
| `query(filters, limit=50)`                   | `{total_rows, rows: [...], filters_applied, ...}`    |
| `aggregate(filters, group_by, top=20)`       | `{total_rows, rows: [{<grouping>, n}], ...}`         |
| `time_series(filters, freq="D")`             | `{n_points, dates: [...], values: [...]}`            |
| `series_for_forecast(filters, freq)`         | `(np.array, DatetimeIndex, info_dict)` para auto_fc  |

### Filtros aceitos

```
# Geografia
uf, uf_ocorrencia (sigla)
municipio_codigo (IBGE 7d)

# Vítima
sexo ("M" | "F" | "I")
idade_anos · idade_anos__lt · idade_anos__lte · idade_anos__gt · idade_anos__gte
faixa_etaria ("< 1 ano" | "1-4" | "5-9" | "10-14" | "15-19" | "20-59" | "60+")
raca_cor ("Branca" | "Preta" | "Amarela" | "Parda" | "Indigena")
escolaridade (texto)

# Datas
ano · ano__gte · ano__lte
data_notificacao__gte · data_notificacao__lte (YYYY-MM-DD)
semana_epi

# Violências (bool)
violencia_fisica, violencia_psicologica, violencia_sexual, tortura,
trafico_pessoas, violencia_financeira, negligencia, violencia_infantil,
intervencao_legal, outras_violencias

# Outros
lesao_autoprovocada, ocorreu_outras_vezes, local_ocorrencia,
autor_sexo, autor_alcool
```

## Tools do chat que usam a camada semântica

Em [`webapp/chat/tools.py`](../webapp/chat/tools.py):

| Tool                     | Mapeia para                |
|--------------------------|-----------------------------|
| `consultar`              | `queries.query`             |
| `contar`                 | `queries.aggregate`         |
| `serie_temporal`         | `queries.time_series`       |
| `previsao_automatica`    | `series_for_forecast` + `auto_forecast` |

As tools antigas (`run_sql`, `peek_table`, `forecast_from_sql`, `auto_forecast`,
etc.) continuam disponíveis como atalhos para casos não cobertos.

## Manutenção

Três caminhos para atualizar:

### A. Upload de arquivo `.dbc` pela UI (mais comum)

Página: `/sinam/importar/`. Aceita o arquivo `.dbc` que você baixa direto do
DataSUS (formato compactado proprietário). O processamento:

1. Descomprime `.dbc` → `.dbf` via [`dbctodbf`](https://pypi.org/project/dbc_to_dbf/)
   (pure-python, ~3-5 min para arquivos típicos do VIOLBR).
2. Lê o DBF via [`dbfread`](https://pypi.org/project/dbfread/).
3. Traduz códigos e popula `Notificacao` em `bulk_create` de 2000 linhas.
4. Roda em **thread daemon** (não bloqueia o servidor); a página de detalhe
   recarrega a cada 3 s mostrando progresso.

Tudo em [`webapp/sinam/views.py:upload`](../webapp/sinam/views.py) +
[`etl.py:import_dbc_file`](../webapp/sinam/etl.py). Histórico em
`ImportacaoDBC` (visível em `/admin/`).

### B. Re-importar do Postgres `Aurola`

Quando os dados já estiverem no Postgres (ETL externo do DataSUS, por exemplo
do servidor da Vigilância):

```powershell
# Todos os anos
python webapp\manage.py etl_violbr

# Só um
python webapp\manage.py etl_violbr --year 2024 --clear
```

### C. Limpar tudo

```powershell
python webapp\manage.py etl_violbr --clear        # do Postgres
# ou via admin do Django: deletar Notificacao
```

### Quando o SINAM atualizar o schema

Se DataSUS adicionar/remover colunas:

1. Ajustar `SRC_COLUMNS` em [`etl_violbr.py`](../webapp/sinam/management/commands/etl_violbr.py).
2. Se for novo campo útil → adicionar ao `Notificacao` + migration + tradução
   em [`lookups.py`](../webapp/sinam/lookups.py).
3. Re-rodar o ETL.

## Quando NÃO usar a camada semântica

- Pesquisa que precisa de uma coluna *não* incluída nos 25 essenciais. Use
  `run_sql` ou `peek_table` direto na tabela `VIOLBRxx`.
- Auditoria que exige rastreabilidade exata de uma linha do banco original
  (a camada limpa filtra ~100 colunas no caminho).
- Cruzamento com outras bases SUS que vivem no Postgres mas não passam pela
  ETL — `run_sql` pode unir.
