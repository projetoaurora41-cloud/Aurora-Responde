# Roteiro de testes — Aurora responde

Bateria de perguntas para **navegar por todas as rotas/fontes ("modelos")** do
chat único (Aurora responde) e validar o roteador, os filtros e os follow-ups.

## Como testar
1. Abra a home (`/`) — o chat já começa numa conversa nova.
2. Cole a pergunta e envie (Ctrl+Enter).
3. Confira o chip **"Consultou `<ferramenta>`"** logo abaixo do seu texto e clique
   em **detalhes** para ver os argumentos e o resultado da ferramenta.
4. A resposta é redigida pelo **Jurema-7B** (badge 🧠 Jurema-7B na mensagem).

As 4 rotas ("modelos") que o roteador escolhe:

| Rota | Ferramenta | Quando |
|------|-----------|--------|
| **SINAM — dados de saúde** | `relatorio_uf` / `relatorio_municipio` / `relatorio_brasil` / `ranking_municipios` / `serie_temporal` / `contar` | pergunta pede números/estatística de violência |
| **Jurídico (Jurema)** | `rag_juridico` | pergunta é SOBRE a lei/ECA/norma |
| **Produto / metodologia** | `rag_interno` | pergunta é sobre o próprio Aurora |
| **SIPIA-CT (Conselho Tutelar)** | `consulta_sipia_ct` | indicadores do SIPIA (direito violado, agente violador…) |

---

## 1. Rota SINAM — níveis geográficos

- **Brasil (nacional):** `Negligência contra crianças no Brasil de 2020 a 2024`
  → `relatorio_brasil`
- **Estado (UF por nome):** `Como evoluiu a violência sexual em Sergipe?`
  → `relatorio_uf(SE)`
- **Estado (UF por sigla):** `Violência física contra adolescentes em SP`
  → `relatorio_uf(SP)`
- **Município (cidade-UF):** `Mostra a evolução das notificações em Salvador-BA`
  → `relatorio_municipio(Salvador, BA)`
- **Município (capital sem UF):** `Casos de violência infantil em Aracaju`
  → `relatorio_municipio(Aracaju, SE)`
- **Ranking de cidades:** `Top 5 cidades com mais tortura em SP em 2024`
  → `ranking_municipios(SP)`

## 2. Rota SINAM — todos os tipos de violência
(valide, em **detalhes**, que `filters_extra` recebeu o tipo certo)

- `Violência sexual contra crianças em Pernambuco` → `violencia_sexual`
- `Violência física contra adolescentes em Minas Gerais` → `violencia_fisica`
- `Violência psicológica no Rio de Janeiro está crescendo?` → `violencia_psicologica`
- `Tortura contra adolescentes em Minas Gerais` → `tortura`
- `Negligência infantil no Paraná` → `negligencia`
- `Tráfico de crianças no Rio de Janeiro` → `trafico_pessoas`
- `Violência infantil no país nos últimos 4 anos` → `violencia_infantil`

## 3. Rota Jurídica (rag_juridico)
(pergunta SOBRE a norma — deve consultar `rag_juridico`, NÃO os dados)

- `O que diz a Lei Henry Borel (Lei 14.344/2022)?`
- `Quais direitos a criança e o adolescente têm segundo o ECA?`
- `Qual a pena para o crime de tráfico de crianças?`
- `O que a lei prevê sobre negligência infantil?`

## 4. Rota Produto / metodologia (rag_interno)
- `Como funciona a análise retrospectiva do Aurora?`
- `De onde vêm os dados que o Aurora usa?`
- `O que é o comitê de modelos e como ele escolhe o vencedor?`

## 5. Rota SIPIA-CT (consulta_sipia_ct)
(indicadores do Conselho Tutelar — fonte distinta do SINAM)

- `Quais os direitos violados mais registrados no SIPIA em SP?` → indicador **Direito Violado**
- `Quem é o agente violador mais comum no SIPIA?` → **Agente Violador**
- `Distribuição por faixa etária no SIPIA-CT` → **Faixa Etária**
- `Perfil por sexo no SIPIA` → **Sexo**
- `Distribuição por cor/raça no SIPIA-CT` → **Cor**

---

## 6. Follow-ups (contexto multi-turn)
Envie em sequência, na MESMA conversa:

- **Carry-over de estado:** `Violência sexual em Sergipe` → depois
  `E a violência física no mesmo estado?`
  → 2ª deve continuar em **Sergipe** (não trocar de estado), tipo **física**.
- **Carry-over de tipo:** `Violência sexual em São Paulo` → depois
  `E em Pernambuco?`
  → 2ª deve buscar **PE** mantendo **sexual**.
- **Comparação entre estados:** `Evolução da violência sexual em Sergipe` → depois
  `E em relação à Bahia, como está?`
  → deve buscar a **Bahia** (mantendo sexual) e **comparar as variações %**
  (ex.: "Bahia +161,4% vs Sergipe +139,9% → cresceu proporcionalmente mais").
- **Escopo nacional após estado:** `Tortura em Minas Gerais` → depois
  `E no Brasil todo?`
  → deve ir para `relatorio_brasil` (não herdar MG).

## 7. Casos de borda (correções recentes)
- **"Minas" (sem "Gerais"):** `Estatísticas de violência física em Minas` → `relatorio_uf(MG)`
- **Cidade longe da UF:** `Dados de Salvador sobre violência infantil — denúncia do MP-BA`
  → `relatorio_municipio(Salvador, BA)` (não confundir "MP-BA" com cidade)
- **"para" ≠ Pará:** `Quero dados para instruir uma ação em São Paulo`
  → deve resolver **SP**, nunca PA
- **Escopo nacional explícito:** `Tráfico de crianças no Brasil (Lei 13.344/2016)`
  → `relatorio_brasil` (mesmo citando lei)
- **Dado com finalidade jurídica:** `Preciso dos dados de violência sexual em SP para peticionar (ECA art. 245)`
  → caminho de **dados** (`relatorio_uf(SP)`), não o RAG jurídico

## 8. Off-scope (recusa determinística)
Recusadas ANTES de chamar qualquer ferramenta (filtro determinístico cobre
código/HTML/site e escrita criativa):
- `Me ajuda a escrever um poema?`
- `Crie um site em HTML pra mim`
- `Escreva um código em Python`
- `Me conta uma piada`

> Conhecimento geral (ex.: "capital da França", "cotação do dólar") **não** é
> bloqueado pelo filtro determinístico — o modelo deve declinar pelo escopo,
> mas sem garantia. Se quiser, dá para ampliar o `_OFFSCOPE_RE`.

---

## Anexo — geração das respostas
Todas as respostas são redigidas pelo **Jurema-7B** (via Ollama) a partir dos
dados retornados pela ferramenta. Não há modelos de forecasting neste fork: os
relatórios são SQL puro (totais por ano, rankings, séries). Ver
[arquitetura.md](arquitetura.md).
