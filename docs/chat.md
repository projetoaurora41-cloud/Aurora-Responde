# Chat (roteador determinístico + Jurema)

Interface conversacional única do Aurora Responde. A pergunta em PT-BR passa por
um **roteador determinístico** (código) que escolhe **uma** fonte; o **Jurema-7B**
(via Ollama) redige a resposta. Tudo local — nenhuma chamada a API externa.

```
Usuário ─► guardrails(entrada) ─► roteador determinístico ─┬─ relatorio_brasil/uf/municipio  (SQL SINAM)
                                                           ├─ ranking_municipios             (SQL SINAM)
                                                           ├─ rag_juridico                   (corpus de leis)
                                                           ├─ consulta_sipia_ct              (view SIPIA-CT)
                                                           └─ rag_interno                    (docs/*.md)
                                      │
                                      └─► Jurema-7B redige ─► guardrails(saída) ─► resposta
```

## Pré-requisitos

1. **Instalar o [Ollama](https://ollama.com/download)**.
2. **Instalar o Jurema-7B** (único LLM, ~4,7 GB) e apelidá-lo `jurema-7b`:
   ```bash
   ollama pull hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF
   ollama cp  hf.co/rlmoura/Jurema-7B-Q4_K_M-GGUF jurema-7b
   ```
3. GPU ajuda, mas **não é obrigatória** (em CPU a 1ª resposta demora mais, pois
   carrega o modelo na memória; as seguintes são rápidas).

## Roteador determinístico (sem LLM escolhendo)

Em [`orchestrator.py`](../webapp/chats/series_temporais/orquestrador/orchestrator.py).
Parte de um default (`relatorio_brasil`, `{}`) e refina com detectores de texto —
os mesmos que, no projeto original, apenas **corrigiam** o Qwen3:

| Detector | Decide |
|----------|--------|
| `_route_category` | tema: dados / legislação / produto / SIPIA-CT |
| `_maybe_rewrite_tool_call` | nível geográfico: Brasil / UF / município |
| `_maybe_rewrite_to_ranking` | ranking ("cidade mais violenta", "top estados") |
| `_enforce_violencia_filter` | tipo de violência (herda do contexto em follow-ups) |
| `_extract_year_filter` | ano (`ano`) ou intervalo (`ano__gte`/`ano__lte`) |

A ferramenta escolhida roda **uma vez** (`run_tool`). O resultado completo vai
para o banco (para a UI); uma versão humanizada (`_humanize_result_for_llm`, com
uma `narrativa_sugerida` pronta) alimenta o gerador.

## Ferramentas

| Tool | Quando o roteador usa | Fonte |
|------|-----------------------|-------|
| `relatorio_brasil` | pergunta nacional | SQL SINAM ao vivo |
| `relatorio_uf` | menção a um estado | SQL SINAM ao vivo |
| `relatorio_municipio` | menção a uma cidade | SQL SINAM ao vivo |
| `ranking_municipios` | pedido de ranking | SQL SINAM ao vivo |
| `rag_juridico` | tema jurídico/leis | corpus curado ([`leis_corpus.py`](../webapp/chats/series_temporais/orquestrador/leis_corpus.py)) |
| `consulta_sipia_ct` | Conselho Tutelar / SIPIA | view `sipiact.vw_sipiact_long` |
| `rag_interno` | "como o Aurora funciona" | busca por palavra-chave nos `docs/*.md` |

As ferramentas de relatório devolvem números **exatos** do PostgreSQL (totais por
ano, rankings, séries). Não há forecasting: relatórios são SQL puro.

## Geração com o Jurema

`_narrar_com_jurema` (em `orchestrator.py`) monta o prompt a partir do payload e
chama o Jurema (`ollama.generate`). Regras embutidas no prompt: usar **apenas** os
números fornecidos, não citar anos sem dados, prosa curta em PT-BR.

- **Jurídico:** o parecer já é gerado dentro de `rag_juridico` (via `_ask_jurema`),
  ancorado nos trechos de lei; `_narrar_com_jurema` só o repassa + cita a base legal.
- **Dados / SIPIA / produto:** o Jurema reescreve a `narrativa_sugerida`.
- **Fallback:** se o Jurema estiver indisponível ou divagar, usa a própria
  `narrativa_sugerida` — garante sempre uma resposta.

## Variáveis de ambiente

| Variável | Default |
|----------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` / `JUREMA_MODEL` | `jurema-7b` |
| `JUREMA_NUM_PREDICT` | `520` |
| `AURORA_MAX_DATA_YEAR` | `2024` |

## Exemplos

- *"Quantos casos de violência sexual em SP em 2023?"* → `relatorio_uf(SP, violencia_sexual, ano=2023)`
- *"Qual a cidade mais violenta do Ceará?"* → `ranking_municipios(uf=CE)`
- *"O que diz a Lei Menino Bernardo?"* → `rag_juridico` → parecer do Jurema citando a lei
- *"Distribuição por sexo no Conselho Tutelar"* → `consulta_sipia_ct(indicador=Sexo)`
- *"Como o Aurora Responde funciona?"* → `rag_interno`

## Limitações conhecidas

- **Sem streaming:** a resposta vem inteira após a geração.
- **1ª resposta lenta:** o Jurema carrega na memória na primeira chamada.
- **Multi-intenção:** uma pergunta que mistura "dados E lei" cai em uma rota só
  (aceitável para esta versão).
- **Dados = notificações registradas** (SINAM/SIPIA), sujeitas a subnotificação.
