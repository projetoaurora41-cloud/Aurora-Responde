# CLI — `python -m src.main`

Todas as chamadas devem usar `-m src.main` (módulo), nunca `python src/main.py`
direto — esse arquivo usa imports relativos. Veja
[troubleshooting.md](troubleshooting.md#modulenotfounderror-no-module-named-db).

## Subcomandos

### `ping`

Testa a conectividade com o Postgres.

```powershell
python -m src.main ping
```

Saída: string de versão do servidor.

---

### `tables`

Lista tabelas do schema.

```powershell
python -m src.main tables --schema public
```

| Flag        | Default   | Descrição                  |
|-------------|-----------|----------------------------|
| `--schema`  | `public`  | Schema a listar            |

---

### `describe <tabela>`

Mostra `column_name`, `data_type`, `is_nullable`.

```powershell
python -m src.main describe VIOLBR24 --schema public
```

---

### `query`

Executa uma SQL arbitrária e imprime o resultado como tabela.

```powershell
python -m src.main query --sql "SELECT COUNT(*) FROM \"VIOLBR24\""
```

Sem `--sql`, lê de stdin:

```powershell
type minha.sql | python -m src.main query
```

---

### `forecast`

Pega uma SQL que retorna `(data, valor)` e chama o ChatTime para prever
`--horizon` passos à frente.

```powershell
python -m src.main forecast `
  --sql "SELECT ""DT_NOTIFIC""::date AS data, COUNT(*)::int AS valor FROM ""VIOLBR24"" WHERE ""DT_NOTIFIC"" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' GROUP BY 1 ORDER BY 1" `
  --date-col data --value-col valor `
  --freq D --horizon 14 `
  --context "Notificacoes diarias SINAM 2024"
```

| Flag           | Default | Descrição                                            |
|----------------|---------|-------------------------------------------------------|
| `--sql`        | stdin   | SQL retornando `(data, valor)`                       |
| `--date-col`   | `data`  | Nome da coluna de data                               |
| `--value-col`  | `valor` | Nome da coluna numérica                              |
| `--freq`       | —       | Freq pandas para resample: `D`, `W`, `MS`, `ME`, `QE`, `YE` |
| `--horizon`    | `24`    | Quantos passos prever                                |
| `--context`    | —       | Contexto em linguagem natural passado ao modelo      |

Saída: `t+1`..`t+N` com os valores previstos.

---

### `ask`

Pergunta de múltipla escolha sobre uma série.

```powershell
python -m src.main ask "A tendencia e (a) crescente (b) estavel (c) decrescente?" `
  --sql "..." --freq D
```

O modelo gera N amostras (`num_samples=8` por default) e o subcomando devolve
a letra mais votada. Quando nenhuma letra puder ser extraída, retorna vazio
— o histórico salvo registra todas as amostras brutas para debug.

---

## Variáveis de ambiente

Lidas via `python-dotenv` a partir do `.env` na raiz:

| Variável         | Default                              |
|------------------|---------------------------------------|
| `PGHOST`         | `localhost`                           |
| `PGPORT`         | `5432`                                |
| `PGDATABASE`     | `Aurola`                              |
| `PGUSER`         | `postgres`                            |
| `PGPASSWORD`     | (obrigatório)                         |
| `CHATTIME_MODEL` | `ChengsenWang/ChatTime-1-7B-Chat`     |
