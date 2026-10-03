"""Pipeline de entrada/saída — proteções reais (encaminhamento 26).

Contrato público estável usado por send_message / orquestrador:

  processar_entrada → EntradaResult
  processar_saida   → SaidaResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from .deteccao.injecao import score_injecao
from .deteccao.pii import mascarar_pii
from .deteccao.topicos import detectar_risco
from .mensagens import MSG_CONSELHO_TUTELAR, MSG_DISQUE_100, MSG_INJECAO
from .saida import filtrar_saida

# Padrões de "instrução" em trechos RAG — neutralizados (snippet = dado).
_INSTR_IN_SNIPPET_RE = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions?|"
    r"system\s*prompt|"
    r"you\s+are\s+now|"
    r"novas?\s+instruc[oõ]es)",
    re.IGNORECASE,
)


@dataclass
class EntradaResult:
    """Resultado de ``processar_entrada``."""

    ok: bool = True
    texto_mascarado: str = ""
    bloqueio: bool = False
    mensagem_usuario: str = ""
    eventos: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SaidaResult:
    """Resultado de ``processar_saida``."""

    ok: bool = True
    texto: str = ""
    bloqueio: bool = False
    mensagem_usuario: str = ""
    eventos: list[dict[str, Any]] = field(default_factory=list)


def _injection_threshold() -> float:
    return float(getattr(settings, "GUARDRAILS_INJECTION_THRESHOLD", 0.70))


def _sanitizar_trechos(trechos: list[str] | None) -> tuple[list[str], bool]:
    """Trechos RAG entram como dado: remove padrões de instrução."""
    if not trechos:
        return [], False
    out: list[str] = []
    mudou = False
    for t in trechos:
        limpo = _INSTR_IN_SNIPPET_RE.sub("[trecho-neutro]", t or "")
        if limpo != (t or ""):
            mudou = True
        out.append(limpo)
    return out, mudou


def processar_entrada(
    texto: str,
    *,
    trechos_recuperados: list[str] | None = None,
    **_kwargs: Any,
) -> EntradaResult:
    """Valida/mascara a entrada do usuário antes do modelo.

    Ordem: risco (Disque 100 / Conselho Tutelar) → injecção → PII. Trechos RAG
    são sanitizados como dado (evento), sem alterar o contrato de retorno.
    """
    eventos: list[dict[str, Any]] = []
    bruto = texto or ""

    _, trechos_mudaram = _sanitizar_trechos(trechos_recuperados)
    if trechos_recuperados:
        eventos.append({
            "tipo": "rag_trechos",
            "n": len(trechos_recuperados),
            "sanitizados": trechos_mudaram,
        })

    # 1) Pessoa em risco → Disque 100 ou Conselho Tutelar (não só recusa).
    risco = detectar_risco(bruto)
    if risco.em_risco:
        pii = mascarar_pii(bruto)
        if pii.campos:
            eventos.append({"tipo": "pii_mascarado", "campos": pii.campos})
        eventos.append({
            "tipo": "risco",
            "encaminhamento": risco.encaminhamento,
            "motivo": risco.motivo,
        })
        if risco.encaminhamento == "conselho_tutelar":
            msg = MSG_CONSELHO_TUTELAR
        else:
            msg = MSG_DISQUE_100
        return EntradaResult(
            ok=False,
            texto_mascarado=pii.texto_mascarado,
            bloqueio=True,
            mensagem_usuario=msg,
            eventos=eventos,
        )

    # 2) Prompt injection.
    inj = score_injecao(bruto)
    limiar = _injection_threshold()
    eventos.append({"tipo": "injecao", "score": inj.score, "limiar": limiar,
                    "motivos": inj.motivos})
    if inj.score >= limiar:
        pii = mascarar_pii(bruto)
        if pii.campos:
            eventos.append({"tipo": "pii_mascarado", "campos": pii.campos})
        return EntradaResult(
            ok=False,
            texto_mascarado=pii.texto_mascarado,
            bloqueio=True,
            mensagem_usuario=MSG_INJECAO,
            eventos=eventos,
        )

    # 3) PII — mascara, não bloqueia.
    pii = mascarar_pii(bruto)
    if pii.campos:
        eventos.append({"tipo": "pii_mascarado", "campos": pii.campos})

    return EntradaResult(
        ok=True,
        texto_mascarado=pii.texto_mascarado,
        bloqueio=False,
        mensagem_usuario="",
        eventos=eventos,
    )


def processar_saida(texto: str, **_kwargs: Any) -> SaidaResult:
    """Filtra a saída do modelo antes de exibir ao usuário."""
    r = filtrar_saida(texto or "")
    return SaidaResult(
        ok=r.ok,
        texto=r.texto,
        bloqueio=r.bloqueio,
        mensagem_usuario=r.mensagem_usuario,
        eventos=r.eventos,
    )
