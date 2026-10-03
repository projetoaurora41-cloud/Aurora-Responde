"""Popula sinam.Municipio com a lista oficial do IBGE.

Usa a API pública de localidades (não exige autenticação). É chamada uma vez;
a lista de municípios é estável (atualizações raras pelo IBGE).
"""
from __future__ import annotations

import unicodedata

from django.core.management.base import BaseCommand


def _normalize(s: str) -> str:
    nkfd = unicodedata.normalize("NFKD", s or "")
    no_accents = "".join(c for c in nkfd if not unicodedata.combining(c))
    return no_accents.lower().strip()


class Command(BaseCommand):
    help = "Baixa municípios do IBGE e popula sinam.Municipio."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Apaga antes de popular.")

    def handle(self, *args, **opts):
        # Lazy import — only required when this command runs.
        import requests
        from sinam.models import Municipio

        if opts["clear"]:
            n = Municipio.objects.count()
            Municipio.objects.all().delete()
            self.stdout.write(f"Removidos {n} municipios existentes.")

        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        self.stdout.write(f"Baixando {url} ...")
        # requests handles gzip automatically and sets default UA
        resp = requests.get(url, timeout=60, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        self.stdout.write(f"  {len(data)} municipios recebidos.")

        def _extract_uf(m: dict) -> str:
            for path in (
                ("microrregiao", "mesorregiao", "UF"),
                ("regiao-imediata", "regiao-intermediaria", "UF"),
            ):
                node = m
                for k in path:
                    node = (node or {}).get(k) if isinstance(node, dict) else None
                if node and "sigla" in node:
                    return node["sigla"]
            return ""

        objs = []
        for m in data:
            codigo = str(m["id"])
            nome = m["nome"]
            uf = _extract_uf(m)
            objs.append(Municipio(
                codigo=codigo, nome=nome,
                nome_normalizado=_normalize(nome), uf=uf,
            ))
        # SQLite bulk insert: usar ignore_conflicts pra idempotência sem --clear
        Municipio.objects.bulk_create(objs, batch_size=1000,
                                       ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(
            f"Pronto. Municipio.count() = {Municipio.objects.count()}"
        ))
