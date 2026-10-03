"""Guardrails do Aurora Responde — entrada, saída e limites.

API pública:

  * ``pipeline.processar_entrada`` / ``pipeline.processar_saida``
  * ``limites.verificar_limite``

Implementação alinhada ao encaminhamento 26 (risco → Disque 100, injecção,
PII, filtro de saída). Ver ``docs/guardrails_integracao.md``.
"""
