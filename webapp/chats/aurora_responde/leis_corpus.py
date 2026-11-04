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
            "disciplina. Pena: detenção, de 2 meses a 1 ano, ou multa. A pena é "
            "aumentada se do fato resulta lesão corporal grave ou morte, e se o crime "
            "é praticado contra pessoa menor de 14 anos."
        ),
        "fonte": "Código Penal, art. 136",
    },
    {
        "id": "cp_art217a_estupro_vulneravel",
        "lei": "Código Penal (Decreto-Lei 2.848/1940)",
        "artigo": "Art. 217-A — Estupro de vulnerável",
        "texto": (
            "Ter conjunção carnal ou praticar outro ato libidinoso com menor de 14 "
            "anos. Pena: reclusão, de 8 a 15 anos. A vulnerabilidade é ABSOLUTA: o "
            "consentimento da vítima, sua eventual experiência sexual anterior ou "
            "relacionamento com o agente NÃO afastam o crime (Súmula 593 do STJ). "
            "Também responde quem pratica o ato com quem, por enfermidade ou "
            "deficiência mental, não tem discernimento, ou não pode oferecer "
            "resistência."
        ),
        "fonte": "Código Penal, art. 217-A",
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


def _tokens(texto: str) -> list[str]:
    """Palavras (>2 letras) + números de lei (14.344, 217-A) da consulta."""
    n = _norm(texto)
    for apelido, extra in _APELIDOS.items():
        if apelido in n:
            n += " " + extra
    toks = [t for t in re.findall(r"[a-z0-9]+", n) if len(t) > 2]
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
        if score:
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
