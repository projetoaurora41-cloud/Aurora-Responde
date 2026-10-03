"""Cria/atualiza a view ``public."VIOLBR"`` = UNION ALL das brutas VIOLBR<YY>.

A view CRUA (colunas originais do DATASUS: DT_OCOR, VIOL_SEXU, ID_MN_OCOR,
NDUPLIC, SG_UF_NOT, ...) é o que o chatbot de datas comemorativas (Carnaval) e
o QA geral consomem — diferente da `sinam_notificacao` (limpa, usada pelo
orquestrador) e da `view_violencia_chatbot` (colunas traduzidas).

A importação `.dbc` (sinam) já chama isso automaticamente ao final. Este comando
serve para recriar a view manualmente (ex.: após uma carga bruta feita por fora).

    python manage.py setup_violbr_view
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from sinam.etl import refresh_violbr_view


class Command(BaseCommand):
    help = 'Cria/atualiza a view public."VIOLBR" unindo as tabelas brutas VIOLBR<YY>.'

    def handle(self, *args, **opts):
        info = refresh_violbr_view()
        tables = info.get("tables", [])
        if not tables:
            self.stderr.write(self.style.ERROR(
                "Nenhuma tabela bruta VIOLBR<YY> encontrada. Nada a fazer."))
            return
        self.stdout.write(self.style.SUCCESS(
            f'View public."VIOLBR" atualizada a partir de {len(tables)} '
            f'tabela(s) [{", ".join(tables)}], {info.get("cols")} colunas.'))
