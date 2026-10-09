"""Modelos do app de mapas.

``SipiactTotal`` guarda os totais agregados do SIPIA-CT (Sistema de Informação
para a Infância e a Adolescência — Conselho Tutelar) por indicador, UF e ano.

No projeto original (Projeto_Sinam) esses totais vinham de uma *view* Postgres
``sipiact.vw_sipiact_totais``. Aqui a mesma fonte de dados é reproduzida como um
modelo Django alimentado por um dataset agregado embutido
(``mapas/data/sipiact_totais.json``), carregado automaticamente na migração de
dados. Assim o mapa funciona em SQLite sem depender de um Postgres externo.
"""
from __future__ import annotations

from django.db import models


class SipiactTotal(models.Model):
    """Total de registros SIPIA-CT para (indicador, UF, ano)."""

    indicador = models.CharField(max_length=120, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)  # sigla (ex.: "SP")
    ano = models.IntegerField(db_index=True)
    total = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Total SIPIA-CT"
        verbose_name_plural = "Totais SIPIA-CT"
        constraints = [
            models.UniqueConstraint(
                fields=["indicador", "uf", "ano"],
                name="uniq_sipiact_indicador_uf_ano",
            )
        ]
        indexes = [
            models.Index(fields=["indicador", "ano"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"{self.indicador} · {self.uf} · {self.ano}: {self.total}"
