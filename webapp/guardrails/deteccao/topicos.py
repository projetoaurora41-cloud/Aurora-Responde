"""Detecção de risco: Disque 100 (emergência) ou Conselho Tutelar (C/A)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# Emergência imediata / pessoa em perigo → Disque 100 + 190.
_EMERGENCIA_RE = re.compile(
    r"\b(me\s+ajud[ae]|preciso\s+de\s+ajuda|estou\s+em\s+perigo|"
    r"estou\s+sendo\s+(?:abusad[oa]|agredid[oa]|violentad[oa])|"
    r"(?:abuso|agressao|violencia)\s+(?:agora|neste momento|em curso)|"
    r"quero\s+denunciar\s+(?:meu|minha|o\s+meu|a\s+minha)\b|"
    r"suicidio|me\s+matar|vou\s+me\s+matar|ideacao\s+suicid|"
    r"emergencia\s+(?:agora|urgente)|socorro\s+(?:urgente|agora))\b"
)

# Perguntas de dado/estatística/produto — não são relato pessoal.
_CONSULTA_DADOS_RE = re.compile(
    r"\b(quantos?|quantas?|ranking|serie\s+temporal|evolucao|"
    r"por\s+(?:uf|sexo|ano|direito)|em\s+20\d{2}|notificac|"
    r"estatistic|sipia|consulta|agregad|total\s+de|"
    r"o\s+que\s+(?:e|faz)\s+(?:o\s+)?conselho|"
    r"como\s+funciona\s+(?:o\s+)?conselho|"
    r"atribuic(?:ao|oes)\s+do\s+conselho)\b"
)

# Situações em que o Conselho Tutelar é o encaminhamento principal
# (criança/adolescente com direito ameaçado ou violado — não só estatística).
_CONSELHO_TUTELAR_RE = re.compile(
    r"\b("
    r"procurar\s+(?:o\s+)?conselho\s+tutelar|"
    r"preciso\s+(?:do|de\s+um)\s+conselho\s+tutelar|"
    r"(?:crianca|adolescente|menor(?:\s+de\s+idade)?|filho|filha|neto|neta)"
    r".{0,40}(?:"
    r"em\s+risco|sendo\s+(?:abusad|agred|violent|negligenc)|"
    r"maltratad|abandonad|explorad|sem\s+escola|sem\s+comida|"
    r"direito\s+(?:violad|ameacad)|violacao\s+de\s+direito"
    r")|"
    r"(?:vizinho|vizinha|tio|tia|padrasto|madrasta|responsavel).{0,30}"
    r"(?:maltrata|agride|abuso|negligencia).{0,30}"
    r"(?:crianca|adolescente|menor|filho|filha)|"
    r"(?:denunciar|relatar|comunicar).{0,40}"
    r"(?:crianca|adolescente|menor|abuso\s+(?:infantil|sexual\s+de\s+menor))|"
    r"medida\s+de\s+protecao|"
    r"quero\s+denunciar\s+(?:uma?\s+)?(?:crianca|adolescente|menor)"
    r")\b",
    re.DOTALL,
)


@dataclass
class RiscoResult:
    """encaminhamento: '' | 'disque_100' | 'conselho_tutelar'."""

    em_risco: bool
    encaminhamento: str = ""
    motivo: str = ""


def detectar_risco(texto: str) -> RiscoResult:
    """Classifica se a mensagem pede encaminhamento humano e para qual canal.

    Prioridade: emergência pessoal → Disque 100; relato envolvendo C/A →
    Conselho Tutelar (mensagem também cita Disque 100 como canal complementar).
    Consultas estatísticas/SIPIA não disparam encaminhamento.
    """
    if not texto or not texto.strip():
        return RiscoResult(em_risco=False)
    n = _norm(texto)

    m_em = _EMERGENCIA_RE.search(n)
    if m_em:
        return RiscoResult(
            em_risco=True,
            encaminhamento="disque_100",
            motivo=m_em.group(0),
        )

    # Evita confundir "Conselho Tutelar em SE 2023" (dado) com relato pessoal.
    if _CONSULTA_DADOS_RE.search(n):
        return RiscoResult(em_risco=False)

    m_ct = _CONSELHO_TUTELAR_RE.search(n)
    if m_ct:
        return RiscoResult(
            em_risco=True,
            encaminhamento="conselho_tutelar",
            motivo=m_ct.group(0)[:80],
        )

    return RiscoResult(em_risco=False)
