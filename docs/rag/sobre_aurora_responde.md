# Sobre o Aurora Responde (como a plataforma funciona)

O Aurora Responde é um assistente conversacional sobre **violência contra
crianças e adolescentes no Brasil**. Ele responde perguntas em linguagem natural
combinando três fontes: dados oficiais ao vivo, legislação e documentação do
próprio produto. Faz parte da Plataforma Aurora (PROCC/UFS — MJSP).

## Como o Aurora responde às perguntas
O Aurora usa um **roteador determinístico** que identifica o tipo da pergunta e
busca a informação na fonte certa; em seguida o modelo de linguagem **Jurema-7B**
(rodando localmente via Ollama) redige a resposta em português claro. O Jurema é
o único modelo generativo do sistema — ele escreve todas as respostas, sejam de
dados, de legislação ou sobre o funcionamento da plataforma.

As quatro rotas são:
1. **Dados de violência (SINAM)** — números exatos vêm de uma consulta SQL ao
   banco PostgreSQL. O Aurora nunca inventa números: ele conta as notificações
   reais e o Jurema narra o resultado.
2. **Legislação (RAG jurídico)** — busca em um corpus curado de leis (ECA,
   Constituição, Código Penal, Lei Henry Borel, Lei Menino Bernardo, Lei da
   Escuta Protegida, entre outras) e o Jurema redige um parecer citando a lei
   e o artigo.
3. **SIPIA-CT (Conselho Tutelar)** — consulta a base do Sistema de Informação
   para a Infância e Adolescência dos Conselhos Tutelares.
4. **Documentação do produto** — busca nesta própria documentação para explicar
   como a plataforma funciona.

## Fontes de dados
- **SINAM/VIOLBR** (Ministério da Saúde / DataSUS) — notificações de violência
  de 2020 a 2024. É uma fonte da área da saúde, com notificação compulsória.
- **SIPIA-CT** — registros dos Conselhos Tutelares.
- **Corpus jurídico** — normas de proteção à criança e ao adolescente.

As duas fontes de dados (SINAM e SIPIA-CT) são **complementares e distintas**:
uma vem da saúde, outra do sistema de garantia de direitos. Números das duas
não devem ser somados.

## Indicadores do SIPIA-CT
No SIPIA-CT, os registros podem ser agregados pelas dimensões:
**Sexo**, **Cor**, **Faixa Etária**, **Direito Violado** e **Agente Violador**.
A dimensão "Direito Violado" descreve qual direito da criança/adolescente foi
violado; "Agente Violador" indica quem cometeu a violação.

## Limitações (o que o Aurora NÃO faz)
- Não substitui aconselhamento jurídico, médico ou psicológico profissional.
- Não projeta nem estima números para anos sem dados (não há dados após 2024).
- Os dados refletem **notificações registradas**, sujeitas a subnotificação —
  não são a contagem absoluta de todos os casos ocorridos.
- Foge do escopo: não escreve código, textos criativos ou temas gerais.

## Encaminhamentos de proteção (quando há risco)
Se a conversa indicar que uma criança ou adolescente está em situação de
violência ou risco, o Aurora orienta os canais oficiais de proteção:
- **Disque 100** (Disque Direitos Humanos) — denúncia anônima, 24h.
- **Conselho Tutelar** do município — órgão que aplica medidas de proteção.
- **Boletim de Ocorrência** — em delegacia física ou pela Delegacia Eletrônica,
  especialmente em casos de crime.
- Em emergência com risco imediato, **Polícia Militar (190)**.

Esses encaminhamentos são acionados por uma camada de segurança (guardrails)
que roda antes do modelo, de forma determinística.
