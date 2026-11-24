"""Regressões do ciclo de testes da versão 1.0 (Tabelas 4 e 7 do relatório).

* Contagem de municípios: notificação com UF de um estado e município de outro
  não pode inflar a contagem (Sergipe aparecia com 76, são 75).
* Ausência de dados: filtro sem registros mostra aviso informativo.
* Limite de requisições por IP (HTTP 429).
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from painel.services import analytics


def _nova(**kw):
    Model = analytics.violbr_model()
    base = {"NU_ANO": "2024", "SG_UF_OCOR": "28", "ID_MN_OCOR": "280030",
            "NU_IDADE_N": "4010", "VIOL_SEXU": "1"}
    base.update(kw)
    return Model.objects.create(**base)


@override_settings(AURORA_RATE_LIMIT_ENABLED=False)
class ContagemMunicipiosTests(TestCase):
    def setUp(self):
        _nova(ID_MN_OCOR="280030")            # Aracaju (SE)
        _nova(ID_MN_OCOR="280670")            # Itabaiana? qualquer município de SE
        _nova(ID_MN_OCOR="280000")            # município ignorado (UF + zeros)
        _nova(ID_MN_OCOR="270030")            # município de AL lançado como SE
        _nova(SG_UF_OCOR="AL", ID_MN_OCOR="270030")

    def test_municipio_da_uf(self):
        self.assertTrue(analytics.municipio_da_uf("280030", "SE"))
        self.assertTrue(analytics.municipio_da_uf("280030", "28"))
        self.assertFalse(analytics.municipio_da_uf("270030", "28"))
        self.assertFalse(analytics.municipio_da_uf("999999", "SE"))

    def test_kpi_sergipe_ignora_municipio_de_outra_uf(self):
        kpis = analytics.overview_kpis({"uf": "SE"})
        self.assertEqual(kpis["municipios"], 2)
        self.assertEqual(kpis["total"], 4)  # notificações continuam no total

    def test_kpi_brasil_conta_codigo_uma_vez(self):
        self.assertEqual(analytics.overview_kpis({})["municipios"], 3)

    def test_lista_de_municipios_do_filtro(self):
        dados = self.client.get(reverse("filter_options")).json()
        codigos_se = [m["codigo"] for m in dados["municipios_por_uf"]["SE"]]
        self.assertNotIn("270030", codigos_se)
        self.assertNotIn("280000", codigos_se)

    def test_mapa_municipal_de_sergipe(self):
        dados = self.client.get(reverse("map_municipalities", args=["SE"])).json()
        self.assertEqual(set(dados["municipios"]), {"280030", "280670"})
        self.assertEqual(dados["sem_municipio"], 2)
        self.assertEqual(dados["total"], 4)

    def test_ranking_de_sergipe(self):
        rows = analytics.municipality_ranking_rows({"uf": "SE"})
        self.assertEqual({r["ID_MN_OCOR"] for r in rows}, {"280030", "280670"})


@override_settings(AURORA_RATE_LIMIT_ENABLED=False)
class AusenciaDeDadosTests(TestCase):
    def setUp(self):
        _nova()

    def test_aviso_quando_filtro_sem_registros(self):
        resp = self.client.get(reverse("dashboards"), {"uf": "SE", "ano_inicio": "2019", "ano_fim": "2019"})
        self.assertContains(resp, "Nenhuma notificação encontrada para a combinação de filtros")

    def test_sem_aviso_com_dados(self):
        resp = self.client.get(reverse("dashboards"), {"uf": "SE"})
        self.assertNotContains(resp, "Nenhuma notificação encontrada para a combinação de filtros")

    def test_sem_aviso_sem_filtro(self):
        resp = self.client.get(reverse("dashboards"))
        self.assertNotContains(resp, "Nenhuma notificação encontrada para a combinação de filtros")


class LimiteRequisicoesTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(AURORA_RATE_LIMIT_API_PER_MIN=3, AURORA_RATE_LIMIT_PAGE_PER_MIN=100)
    def test_api_retorna_429_ao_estourar(self):
        url = reverse("filter_options")
        codigos = [self.client.get(url, REMOTE_ADDR="10.0.0.1").status_code for _ in range(4)]
        self.assertEqual(codigos[:3], [200, 200, 200])
        self.assertEqual(codigos[3], 429)
        resp = self.client.get(url, REMOTE_ADDR="10.0.0.1")
        self.assertIn("Retry-After", resp)
        # Outro IP não é afetado.
        self.assertEqual(self.client.get(url, REMOTE_ADDR="10.0.0.2").status_code, 200)

    @override_settings(AURORA_RATE_LIMIT_API_PER_MIN=2, AURORA_TRUST_X_FORWARDED_FOR=True)
    def test_usa_ip_acrescentado_pelo_proxy(self):
        url = reverse("filter_options")
        for i in range(2):
            self.client.get(url, HTTP_X_FORWARDED_FOR=f"1.1.1.{i}, 200.0.0.9")
        # Cliente forjando o 1º endereço continua limitado pelo IP real.
        resp = self.client.get(url, HTTP_X_FORWARDED_FOR="9.9.9.9, 200.0.0.9")
        self.assertEqual(resp.status_code, 429)

    @override_settings(AURORA_RATE_LIMIT_PAGE_PER_MIN=1)
    def test_estaticos_isentos(self):
        for _ in range(3):
            resp = self.client.get("/static/painel/css/govbr.css", REMOTE_ADDR="10.0.0.3")
            self.assertNotEqual(resp.status_code, 429)
