# Dicionário de dados SINAM/VIOLBR (base de violência)

Esta é a base de dados que o Aurora Responde consulta ao vivo para números
exatos. Cada registro (linha) é **uma notificação de violência** contra criança
ou adolescente feita ao SINAM (Sistema de Informação de Agravos de Notificação)
e consolidada nas tabelas VIOLBR do DataSUS/Ministério da Saúde. Os dados vão de
2020 a 2024 (tabelas VIOLBR20 a VIOLBR24).

## Fonte e natureza
O SINAM é um sistema de **notificação compulsória da área da saúde**: profissionais
de saúde registram casos atendidos de violência. Portanto o número reflete
notificações registradas, não necessariamente todos os casos ocorridos
(há subnotificação). É uma fonte distinta do SIPIA-CT (Conselho Tutelar).

## Campos da vítima
- **sexo**: Masculino (M), Feminino (F) ou Ignorado (I).
- **idade_anos**: idade em anos; bebês com menos de 1 ano contam como 0.
- **faixa_etaria**: faixas etárias — `< 1 ano`, `1-4`, `5-9`, `10-14`, `15-19`,
  `20-59`, `60+` ou `Ignorada`. O recorte do Aurora é criança e adolescente
  (0 a 19 anos).
- **raca_cor**: Branca, Preta, Amarela, Parda, Indígena ou Ignorada.
- **escolaridade**, **gestante**: informações complementares da vítima.

## Campos de geografia
- **uf**: sigla da Unidade da Federação de residência da vítima (ex.: SP, SE, BA).
- **uf_ocorrencia**: UF onde ocorreu a violência.
- **municipio_codigo**: código IBGE de 7 dígitos do município de residência
  (cruzado com o dicionário de municípios para obter o nome da cidade).
- **local_ocorrencia**: onde aconteceu — Residência, Via pública, Escola etc.
- **zona**: urbana/rural.

## Tipos de violência (campos sim/não)
Cada notificação pode marcar um ou mais tipos. Os tipos disponíveis são:
- **violencia_fisica** — violência física.
- **violencia_psicologica** — violência psicológica/moral.
- **violencia_sexual** — violência sexual / abuso sexual / estupro.
- **negligencia** — negligência ou abandono.
- **tortura** — tortura.
- **trafico_pessoas** — tráfico de pessoas.
- **violencia_financeira** — violência financeira/econômica.
- **violencia_infantil** — violência contra a criança (marcador específico).
- **intervencao_legal** — intervenção legal.
- **outras_violencias** — outras violências.

## Outros marcadores
- **lesao_autoprovocada** — autoagressão, automutilação ou tentativa de suicídio.
- **ocorreu_outras_vezes** — indica reincidência (vítima já sofreu antes).
- **autor_sexo** — sexo do provável autor (M/F/I).
- **autor_alcool** — se o autor estava sob efeito de álcool (Sim/Não/Ignorado).

## Como perguntar (exemplos que o Aurora entende)
- "Quantos casos de violência sexual contra crianças em São Paulo em 2023?"
  → filtra uf=SP, ano=2023, violencia_sexual.
- "Qual o estado com mais notificações de negligência?"
  → ranking por UF, negligência.
- "Compare a violência física entre Sergipe e Bahia."
  → série por UF, violência física, comparação.
- "Quantas meninas de 10 a 14 anos sofreram violência em 2024?"
  → filtra sexo=F, faixa 10-14, ano=2024.
- "Qual a cidade mais violenta do Ceará?"
  → ranking de municípios dentro de CE.

Quando a pergunta não especifica o tipo de violência, o Aurora considera o
total de notificações. Quando não especifica o local, considera o Brasil inteiro.
Números posteriores a 2024 não existem na base — o Aurora não projeta/estima.
