"""Regressões do relatório de erros de 13/11/2026 (roteamento, escopo, lei)."""
from django.test import SimpleTestCase

from chats.aurora_responde import leis_corpus
from chats.aurora_responde import roteador as r
from guardrails.deteccao.topicos import detectar_risco


class EscopoTests(SimpleTestCase):
    def test_fora_do_tema_recusa(self):
        for q in ("quanto custa um mais um?", "Qual a capital da França?",
                  "Como um gato bebe leite?", "Quem vai ganhar a próxima eleição?",
                  "Me ajuda a escrever um poema?", "Me dá uma receita de bolo"):
            self.assertTrue(r._is_offscope(q), q)

    def test_dentro_do_tema_passa(self):
        for q in ("Evolução da violência sexual em Sergipe",
                  "O que é escuta especializada?",
                  "Cidades com mais notificações na Bahia"):
            self.assertFalse(r._is_offscope(q), q)
        self.assertFalse(r._is_offscope("e na Bahia?", tem_contexto=True))


class RespostasFixasTests(SimpleTestCase):
    def test_denuncia(self):
        for q in ("Como denunciar de forma anônima?", "A plataforma Aurora recebe denúncias?"):
            txt = r._resposta_fixa(q) or ""
            self.assertIn("Disque 100", txt)
            self.assertIn("não recebe denúncias", txt)
            self.assertNotIn("CACIA", txt)

    def test_como_consultar(self):
        self.assertIn("Aplicar filtros", r._resposta_fixa("Como consulto os dados do meu estado?") or "")


class RotaJuridicaTests(SimpleTestCase):
    casos = {
        "Qual a pena prevista no ECA para quem submete criança ou adolescente à exploração sexual?": "244-A",
        "Quantos membros tem o Conselho Tutelar e qual é o mandato?": "132",
        "O que a lei diz sobre tráfico de crianças?": "149-A",
        "O que é estupro de vulnerável?": "217-A",
        "Professor é obrigado a comunicar suspeita de abuso?": "245",
        "O que é escuta especializada?": "13.431",
        "Até que idade uma pessoa é considerada criança pelo ECA?": "Art. 2º",
    }

    def test_rota_e_artigo(self):
        for q, art in self.casos.items():
            self.assertEqual(r._route_category(q), "legal", q)
            achados = leis_corpus.por_tema(q)
            self.assertTrue(achados, q)
            self.assertIn(art, achados[0]["artigo"] + achados[0]["fonte"] + achados[0]["lei"], q)

    def test_pergunta_de_dados_nao_vira_lei(self):
        self.assertIsNone(r._route_category("Evolução da violência sexual em Sergipe"))

    def test_parecer_com_raciocinio_e_descartado(self):
        self.assertEqual(r._limpar_parecer("Analisando as alternativas: A) x B) y"), "")
        self.assertEqual(r._limpar_parecer("Resposta: art. 244"), "")


class RiscoTests(SimpleTestCase):
    def test_adolescente_fotos(self):
        res = detectar_risco("Tenho 15 anos e um adulto está me oferecendo dinheiro em troca de fotos")
        self.assertEqual(res.encaminhamento, "aliciamento")

    def test_poema_nao_e_socorro(self):
        self.assertFalse(detectar_risco("Me ajuda a escrever um poema?").em_risco)


class NarrativaTests(SimpleTestCase):
    def test_pico_e_ultimo_ano(self):
        txt = r._narrativa_relatorio({
            "escopo": "Estado de SE", "filtros_aplicados": {"uf": "SE", "violencia_sexual": True},
            "por_ano": [{"ano": 2020, "n": 287}, {"ano": 2024, "n": 717}, {"ano": 2025, "n": 801}],
        })
        self.assertIn("801 em 2025", txt)
        self.assertIn("maior valor da série é o de 2025", txt)
        self.assertNotIn("casos", txt.split("\n\n")[0])

    def test_violencia_infantil_nao_vira_filtro(self):
        self.assertEqual(r._detect_violencias("violência infantil em Sergipe"), [])
        self.assertEqual(r._detect_violencias("exploração sexual em Sergipe"), ["exploracao_sexual"])
