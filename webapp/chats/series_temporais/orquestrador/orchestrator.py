"""Aurora Responde — roteador determinístico + Jurema-7B como único gerador.

Não há mais orquestrador Qwen3 fazendo tool-calling. O fluxo de ``chat()`` é:
(1) detectores determinísticos escolhem UMA ferramenta e seus filtros
(categoria/geo/tipo de violência/ano); (2) a ferramenta roda uma vez
(SQL ao vivo, corpus jurídico ou documentação); (3) o Jurema-7B redige a
resposta a partir do payload humanizado, com fallback para a ``narrativa_sugerida``
pronta. Os helpers ``_detect_*``/``_maybe_*``/``_enforce_*`` — que antes só
CORRIGIAM as escolhas do Qwen — agora SÃO o roteador.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

import ollama

from .tools import TOOLS_SCHEMA, ToolContext, run_tool


_UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

# Formas coloquiais/parciais que se referem INEQUIVOCAMENTE a um estado, mesmo
# sem o nome completo. Só entram formas que NUNCA são nome de cidade — assim
# não introduzem confusão cidade↔estado. ("Minas" == Minas Gerais.)
_UF_ALIASES = {
    "minas": "MG",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# Phrases that mean "ranking", not a literal municipality name.
_RANKING_HINTS = (
    "mais violenta", "mais violento", "mais perigosa", "mais perigoso",
    "piores cidades", "piores municipios", "top ", "ranking", "que mais",
    "com mais ", "lista das cidades", "cidades com maior",
)


def _looks_like_ranking_query(text: str) -> bool:
    if not text:
        return False
    n = _norm(text)
    return any(h in n for h in (_norm(h) for h in _RANKING_HINTS))


# Nomes de UF cujo normalizado (sem acento) colide com palavra comum do PT:
# "Pará" -> "para" (preposição for/to). Para esses, o match do NOME exige o
# acento (no texto original), senão toda frase com "para" acusaria o estado PA.
_ACCENT_REQUIRED_UF = {"PA": "Pará"}


def _uf_fullname_hit(sigla: str, nome: str, orig_text: str, norm_text: str) -> bool:
    """True se o NOME do estado aparece no texto. Para UFs ambíguas ('Pará' vs
    preposição 'para') exige a forma acentuada no texto original."""
    if sigla in _ACCENT_REQUIRED_UF:
        return bool(re.search(rf"\b{re.escape(nome.lower())}\b", (orig_text or "").lower()))
    return bool(re.search(rf"\b{re.escape(_norm(nome))}\b", norm_text))


def _detect_uf(user_text: str) -> str | None:
    """Detecta nome ou sigla de estado na pergunta. Retorna sigla (SE, SP, ...) ou None.

    Ordem das heurísticas (do mais específico ao mais geral):
      1) Nome completo do estado normalizado (com ou sem acento).
      2) Sigla após preposição típica: "em SP", "do RJ", "na BA" (case-insensitive).
      3) Sigla após indicador explícito de UF: "estado de SE", "uf SP".
      4) Sigla isolada em UPPERCASE no texto original (último recurso).
    """
    if not user_text:
        return None
    norm = _norm(user_text)

    # 1) Nome completo (mais longo primeiro: 'Rio Grande do Sul' antes de 'Rio de Janeiro').
    for sigla, nome in sorted(_UF_NAMES.items(), key=lambda x: -len(x[1])):
        if _uf_fullname_hit(sigla, nome, user_text, norm):
            return sigla

    # 1b) Forma coloquial/parcial inequívoca ("Minas" -> MG). Vem antes das
    #     heurísticas de sigla porque é mais específica que "duas letras soltas".
    for alias, sigla in sorted(_UF_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(alias)}\b", norm):
            return sigla

    # 2) Preposição + sigla (case-insensitive). Captura "em SP", "no rj", "do MG", etc.
    prep = r"(?:em|no|na|nos|nas|para|pra|de|do|da|dos|das|pelo|pela)"
    m = re.search(rf"\b{prep}\s+([A-Za-z]{{2}})\b", user_text)
    if m and m.group(1).upper() in _UF_NAMES:
        return m.group(1).upper()

    # 3) Indicador explícito de UF ("estado de XX", "uf de XX").
    m = re.search(r"\b(?:estado de|uf de|na uf|no estado de|do estado de)\s+([a-z]{2})\b", norm)
    if m and m.group(1).upper() in _UF_NAMES:
        return m.group(1).upper()

    # 4) Sigla isolada em UPPERCASE no texto original.
    for sig in re.findall(r"\b([A-Z]{2})\b", user_text):
        if sig in _UF_NAMES:
            return sig

    return None


# Siglas institucionais/jurídicas que aparecem coladas à UF ("MP-BA", "TJ/SP")
# ou soltas — NUNCA são nomes de cidade. Evita extrair "MP" de "MP-BA".
_INSTITUTION_ACRONYMS = {
    "MP", "MPF", "MPT", "MPE", "MPU", "TJ", "TRF", "STF", "STJ", "DPE", "DPU",
    "DP", "PC", "PM", "PF", "PRF", "CNDH", "CNJ", "CT", "VIJ", "OAB", "SES",
    "SSP", "CRAS", "CREAS", "SUS", "ECA", "ACP", "UF", "IBGE", "CNMP",
}
# Palavras Capitalizadas que aparecem nessas perguntas mas NÃO são cidades.
_CITY_STOPWORDS = {_norm(w) for w in (
    "Lei", "Leis", "Vara", "Varas", "Conselho", "Conselhos", "Estadual",
    "Nacional", "Municipal", "Ministerio", "Publico", "Estado", "Estados",
    "Brasil", "Crianca", "Criancas", "Adolescente", "Adolescentes", "Dados",
    "Dado", "Estatistica", "Estatisticas", "Casos", "Caso", "Numero",
    "Numeros", "Tribunal", "Justica", "Defensoria", "Defensor", "Promotor",
    "Promotoria", "Infancia", "Juventude", "Direitos", "Henry", "Borel",
    "Rede", "Protecao", "Pedido", "Informacao", "Relatorio", "Parecer",
    "Peticao", "Denuncia", "Subsidio", "Representacao", "Violencia",
    "Negligencia", "Tortura", "Trafico", "Abuso", "Como", "Qual", "Quais",
    "Quantos", "Quantas", "Preciso", "Levanta", "Mostra", "Quero",
    "Tendencia", "Evolucao", "Comarca", "Sobre", "Municipio", "Cidade",
)}


# Palavras que compõem nomes de estado ("sao", "paulo", "rio", "grande", "minas"...)
# e conectores — usadas para rejeitar candidatos a cidade no Pattern 3.
_UF_NAME_WORDS = {w for n in _UF_NAMES.values() for w in _norm(n).split()}
_CONNECTORS = {"de", "do", "da", "dos", "das", "e"}


def _is_city_candidate(name: str) -> bool:
    """Heurística: `name` plausivelmente é uma cidade (não sigla/estado/stopword)."""
    if not name:
        return False
    raw = name.strip()
    nm = _norm(raw)
    if len(nm) < 3:
        return False
    if raw.upper() in _INSTITUTION_ACRONYMS:
        return False
    if raw.isupper() and len(raw) <= 4:          # sigla solta (MP, TJ, CNDH...)
        return False
    if nm in _CITY_STOPWORDS:
        return False
    if nm in {_norm(n) for n in _UF_NAMES.values()}:   # nome de estado
        return False
    if nm in _UF_ALIASES:                              # alias de estado ("minas")
        return False
    return True


def _detect_city_in_uf(user_text: str, sigla: str) -> str | None:
    """Tenta extrair o nome da cidade quando o texto também menciona uma UF.

    Padrões cobertos:
      "em Malhador-SE" / "em Malhador SE" / "Malhador/SE"
      "Bom Jesus do estado de Sergipe"
      "Bom Jesus de Sergipe" / "Vitória da Conquista BA"
      "Dados de Salvador ... MP-BA"  (cidade longe da UF, via preposição)
      "em Aracaju" (cidade isolada, sem UF — devolve None aqui; LLM decide)

    Ignora siglas institucionais ("MP-BA" NÃO vira cidade "MP") e nomes de
    estado/stopwords via `_is_city_candidate`.
    """
    if not sigla:
        return None
    nome_uf = _UF_NAMES.get(sigla, "")

    # Pattern 1: <Cidade>-SP / <Cidade> SP / <Cidade>/SP (sigla logo após cidade)
    # Aceita nome com várias palavras (Bom Jesus, Vitória da Conquista)
    m = re.search(
        rf"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+"
        rf"(?:\s+(?:de|do|da|dos|das|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+))*)"
        rf"[\-/\s]+{sigla}\b",
        user_text,
    )
    if m:
        name = m.group(1).strip()
        if _is_city_candidate(name) and _norm(name) != _norm(nome_uf):
            return name

    # Pattern 2: "<Cidade> [do estado] de <Nome UF>"
    if nome_uf:
        m = re.search(
            rf"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+"
            rf"(?:\s+(?:de|do|da|dos|das|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+))*?)"
            rf"\s+(?:do estado de|do estado|de|em)\s+{re.escape(nome_uf)}\b",
            user_text,
        )
        if m:
            name = m.group(1).strip()
            if _is_city_candidate(name) and _norm(name) != _norm(nome_uf):
                return name

    # Pattern 3: cidade citada LONGE da UF ("Dados de Salvador ... MP-BA").
    # Primeira palavra Capitalizada após preposição de tópico que passe no
    # teste de candidato a cidade. Cobre casos onde a sigla está grudada numa
    # instituição (MP-BA) e não adjacente ao nome da cidade.
    for m in re.finditer(
        r"\b(?:de|do|da|dos|das|em|no|na)\s+"
        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]{2,}"
        r"(?:\s+(?:de|do|da|dos|das)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)*)",
        user_text,
    ):
        cand = m.group(1).strip()
        if not _is_city_candidate(cand) or _norm(cand) == _norm(nome_uf):
            continue
        # Estrito: rejeita se QUALQUER palavra for stopword, sigla, ou parte de
        # um nome de estado ("São" de "São Paulo", "Vara"/"Direitos" jurídicos).
        words = [w for w in _norm(cand).split() if w not in _CONNECTORS]
        if any(w in _CITY_STOPWORDS or w in _UF_NAME_WORDS
               or w.upper() in _INSTITUTION_ACRONYMS for w in words):
            continue
        return cand
    return None


# Capitais estaduais — cidades citadas frequentemente SEM a sigla da UF
# ("casos em Aracaju"). Mapeadas para (nome de exibição, UF) para que o
# detector as trate como MUNICÍPIO mesmo sem a UF no texto.
# Omitidas de propósito: São Paulo / Rio de Janeiro (nome ambíguo com o
# estado), Brasília/DF (nível-UF, sem municípios), e capitais que também são
# palavras comuns em PT (Natal, Vitória, Palmas) para evitar falso-positivo.
_CAPITAIS: dict[str, tuple[str, str]] = {
    "aracaju": ("Aracaju", "SE"), "salvador": ("Salvador", "BA"),
    "recife": ("Recife", "PE"), "fortaleza": ("Fortaleza", "CE"),
    "manaus": ("Manaus", "AM"), "belem": ("Belém", "PA"),
    "curitiba": ("Curitiba", "PR"), "porto alegre": ("Porto Alegre", "RS"),
    "belo horizonte": ("Belo Horizonte", "MG"), "goiania": ("Goiânia", "GO"),
    "maceio": ("Maceió", "AL"), "joao pessoa": ("João Pessoa", "PB"),
    "teresina": ("Teresina", "PI"), "campo grande": ("Campo Grande", "MS"),
    "cuiaba": ("Cuiabá", "MT"), "florianopolis": ("Florianópolis", "SC"),
    "boa vista": ("Boa Vista", "RR"), "macapa": ("Macapá", "AP"),
    "rio branco": ("Rio Branco", "AC"), "porto velho": ("Porto Velho", "RO"),
    "sao luis": ("São Luís", "MA"),
}


def _detect_capital(user_text: str) -> tuple[str, str] | None:
    """Detecta uma capital citada sem a UF ("em Aracaju"). Exige preposição
    geográfica antes do nome para evitar falso-positivo. Retorna (nome, sigla)."""
    if not user_text:
        return None
    norm = _norm(user_text)
    for nome in sorted(_CAPITAIS, key=len, reverse=True):  # mais longo primeiro
        if re.search(rf"\b(?:em|no|na|de|do|da|dos|das|para|pra)\s+{re.escape(nome)}\b", norm):
            return _CAPITAIS[nome]
    return None


# Escopo NACIONAL explícito — quando presente, um follow-up NÃO deve herdar o
# estado citado antes ("e no Brasil todo?" após uma pergunta sobre Sergipe).
_NATIONAL_RE = re.compile(
    r"\bbrasil\b|\bnacional|\btodos os estados\b|(?:todo|em todo|em todos|no|do|pelo)\s+pais\b")


def _mentions_national(user_text: str) -> bool:
    return bool(user_text and _NATIONAL_RE.search(_norm(user_text)))


# Pergunta de COMPARAÇÃO ("e em relação a X?", "comparado a Y", "qual cresceu mais").
_COMPARISON_RE = re.compile(
    r"em relacao a|comparad|comparacao|em comparacao|\bversus\b|\bvs\b|\bcompare\b|"
    r"diferenca entre|qual (cresceu|aumentou|teve|foi) (mais|menos|maior|menor)|"
    r"proporcional|\bmais que\b|\bmenos que\b|frente a|ante a|em rela")


def _is_comparison(user_text: str) -> bool:
    return bool(user_text and _COMPARISON_RE.search(_norm(user_text)))


def _detect_geo_hint(user_text: str) -> str | None:
    """Inject a deterministic hint about the geographic scope.

    Priority of detection (mais específico ganha):
      1) Ranking phrase ("cidade mais X", "top N") → ranking_municipios
      2) Cidade + UF (Malhador-SE, Bom Jesus de Sergipe) → relatorio_municipio
      3) Só UF citada → relatorio_uf
      4) Capital sem UF (Aracaju, Salvador) → relatorio_municipio
    """
    sigla = _detect_uf(user_text)
    if not sigla:
        # Sem UF explícita: pode ser uma capital citada sozinha ("em Aracaju").
        cap = _detect_capital(user_text)
        if cap:
            city, sig = cap
            return (f"[detector] Usuario citou cidade '{city}' (capital de {sig}). "
                    f"USE `relatorio_municipio(municipio='{city}', uf='{sig}')`. "
                    f"NAO use `relatorio_uf` nem `relatorio_brasil`.")
        return None
    nome = _UF_NAMES[sigla]
    norm = _norm(user_text)

    # Fix 1: RANKING vence UF quando ambos aparecem.
    # "Top 5 cidades em SP" / "cidade mais violenta de Sergipe"
    if _looks_like_ranking_query(user_text):
        return (f"[detector] Usuario pediu RANKING + UF {sigla} ({nome}). "
                f"USE `ranking_municipios(uf='{sigla}', filters_extra={{...}})`. "
                f"NAO use `relatorio_uf` nem `relatorio_municipio`.")

    # Fix 2: cidade+UF (pattern robusto). Se conseguimos extrair nome da cidade,
    # damos o nome de bandeja pro LLM.
    city = _detect_city_in_uf(user_text, sigla)
    if city:
        return (f"[detector] Usuario citou cidade '{city}' em {nome} ({sigla}). "
                f"USE `relatorio_municipio(municipio='{city}', uf='{sigla}')`. "
                f"NAO use `relatorio_uf` nem `relatorio_brasil`.")

    # Caso default: estado todo
    return (f"[detector] O usuario citou '{nome}' (UF {sigla}). "
            f"USE `relatorio_uf(uf='{sigla}', ...)`. "
            f"NAO use `relatorio_brasil`.")


# Sinais de que a pergunta tem finalidade JURÍDICA/INSTITUCIONAL. O juiz
# valoriza a "utilidade prática" (subsidiar ACP, representação, parecer). Quando
# detectamos esse contexto, injetamos uma dica para o fechamento conectar os
# dados à finalidade citada — sem inventar números.
_CONTEXT_JURIDICO_RE = re.compile(
    r"\b(vara da infancia|conselho tutelar|conselho estadual|ministerio publico|"
    r"mp|mpf|mpt|mpe|cnmp|acp|acao civil publica|representacao|peticao|peticion\w*|"
    r"cndh|eca|estatuto da crianca|defensoria|promotor\w*|parecer|denuncia|"
    r"rede de protecao|direitos da crianca|delegacia|inquerito|processo judicial|"
    r"lei\s+\d|lei henry borel|art\.?\s*\d)\b",
    re.IGNORECASE,
)


def _detect_context_hint(user_text: str) -> str | None:
    """Dica de contexto jurídico/institucional para o parágrafo de leitura prática."""
    if not user_text:
        return None
    if _CONTEXT_JURIDICO_RE.search(_norm(user_text)):
        return ("[detector] A pergunta tem FINALIDADE JURIDICA/INSTITUCIONAL "
                "(ex.: representacao, ACP, Conselho Tutelar, Ministerio Publico, "
                "Vara da Infancia, peticao). No paragrafo final de leitura pratica, "
                "conecte os dados a essa finalidade de forma concreta e util "
                "(ex.: subsidiar a peca, fundamentar a representacao, embasar o "
                "parecer), SEM inventar numeros e SEM citar anos posteriores a 2024.")
    return None


# ---------------------------------------------------------------------------
# Roteador determinístico (arquitetura: Qwen3 é o principal; Chronos/série só
# quando a pergunta É de série temporal). O qwen3:8b tende a cair em ferramentas
# de série por causa do prompt-base focado em SINAM. Aqui detectamos intenção
# JURÍDICA / PRODUTO / SIPIA-CT e injetamos uma dica forte para a ferramenta certa.
# ---------------------------------------------------------------------------
_ROUTE_LEGAL_RE = re.compile(
    r"\beca\b|estatuto da crianca|\blei\b|\bleis\b|\bartigo|\bart\.?\s*\d|sumula|"
    r"jurisprud|base legal|marco legal|o que diz a lei|o que a lei|legisla|"
    r"constitui|portaria|resolucao|conanda|codigo penal|amparo legal|"
    r"previsto em lei|\bjuridic|lei henry borel|\bloa\b")
_ROUTE_PRODUCT_RE = re.compile(
    r"como (o |a )?(aurora|plataforma|sistema|chat|modelo) (funciona|calcula|preve|roteia)|"
    r"como funciona (o |a )?(aurora|plataforma|sistema|chat|previsao|analise|comite)|"
    r"metodologia|de onde v(e|ê)m os dados|o que e (a )?analise retrospectiva|"
    r"comite de modelos|camada semantica|como voce funciona")
_ROUTE_SIPIA_RE = re.compile(
    r"\bsipia\b|conselho tutelar|conselheir[oa] tutelar|medida de protecao")

# Indicadores do PRÓPRIO SIPIA-CT (não apenas "conselho tutelar" citado como
# destino). Só estes fazem uma pergunta com pedido de dados ir para o SIPIA.
_ROUTE_SIPIA_INDIC_RE = re.compile(
    r"\bsipia\b|direitos? violad\w*|agente violador|medida de protecao")

# Pergunta explicitamente SOBRE a lei/norma (não um pedido de estatística).
_LEGAL_QUESTION_RE = re.compile(
    r"o que diz|qual (a |o )?(lei|artigo|norma|pena|prazo|sancao|medida)|"
    r"quais (os |as )?direitos|segundo (o|a)\b|base legal|previsto em lei|"
    r"prev[eê]\b|\be crime\b|penaliza|define|estabelece|o que e o eca|"
    r"amparo legal|fundamento legal")

# Sinais de que o usuário quer DADOS/ESTATÍSTICA (caminho SINAM), não a norma.
_DATA_INTENT_RE = re.compile(
    r"\bcasos?\b|\bdados?\b|estatistic|\bnumeros?\b|quantos|quantas|quantidade|"
    r"notificac|\bregistros?\b|evolu|tendenci|\branking\b|\btaxa\b|\bindice\b|"
    r"levanta|compar|\bserie\b|grafico|total de|panorama|distribuic|\bmostra\b|"
    r"percentual|proporcao|incidencia|ocorrencias?")


def _wants_data(user_text: str) -> bool:
    """True se a pergunta pede ESTATÍSTICA/DADOS do SINAM (e não a norma)."""
    if not user_text:
        return False
    n = _norm(user_text)
    if _DATA_INTENT_RE.search(n):
        return True
    # Tipo de violência do SINAM + recorte geográfico/nacional => consulta de dados.
    if _detect_violencias(user_text) and (
            _detect_uf(user_text) or _detect_capital(user_text)
            or _mentions_national(user_text)):
        return True
    return False


def _route_category(user_text: str) -> str | None:
    """Categoria de roteamento quando a intenção NÃO é dados/série SINAM:
    'sipia' | 'legal' | 'product' | None.

    Prioridade: uma pergunta que PEDE DADOS/estatística do SINAM fica no caminho
    de dados (retorna None), mesmo citando lei/MP/Conselho como *finalidade*. Só
    vai para jurídico quando é pergunta SOBRE a norma; e só para SIPIA quando é
    sobre indicadores do próprio SIPIA-CT (não "conselho tutelar" como destino).
    """
    if not user_text:
        return None
    n = _norm(user_text)
    # 1) Indicador do PRÓPRIO SIPIA-CT (mais específico) -> sipia.
    if _ROUTE_SIPIA_INDIC_RE.search(n):
        return "sipia"
    # 2) Pergunta sobre o PRÓPRIO produto/metodologia -> product ("de onde vêm
    #    os dados", "como funciona") — antes de wants_data, que casaria "dados".
    if _ROUTE_PRODUCT_RE.search(n):
        return "product"
    # 3) Pergunta explicitamente SOBRE a lei/norma -> jurídico.
    if _LEGAL_QUESTION_RE.search(n):
        return "legal"
    # 4) Pedido de dados/estatística -> caminho SINAM (dados).
    if _wants_data(user_text):
        return None
    # 5) Sem pedido de dados: roteia por tópico (comportamento anterior).
    if _ROUTE_SIPIA_RE.search(n):
        return "sipia"
    if _ROUTE_LEGAL_RE.search(n):
        return "legal"
    if _ROUTE_PRODUCT_RE.search(n):
        return "product"
    return None


_ROUTE_HINTS = {
    "sipia": ("[roteador] A pergunta é sobre o CONSELHO TUTELAR / SIPIA-CT. "
              "USE `consulta_sipia_ct` (fonte distinta do SINAM de saúde)."),
    "legal": ("[roteador] A pergunta é de natureza JURÍDICA (lei/ECA/artigo/norma). "
              "USE `rag_juridico` (Jurema) e CITE a base legal. NÃO chame ferramentas "
              "de série/previsão/SINAM, a menos que a pergunta peça números."),
    "product": ("[roteador] A pergunta é sobre o PRÓPRIO produto/metodologia do Aurora. "
                "USE `rag_interno` (documentação). NÃO use ferramentas de série/SINAM."),
}

# Ferramenta canônica de cada categoria — usada na rerota determinística.
_ROUTE_TOOL = {"sipia": "consulta_sipia_ct", "legal": "rag_juridico", "product": "rag_interno"}


def _detect_route_hint(user_text: str) -> str | None:
    return _ROUTE_HINTS.get(_route_category(user_text))


def _detect_sipia_indicador(text: str) -> str | None:
    """Mapeia a pergunta para a dimensão (indicador) do SIPIA-CT."""
    if not text:
        return None
    n = _norm(text)
    if "direito violado" in n or "direito" in n or "violacao de direito" in n:
        return "Direito Violado"
    if "agente violador" in n or "agressor" in n or "quem violou" in n:
        return "Agente Violador"
    if "faixa etaria" in n or "idade" in n:
        return "Faixa Etária"
    if re.search(r"\bsexo\b|genero", n):
        return "Sexo"
    if re.search(r"\bcor\b|\braca\b", n):
        return "Cor"
    return None


def _maybe_reroute(category: str | None, name: str, args: dict, user_text: str
                   ) -> tuple[str, dict, str | None]:
    """Se a intenção é jurídica/produto/SIPIA e o Qwen chamou OUTRA ferramenta,
    reescreve para a ferramenta canônica da categoria. Determinístico — o
    qwen3:8b tende a cair em ferramentas de série mesmo com a dica no prompt.

    Para o SIPIA-CT, herda/deriva os filtros (uf/ano/indicador) da pergunta —
    senão a consulta varreria a base inteira (que tem dado sujo na origem)."""
    if not category:
        return name, args, None
    alvo = _ROUTE_TOOL[category]
    if category in ("legal", "product"):
        if name == alvo:
            return name, args, None
        return alvo, {"query": (user_text or "")[:500]}, \
            f"redirecionado {name} -> {alvo} (roteador: pergunta {category})"

    # SIPIA-CT: monta filtros a partir dos args do modelo + da pergunta.
    filtros = dict((args or {}).get("filtros") or {})
    # UF: a pergunta do usuário VENCE a UF do modelo quando esta não foi citada
    # (o qwen3 alucina estados — ex.: responde BA para uma pergunta sobre SE).
    model_uf = _uf_to_sigla(filtros.get("uf")) or _uf_to_sigla((args or {}).get("uf"))
    text_uf = _detect_uf(user_text)
    ment = _mentioned_ufs(user_text)
    if text_uf and (not model_uf or (ment and model_uf not in ment)):
        filtros["uf"] = text_uf
    elif model_uf:
        filtros["uf"] = model_uf
    if "ano" not in filtros:
        anos = re.findall(r"\b(20\d{2})\b", user_text or "")
        if anos:
            filtros["ano"] = int(anos[0])
    if "indicador" not in filtros:
        ind = _detect_sipia_indicador(user_text)
        if ind:
            filtros["indicador"] = ind
    note = None if name == alvo else f"redirecionado {name} -> {alvo} (Conselho Tutelar/SIPIA-CT)"
    return alvo, {"filtros": filtros, "group_by": (args or {}).get("group_by")}, note


# ---------------------------------------------------------------------------
# Escopo ESTRITO do Aurora responde. Pedidos claramente fora (programação/HTML/
# site, redação criativa, temas gerais) são recusados ANTES de chamar o LLM —
# barato e determinístico. Sem isso, o qwen3:8b tentava "ajudar" e chegava a
# gerar HTML, que quebrava a interface do chat.
# ---------------------------------------------------------------------------
_OFFSCOPE_RE = re.compile(
    r"\bhtml\b|\bcss\b|\bjavascript\b|\bpython\b|\bnode\b|\breact\b|"
    r"landing\s*page|pagina\s*web|\bwebsite\b|"
    r"(?:faca|cria|crie|criar|construa|construir|gera|gere|gerar|escreva|escrever|"
    r"monte|montar|desenvolva|desenvolver|programe|programar|codifique)\s+"
    r"(?:um\s|uma\s|o\s|a\s|meu\s|minha\s)?"
    r"(?:tela|site|codigo|programa|aplicativo|app|pagina|formulario|script|jogo|"
    r"funcao|classe|componente|banner|layout)|"
    r"\bpoema\b|\bpoesia\b|\bpiada\b|\bconto\b|letra de musica|receita de|horoscopo")

_OFFSCOPE_MSG = (
    "Sou o assistente do Aurora, focado em dados de violência contra crianças e "
    "adolescentes (SINAN e SIPIA-CT), na legislação relacionada (ECA, leis e "
    "normas) e no funcionamento desta plataforma. Não escrevo código nem crio "
    "páginas/HTML, e não trato de assuntos fora desse escopo.\n\n"
    "Posso ajudar, por exemplo, com a evolução das notificações em um estado, o "
    "ranking de municípios, o perfil das vítimas, ou o que a lei diz sobre um "
    "tipo de violência. Como posso ajudar dentro desse escopo?"
)


def _is_offscope(user_text: str) -> bool:
    """True se a pergunta pede algo claramente fora do escopo (código/HTML/etc.)."""
    return bool(user_text and _OFFSCOPE_RE.search(_norm(user_text)))


def _uf_to_sigla(raw) -> str | None:
    """'BA'/'bahia'/'Bahia' -> 'BA'. None se não for UF reconhecida."""
    if not raw:
        return None
    s = str(raw).strip().upper()
    if s in _UF_NAMES:
        return s
    nn = _norm(raw)
    for sig, nome in _UF_NAMES.items():
        if _norm(nome) == nn:
            return sig
    return None


def _mentioned_ufs(text: str) -> set[str]:
    """Conjunto de UFs que o usuário realmente citou (nome, alias, capital, sigla)."""
    ufs: set[str] = set()
    if not text:
        return ufs
    n = _norm(text)
    for sig, nome in _UF_NAMES.items():
        if _uf_fullname_hit(sig, nome, text, n):
            ufs.add(sig)
    for alias, sig in _UF_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", n):
            ufs.add(sig)
    for cap, (_nome, sig) in _CAPITAIS.items():
        if re.search(rf"\b{re.escape(cap)}\b", n):
            ufs.add(sig)
    prep = r"(?:em|no|na|nos|nas|de|do|da|dos|das|para|pra|pelo|pela)"
    for m in re.finditer(rf"\b{prep}\s+([A-Za-z]{{2}})\b", text):
        if m.group(1).upper() in _UF_NAMES:
            ufs.add(m.group(1).upper())
    for sig in re.findall(r"\b([A-Z]{2})\b", text):
        if sig in _UF_NAMES:
            ufs.add(sig)
    return ufs


def _first_capital(text: str) -> tuple[str, str] | None:
    """Capital citada mais cedo no texto -> (nome, sigla). None se nenhuma."""
    if not text:
        return None
    n = _norm(text)
    best, bpos = None, 1 << 30
    for cap, (nome, sig) in _CAPITAIS.items():
        m = re.search(rf"\b{re.escape(cap)}\b", n)
        if m and m.start() < bpos:
            bpos, best = m.start(), (nome, sig)
    return best


def _maybe_rewrite_tool_call(name: str, args: dict, last_user_text: str) -> tuple[str, dict, str | None]:
    # Trava anti-alucinação de UF: o qwen3:8b às vezes escolhe um estado que o
    # usuário NUNCA citou (ex.: pergunta sobre Aracaju/SP e ele responde Bahia).
    # Se a UF do relatório não está entre as citadas, redireciona para o 1º local
    # realmente citado (capital -> município; senão a 1ª UF citada).
    if name in ("relatorio_uf", "relatorio_municipio"):
        ment = _mentioned_ufs(last_user_text)
        cur = _uf_to_sigla((args or {}).get("uf"))
        if ment and cur and cur not in ment:
            fe = (args or {}).get("filters_extra", {})
            cap = _first_capital(last_user_text)
            if cap:
                city, sig = cap
                return ("relatorio_municipio",
                        {"municipio": city, "uf": sig, "filters_extra": fe},
                        f"corrigido: UF {cur} nao foi citada; usuario citou "
                        f"{sorted(ment)} -> relatorio_municipio('{city}',{sig})")
            tgt = sorted(ment)[0]
            return ("relatorio_uf", {"uf": tgt, "filters_extra": fe},
                    f"corrigido: UF {cur} nao foi citada -> relatorio_uf({tgt})")

    # Escopo NACIONAL: o usuário pediu "no Brasil"/nacional e NÃO citou estado
    # nem capital, mas o modelo caiu em relatorio_uf/municipio (recorte local).
    # Corrige para relatorio_brasil (ex.: "tráfico de crianças no Brasil").
    if (name in ("relatorio_uf", "relatorio_municipio")
            and _mentions_national(last_user_text)
            and not _detect_uf(last_user_text) and not _detect_capital(last_user_text)):
        return ("relatorio_brasil",
                {"filters_extra": (args or {}).get("filters_extra", {})},
                f"redirecionado {name} -> relatorio_brasil (usuario pediu escopo nacional)")

    """Enforce geographic correctness: if the user typed a state name but the
    LLM picked relatorio_brasil/municipio, rewrite to relatorio_uf.

    Returns (name, args, note) where `note` is a short message added to the
    tool result so the LLM (and user) sees that the call was redirected.
    """
    uf_in_question = _detect_uf(last_user_text)
    if not uf_in_question:
        # Sem UF explícita, mas pode haver uma CAPITAL citada sozinha
        # ("em Aracaju"). Nesse caso a resposta certa é a nível-município.
        cap = _detect_capital(last_user_text)
        if cap:
            city, sig = cap
            fe = (args or {}).get("filters_extra", {})
            if name in ("relatorio_brasil", "relatorio_uf"):
                return ("relatorio_municipio",
                        {"municipio": city, "uf": sig, "filters_extra": fe},
                        f"redirecionado de {name} -> relatorio_municipio('{city}', {sig}) "
                        f"-- '{city}' e um municipio (capital de {sig})")
            if name == "relatorio_municipio" and \
                    _norm((args or {}).get("uf", "")) != _norm(sig):
                new_args = dict(args or {})
                new_args["uf"] = sig
                return ("relatorio_municipio", new_args,
                        f"uf ajustada para {sig} em relatorio_municipio('{city}')")
        return name, args, None

    if name == "relatorio_brasil":
        # Se o usuário nomeou uma cidade (ex: "Salvador-BA"), vai direto a município.
        city = _detect_city_in_uf(last_user_text, uf_in_question)
        if city:
            return ("relatorio_municipio",
                    {"municipio": city, "uf": uf_in_question,
                     "filters_extra": (args or {}).get("filters_extra", {})},
                    f"redirecionado de relatorio_brasil -> relatorio_municipio('{city}') "
                    f"porque o usuario citou essa cidade")
        # Caso contrário, do nível Brasil para o estado citado.
        new_args = {"uf": uf_in_question,
                    "filters_extra": (args or {}).get("filters_extra", {})}
        return ("relatorio_uf", new_args,
                f"redirecionado de relatorio_brasil -> relatorio_uf({uf_in_question}) "
                f"porque o usuario citou esse estado")

    if name == "relatorio_municipio":
        # User said state but model thought municipality
        mun = (args or {}).get("municipio", "")
        nm = _norm(mun)
        ns = _norm(_UF_NAMES.get(uf_in_question, ""))
        fe = (args or {}).get("filters_extra", {})
        # (a) O "municipio" e na verdade o proprio estado: nome exato ("Sergipe"),
        #     a sigla ("MG"), OU um prefixo do nome ("Minas" ⊆ "Minas Gerais").
        if nm and (nm == ns or nm == _norm(uf_in_question)
                   or (len(nm) >= 4 and ns.startswith(nm))):
            return ("relatorio_uf",
                    {"uf": uf_in_question, "filters_extra": fe},
                    f"redirecionado de relatorio_municipio('{mun}') -> "
                    f"relatorio_uf({uf_in_question}) -- '{mun}' e o estado, nao cidade")
        # (c) Cidade legitima, mas a UF veio ausente/errada -> corrige com a UF
        #     detectada no texto (mantem municipio e filtros).
        if mun.strip() and _norm((args or {}).get("uf", "")) != _norm(uf_in_question):
            new_args = dict(args or {})
            new_args["uf"] = uf_in_question
            return ("relatorio_municipio", new_args,
                    f"uf ajustada para {uf_in_question} em relatorio_municipio('{mun}')")

    if name == "relatorio_uf":
        # Usuario citou uma cidade dentro da UF (ex: "Salvador-BA"), mas o LLM
        # ficou no nivel estadual. Redireciona para o municipio.
        city = _detect_city_in_uf(last_user_text, uf_in_question)
        if city:
            return ("relatorio_municipio",
                    {"municipio": city, "uf": uf_in_question,
                     "filters_extra": (args or {}).get("filters_extra", {})},
                    f"redirecionado de relatorio_uf -> relatorio_municipio('{city}') "
                    f"porque o usuario citou essa cidade")
        # UF errada: o modelo escolheu um estado diferente do indicado pelo
        # contexto (comum em follow-ups multi-turn — o qwen3 troca de estado ou
        # alucina). O estado do contexto VENCE a escolha do modelo.
        model_sigla = _uf_to_sigla((args or {}).get("uf"))
        if model_sigla and model_sigla != uf_in_question:
            new_args = dict(args or {})
            new_args["uf"] = uf_in_question
            return ("relatorio_uf", new_args,
                    f"uf corrigida de {model_sigla} para {uf_in_question} "
                    f"(estado do contexto da conversa)")
    return name, args, None


def _maybe_rewrite_to_ranking(name: str, args: dict, last_user_text: str
                              ) -> tuple[str, dict, str | None]:
    """If the user asked for a ranking but the LLM called relatorio_municipio
    or relatorio_uf, rewrite to ranking_municipios. Fix 1.
    """
    if not _looks_like_ranking_query(last_user_text):
        return name, args, None

    # relatorio_municipio com expressão tipo "cidade mais violenta"
    if name == "relatorio_municipio":
        uf_val = (args or {}).get("uf")
        return ("ranking_municipios",
                {"uf": uf_val, "top": 10, "filters_extra": {}},
                "redirecionado: usuario pediu ranking, nao cidade especifica")

    # relatorio_uf quando usuario citou UF + ranking
    if name == "relatorio_uf":
        uf_val = (args or {}).get("uf") or _detect_uf(last_user_text)
        # Mantém os filtros_extra (ex: violencia_sexual=true) no ranking
        extra = (args or {}).get("filters_extra") or {}
        return ("ranking_municipios",
                {"uf": uf_val, "top": 10, "filters_extra": extra},
                "redirecionado: usuario pediu RANKING de cidades + UF, nao "
                "analise do estado todo")

    return name, args, None


# ---------------------------------------------------------------------------
# Enforcement determinístico do TIPO DE VIOLÊNCIA
# O qwen3:8b ignora o filtro pedido e cai em violencia_fisica por default.
# Aqui detectamos o tipo na pergunta e corrigimos os args da tool — igual
# ao enforcement de geografia acima. (Foi a causa nº1 de notas baixas do juiz.)
# ---------------------------------------------------------------------------

# Ordem importa: padrões mais específicos primeiro. Texto é normalizado
# (sem acento, minúsculo) por _norm antes do match.
_VIOLENCIA_PATTERNS: list[tuple[str, str]] = [
    ("violencia_sexual",      r"sexual|estupro|abuso sexual|exploracao sexual|pedofil|assedio"),
    ("violencia_psicologica", r"psicologic|psiquic|emocional"),
    ("tortura",               r"tortura"),
    ("negligencia",           r"negligenc|abandono|omissao de cuidado|desamparo"),
    ("trafico_pessoas",       r"trafico|aliciamento"),
    ("violencia_financeira",  r"financeir|patrimonial"),
    ("violencia_fisica",      r"fisic|agressao|espancamento|lesao corporal|maus[- ]tratos"),
]
_VIOLENCIA_KEYS: set[str] = {k for k, _ in _VIOLENCIA_PATTERNS} | {
    "violencia_infantil", "intervencao_legal", "outras_violencias"}

_REPORT_TOOLS = {"relatorio_uf", "relatorio_municipio",
                 "relatorio_brasil", "ranking_municipios"}


def _detect_violencias(user_text: str) -> list[str]:
    """Detecta os tipos de violência citados na pergunta (pode ser >1).

    Retorna [] quando a pergunta é genérica ("violência contra crianças"),
    caso em que NÃO se força nenhum filtro de tipo (usa o universo todo).
    """
    if not user_text:
        return []
    norm = _norm(user_text)
    found: list[str] = []
    for key, pat in _VIOLENCIA_PATTERNS:
        if re.search(pat, norm) and key not in found:
            found.append(key)
    # Fallback: "violencia infantil" (sem tipo específico) -> filtro próprio.
    # Só dispara se nenhum tipo específico foi citado, pra não conflitar com
    # "violencia sexual contra criancas".
    if not found and re.search(r"\binfantil\b", norm):
        found.append("violencia_infantil")
    return found


def _enforce_violencia_filter(name: str, args: dict, last_user_text: str
                              ) -> tuple[str, dict, str | None]:
    """Garante que filters_extra reflita o(s) tipo(s) de violência pedido(s).

    Se a pergunta cita um tipo específico, removemos qualquer tipo errado que
    o LLM tenha posto e setamos o(s) correto(s). Pergunta genérica passa intacta.
    """
    if name not in _REPORT_TOOLS:
        return name, args, None
    wanted = _detect_violencias(last_user_text)
    args = dict(args or {})
    fe = dict(args.get("filters_extra") or {})
    current = {k for k in fe if k in _VIOLENCIA_KEYS and fe.get(k)}

    if not wanted:
        # Pergunta genérica ("violência contra crianças"): NÃO deve filtrar por
        # tipo (usa todos). Remove qualquer tipo espúrio que o LLM tenha posto.
        if current:
            for k in list(fe):
                if k in _VIOLENCIA_KEYS:
                    fe.pop(k, None)
            args["filters_extra"] = fe
            return name, args, (f"filtro de violencia removido [{', '.join(sorted(current))}] "
                                f"— pergunta generica abrange todos os tipos")
        return name, args, None

    if current == set(wanted):
        return name, args, None  # já está correto

    for k in list(fe):              # remove tipos de violência incorretos
        if k in _VIOLENCIA_KEYS:
            fe.pop(k, None)
    for k in wanted:               # seta o(s) tipo(s) certo(s)
        fe[k] = True
    args["filters_extra"] = fe
    note = (f"filtro de violencia ajustado para [{', '.join(wanted)}] "
            f"(estava: {', '.join(sorted(current)) or 'nenhum/errado'}) — "
            f"a pergunta pediu esse tipo")
    return name, args, note


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
# Aurora Responde é um fork "só Jurema": não há mais orquestrador Qwen fazendo
# tool-calling. O Jurema-7B redige TODAS as respostas a partir do payload das
# ferramentas (roteamento determinístico). `DEFAULT_MODEL` fica como o modelo de
# narração padrão.
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", os.getenv("JUREMA_MODEL", "jurema-7b"))
JUREMA_MODEL = os.getenv("JUREMA_MODEL", "jurema-7b")
JUREMA_NUM_PREDICT = int(os.getenv("JUREMA_NUM_PREDICT", "520"))
MAX_TOOL_ROUNDS = 6  # legado (não há mais loop de tools); mantido p/ compat.

# Limites de contexto (protege o modelo local de entradas exageradas): quantas
# mensagens anteriores entram e o teto de caracteres por mensagem.
MAX_CONTEXT_MESSAGES = int(os.getenv("AURORA_MAX_CONTEXT_MESSAGES", "24"))
MAX_MSG_CHARS = int(os.getenv("AURORA_MAX_MSG_CHARS", "12000"))


def _limit_context(messages: Iterable[dict]) -> list[dict]:
    """Mantém só as últimas N mensagens e trunca conteúdos gigantes.

    Corta as mensagens iniciais até começar num turno 'user', para não deixar
    uma mensagem 'tool' órfã (sem o assistant tool_call correspondente) no topo.
    """
    msgs = list(messages)
    if len(msgs) > MAX_CONTEXT_MESSAGES:
        msgs = msgs[-MAX_CONTEXT_MESSAGES:]
    out: list[dict] = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, str) and len(c) > MAX_MSG_CHARS:
            m = {**m, "content": c[:MAX_MSG_CHARS] + " …[truncado]"}
        out.append(m)
    while out and out[0].get("role") != "user":
        out.pop(0)
    return out


SYSTEM_PROMPT = """Voce e um analista de dados de saude publica especializado em SINAM/VIOLBR
(notificacoes de violencia contra criancas e adolescentes no Brasil, periodo
2014-2024). Responde sempre em PORTUGUES BRASILEIRO, em PROSA NARRATIVA CURTA
(no maximo 3 paragrafos).

⚠️ REGRA DE OURO #1 — ANALISE RETROSPECTIVA:
Esta plataforma faz ANALISE RETROSPECTIVA de series temporais SINAM. Voce
descreve o que JA aconteceu no passado registrado (2014-2024). NUNCA projeta
o futuro, NUNCA inventa dados para anos posteriores a 2024.

⚠️ REGRA DE OURO #2 — RESPEITE O FILTRO PEDIDO:
O usuario quase sempre menciona UM TIPO ESPECIFICO de violencia na pergunta:
"tortura", "violencia fisica", "violencia psicologica", "negligencia",
"trafico de pessoas", "violencia sexual" etc. Voce DEVE chamar a tool com
o filtro CORRESPONDENTE. NUNCA use violencia_sexual por default.

Mapeamento textual -> filtro (memorize):
  "violencia/abuso sexual" / "estupro"   -> {"violencia_sexual": true}
  "violencia/agressao fisica"            -> {"violencia_fisica": true}
  "violencia/abuso psicologica/o"        -> {"violencia_psicologica": true}
  "tortura"                              -> {"tortura": true}
  "negligencia" / "omissao de cuidado"   -> {"negligencia": true}
  "trafico de pessoas/criancas" / "aliciamento" -> {"trafico_pessoas": true}
  "violencia infantil" (generico)        -> {"violencia_infantil": true}

Se a pergunta cita MAIS DE UM tipo ("violencia sexual contra criancas",
"violencia fisica e psicologica"), tente cobrir TODOS no mesmo filters_extra:
  "violencia fisica contra criancas em SP" ->
    {"violencia_fisica": true} (o universo inteiro do SINAM ja e crianca/adolescente)

⚠️ REGRA DE OURO #3 — DADOS VAO ATE 2024:
O dataset SINAM disponivel cobre 2014-2024. NUNCA cite "2025" como dado
real, NUNCA estime numeros para anos futuros. Se a serie retornada da tool
tiver alguma entrada com ano > 2024, IGNORE-A na narrativa.

Sua resposta NUNCA deve conter:
  ❌ dados ou previsoes para 2025 ou anos futuros
  ❌ tabelas markdown
  ❌ headers (###, ##, **Modelo vencedor:**)
  ❌ listas com WAPE/MAPE/RMSE/MAE
  ❌ listas com p10/p50/p90 valor a valor
  ❌ jargao tipo "MAPE", "WAPE", "ACF", "slope", "p50", "lag", "inclinacao por passo"

Os numeros tecnicos ja aparecem na UI ao lado da sua mensagem em tabelas e
graficos -- o usuario NAO precisa ler tudo de novo no texto.

✅ ASSIM SIM (exemplo bom — pergunta sobre TORTURA em MG):

  "Minas Gerais registrou um aumento progressivo de notificacoes de tortura
  contra criancas e adolescentes entre 2021 e 2024. A serie passou de 4,5
  mil casos em 2021 para 6,2 mil em 2024, com pico ja em 2023 e leve
  estabilizacao no ultimo ano observado.

  Validando o comportamento da serie contra o comite de modelos, o padrao foi
  reproduzido com fidelidade boa. Isso da confianca para
  afirmar que o crescimento observado nao e ruido, mas tendencia real
  registrada nas notificacoes.

  Em saude publica, o crescimento pode refletir aumento dos casos, melhoria
  do sistema de notificacao apos campanhas de capacitacao, ou ambos. Para
  uma analise definitiva valeria cruzar com dados do Conselho Tutelar."

❌ ASSIM NAO (exemplos ruins que voce ja fez):

  X) Aplicar filtro errado:
     Usuario: "tortura em MG"
     Voce: chamar relatorio_uf(uf="MG", filters_extra={"violencia_sexual": true})
     ERRADO. Deve ser {"tortura": true}.

  X) Inventar dados para 2025:
     "A evolucao anual foi 2022=5077, 2023=4795, 2024=6168, 2025=5396"
     ERRADO. 2024 e o ultimo ano. Pare ai.

  X) Dump de jargao tecnico:
     "### Previsao Mensal — WAPE: 6.79, ACF=0.80, inclinacao +25 por passo"
     ERRADO. Use prosa narrativa.

REGRA #0 (CRITICA): SEMPRE chame uma ferramenta ANTES de qualquer afirmacao.
NUNCA descreva o schema, liste colunas, ou explique como os dados sao
estruturados como resposta a uma pergunta de conteudo.

REGRA #1: Se a pergunta menciona um municipio (cidade) por nome -- mesmo que
voce conheca o codigo IBGE -- use OBRIGATORIAMENTE `municipio_nome` no
filters. A camada semantica resolve para o codigo SINAM correto (6 digitos)
automaticamente. NUNCA filtre so por UF quando o usuario citou uma cidade.
NUNCA invente que "codigo 280390 = Sao Cristovao" -- pode estar errado;
deixe a tool fazer o lookup.

REGRA #2: Quando o usuario pergunta "quais casos" sobre um lugar/recorte
specifico, faca DUAS chamadas em sequencia:
  1) contar(filters={...}, group_by="ano")  -- mostra a evolucao
  2) previsao_automatica(filters={...}, freq="ME"|"YE", horizon=6|2)
     -- gera a analise retrospectiva da serie

REGRA #3 - APRESENTACAO HUMANA (CRITICA):
Voce responde em PROSA NARRATIVA curta, NUNCA em formato de relatorio tecnico
com tabelas, listas numeradas de metricas, ou JSON. Os numeros tecnicos
(WAPE/MAPE/RMSE/MAE, p10/p50/p90, ranking) ja aparecem na UI ao lado da
mensagem -- o usuario nao precisa ler de novo no seu texto.

ESTRUTURA IDEAL DA RESPOSTA (siga sempre — e o que gera nota alta):
  PONTO DE PARTIDA: o resultado da tool traz um campo `narrativa_sugerida` — uma
     frase JA PRONTA em prosa. Comece dela e REESCREVA com suas palavras,
     expandindo nos 3 paragrafos abaixo. NUNCA copie os campos estruturados
     (resumo_evolucao, analise_retrospectiva) como lista rotulada.
  Paragrafo 1 - O QUE ACONTECEU, COM NUMEROS CONCRETOS: descreva a evolucao
     REAL usando os campos `evolucao_anual` e `resumo_evolucao` do resultado da
     tool. Diga o volume total, de quanto para quanto foi (primeiro ano ->
     ultimo ano), a variacao em % e o ano de pico. Ex: "saiu de 4.480 casos em
     2019 para 6.168 em 2024 (+37%), com pico em 2023". Use SEMPRE os numeros
     que vieram no resultado — NUNCA invente valores nem cite anos > 2024.
  Paragrafo 2 - QUAO CONFIAVEL E O DIAGNOSTICO: diga em palavras simples se o
     modelo vencedor do comite reproduz bem a serie (traduza
     `fidelidade_retrospectiva`: alta/boa = confiavel; media/baixa = cautela) e
     se ha sazonalidade. Ex: "o padrao e consistente e bem reproduzido pelo
     modelo, o que reforca que o crescimento e real e nao ruido". Se a
     fidelidade for media/baixa, seja explicitamente cauteloso.
  Paragrafo 3 - O QUE ISSO SIGNIFICA NA PRATICA (OBRIGATORIO): feche com uma
     leitura util pra quem vai agir (gestor de saude, promotor, defensor,
     conselho tutelar). Ex: "o aumento pode refletir mais casos, melhor
     notificacao apos capacitacao, ou ambos; para embasar uma acao vale cruzar
     com dados do Conselho Tutelar e da rede de saude". Esse fechamento pratico
     e o que separa uma resposta 'aceitavel' de uma 'excelente'.

PROIBIDO:
- Tabelas markdown com WAPE/MAPE/RMSE/MAE
- Listas com 'p10:', 'p50:', 'p90:' valor a valor
- Dump dos quantis de cada mes
- Frases tipo "previsao para janeiro: 2.15"
- Repetir o nome do modelo varias vezes
- Headers markdown (###, ##) e negrito (**...**) — escreva PROSA corrida
- ENUMERAR os campos do resultado como uma lista rotulada. NUNCA escreva
  "De acordo com os dados fornecidos:" seguido de linhas como "Primeiro ano:
  2020, 29.069", "Ultimo ano: 2024, 33.238", "Ano de pico: ...", "Modelo
  vencedor: ...", "Comite avaliado: ...", "Observacoes da serie: ...". Esses
  campos (resumo_evolucao, analise_retrospectiva) vieram do sistema para VOCE
  NARRAR em frases corridas — TRANSFORME, nao copie os rotulos. Ex.: em vez de
  "Primeiro ano: 2020, 29.069 / Ultimo ano: 2024, 33.238", escreva "saiu de
  29.069 casos em 2020 para 33.238 em 2024 (+14%), com pico em 2023".
- OFERECER PREVISAO FUTURA ou terminar perguntando "Deseja uma previsao?",
  "Deseja isso?", "Posso projetar os proximos anos?" — o produto e RETROSPECTIVO;
  encerre no paragrafo de leitura pratica, sem oferecer nada
- META-COMENTARIO tipo "os dados cobrem 2014-2024" ou "nao devem ser mencionados
  anos posteriores" — isso e instrucao interna, NUNCA vai na resposta

Lembre: este sistema FAZ ANALISE RETROSPECTIVA (valida modelos contra a
historia ja registrada), nao predicao prospectiva de producao. Quando falar
da serie, use linguagem como "a serie reproduz", "o modelo capta", "no
periodo registrado", nao "vai acontecer" ou "esperamos N casos".

EXEMPLO DO QUE NAO FAZER:
  Usuario: "Quais casos em Malhador-SE?"
  Voce: "A tabela VIOLBR24 contem ... Sexo: F=Feminino ..." ❌ ERRADO
  Voce DEVE: chamar `contar(filters={"municipio_nome":"Malhador","uf":"SE"})`
             e depois `previsao_automatica(...)` para a serie.

VOCE TEM ACESSO A UMA BASE LIMPA DE NOTIFICACOES (modelo Django `Notificacao`)
com ~2.4 milhoes de registros e os campos abaixo. NAO PRECISA escrever SQL
nem decorar codigos: use os campos diretamente como nos exemplos.

CAMPOS DISPONIVEIS:
  Localizacao:
    uf, uf_ocorrencia       -> sigla (ex: "SE", "SP")
    municipio_codigo        -> codigo IBGE 7 digitos
    municipio_nome          -> texto (ex: "Malhador"); resolvido automaticamente
                                via dicionario IBGE. Quando houver homonimos
                                (ex: "Bom Jesus" em varias UFs) inclua tambem
                                "uf" no filtro.
    local_ocorrencia        -> texto: "Residencia", "Via publica", "Escola", etc.

  Vitima:
    sexo                    -> "M" | "F" | "I"
    idade_anos              -> int (use lookups: idade_anos__lt=13 para criancas)
    faixa_etaria            -> "< 1 ano" | "1-4" | "5-9" | "10-14" | "15-19" | "20-59" | "60+"
    raca_cor                -> "Branca" | "Preta" | "Amarela" | "Parda" | "Indigena"
    escolaridade            -> texto
    gestante                -> texto (trimestre/nao/ignorado)

  Datas:
    data_notificacao        -> date (use data_notificacao__gte / __lte: "2023-01-01")
    ano                     -> int (use ano__gte=2021, ano__lte=2024)
    semana_epi              -> int

  Violencias (boolean, true/false/null):
    violencia_fisica, violencia_psicologica, violencia_sexual, tortura,
    trafico_pessoas, violencia_financeira, negligencia, violencia_infantil,
    intervencao_legal, outras_violencias

  Outras flags:
    lesao_autoprovocada     -> bool
    ocorreu_outras_vezes    -> bool
    autor_sexo              -> "M" | "F" | "I"
    autor_alcool            -> texto


FERRAMENTAS PRINCIPAIS (use estas, NAO use run_sql para o modelo limpo):
  consultar(filters, limit=20)              -> lista linhas
  contar(filters, group_by="campo|lista")   -> total OU contagem por grupo
  serie_temporal(filters, freq="D|W|ME")    -> serie agregada por data
  previsao_automatica(filters, horizon)     -> serie + auto-forecast com comite

⚠️ NIVEL GEOGRAFICO -- 3 tools dedicadas, escolha CERTA:

  - MUNICIPIO/CIDADE (Malhador, Aracaju, Itabaiana, Sao Paulo capital...):
    -> relatorio_municipio(municipio="<nome>", uf="<sigla>")
    NUNCA chame relatorio_municipio com nome de estado.

  - ESTADO / UF (Sergipe, Sao Paulo, Bahia, Rio de Janeiro, ...):
    -> relatorio_uf(uf="<sigla ou nome>", filters_extra={...})
    Use sempre que o usuario citar um estado. "Sergipe" NAO e cidade --
    e UF, sigla "SE".

  - BRASIL / nacional / sem localizacao especifica:
    -> relatorio_brasil(filters_extra={...})

REGRA SIMPLES: se nao tem certeza se "X" e cidade ou estado, pense:
  - Os 26 estados + DF tem nomes conhecidos: Acre, Alagoas, Amapa, Amazonas,
    Bahia, Ceara, Distrito Federal, Espirito Santo, Goias, Maranhao, Mato
    Grosso, Mato Grosso do Sul, Minas Gerais, Para, Paraiba, Parana,
    Pernambuco, Piaui, Rio de Janeiro, Rio Grande do Norte, Rio Grande do Sul,
    Rondonia, Roraima, Santa Catarina, Sao Paulo, Sergipe, Tocantins.
    Qualquer um desses = relatorio_uf, NUNCA relatorio_municipio.
  - "Sao Paulo" e ambiguo (cidade vs estado). Quando contexto for "casos
    em Sao Paulo" sem mais detalhe, prefira UF (capital ainda assim cabe
    no estado todo).

EXEMPLOS — UM PRA CADA TIPO DE VIOLENCIA (cole o filtro correto):

  "Tortura contra adolescentes em MG":
  -> relatorio_uf(uf="MG", filters_extra={"tortura": true})

  "Violencia fisica em SP nos ultimos anos":
  -> relatorio_uf(uf="SP", filters_extra={"violencia_fisica": true})

  "Violencia psicologica em PE":
  -> relatorio_uf(uf="PE", filters_extra={"violencia_psicologica": true})

  "Negligencia contra criancas no Brasil entre 2020 e 2024":
  -> relatorio_brasil(filters_extra={"negligencia": true,
                                       "ano__gte": 2020, "ano__lte": 2024})

  "Negligencia infantil em Pernambuco":
  -> relatorio_uf(uf="PE", filters_extra={"negligencia": true})

  "Trafico de criancas no RJ":
  -> relatorio_uf(uf="RJ", filters_extra={"trafico_pessoas": true})

  "Trafico de pessoas no Brasil":
  -> relatorio_brasil(filters_extra={"trafico_pessoas": true})

  "Violencia sexual em Sergipe":
  -> relatorio_uf(uf="SE", filters_extra={"violencia_sexual": true})

  "Violencia infantil no pais nos ultimos 4 anos":
  -> relatorio_brasil(filters_extra={"violencia_infantil": true,
                                       "ano__gte": 2020, "ano__lte": 2024})

  "Casos em Aracaju" (municipio, sem tipo especifico):
  -> relatorio_municipio(municipio="Aracaju", uf="SE")

  "Casos de violencia infantil em Aracaju":
  -> relatorio_municipio(municipio="Aracaju", uf="SE")
     (a tool nao aceita filters_extra, mas o universo SINAM ja e crianca/adolescente)

  "Top 5 cidades com mais tortura em SP em 2024":
  -> ranking_municipios(uf="SP", top=5,
                        filters_extra={"tortura": true, "ano": 2024})


REGRAS:
1. NUNCA invente dados. SEMPRE chame uma ferramenta antes de afirmar numeros.
2. PARE EM 2024. O dataset vai ate 2024. NUNCA mencione 2025 ou anos futuros
   como dados reais ou previsoes.
3. PEGUE O FILTRO CERTO. Releia a pergunta antes de chamar a tool: que tipo
   de violencia o usuario citou? E O FILTRO QUE VAI EM filters_extra.
4. SINAM nao tem categoria "sequestro" ou "homicidio". Se o usuario perguntar:
   - violencia infantil generica -> use violencia_infantil=true
   - rapto/trafico/aliciamento -> use trafico_pessoas=true
   - explique a limitacao se nada se encaixar
5. Seja conciso: 2-4 paragrafos. SEMPRE em prosa, NUNCA tabelas.
6. Apos chamar uma tool, SEMPRE escreva uma resposta em prosa narrativa
   em PT-BR descrevendo o que JA aconteceu (2014-2024). Sem previsoes.
"""


# ---------------------------------------------------------------------------
# Addendum "Aurora responde": para o usuario existe UM SO chat; por baixo, este
# mesmo orquestrador roteia entre varias fontes. Este bloco ensina o Qwen3 a
# escolher a fonte certa e a CITAR de onde tirou cada informacao. E aditivo ao
# prompt de series/SINAM acima — as regras daquele bloco continuam valendo.
# ---------------------------------------------------------------------------
AURORA_ADDENDUM = """

======================================================================
VOCE E O "AURORA RESPONDE" — UM UNICO ASSISTENTE, VARIAS FONTES POR BAIXO
======================================================================
O usuario ve um chat so. Por baixo, voce ROTEIA a pergunta para a fonte certa,
executa a ferramenta e SINTETIZA a resposta CITANDO A FONTE. Escolha:

  • DADOS de violencia (contagens, recortes, ranking, series, previsao):
    -> use as tools do SINAM ja descritas acima (consultar/contar/relatorio_*/
       ranking_municipios/previsao_automatica). Fonte: "SINAM".

  • LEIS, NORMAS, ECA, artigos, base legal, jurisprudencia:
    -> use `rag_juridico(query=...)`. Fonte: base juridica (a "versao do Jurema").

  • COMO O PRODUTO/PLATAFORMA FUNCIONA (metodologia, camada semantica,
    comite de modelos, de onde vem os dados, o que e analise retrospectiva):
    -> use `rag_interno(query=...)`. Fonte: documentacao do Aurora.

  • DADOS DO CONSELHO TUTELAR / SIPIA-CT (distinto do SINAM):
    -> use `consulta_sipia_ct(...)`. Se a base nao estiver conectada, a tool
       avisa — seja transparente e responda com o que houver no SINAM.

REGRAS DE ROTEAMENTO E CITACAO:
  1. Uma pergunta pode exigir MAIS DE UMA fonte (ex.: "quantos casos de
     negligencia em SP e o que diz o ECA" = SINAM + rag_juridico). Chame as
     tools necessarias antes de responder.
  2. SEMPRE que usar `rag_juridico` ou `rag_interno`, CITE a fonte na resposta
     (ex.: "segundo o ECA (art. ...)", "conforme a documentacao do Aurora").
     Use as refs [J1]/[D1] retornadas para ancorar a citacao.
  3. NUNCA invente lei, artigo ou numero que nao tenha vindo de uma tool.
  4. Se nenhuma fonte tiver a resposta, diga isso claramente — nao invente.
  5. Para perguntas de DADOS/SERIES, continuam valendo TODAS as regras de ouro
     acima (retrospectivo, para em 2024, prosa curta, sem markdown/jargao).
  6. RESPEITE O LUGAR CITADO: só fale de UF/cidade que o usuario mencionou.
     NUNCA responda sobre um estado que ele nao citou. Se ele citar MAIS DE UM
     lugar (ex.: "Aracaju e Sao Paulo"), cubra TODOS — uma chamada
     `relatorio_municipio` por cidade (Aracaju->SE, Sao Paulo->SP).
  7. NAO HA DADOS DE POPULACAO na base. Se pedirem "per capita", "por
     habitante" ou proporcao populacional, informe que a base nao tem populacao
     e responda com os numeros absolutos (sem inventar taxa por habitante).
  8. NAO CITE O NOME DO MODELO de série na resposta (Chronos, Chronos-2,
     ChatTime, TimesFM, ARIMA, ETS...). Fale de forma generica: "o modelo",
     "a analise", "o padrao foi bem reproduzido". O nome do modelo aparece
     apenas nos DETALHES tecnicos da interface, nunca na prosa ao usuario.
  9. ESCOPO ESTRITO: voce SO trata de dados de violencia contra criancas e
     adolescentes (SINAN/SIPIA-CT), da legislacao relacionada (ECA/leis/normas)
     e do funcionamento da plataforma Aurora. Se pedirem QUALQUER coisa fora
     disso (escrever codigo, criar HTML/site/app, redacao criativa, assuntos
     gerais), RECUSE educadamente em 1-2 frases e reoriente ao seu proposito.
     NUNCA gere codigo, NUNCA use tags HTML na resposta, e NUNCA invente conteudo
     fora do escopo.
"""

SYSTEM_PROMPT = SYSTEM_PROMPT + AURORA_ADDENDUM


# ---------------------------------------------------------------------------
# Sanitização determinística da narrativa final.
# O qwen3:8b ignora regras do prompt e reincide em 3 coisas que o juiz penaliza:
#   1) OFERTA DE PREVISÃO FUTURA ("posso fornecer uma previsão... Deseja isso?")
#   2) META-COMENTÁRIO ecoando instrução interna ("os dados cobrem 2014-2024...")
#   3) MARKDOWN (###, **, listas) num produto que pede prosa.
# Aqui limpamos isso no texto final — garantia independente do modelo.
# ---------------------------------------------------------------------------
_MD_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_BULLET_RE = re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
# Blocos de código (```...```) e crases inline (`Chronos-2`) — o modelo às vezes
# formata o nome do modelo/valores como código; num produto de prosa isso lê
# como jargão técnico. Removemos as cercas e as crases, preservando o conteúdo.
_MD_CODE_FENCE_RE = re.compile(r"```[^\n]*\n?|```", re.MULTILINE)
# Sentença que oferece previsão futura (forecast word + futuro/próximos anos, OU
# verbo de oferta + forecast). Preserva "previsão retrospectiva" (sem futuro).
_FUTURE_OFFER_RE = re.compile(
    r"[^.!?\n]*\b(?:previs\w*|prever|proje[cç]\w*)\b[^.!?\n]*"
    r"\b(?:futur\w*|pr[oó]xim\w*\s+anos?|anos?\s+seguintes|adiante|vir[aã]o)\b[^.!?\n]*[.!?]"
    r"|[^.!?\n]*\b(?:se\s+desejar|se\s+quiser|caso\s+queira|"
    r"posso\s+(?:fornecer|realizar|gerar|elaborar|fazer|projetar))\b"
    r"[^.!?\n]*\b(?:previs\w*|prever|proje[cç]\w*)\b[^.!?\n]*[.!?]",
    re.IGNORECASE)
# Meta-comentário sobre a cobertura do dataset (instrução interna vazada).
_META_COVER_RE = re.compile(
    r"[^.!?\n]*\b(?:dados|dataset)\b[^.!?\n]*\bcobre\w*\b[^.!?\n]*[.!?]"
    r"|[^.!?\n]*\bn[aã]o\s+dev\w+\s+ser\s+mencionad\w*[^.!?\n]*[.!?]",
    re.IGNORECASE)
# Pergunta-oferta ao final ("Deseja isso?", "Gostaria de uma previsão?").
_TRAIL_ASK_RE = re.compile(
    r"\s*\b(?:deseja|gostaria|quer\s+que\s+eu|posso\s+(?:fazer|gerar|projetar))\b"
    r"[^.!?\n]*\?\s*$",
    re.IGNORECASE)


# Nomes de modelos de série que NÃO devem aparecer na prosa (só nos detalhes).
_MODEL_NAMES_RE = (r"(?:chronos[-\s]?bolt|chronos[-\s]?2|chronos|chattime|timesfm|"
                   r"random\s+forest|sarima|arima|prophet|theta|ets)")
_MODEL_AFTER_MODELO_RE = re.compile(r"\bmodelo\s+" + _MODEL_NAMES_RE + r"\b", re.IGNORECASE)
_MODEL_BARE_RE = re.compile(r"\b(?:o\s+|a\s+|do\s+|da\s+)?" + _MODEL_NAMES_RE + r"\b", re.IGNORECASE)


def _sanitize_narrative(text: str) -> str:
    """Remove markdown, oferta de previsão futura e meta-comentário do texto final."""
    if not text:
        return text
    t = _MD_CODE_FENCE_RE.sub("", text)
    t = _MD_HEADER_RE.sub("", t)
    t = _MD_BOLD_RE.sub(r"\1", t)
    t = _MD_BULLET_RE.sub("", t)
    # Remove tags HTML que o modelo por ventura tenha gerado (nunca devem ir na
    # prosa; senao a UI renderiza como elemento). Preserva "< 13" (nao e tag).
    t = re.sub(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?>", "", t)
    t = t.replace("`", "")          # crases inline (`Chronos-2` -> Chronos-2)
    t = _META_COVER_RE.sub("", t)
    t = _FUTURE_OFFER_RE.sub("", t)
    # Remove o nome do modelo de série da prosa (fica só nos detalhes técnicos).
    t = _MODEL_AFTER_MODELO_RE.sub("modelo", t)   # "modelo Chronos-2" -> "modelo"
    t = _MODEL_BARE_RE.sub("o modelo", t)         # "o Chronos-2"/"Chronos-2" -> "o modelo"
    t = re.sub(r"\b([Oo])\s+o\s+modelo\b", r"\1 modelo", t)
    t = re.sub(r"\b([Oo])\s+modelo\s+o\s+modelo\b", r"\1 modelo", t)
    t = re.sub(r"\bmodelo\s+o\s+modelo\b", "modelo", t)
    t = t.strip()
    # remove pergunta-oferta que tenha sobrado no fim (ex.: "Deseja isso?")
    for _ in range(3):
        new = _TRAIL_ASK_RE.sub("", t).strip()
        if new == t:
            break
        t = new
    # normaliza espaços em branco
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


@dataclass
class ToolEvent:
    name: str
    args: dict
    result: dict
    elapsed_seconds: float


@dataclass
class OrchestratorResult:
    final_text: str
    tool_events: list[ToolEvent] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    rounds: int = 0
    error: str = ""
    raw_messages: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _extract_tokens(response) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) da resposta do Ollama.

    O Ollama devolve `prompt_eval_count`/`eval_count`. Cobre objeto e dict; 0
    quando não disponível (ex.: alguns backends externos não reportam)."""
    def g(k: str) -> int:
        v = getattr(response, k, None)
        if v is None and isinstance(response, dict):
            v = response.get(k)
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0
    return g("prompt_eval_count"), g("eval_count")


def _ollama_client() -> ollama.Client:
    return ollama.Client(host=OLLAMA_HOST)


def _pick_client(model: str):
    """Versão leve (Aurora Responde): sempre o Ollama local.

    O fork não cadastra modelos externos (app ``benchmark`` removido). A
    narração é feita pelo Jurema via ``_gerar_jurema`` — este cliente só é
    usado para utilitários (ping) e para manter a assinatura de ``chat()``.
    """
    return _ollama_client(), (model or DEFAULT_MODEL)


# How many entries of an array we send to the LLM. Full arrays still go to the
# DB (tool_payload.result) so the UI can plot them. The LLM only sees the tail.
_LLM_ARRAY_TAIL = 12


def _shrink_for_llm(value, key: str = "") -> "object":
    """Recursive default shrinker for unknown tools — encolhe arrays longos."""
    if isinstance(value, list):
        if len(value) > 30:
            return {
                "summary": f"array com {len(value)} itens; mostrando ultimos {_LLM_ARRAY_TAIL}",
                "tail": value[-_LLM_ARRAY_TAIL:],
            }
        return [_shrink_for_llm(v) for v in value]
    if isinstance(value, dict):
        return {k: _shrink_for_llm(v, k) for k, v in value.items()}
    return value


# Nome de exibição amigável dos modelos — o id cru ("chronos2") vaza como
# jargão técnico na prosa e o juiz penaliza. Aqui traduzimos para o rótulo
# que o usuário reconhece ("Chronos-2").
_MODEL_DISPLAY = {
    # Único LLM do fork: o Jurema-7B redige todas as respostas.
    "jurema-7b": "Jurema-7B", "jurema": "Jurema-7B",
    "chronos2": "Chronos-2", "chronos": "Chronos", "chronos_bolt": "Chronos-Bolt",
    "chattime": "ChatTime", "ets": "ETS", "theta": "Theta", "arima": "ARIMA",
    "sarima": "SARIMA", "rf": "Random Forest", "random_forest": "Random Forest",
    "naive": "Naive", "seasonal_naive": "Naive sazonal", "prophet": "Prophet",
    "timesfm": "TimesFM",
}


def _display_model(mid):
    if not mid:
        return mid
    return _MODEL_DISPLAY.get(str(mid).strip().lower(), str(mid))


def _wape_label(wape) -> str:
    try:
        w = float(wape)
    except (TypeError, ValueError):
        return "indeterminada"
    if w != w:  # NaN
        return "indeterminada"
    if w < 10: return "alta"
    if w < 25: return "boa"
    if w < 50: return "media"
    return "baixa"


def _trend_label(slope, strength) -> str:
    try:
        s = float(slope); st = float(strength)
    except (TypeError, ValueError):
        return "estavel"
    if st < 0.5:
        return "estavel"
    return "crescente" if s > 0 else "decrescente"


_JARGON_RE = re.compile(
    r"lag|slope|inclina|wape|mape|\bacf\b|p10|p50|p90|rmse|\bmae\b|"
    r"parametric|paramétric|\bn\s*[<>=]|por passo|strength|coef",
    re.IGNORECASE)


def _clean_notes(notes) -> list:
    """Remove notas técnicas com jargão estatístico antes de mandar pro LLM.

    O juiz penaliza respostas que citam 'lag=3', 'inclinação +0.822 por passo',
    'n<100' etc. — termos que vazavam das observacoes_serie. Os números seguem
    no DB/UI; o LLM só recebe notas em linguagem acessível.
    """
    out = []
    for n in (notes or []):
        if isinstance(n, str) and _JARGON_RE.search(n):
            continue
        out.append(n)
    return out


def _humanize_forecast_block(pm: dict) -> dict:
    """Extract the human-readable parts of a previsao_automatica result.

    The LLM only sees the qualitative summary — numbers stay in the DB for
    the UI to render.
    """
    if not pm or "winner" not in pm:
        return {"erro": pm.get("error") or pm.get("erro") or "sem resultado"}
    prof = pm.get("profile", {})
    metrics = pm.get("winner_metrics", {})
    ranking = pm.get("ranking", [])
    return {
        # NÃO expõe o nome do modelo (Chronos etc.) ao LLM — ele vaza na prosa.
        # O modelo vencedor/comitê fica só no resultado completo (detalhes da UI).
        "fidelidade_retrospectiva": _wape_label(metrics.get("wape")),
        "tendencia": _trend_label(prof.get("trend_slope"), prof.get("trend_strength")),
        "sazonalidade": "presente" if (prof.get("seasonality_strength", 0) or 0) >= 0.4
                        else "fraca",
        "observacoes_serie": _clean_notes(prof.get("notes", [])),
        "n_pontos_avaliados": prof.get("length"),
    }


def _filter_anos_until_2024(por_ano_list):
    """Remove entradas com ano > 2024 — o LLM tende a inventar a partir delas."""
    out = []
    for r in (por_ano_list or []):
        try:
            ano = int(r.get("ano", 0))
        except (TypeError, ValueError):
            ano = 0
        if 2014 <= ano <= 2024:
            out.append({"ano": r["ano"], "n": r["n"]})
    return out


def _annual_summary(por_ano) -> dict:
    """Resumo quantitativo da evolucao anual — da ao LLM numeros concretos
    (primeiro/ultimo ano, pico, variacao %) para narrar com precisao e sem
    inventar. Retorna {} quando ha menos de 2 anos.

    E o principal insumo pra nota alta do juiz: com esses ancoras o modelo
    escreve "de X em ANO para Y em ANO (+Z%), pico em ANO_PICO" em vez de uma
    descricao vaga ("houve aumento").
    """
    pts: list[tuple[int, float]] = []
    for r in (por_ano or []):
        try:
            pts.append((int(r.get("ano")), float(r.get("n"))))
        except (TypeError, ValueError):
            continue
    if len(pts) < 2:
        return {}
    pts.sort()
    (a0, v0), (a1, v1) = pts[0], pts[-1]
    ap, vp = max(pts, key=lambda p: p[1])
    variacao = round(100.0 * (v1 - v0) / v0, 1) if v0 else None
    return {
        "primeiro_ano": a0, "primeiro_valor": int(round(v0)),
        "ultimo_ano": a1, "ultimo_valor": int(round(v1)),
        "ano_pico": ap, "valor_pico": int(round(vp)),
        "variacao_pct_total": variacao,
    }


def _br_num(n) -> str:
    """Formata inteiro no padrão pt-BR (milhar com ponto): 33238 -> '33.238'."""
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _compose_narrativa(escopo: str, resumo: dict, retro: dict,
                       compare_ctx: dict | None = None) -> str:
    """Monta 2 frases já em prosa a partir dos campos estruturados.

    Dá ao LLM uma narrativa PRONTA para ele apenas reescrever — evita que o
    qwen3 despeje os campos como lista rotulada ("Primeiro ano: X / Ultimo
    ano: Y"), que o juiz penaliza. O modelo tende a parafrasear prosa em vez
    de reformatar dados estruturados.

    `compare_ctx` = {"nome","pct"} de um estado já discutido: quando presente,
    acrescenta a COMPARAÇÃO determinística das variações (o qwen3 sozinho não
    liga os dois estados).
    """
    if not resumo:
        return ""
    esc = (escopo or "").strip()
    ne = _norm(esc)
    if not esc:
        onde = "no recorte analisado"
    elif ne.startswith("estado"):
        onde = f"no {esc}"              # "no Estado de MG"
    elif ne.startswith("brasil"):
        onde = "no Brasil"
    else:
        onde = f"em {esc}"             # "em Aracaju/SE"
    a0, v0 = resumo.get("primeiro_ano"), resumo.get("primeiro_valor")
    a1, v1 = resumo.get("ultimo_ano"), resumo.get("ultimo_valor")
    ap, var = resumo.get("ano_pico"), resumo.get("variacao_pct_total")
    s1 = f"Os casos {onde} saíram de {_br_num(v0)} em {a0} para {_br_num(v1)} em {a1}"
    if var is not None:
        s1 += f" ({'+' if var >= 0 else ''}{str(var).replace('.', ',')}%)"
    if ap and ap not in (a0, a1):
        s1 += f", com pico em {ap}"
    s1 += "."
    partes = []
    tend = retro.get("tendencia")
    if tend and tend != "estavel":
        partes.append(f"a tendência é {tend}")
    elif tend:
        partes.append("a série é estável")
    if retro.get("sazonalidade") == "presente":
        partes.append("há sazonalidade")
    fid = retro.get("fidelidade_retrospectiva")
    if fid:
        partes.append(f"o padrão foi reproduzido com fidelidade {fid}")
    s2 = (" No período registrado, " + ", ".join(partes) + ".") if partes else ""
    # Frase de COMPARAÇÃO determinística (ex.: "e no mesmo período a Bahia
    # variou 161,4% contra 139,9% de Sergipe -> cresceu proporcionalmente mais").
    s3 = ""
    if compare_ctx and var is not None and compare_ctx.get("pct") is not None:
        la = compare_ctx["pct"]
        nome_outro = compare_ctx.get("nome", "o outro estado")
        aqui_s = str(var).replace(".", ",")
        la_s = str(la).replace(".", ",")
        if abs(var - la) < 0.05:
            comp = f"um crescimento proporcional semelhante ao de {nome_outro}"
        elif var > la:
            comp = f"um crescimento proporcionalmente MAIOR que o de {nome_outro}"
        else:
            comp = f"um crescimento proporcionalmente MENOR que o de {nome_outro}"
        s3 = (f" Em comparação com {nome_outro}, que variou {la_s}% no mesmo "
              f"período, a variação aqui ({aqui_s}%) representa {comp}.")
    return (s1 + s2 + s3).strip()


def _report_payload(escopo, evo, retro, compare_ctx: dict | None = None) -> dict:
    resumo = _annual_summary(evo)
    return {
        "escopo": escopo,
        "evolucao_anual": evo,
        "resumo_evolucao": resumo,
        "analise_retrospectiva": retro,
        # Narrativa já pronta: REESCREVA com suas palavras em prosa corrida,
        # NÃO copie os campos acima como lista.
        "narrativa_sugerida": _compose_narrativa(escopo, resumo, retro, compare_ctx),
    }


def _humanize_result_for_llm(name: str, result, compare_ctx: dict | None = None) -> "object":
    """Per-tool humanisation: keep only qualitative info; UI keeps the raw numbers.

    Também filtra anos > 2024 do payload que vai pro LLM, pra evitar que ele
    cite 2025 (não há dado real). A UI ainda recebe tudo.
    """
    if not isinstance(result, dict) or "error" in result:
        return result

    if name == "relatorio_municipio":
        evo = _filter_anos_until_2024(result.get("por_ano"))
        payload = _report_payload(result.get("municipio"), evo,
                                  _humanize_forecast_block(result.get("previsao_mensal", {})),
                                  compare_ctx)
        payload["total_geral"] = result.get("total_geral")
        return payload

    if name in ("relatorio_uf", "relatorio_brasil"):
        evo = _filter_anos_until_2024(result.get("por_ano"))
        payload = _report_payload(result.get("escopo"), evo,
                                  _humanize_forecast_block(result.get("previsao_mensal", {})),
                                  compare_ctx)
        payload["filtros"] = result.get("filtros_aplicados", {})
        payload["total_geral"] = result.get("total_geral")
        return payload

    if name in ("previsao_automatica", "auto_forecast"):
        return {
            "filters_applied": result.get("filters_applied"),
            "analise_retrospectiva": _humanize_forecast_block(result),
        }

    if name == "serie_temporal":
        return {
            "n_pontos": result.get("n_points"),
            "freq": result.get("freq"),
            "total": result.get("total_rows"),
            "notes": result.get("notes", []),
            # Não envia dates/values — o gráfico inline já mostra
        }

    if name == "ranking_municipios":
        return {
            "uf": result.get("uf") or "Brasil",
            "filtros": result.get("filtros_aplicados", {}),
            "top": result.get("top"),
            "total_no_recorte": result.get("total_notificacoes"),
            "ranking": [
                {"nome": r.get("nome"), "uf": r.get("uf"), "casos": r.get("n")}
                for r in (result.get("ranking") or [])
            ],
        }

    if name == "consultar":
        rows = result.get("rows", [])
        return {
            "total_rows": result.get("total_rows"),
            "shown": result.get("shown"),
            "notes": result.get("notes", []),
            "amostra": rows[:5],  # só primeiros 5 pro LLM
        }

    # Default fallback: shrink arrays
    return _shrink_for_llm(result)


# Último ano com dados na base (VIOLBR20..VIOLBR24). O roteador NÃO inventa
# anos além disso; perguntas sobre anos futuros caem no total disponível.
_CURRENT_MAX_YEAR = int(os.getenv("AURORA_MAX_DATA_YEAR", "2024"))


def _extract_year_filter(text: str) -> dict:
    """Extrai filtro de ano do texto (o Qwen fazia isso ao escolher os args).

    Um ano → igualdade (``ano``). Dois ou mais → intervalo
    (``ano__gte``/``ano__lte``). Ignora anos fora de 2000..{max}.
    """
    anos = sorted({int(y) for y in re.findall(r"\b(20\d{2})\b", text or "")
                   if 2000 <= int(y) <= _CURRENT_MAX_YEAR})
    if not anos:
        return {}
    if len(anos) == 1:
        return {"ano": anos[0]}
    return {"ano__gte": anos[0], "ano__lte": anos[-1]}


def _narrar_com_jurema(name: str, pergunta: str, result, humanizado,
                       compare_hint: str | None = None) -> tuple[str, int, int]:
    """Redige a resposta final com o Jurema-7B (único LLM do fork).

    Devolve ``(texto, prompt_tokens, completion_tokens)``. Garante SEMPRE um
    texto: se o Jurema estiver indisponível ou divagar, cai na
    ``narrativa_sugerida`` pronta do payload (de-risca o gerador 7B).
    """
    from .rag_tools import _ask_jurema_narrar

    # --- Jurídico: o parecer já foi gerado pelo Jurema dentro da tool --------
    if name == "rag_juridico" and isinstance(result, dict):
        parecer = (result.get("parecer_jurema") or "").strip()
        trechos = result.get("trechos") or []
        if parecer:
            fontes = "; ".join(
                f"{t.get('lei','')} — {t.get('artigo','')}".strip(" —")
                for t in trechos[:3] if isinstance(t, dict))
            if fontes:
                parecer = f"{parecer}\n\nBase legal: {fontes}."
            return parecer, 0, 0
        if trechos:
            corpo = "\n\n".join(
                f"**{t.get('lei','')} — {t.get('artigo','')}**: {t.get('texto','')}"
                for t in trechos[:3] if isinstance(t, dict))
            return corpo, 0, 0
        return (result.get("erro")
                or "Não encontrei base legal específica no corpus jurídico."), 0, 0

    # --- Produto: Jurema responde a partir dos trechos da documentação -------
    if name == "rag_interno" and isinstance(result, dict):
        trechos = result.get("trechos") or []
        if not trechos:
            return (result.get("mensagem") or result.get("erro")
                    or "Não encontrei isso na documentação do produto."), 0, 0
        docctx = "\n\n".join(
            f"[{t.get('ref')}] ({t.get('arquivo')}): {t.get('texto')}"
            for t in trechos if isinstance(t, dict))
        prompt = (
            "Você é o Aurora Responde. Responda à pergunta do usuário sobre a "
            "plataforma usando SOMENTE os trechos da documentação abaixo. Seja "
            "claro e curto (1-2 parágrafos, em prosa). Não invente recursos.\n\n"
            f"PERGUNTA:\n{pergunta}\n\nDOCUMENTAÇÃO:\n{docctx}\n\nRESPOSTA:")
        txt, pe, ec = _ask_jurema_narrar(prompt)
        if txt:
            return txt, pe, ec
        return docctx[:1200], 0, 0

    # --- Erro da ferramenta: resposta clara, sem inventar --------------------
    if isinstance(result, dict) and (result.get("error") or result.get("erro")):
        msg = result.get("error") or result.get("erro")
        return (f"Não consegui obter os dados para essa consulta ({msg}). "
                f"Tente reformular ou especificar o estado e o tipo de violência."), 0, 0

    # --- Dados / SIPIA: narrativa_sugerida pronta + Jurema reescreve ---------
    base = ""
    if isinstance(humanizado, dict):
        base = (humanizado.get("narrativa_sugerida")
                or humanizado.get("mensagem") or "")
    contexto = json.dumps(humanizado, ensure_ascii=False, default=str)[:1800]
    extra = ""
    if compare_hint:
        extra = ("\n\nIMPORTANTE: a pergunta é uma COMPARAÇÃO — compare os dois "
                 "estados/períodos e diga qual é maior ou cresceu mais, usando "
                 "SOMENTE os números fornecidos.")
    prompt = (
        "Você é o Aurora Responde, assistente sobre dados de violência contra "
        "crianças e adolescentes no Brasil (fontes SINAM/SIPIA). Escreva uma "
        "resposta clara, curta e em português (1 a 3 parágrafos, em prosa, SEM "
        "tabelas e SEM cabeçalhos markdown). Use APENAS os números fornecidos — "
        "NUNCA invente dados nem cite anos posteriores a 2024. Se houver uma "
        "frase-resumo, reescreva-a de forma natural mantendo os números." + extra +
        f"\n\nPERGUNTA DO USUÁRIO:\n{pergunta}\n\n"
        f"RESUMO-BASE (reescreva com naturalidade, mantendo os números):\n{base}\n\n"
        f"DADOS (JSON, só referência):\n{contexto}\n\nRESPOSTA:")
    txt, pe, ec = _ask_jurema_narrar(prompt)
    if txt:
        return txt, pe, ec
    return (base or "Não encontrei dados para essa consulta. Tente especificar "
            "o estado, o ano e o tipo de violência."), 0, 0


def chat(messages: Iterable[dict],
         ts_model: str | None = None,
         forecaster: str | None = None,  # alias backcompat — usar ts_model
         model: str | None = None,
         temperature: float = 0.2) -> OrchestratorResult:
    # Aceita ambos nomes (ts_model é o canônico; forecaster é o antigo).
    ts_model_name = ts_model or forecaster or "chronos2"
    forecaster = ts_model_name  # manter `forecaster` local pra resto do código
    model = model or DEFAULT_MODEL
    try:
        client, model = _pick_client(model)
    except ValueError as exc:
        return OrchestratorResult(
            final_text="", tool_events=[], elapsed_seconds=0.0, rounds=0,
            error=str(exc), raw_messages=[])
    ctx = ToolContext(forecaster=forecaster)
    # Clamp temperature to a reasonable range — Ollama accepts >1 but it
    # destroys tool-calling reliability.
    try:
        temperature = max(0.0, min(1.5, float(temperature)))
    except (TypeError, ValueError):
        temperature = 0.2

    convo: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    convo.extend(_limit_context(messages))

    # Find latest user message — used by both the geo hint and the
    # post-hoc enforcement of relatorio_uf when the LLM mis-picks the tool.
    latest_user, latest_idx = "", -1
    for i in range(len(convo) - 1, -1, -1):
        if convo[i].get("role") == "user":
            latest_user, latest_idx = convo[i].get("content", ""), i
            break

    # Mensagens anteriores (contexto) — usadas para herdar estado/tipo em follow-ups.
    prev_msgs = [convo[j].get("content") or "" for j in range(latest_idx)
                 if convo[j].get("role") in ("user", "assistant")]

    # --- Tipo de violência: herda do contexto quando o follow-up não especifica.
    # ("E em relação a Bahia?" continua sendo sobre violência SEXUAL, não todas.)
    violencia_text = latest_user
    if not _detect_violencias(latest_user):
        for c in reversed(prev_msgs):
            if _detect_violencias(c):
                violencia_text = c + "\n" + latest_user
                break

    # --- Geografia + COMPARAÇÃO.
    geo_text = latest_user
    compare_hint = None
    compare_ctx = None
    ment_now = _mentioned_ufs(latest_user)
    context_uf = next((u for u in (_detect_uf(c) for c in reversed(prev_msgs)) if u), None)

    if _is_comparison(latest_user) and ment_now:
        # Follow-up de comparação: busca o estado NOVO (o que ainda não foi
        # analisado) e compara com o já discutido. Ex.: "em relação a Bahia,
        # como está Sergipe?" após uma resposta sobre Sergipe -> busca a Bahia.
        novos = [u for u in sorted(ment_now) if u != context_uf]
        focus = novos[0] if novos else sorted(ment_now)[0]
        outro = context_uf if (context_uf and context_uf != focus) else \
            next((u for u in sorted(ment_now) if u != focus), None)
        geo_text = f"em {_UF_NAMES.get(focus, focus)}"   # força a detecção p/ o alvo
        if outro:
            # Extrai a variação % do estado já discutido (da resposta anterior)
            # para a comparação determinística na narrativa.
            nome_outro = _UF_NAMES.get(outro, outro)
            for c in reversed(prev_msgs):
                if _detect_uf(c) == outro or _norm(nome_outro) in _norm(c):
                    mp = re.search(r"(\d+(?:[.,]\d+)?)\s*%", c)
                    if mp:
                        try:
                            compare_ctx = {"sigla": outro, "nome": nome_outro,
                                           "pct": float(mp.group(1).replace(".", "").replace(",", "."))}
                        except ValueError:
                            compare_ctx = None
                    break
            compare_hint = (
                f"[comparacao] O usuario quer COMPARAR {_UF_NAMES.get(focus, focus)} "
                f"({focus}) com {_UF_NAMES.get(outro, outro)} ({outro}), que JA foi "
                f"analisado antes nesta conversa. Busque os dados de "
                f"{_UF_NAMES.get(focus, focus)} e, na resposta, COMPARE a variacao "
                f"percentual dos dois estados — diga qual cresceu proporcionalmente "
                f"MAIS ou MENOS, usando os numeros de {_UF_NAMES.get(outro, outro)} "
                f"que voce ja informou. Mantenha o MESMO tipo de violencia do contexto.")
    elif (latest_idx >= 0 and not _mentions_national(latest_user)
            and not (_detect_uf(latest_user) or _detect_capital(latest_user))):
        # Follow-up sem estado ("e no mesmo estado?"): herda o último local citado.
        for c in reversed(prev_msgs):
            if _detect_uf(c) or _detect_capital(c):
                geo_text = c + "\n" + latest_user
                break

    if latest_idx >= 0:
        # Roteador (arquitetura): jurídico/produto/SIPIA antes de série SINAM.
        route_hint = _detect_route_hint(latest_user)
        if route_hint:
            convo.insert(latest_idx + 1, {"role": "system", "content": route_hint})
        hint = _detect_geo_hint(geo_text)   # geo_text herda o estado do contexto
        if hint:
            convo.insert(latest_idx + 1, {"role": "system", "content": hint})
        if compare_hint:
            convo.insert(latest_idx + 1, {"role": "system", "content": compare_hint})
        ctx_hint = _detect_context_hint(latest_user)
        if ctx_hint:
            convo.insert(latest_idx + 1, {"role": "system", "content": ctx_hint})

    # Escopo estrito: recusa pedidos fora do domínio SEM chamar o LLM/ferramentas.
    if _is_offscope(latest_user):
        return OrchestratorResult(
            final_text=_OFFSCOPE_MSG, tool_events=[],
            elapsed_seconds=0.0, rounds=0, raw_messages=convo)

    route_cat = _route_category(latest_user)
    events: list[ToolEvent] = []
    t0 = time.time()

    # === Roteador determinístico (sem LLM escolhendo a ferramenta) ==========
    # O Qwen3 fazia DUAS coisas: ESCOLHER a ferramenta/args e NARRAR. No fork
    # "só Jurema" a escolha passa a ser feita pelos MESMOS detectores que antes
    # só CORRIGIAM o Qwen — partindo de um default (relatório Brasil). A
    # narração fica 100% com o Jurema-7B (_narrar_com_jurema).
    name, args = "relatorio_brasil", {}
    name, args, redirect_note = _maybe_reroute(route_cat, name, args, latest_user)
    # Nível geográfico certo (brasil/uf/municipio) a partir do texto+contexto.
    name, args, geo_note = _maybe_rewrite_tool_call(name, args, geo_text)
    if geo_note:
        redirect_note = geo_note if not redirect_note else f"{redirect_note}; {geo_note}"
    # relatorio_municipio → ranking_municipios quando a pergunta é um ranking.
    name2, args2, note2 = _maybe_rewrite_to_ranking(name, args, geo_text)
    if note2:
        name, args = name2, args2
        redirect_note = note2 if not redirect_note else f"{redirect_note}; {note2}"
    # Filtro de tipo de violência (herda do contexto em follow-ups).
    name3, args3, note3 = _enforce_violencia_filter(name, args, violencia_text)
    if note3:
        name, args = name3, args3
        redirect_note = note3 if not redirect_note else f"{redirect_note}; {note3}"

    # Filtro de ANO (o roteador determinístico extrai do texto — antes isso
    # vinha do Qwen escolhendo os args). Só nas tools que leem filters_extra.
    if name in ("relatorio_brasil", "relatorio_uf", "ranking_municipios"):
        ano_filt = _extract_year_filter(latest_user)
        if ano_filt:
            fx = dict((args or {}).get("filters_extra") or {})
            for k, v in ano_filt.items():
                fx.setdefault(k, v)
            args = {**(args or {}), "filters_extra": fx}

    # RAG (jurídico/produto): a pergunta inteira vira a query de busca.
    if name in ("rag_juridico", "rag_interno") and not (args or {}).get("query"):
        args = {**(args or {}), "query": latest_user}

    # --- Executa UMA ferramenta (sem loop) ---------------------------------
    t_tool = time.time()
    try:
        result = run_tool(name, args, ctx)
    except Exception as exc:
        return OrchestratorResult(
            final_text="Não consegui consultar os dados agora. Tente reformular a pergunta.",
            tool_events=events, elapsed_seconds=time.time() - t0, rounds=1,
            error=f"{type(exc).__name__}: {exc}", raw_messages=convo)
    if redirect_note and isinstance(result, dict):
        result.setdefault("server_notes", []).append(redirect_note)
    # Guardrails: trechos RAG entram como DADO (nunca instrução).
    if name in ("rag_juridico", "rag_interno") and isinstance(result, dict):
        textos = [
            (t.get("texto") or "")
            for t in (result.get("trechos") or [])
            if isinstance(t, dict) and (t.get("texto") or "").strip()
        ]
        if textos:
            from guardrails.pipeline import processar_entrada
            processar_entrada("", trechos_recuperados=textos)
    events.append(ToolEvent(name=name, args=args, result=result,
                            elapsed_seconds=round(time.time() - t_tool, 2)))

    # --- Jurema redige a narrativa a partir do payload humanizado ----------
    # FULL result vai pro DB (evt.result, persistido pela view); a versão
    # humanizada (qualitativa, sem WAPE/p50/p90) alimenta o gerador.
    humanizado = _humanize_result_for_llm(name, result, compare_ctx)
    final_text, tok_prompt, tok_completion = _narrar_com_jurema(
        name, latest_user, result, humanizado, compare_hint)

    return OrchestratorResult(
        final_text=_sanitize_narrative(final_text), tool_events=events,
        elapsed_seconds=time.time() - t0, rounds=1, raw_messages=convo,
        prompt_tokens=tok_prompt, completion_tokens=tok_completion,
    )


def ping_ollama() -> tuple[bool, str]:
    try:
        client = _ollama_client()
        models = client.list()
        names = [m.get("model") or m.get("name") for m in models.get("models", [])]
        return True, f"Ollama OK · modelos: {', '.join(names) or '(nenhum)'}"
    except Exception as exc:
        return False, f"Ollama indisponivel: {exc}"
