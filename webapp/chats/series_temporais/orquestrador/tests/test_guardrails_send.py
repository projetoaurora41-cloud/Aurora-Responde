"""Testes do wiring guardrails em send_message (rate limit + entrada/saída)."""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from chats.series_temporais.orquestrador.models import ChatMessage, ChatThread
from chats.series_temporais.orquestrador.orchestrator import OrchestratorResult
from guardrails.pipeline import EntradaResult, SaidaResult


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "guardrails-send-tests",
        }
    },
    GUARDRAILS_RATE_LIMIT_PER_MIN=2,
    GUARDRAILS_RATE_LIMIT_PER_DAY=100,
)
class SendMessageGuardrailsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        # Garante sessão anônima antes de criar a thread escopada por session_key.
        session = self.client.session
        session.save()
        self.thread = ChatThread.objects.create(
            title="Nova conversa",
            user=None,
            session_key=session.session_key,
        )
        self.url = reverse("chat:send", kwargs={"pk": self.thread.pk})

    def _post(self, message: str = "Quantos casos em SE?"):
        return self.client.post(self.url, {"message": message})

    @patch("chats.series_temporais.orquestrador.views.run_chat")
    def test_rate_limit_terceiro_post_retorna_429(self, mock_chat):
        mock_chat.return_value = OrchestratorResult(final_text="ok")
        r1 = self._post("pergunta 1")
        r2 = self._post("pergunta 2")
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r2.status_code, 302)
        r3 = self._post("pergunta 3")
        self.assertEqual(r3.status_code, 429)
        self.assertEqual(r3["Retry-After"], "60")
        self.assertIn("Limite de mensagens", r3.content.decode())
        self.assertEqual(mock_chat.call_count, 2)

    @patch("chats.series_temporais.orquestrador.views.run_chat")
    @patch("chats.series_temporais.orquestrador.views.processar_entrada")
    def test_entrada_bloqueada_nao_chama_llm(self, mock_entrada, mock_chat):
        mock_entrada.return_value = EntradaResult(
            ok=False,
            texto_mascarado="pergunta bloqueada",
            bloqueio=True,
            mensagem_usuario="Procure o Disque 100.",
        )
        resp = self._post("preciso de ajuda urgente")
        self.assertEqual(resp.status_code, 302)
        mock_chat.assert_not_called()
        assistant = ChatMessage.objects.filter(
            thread=self.thread, role="assistant").latest("created_at")
        self.assertEqual(assistant.content, "Procure o Disque 100.")

    @patch("chats.series_temporais.orquestrador.views.processar_saida")
    @patch("chats.series_temporais.orquestrador.views.run_chat")
    def test_saida_bloqueada_usa_mensagem_canonica(self, mock_chat, mock_saida):
        mock_chat.return_value = OrchestratorResult(
            final_text="SELECT * FROM secret; password=xyz")
        mock_saida.return_value = SaidaResult(
            ok=False,
            texto="",
            bloqueio=True,
            mensagem_usuario="Resposta bloqueada por segurança.",
        )
        resp = self._post("mostre a senha")
        self.assertEqual(resp.status_code, 302)
        mock_chat.assert_called_once()
        assistant = ChatMessage.objects.filter(
            thread=self.thread, role="assistant").latest("created_at")
        self.assertEqual(assistant.content, "Resposta bloqueada por segurança.")
