"""Ferramentas de RAG e fontes extra do orquestrador "Aurora responde".

Estas tools estendem o loop de tool-calling do [orchestrator.py] para além do
SINAM + Chronos-2. São a parte "por baixo" do chat único: o Qwen3 roteia a
pergunta e chama a ferramenta certa, depois sintetiza CITANDO A FONTE.

Ferramentas expostas aqui:

  * ``rag_juridico``      -> Leis, normas e jurisprudência (a "versão do Jurema").
                             Reaproveita a busca full-text já existente no chat
                             Dados Jurídicos ([dados_juridicos/retrieval.py]).
  * ``rag_interno``       -> Documentação do próprio produto (pasta ``docs/``):
                             arquitetura, metodologia, camada semântica, etc.
  * ``consulta_sipia_ct`` -> Fonte SQL do SIPIA-CT (Conselho Tutelar). Ainda
                             não plugada — degrada com mensagem clara até a
                             base/env estar configurada.

Todas retornam um dict pequeno com um campo ``fonte``/``fontes`` para que o
modelo consiga citar de onde tirou a informação. Quando a fonte não está
disponível, retornam ``{"disponivel": False, ...}`` com uma explicação — nunca
levantam exceção que quebre o loop do orquestrador.

Registro: ``RAG_TOOLS_SCHEMA`` e ``RAG_DISPATCH`` são mesclados em
``TOOLS_SCHEMA``/``DISPATCH`` no final de [tools.py].
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any

# Diretório da documentação do produto (RAG interno). Default: pasta ``docs/``
# na raiz do repositório (este arquivo fica em
# webapp/chats/series_temporais/orquestrador/rag_tools.py -> parents[4] == raiz).
_DEFAULT_DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"
_DOCS_DIR = Path(os.getenv("AURORA_DOCS_DIR", str(_DEFAULT_DOCS_DIR)))

# Fonte SQL do SIPIA-CT. Enquanto não existir a tabela/conexão, a tool degrada.
_SIPIA_CT_TABLE = os.getenv("SIPIA_CT_TABLE", "").strip()

# Modelo jurídico local (Jurema-7B via Ollama). Usado como GERADOR do parecer
# jurídico dentro de `rag_juridico`. Se o modelo não estiver instalado, a tool
# degrada para só os trechos recuperados.
_JUREMA_MODEL = os.getenv("JUREMA_MODEL", "jurema-7b")
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
_JUREMA_NUM_PREDICT = int(os.getenv("JUREMA_NUM_PREDICT", "450"))


def _ask_jurema(query: str, contexto: str = "") -> str | None:
    """Gera um parecer jurídico com o Jurema-7B (best-effort). None se indisponível.

    Quando há `contexto` (trechos recuperados), o parecer é ancorado neles; sem
    contexto, o Jurema responde pelo próprio conhecimento jurídico (sinalizado
    depois na resposta como não confirmado na base).
    """
    try:
        import ollama
    except Exception:
        return None
    if contexto.strip():
        prompt = ("Com base nos TRECHOS abaixo e na legislação brasileira, responda de "
                  "forma objetiva, citando lei/artigo/súmula quando possível.\n\n"
                  f"PERGUNTA: {query}\n\nTRECHOS:\n{contexto}")
    else:
        prompt = ("Responda juridicamente, com base na legislação brasileira, citando "
                  f"lei/artigo/súmula quando possível:\n\n{query}")
    try:
        # trust_env=False evita que proxies corporativos quebrem o localhost.
        client = ollama.Client(host=_OLLAMA_HOST, trust_env=False)
        resp = client.generate(model=_JUREMA_MODEL, prompt=prompt, stream=False,
                               options={"temperature": 0.2,
                                        "num_predict": _JUREMA_NUM_PREDICT})
        # ollama >=0.4 devolve objeto; versões antigas, dict. Cobre os dois.
        txt = resp.get("response") if isinstance(resp, dict) else getattr(resp, "response", "")
        txt = (txt or "").strip()
        return txt or None
    except Exception:
        return None


def _ask_jurema_narrar(prompt: str, num_predict: int | None = None
                       ) -> tuple[str | None, int, int]:
    """Gera texto livre com o Jurema-7B a partir de um prompt pronto.

    Diferente de [_ask_jurema] (que monta um prompt jurídico), aqui o prompt já
    vem montado pelo orquestrador — é o GERADOR de narrativa de TODAS as rotas
    (dados/SIPIA/produto) no fork "só Jurema". Devolve ``(texto, prompt_tokens,
    completion_tokens)``; ``texto`` é ``None`` se o modelo estiver indisponível
    (o chamador cai no fallback da narrativa_sugerida).
    """
    try:
        import ollama
    except Exception:
        return None, 0, 0
    try:
        client = ollama.Client(host=_OLLAMA_HOST, trust_env=False)
        resp = client.generate(
            model=_JUREMA_MODEL, prompt=prompt, stream=False,
            options={"temperature": 0.2,
                     "num_predict": int(num_predict or _JUREMA_NUM_PREDICT)})
        if isinstance(resp, dict):
            txt = resp.get("response") or ""
            pe = int(resp.get("prompt_eval_count") or 0)
            ec = int(resp.get("eval_count") or 0)
        else:
            txt = getattr(resp, "response", "") or ""
            pe = int(getattr(resp, "prompt_eval_count", 0) or 0)
            ec = int(getattr(resp, "eval_count", 0) or 0)
        txt = txt.strip()
        return (txt or None), pe, ec
    except Exception:
        return None, 0, 0


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# Schemas (formato de tool-calling do Ollama = function tools da OpenAI)
# ---------------------------------------------------------------------------
RAG_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "rag_juridico",
            "description": (
                "BUSCA JURÍDICA (leis, normas, ECA, artigos, portarias, "
                "jurisprudência). USE quando a pergunta for sobre o DIREITO / o "
                "marco legal — ex.: 'o que diz o ECA sobre...', 'qual a lei que "
                "trata de...', 'base legal para uma representação ao MP', "
                "'artigo sobre negligência'. Retorna trechos legais relevantes "
                "que você DEVE citar como fonte na resposta. NÃO use para contar "
                "casos/estatísticas (isso é SINAM) nem para séries temporais."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Assunto jurídico a pesquisar, em PT-BR."},
                    "limit": {"type": "integer", "description": "Nº de trechos. Default 5."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_interno",
            "description": (
                "DOCUMENTAÇÃO DO PRODUTO Aurora (como a plataforma funciona, "
                "metodologia, camada semântica, arquitetura, forecast, benchmark). "
                "USE quando o usuário perguntar sobre o PRÓPRIO sistema — ex.: "
                "'como o Aurora calcula a previsão', 'de onde vêm os dados', "
                "'o que é a análise retrospectiva', 'como funciona o comitê de "
                "modelos'. Retorna trechos da documentação para você citar. NÃO "
                "use para dados de violência (SINAM) nem leis (rag_juridico)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Assunto sobre o produto/plataforma, em PT-BR."},
                    "limit": {"type": "integer", "description": "Nº de trechos. Default 4."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consulta_sipia_ct",
            "description": (
                "Consulta a base do SIPIA-CT (Conselho Tutelar) — registros por UF, "
                "ano e mês, agregados por dimensão. É uma fonte DISTINTA do SINAM "
                "(saúde). USE quando o usuário perguntar sobre Conselho Tutelar / "
                "SIPIA. A dimensão vai em filtros['indicador'] e pode ser: 'Sexo', "
                "'Cor', 'Faixa Etária', 'Direito Violado' ou 'Agente Violador'. "
                "Retorna a soma de registros e a distribuição por dimensão."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filtros": {"type": "object",
                                "description": ("Filtros: uf (sigla), ano (aceita ano__gte/ano__lte), "
                                                "indicador ('Sexo'|'Cor'|'Faixa Etária'|'Direito "
                                                "Violado'|'Agente Violador'), mes. Opcional.")},
                    "group_by": {"type": "string",
                                 "description": "Dimensão p/ distribuição: indicador, uf, ano ou categoria. Opcional."},
                    "top": {"type": "integer", "description": "Máx. de linhas na distribuição. Default 15."},
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Implementações
# ---------------------------------------------------------------------------
def tool_rag_juridico(args: dict, ctx) -> dict:
    """Trechos de leis de proteção à criança/adolescente + parecer do Jurema.

    Recupera do CORPUS JURÍDICO curado ([leis_corpus.py]) — CF/88, Código Penal,
    ECA, Lei Henry Borel, Escuta Protegida, Menino Bernardo, Leis 14.811/2024 e
    15.487/2026, além de orientação sobre denúncia/boletim de ocorrência. Os
    trechos ancoram o parecer do Jurema-7B (corrige o que o modelo erra sozinho)
    e dão citação verificável da lei/artigo.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"disponivel": False, "erro": "query vazia."}
    limit = int(args.get("limit") or 5)

    # 1) Recupera trechos do corpus jurídico curado (leis).
    from . import leis_corpus
    encontrados = leis_corpus.buscar(query, limit=limit)
    trechos = [
        {"ref": t["ref"], "lei": t["lei"], "artigo": t["artigo"],
         "texto": t["texto"][:800], "fonte": t["fonte"]}
        for t in encontrados
    ]

    # 2) Gera o parecer com o Jurema, ANCORADO nos trechos da lei (quando houver).
    contexto = "\n".join(
        f"[{t['ref']}] {t['lei']} — {t['artigo']}: {t['texto']}" for t in trechos)
    parecer = _ask_jurema(query, contexto)

    if not trechos and not parecer:
        return {"disponivel": False,
                "fonte": "Corpus jurídico (Aurora)",
                "erro": ("Nem o corpus jurídico nem o modelo Jurema estão "
                         "disponíveis para esta consulta.")}

    return {
        "disponivel": True,
        "encontrou": bool(trechos),
        "fonte": ("Jurema (LLM jurídico) + corpus de leis (Aurora)"
                  if parecer else "Corpus de leis (Aurora)"),
        "parecer_jurema": parecer,
        "parecer_baseado_em": (
            "trechos de lei do corpus" if (parecer and trechos)
            else "conhecimento do modelo Jurema (NÃO confirmado no corpus)" if parecer
            else None),
        "trechos": trechos,
        "instrucao_citacao": (
            "Baseie a resposta nos trechos [L#], CITANDO a lei/artigo (campo "
            "'fonte'). Se o parecer vier só do modelo (sem trechos), sinalize que "
            "não foi confirmado no corpus. Se a pergunta envolver DENÚNCIA ou relato "
            "de violência contra criança/adolescente, oriente também a registrar um "
            "BOLETIM DE OCORRÊNCIA (delegacia física ou Delegacia Eletrônica online), "
            "além do Conselho Tutelar e do Disque 100."),
    }


def _iter_doc_files() -> list[Path]:
    if not _DOCS_DIR.is_dir():
        return []
    return sorted(p for p in _DOCS_DIR.rglob("*.md") if p.is_file())


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def tool_rag_interno(args: dict, ctx) -> dict:
    """Busca por palavra-chave na documentação do produto (``docs/*.md``).

    Scoring simples: conta ocorrências dos termos (>3 letras) da pergunta em
    cada parágrafo, normalizado sem acento. Retorna os melhores parágrafos com
    o nome do arquivo como fonte. Sem embeddings — leve e sem dependências.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"disponivel": False, "erro": "query vazia."}
    limit = int(args.get("limit") or 4)

    files = _iter_doc_files()
    if not files:
        return {"disponivel": False,
                "erro": f"Documentação não encontrada em {_DOCS_DIR}. "
                        f"Defina AURORA_DOCS_DIR ou indexe os docs (ver plano)."}

    termos = {_norm(t) for t in re.findall(r"\w+", query) if len(t) > 3}
    if not termos:
        return {"disponivel": True, "encontrou": False,
                "mensagem": "Pergunta sem termos pesquisáveis (use palavras >3 letras)."}

    candidatos: list[tuple[int, str, str]] = []  # (score, arquivo, paragrafo)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for par in _split_paragraphs(text):
            pnorm = _norm(par)
            score = sum(pnorm.count(t) for t in termos)
            if score > 0:
                candidatos.append((score, f.name, par[:800]))

    if not candidatos:
        return {"disponivel": True, "encontrou": False,
                "mensagem": "Nenhum trecho da documentação bate com a pergunta.",
                "fonte": "Documentação do produto (docs/)"}

    candidatos.sort(key=lambda x: -x[0])
    trechos = [{"ref": f"D{i}", "arquivo": arq, "texto": par}
               for i, (_score, arq, par) in enumerate(candidatos[:limit], 1)]
    return {
        "disponivel": True,
        "encontrou": True,
        "fonte": "Documentação do produto (docs/)",
        "trechos": trechos,
        "instrucao_citacao": "Cite pela ref (ex.: [D1]) e mencione o arquivo de origem.",
    }


def tool_consulta_sipia_ct(args: dict, ctx) -> dict:
    """Fonte SQL do SIPIA-CT (Conselho Tutelar) via camada segura ``sipia_ct``.

    Agrega atendimentos/medidas por total e por dimensão (uf, ano, medida, etc.).
    Degrada limpo quando ``SIPIA_CT_TABLE`` não está definido/plugado.
    """
    from . import sipia_ct
    return sipia_ct.consultar(
        args.get("filtros") or {},
        group_by=args.get("group_by"),
        top=int(args.get("top") or 15),
    )


RAG_DISPATCH = {
    "rag_juridico": tool_rag_juridico,
    "rag_interno": tool_rag_interno,
    "consulta_sipia_ct": tool_consulta_sipia_ct,
}
