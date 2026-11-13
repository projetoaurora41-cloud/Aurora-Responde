"""Corpus jurídico curado para o `rag_juridico` (grounding do Jurema-7B).

Base pequena e VERSIONADA de leis de proteção à criança e ao adolescente. É o
"conhecimento confiável" que o `rag_juridico` recupera e injeta como contexto no
Jurema — corrige os pontos em que o modelo sozinho erra (ex.: Lei Menino Bernardo
e ECA Digital) e dá citação verificável da lei/artigo.

Sem banco/embeddings: busca por sobreposição de termos (normalizada), leve e
determinística — o corpus é pequeno (dezenas de trechos). Para crescer, basta
adicionar entradas em ``LEIS`` (ou apontar para uma tabela no futuro).
"""
from __future__ import annotations

import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# Cada entrada = um trecho citável (lei/artigo + texto fiel + fonte).
LEIS: list[dict[str, str]] = [
    {
        "id": "cf88_art227",
        "lei": "Constituição Federal de 1988",
        "artigo": "Art. 227",
        "texto": (
            "É dever da família, da sociedade e do Estado assegurar à criança, ao "
            "adolescente e ao jovem, com ABSOLUTA PRIORIDADE, o direito à vida, à "
            "saúde, à alimentação, à educação, ao lazer, à profissionalização, à "
            "cultura, à dignidade, ao respeito, à liberdade e à convivência familiar "
            "e comunitária, além de colocá-los a salvo de toda forma de negligência, "
            "discriminação, exploração, violência, crueldade e opressão. § 4º A lei "
            "punirá severamente o abuso, a violência e a exploração sexual da criança "
            "e do adolescente."
        ),
        "fonte": "Constituição Federal de 1988, art. 227",
    },
    {
        "id": "cp_art136_maus_tratos",
        "lei": "Código Penal (Decreto-Lei 2.848/1940)",
        "artigo": "Art. 136 — Maus-tratos",
        "texto": (
            "Expor a perigo a vida ou a saúde de pessoa sob sua autoridade, guarda ou "
            "vigilância, para fim de educação, ensino, tratamento ou custódia, quer "
            "privando-a de alimentação ou cuidados indispensáveis, quer sujeitando-a a "
            "trabalho excessivo ou inadequado, quer abusando de meios de correção ou "
            "disciplina. Pena (redação da Lei 15.163/2025): reclusão, de 2 a 5 anos; "
            "de 3 a 7 anos se resulta lesão corporal grave; de 8 a 14 anos se resulta "
            "morte."
        ),
        "fonte": "Código Penal, art. 136 (redação da Lei 15.163/2025)",
        "chaves": r"maus.?tratos|art\.? ?136",
    },
    {
        "id": "cp_art217a_estupro_vulneravel",
        "lei": "Código Penal (Decreto-Lei 2.848/1940)",
        "artigo": "Art. 217-A — Estupro de vulnerável",
        "texto": (
            "Ter conjunção carnal ou praticar outro ato libidinoso com menor de 14 "
            "anos. Pena: reclusão, de 10 a 18 anos, e multa (redação da Lei "
            "15.280/2025). A vulnerabilidade é ABSOLUTA: o consentimento da vítima, sua "
            "eventual experiência sexual anterior ou relacionamento com o agente NÃO "
            "afastam o crime (Súmula 593 do STJ). Também responde quem pratica o ato "
            "com quem, por enfermidade ou deficiência mental, não tem discernimento, "
            "ou não pode oferecer resistência. Observação: as notificações de "
            "violência sexual do SINAN não equivalem a casos de estupro de vulnerável; "
            "são registros do sistema de saúde, sem classificação penal."
        ),
        "fonte": "Código Penal, art. 217-A (Lei 15.280/2025)",
        "chaves": r"estupro de vulneravel|217-a|estupro.{0,40}(crianca|menor de 14|adolescente)",
    },
    {
        "id": "cp_arts218",
        "lei": "Código Penal (Decreto-Lei 2.848/1940)",
        "artigo": "Arts. 218, 218-A e 218-B",
        "texto": (
            "Art. 218 (corrupção de menores): induzir menor de 14 anos a satisfazer a "
            "lascívia de outrem. Art. 218-A (satisfação de lascívia mediante presença "
            "de criança ou adolescente): praticar, na presença de menor de 14 anos, ou "
            "induzi-lo a presenciar, conjunção carnal ou outro ato libidinoso. Art. "
            "218-B (favorecimento da prostituição ou de outra forma de exploração "
            "sexual): submeter, induzir ou atrair à prostituição ou à exploração "
            "sexual criança, adolescente ou vulnerável."
        ),
        "fonte": "Código Penal, arts. 218, 218-A, 218-B",
    },
    {
        "id": "cp_art146a_bullying",
        "lei": "Código Penal (Decreto-Lei 2.848/1940)",
        "artigo": "Art. 146-A — Intimidação sistemática (bullying)",
        "texto": (
            "Incluído pela Lei 14.811/2024. Intimidar sistematicamente, individualmente "
            "ou em grupo, mediante violência física ou psicológica, uma ou mais "
            "pessoas, de modo intencional e repetitivo, sem motivação evidente, por "
            "meio de intimidação, humilhação ou discriminação. Pena de multa, se a "
            "conduta não constituir crime mais grave. Parágrafo único: se praticada por "
            "meio da rede de computadores, internet ou redes sociais (bullying "
            "virtual/cyberbullying), a pena é de reclusão, de 2 a 4 anos, e multa."
        ),
        "fonte": "Código Penal, art. 146-A (Lei 14.811/2024)",
        "chaves": r"bullying|intimidacao sistematica|146-a",
    },
    {
        "id": "eca_8069",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "ECA — proteção integral",
        "texto": (
            "Norma fundamental de PROTEÇÃO INTEGRAL a crianças (até 12 anos "
            "incompletos) e adolescentes (12 a 18). Art. 5º: nenhuma criança ou "
            "adolescente será objeto de qualquer forma de negligência, discriminação, "
            "exploração, violência, crueldade e opressão. Art. 13: os casos de "
            "suspeita ou confirmação de castigo físico, maus-tratos ou violência serão "
            "obrigatoriamente comunicados ao Conselho Tutelar, sem prejuízo de outras "
            "providências. Art. 70: é dever de TODOS prevenir a ameaça ou violação dos "
            "direitos da criança e do adolescente. Art. 245: deixar de comunicar à "
            "autoridade competente caso de maus-tratos é infração administrativa."
        ),
        "fonte": "Lei 8.069/1990 (ECA), arts. 5º, 13, 70, 245",
    },
    {
        "id": "lei_henry_borel_14344",
        "lei": "Lei Henry Borel (Lei 14.344/2022)",
        "artigo": "Lei 14.344/2022",
        "texto": (
            "Cria mecanismos para a PREVENÇÃO E O ENFRENTAMENTO DA VIOLÊNCIA DOMÉSTICA "
            "E FAMILIAR contra a criança e o adolescente, nos moldes da Lei Maria da "
            "Penha (Lei 11.340/2006). Considera violência doméstica e familiar as "
            "ações ou omissões praticadas em casa, na família ou em relação de "
            "convivência que causem morte, lesão, sofrimento físico, sexual, "
            "psicológico ou dano patrimonial. Prevê medidas protetivas de urgência, "
            "atendimento especializado e articulação da rede de proteção."
        ),
        "fonte": "Lei 14.344/2022 (Lei Henry Borel)",
        "chaves": r"henry borel|14\.?344",
    },
    {
        "id": "lei_escuta_protegida_13431",
        "lei": "Lei da Escuta Protegida (Lei 13.431/2017)",
        "artigo": "Lei 13.431/2017",
        "texto": (
            "Estabelece o sistema de garantia de direitos da criança e do adolescente "
            "VÍTIMA OU TESTEMUNHA de violência. Para evitar a revitimização, cria dois "
            "procedimentos: a ESCUTA ESPECIALIZADA (perante órgão da rede de proteção) "
            "e o DEPOIMENTO ESPECIAL (perante autoridade policial ou judiciária, em "
            "ambiente acolhedor e, sempre que possível, uma única vez). Reconhece "
            "quatro formas de violência: física, psicológica, sexual e institucional."
        ),
        "fonte": "Lei 13.431/2017 (Escuta Protegida)",
    },
    {
        "id": "lei_menino_bernardo_13010",
        "lei": "Lei Menino Bernardo / Lei da Palmada (Lei 13.010/2014)",
        "artigo": "Lei 13.010/2014",
        "texto": (
            "Altera o ECA (arts. 18-A e 18-B) para estabelecer o direito da criança e "
            "do adolescente de ser EDUCADO E CUIDADO SEM O USO DE CASTIGO FÍSICO ou de "
            "tratamento cruel ou degradante como formas de correção, disciplina ou "
            "educação. Define castigo físico como ação de natureza disciplinar com uso "
            "da força que resulte em sofrimento ou lesão. Prevê medidas aos pais ou "
            "responsáveis (encaminhamento a programas de proteção/orientação, "
            "advertência), sem caráter apenas punitivo."
        ),
        "fonte": "Lei 13.010/2014 (Menino Bernardo)",
        "chaves": r"menino bernardo|lei da palmada|palmada|castigo fisico|13\.?010",
    },
    {
        "id": "lei_14811_2024",
        "lei": "Lei 14.811/2024",
        "artigo": "Lei 14.811/2024",
        "texto": (
            "Institui medidas de PROTEÇÃO à criança e ao adolescente contra a violência "
            "nos ESTABELECIMENTOS EDUCACIONAIS ou similares e prevê a Política Nacional "
            "de Prevenção e Combate ao Abuso e Exploração Sexual da Criança e do "
            "Adolescente. Cria o crime de intimidação sistemática (BULLYING) no art. "
            "146-A do Código Penal, com pena maior para o bullying virtual "
            "(cyberbullying). Torna HEDIONDOS crimes como o induzimento/instigação ao "
            "suicídio ou automutilação de menor e a pornografia infantil (§1º do art. "
            "240 e art. 241-B do ECA). Fonte: "
            "planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14811.htm"
        ),
        "fonte": "Lei 14.811/2024",
    },
    {
        "id": "lei_15487_2026",
        "lei": "Lei 15.487/2026",
        "artigo": "Lei 15.487/2026",
        "texto": (
            "Institui medidas de ENFRENTAMENTO E REPRESSÃO ao crime de violência sexual "
            "contra criança ou adolescente, INCLUSIVE NO AMBIENTE DIGITAL e com uso de "
            "INTELIGÊNCIA ARTIFICIAL (ex.: imagens ou vídeos manipulados/deepfakes). "
            "Prevê instrumentos de investigação — coleta de arquivos e infiltração de "
            "agentes que se fazem passar por criança/adolescente em ambientes digitais "
            "— e atendimento à vítima na forma da Lei 13.431/2017. Altera o Código "
            "Penal, a Lei dos Crimes Hediondos (8.072/1990), o ECA (8.069/1990) e a Lei "
            "de Organização Criminosa (12.850/2013). Fonte: "
            "planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15487.htm"
        ),
        "fonte": "Lei 15.487/2026",
        "chaves": r"15\.?487|deepfake|inteligencia artificial.{0,40}(sexual|crianca)",
    },
    {
        "id": "eca_art2_idade",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Art. 2º — Quem é criança e quem é adolescente",
        "texto": (
            "Considera-se criança, para os efeitos do ECA, a pessoa até 12 anos de "
            "idade incompletos, e adolescente aquela entre 12 e 18 anos de idade. Nos "
            "casos expressos em lei, aplica-se excepcionalmente o Estatuto às pessoas "
            "entre 18 e 21 anos de idade."
        ),
        "fonte": "ECA, art. 2º",
        "chaves": r"(ate que|qual a|com que|a partir de que) idade|idade.{0,40}(crianca|adolescente)|"
                  r"(considerad[oa]|e considerad[oa]|definicao de) (crianca|adolescente)|quem e crianca|"
                  r"diferenca entre crianca e adolescente|\bart\.? ?2\b.{0,10}eca",
    },
    {
        "id": "eca_art132_conselho_tutelar",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Art. 132 — Composição do Conselho Tutelar",
        "texto": (
            "Em cada Município e em cada Região Administrativa do Distrito Federal "
            "haverá, no mínimo, 1 Conselho Tutelar como órgão integrante da "
            "administração pública local, composto de 5 membros, escolhidos pela "
            "população local para mandato de 4 anos, permitida recondução por novos "
            "processos de escolha. O Conselho Tutelar é órgão permanente e autônomo, "
            "não jurisdicional, encarregado de zelar pelo cumprimento dos direitos da "
            "criança e do adolescente (art. 131); suas atribuições estão no art. 136."
        ),
        "fonte": "ECA, arts. 131, 132 e 136",
        "chaves": r"conselho tutelar.{0,80}(membros|conselheir|mandato|composi|quantas pessoas|eleit|escolh|o que e|o que faz|atribui|funcao)|"
                  r"(membros|conselheiros|mandato|composicao|atribuicoes).{0,60}conselho tutelar|"
                  r"o que (e|faz) (o )?conselho tutelar|art\.? ?132",
    },
    {
        "id": "eca_art244a_exploracao_sexual",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Art. 244-A — Exploração sexual de criança ou adolescente",
        "texto": (
            "Submeter criança ou adolescente à prostituição ou à exploração sexual. "
            "Pena: reclusão de 4 a 10 anos e multa, além da perda de bens e valores "
            "utilizados na prática criminosa em favor do Fundo dos Direitos da Criança "
            "e do Adolescente. Incorrem nas mesmas penas o proprietário, o gerente ou o "
            "responsável pelo local em que se verifique a submissão. No Código Penal, "
            "o art. 218-B (favorecimento da prostituição ou de outra forma de "
            "exploração sexual de vulnerável) também tipifica a conduta. Atenção: o "
            "art. 244 do ECA trata de outra coisa (venda de fogos de artifício a "
            "criança ou adolescente)."
        ),
        "fonte": "ECA, art. 244-A; Código Penal, art. 218-B",
        "chaves": r"exploracao sexual.{0,80}(pena|crime|lei|eca|artigo|punid|preve)|"
                  r"(pena|crime|lei|eca|artigo|punid|preve).{0,80}exploracao sexual|"
                  r"prostituicao infantil|prostituicao de (criancas|adolescentes|menores)|244-a",
    },
    {
        "id": "trafico_criancas",
        "lei": "Código Penal e ECA",
        "artigo": "CP, art. 149-A (Lei 13.344/2016) e ECA, art. 239 — Tráfico de pessoas",
        "texto": (
            "Código Penal, art. 149-A (incluído pela Lei 13.344/2016): agenciar, "
            "aliciar, recrutar, transportar, transferir, comprar, alojar ou acolher "
            "pessoa, mediante grave ameaça, violência, coação, fraude ou abuso, para "
            "remoção de órgãos, trabalho em condições análogas à de escravo, "
            "servidão, adoção ilegal ou exploração sexual. Pena: reclusão de 4 a 8 "
            "anos e multa, aumentada de um terço até a metade quando o crime é "
            "cometido contra criança ou adolescente (§ 1º, II). ECA, art. 239: "
            "promover ou auxiliar o envio de criança ou adolescente para o exterior "
            "sem as formalidades legais ou para obter lucro. Pena: reclusão de 4 a 6 "
            "anos e multa. A Lei 13.344/2016 também trata da prevenção, da repressão "
            "e da atenção às vítimas."
        ),
        "fonte": "Código Penal, art. 149-A (Lei 13.344/2016); ECA, art. 239",
        "chaves": r"trafico (de )?(criancas|crianca|pessoas|menores|adolescentes|humano|infantil)|"
                  r"\btrafico\b.{0,60}(lei|pena|crime|diz|preve)|(lei|pena|crime).{0,60}\btrafico\b|"
                  r"149-a|13\.?344|envio de crianca.{0,20}exterior|art\.? ?239",
    },
    {
        "id": "eca_negligencia",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Negligência — arts. 5º, 13, 98 e 130",
        "texto": (
            "Art. 5º: nenhuma criança ou adolescente será objeto de qualquer forma de "
            "negligência, discriminação, exploração, violência, crueldade e opressão, "
            "punido na forma da lei qualquer atentado, por ação ou omissão, aos seus "
            "direitos fundamentais. Art. 13: a suspeita ou confirmação de castigo "
            "físico, tratamento cruel ou degradante e maus-tratos deve ser comunicada "
            "obrigatoriamente ao Conselho Tutelar. Art. 98: as medidas de proteção se "
            "aplicam sempre que os direitos forem ameaçados ou violados, inclusive por "
            "falta, omissão ou abuso dos pais ou responsável. Art. 130 (redação da Lei "
            "15.240/2025): em caso de maus-tratos, negligência, opressão ou abuso "
            "sexual praticados pelos pais ou responsável, a autoridade judiciária pode "
            "determinar o afastamento do agressor da moradia comum. No Código Penal, a "
            "privação de alimentação ou de cuidados indispensáveis pode configurar "
            "maus-tratos (art. 136)."
        ),
        "fonte": "ECA, arts. 5º, 13, 98 e 130; Código Penal, art. 136",
        "chaves": r"negligenc|abandono de (crianca|incapaz)|omissao de cuidado",
    },
    {
        "id": "eca_art130_afastamento",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Art. 130 — Afastamento do agressor",
        "texto": (
            "Art. 130 (redação da Lei 15.240/2025): verificada a hipótese de "
            "maus-tratos, negligência, opressão ou abuso sexual impostos pelos pais ou "
            "responsável, a autoridade judiciária poderá determinar, como medida "
            "cautelar, o afastamento do agressor da moradia comum. O art. 101, por "
            "sua vez, lista as medidas de proteção aplicadas à própria criança ou "
            "adolescente (como encaminhamento aos pais, orientação, matrícula em "
            "escola, tratamento de saúde e acolhimento)."
        ),
        "fonte": "ECA, arts. 101 e 130",
        "chaves": r"afastamento do agressor|afastar o agressor|agressor.{0,40}(sair|retirad|afastad).{0,20}(casa|lar|moradia)|art\.? ?130",
    },
    {
        "id": "eca_comunicacao_obrigatoria",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Arts. 13, 56 e 245 — Dever de comunicar",
        "texto": (
            "Art. 13: os casos de suspeita ou confirmação de castigo físico, "
            "tratamento cruel ou degradante e maus-tratos contra criança ou "
            "adolescente serão obrigatoriamente comunicados ao Conselho Tutelar da "
            "localidade, sem prejuízo de outras providências legais. Art. 56: os "
            "dirigentes de estabelecimentos de ensino fundamental comunicarão ao "
            "Conselho Tutelar os casos de maus-tratos envolvendo seus alunos, a "
            "reiteração de faltas injustificadas e a evasão escolar. Art. 245: deixar "
            "o médico, o professor ou o responsável por estabelecimento de saúde ou de "
            "ensino fundamental, pré-escola ou creche de comunicar à autoridade "
            "competente caso de suspeita ou confirmação de maus-tratos é infração "
            "administrativa, com multa de 3 a 20 salários de referência (o dobro em "
            "caso de reincidência)."
        ),
        "fonte": "ECA, arts. 13, 56 e 245",
        "chaves": r"(professor|escola|diretor|medico|enfermeir|profissional|educador).{0,80}(obrigad|dever|comunicar|notificar|denunciar|avisar)|"
                  r"(obrigad|dever).{0,40}(comunicar|notificar|denunciar).{0,60}(suspeita|abuso|maus)|"
                  r"deixar de comunicar|art\.? ?245|art\.? ?56\b",
    },
    {
        "id": "lei13431_escuta_depoimento",
        "lei": "Lei 13.431/2017",
        "artigo": "Arts. 7º e 8º — Escuta especializada e depoimento especial",
        "texto": (
            "Art. 7º: escuta especializada é o procedimento de entrevista sobre "
            "situação de violência com criança ou adolescente perante órgão da rede "
            "de proteção (saúde, assistência social, educação, Conselho Tutelar), "
            "limitado o relato estritamente ao necessário para o cumprimento de sua "
            "finalidade. Art. 8º: depoimento especial é o procedimento de oitiva de "
            "criança ou adolescente vítima ou testemunha de violência perante "
            "autoridade policial ou judiciária. A diferença: a escuta especializada "
            "serve à proteção e ao cuidado; o depoimento especial serve à produção de "
            "prova. Os dois buscam evitar a revitimização."
        ),
        "fonte": "Lei 13.431/2017, arts. 7º e 8º",
        "chaves": r"escuta especializada|depoimento especial|escuta protegida|13\.?431|revitimiza",
    },
    {
        "id": "eca_240_241d_fotos",
        "lei": "Estatuto da Criança e do Adolescente (Lei 8.069/1990)",
        "artigo": "Arts. 240 e 241-D — Imagens e aliciamento",
        "texto": (
            "Art. 240: produzir, reproduzir, dirigir, fotografar, filmar ou registrar, "
            "por qualquer meio, cena de sexo explícito ou pornográfica envolvendo "
            "criança ou adolescente. Pena: reclusão de 4 a 8 anos e multa; incorre "
            "nas mesmas penas quem agencia, facilita, recruta, coage ou intermedeia a "
            "participação. Art. 241-D: aliciar, assediar, instigar ou constranger, "
            "por qualquer meio de comunicação, criança, com o fim de com ela praticar "
            "ato libidinoso. Pena: reclusão de 1 a 3 anos e multa. Pedir ou oferecer "
            "dinheiro a criança ou adolescente em troca de fotos íntimas é crime e "
            "deve ser denunciado (Disque 100, delegacia, Conselho Tutelar)."
        ),
        "fonte": "ECA, arts. 240 e 241-D",
        "chaves": r"(foto|fotos|video|videos|imagem|imagens|nude|nudes).{0,60}(crianca|adolescente|menor|intim|sem roupa|sexual|crime)|"
                  r"pornografia infantil|aliciamento|grooming|art\.? ?240|241-d",
    },
    {
        "id": "como_denunciar_boletim_ocorrencia",
        "lei": "Como denunciar — canais e boletim de ocorrência",
        "artigo": "Encaminhamento",
        "texto": (
            "Maus-tratos, abuso e exploração de crianças e adolescentes são CRIMES. "
            "Diante de suspeita, além de acionar o CONSELHO TUTELAR do município e o "
            "DISQUE 100 (denúncia anônima, gratuita, 24h), qualquer pessoa pode "
            "registrar um BOLETIM DE OCORRÊNCIA (B.O.): presencialmente na delegacia — "
            "de preferência na Delegacia de Proteção à Criança e ao Adolescente (DPCA) "
            "ou, quando envolver mulher/menina, na Delegacia da Mulher (DEAM) — OU pela "
            "DELEGACIA ELETRÔNICA (online) do estado. O B.O. formaliza a notícia-crime "
            "e permite a investigação policial. Em emergência ou crime em andamento, "
            "ligue 190. Base: art. 136 do Código Penal; arts. 13, 70 e 245 do ECA; "
            "Leis 14.811/2024 e 15.487/2026."
        ),
        "fonte": "Orientação (CP art. 136; ECA arts. 13/70/245; Leis 14.811/2024 e 15.487/2026)",
    },
]

# Índice pré-normalizado (texto pesquisável por entrada).
_INDEX: list[tuple[dict[str, str], str]] = [
    (e, _norm(f"{e['lei']} {e['artigo']} {e['texto']} {e.get('fonte', '')}"))
    for e in LEIS
]

# Sinônimos/apelidos → termos que ajudam a casar a pergunta com a lei certa.
_APELIDOS = {
    "palmada": "menino bernardo castigo fisico 13.010",
    "lei da palmada": "menino bernardo castigo fisico 13.010",
    "henry borel": "violencia domestica familiar 14.344",
    "escuta protegida": "depoimento especial revitimizacao 13.431",
    "eca digital": "14.811 ambiente digital escolas bullying",
    "estupro": "217-a vulneravel",
    "bullying": "146-a intimidacao sistematica cyberbullying",
    "cyberbullying": "146-a bullying virtual rede social",
    "boletim de ocorrencia": "denunciar delegacia eletronica b.o.",
    "denunciar": "delegacia conselho tutelar disque 100 boletim",
    "delegacia": "boletim de ocorrencia delegacia eletronica online",
}


_STOP = {
    "que", "uma", "um", "para", "com", "sobre", "diz", "lei", "leis", "qual",
    "quais", "como", "ser", "tem", "dos", "das", "nos", "nas", "pela", "pelo",
    "por", "the", "seu", "sua", "isso", "esse", "essa", "este", "esta", "mais",
    "quem", "onde", "quando", "ate", "nao", "sim", "eca", "artigo", "crianca",
    "criancas", "adolescente", "adolescentes", "contra", "brasil", "preve",
    "prevista", "previsto", "estatuto", "codigo", "penal",
}


def _tokens(texto: str) -> list[str]:
    """Palavras (>2 letras) + números de lei (14.344, 217-A) da consulta."""
    n = _norm(texto)
    for apelido, extra in _APELIDOS.items():
        if apelido in n:
            n += " " + extra
    toks = [t for t in re.findall(r"[a-z0-9]+", n) if len(t) > 2 and t not in _STOP]
    # números de lei/artigo (14.344, 8.069, 217-a, 146-a) como termo forte
    toks += re.findall(r"\d{2,3}[.\-]\d{1,3}|\d{2,3}-[a-z]", n)
    return toks


def buscar(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Retorna até `limit` trechos do corpus mais relevantes para `query`.

    Score = soma das ocorrências dos termos da pergunta no texto da entrada,
    com peso extra (x4) para números de lei/artigo (casam a norma exata).
    """
    toks = _tokens(query)
    if not toks:
        return []
    num_re = re.compile(r"^\d{2,3}[.\-]\d|-[a-z]$|\d-[a-z]$")
    ranked: list[tuple[int, dict[str, str]]] = []
    for entrada, blob in _INDEX:
        score = 0
        for t in toks:
            c = blob.count(t)
            if not c:
                continue
            peso = 4 if (("." in t) or ("-" in t)) else 1
            score += c * peso
        if score >= 2:
            ranked.append((score, entrada))
    ranked.sort(key=lambda x: -x[0])
    saida = []
    for i, (_score, e) in enumerate(ranked[:limit], 1):
        saida.append({
            "ref": f"L{i}",
            "lei": e["lei"],
            "artigo": e["artigo"],
            "texto": e["texto"],
            "fonte": e["fonte"],
        })
    return saida


_CHAVES = [(e, re.compile(e["chaves"])) for e in LEIS if e.get("chaves")]


def por_tema(pergunta: str, limit: int = 2) -> list[dict[str, str]]:
    """Trechos cujo TEMA casa com a pergunta (regex curada por entrada).

    Mais preciso que a sobreposição de palavras de :func:`buscar`: a pergunta
    "qual a pena para exploração sexual" cai no art. 244-A, e não em qualquer
    trecho que cite "pena". Ordem = posição do primeiro casamento na pergunta.
    """
    n = _norm(pergunta)
    achados: list[tuple[int, dict[str, str]]] = []
    for e, rx in _CHAVES:
        m = rx.search(n)
        if m:
            achados.append((m.start(), e))
    achados.sort(key=lambda x: x[0])
    saida = []
    for i, (_pos, e) in enumerate(achados[:limit], 1):
        saida.append({"ref": f"L{i}", "lei": e["lei"], "artigo": e["artigo"],
                      "texto": e["texto"], "fonte": e["fonte"]})
    return saida


def tem_tema(pergunta: str) -> bool:
    return bool(por_tema(pergunta, limit=1))

