"""Chat threads and messages.

A ChatThread is one conversation; ChatMessage stores each turn including
tool calls/results so the assistant can be replayed deterministically.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class ChatThread(models.Model):
    # Usuário é OPCIONAL: o "Aurora responde" é um chat aberto (sem login). Quando
    # anônimo, a conversa é escopada por `session_key` em vez de por usuário.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="chat_threads", null=True, blank=True,
    )
    session_key = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="Chave de sessão do dono anônimo (quando user é nulo).",
    )
    title = models.CharField(max_length=200, blank=True)
    forecaster = models.CharField(
        max_length=32, default="chronos2",
        help_text="Forecaster backend key (chronos2, chattime, ...).",
    )
    model = models.CharField(
        max_length=64, default="jurema-7b",
        help_text="Ollama model name used as the answer generator (Aurora Responde: Jurema-7B).",
    )
    temperature = models.FloatField(
        default=0.2,
        help_text=("Temperatura de amostragem do orquestrador (0.0 = determinístico, "
                   "1.0 = criativo). 0.2 dá respostas estáveis e baixa alucinação."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversa #{self.pk}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("system", "system"),
        ("user", "user"),
        ("assistant", "assistant"),
        ("tool", "tool"),
    ]

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    # When the assistant calls tools, we persist the structured tool_calls here.
    tool_calls = models.JSONField(default=list, blank=True)
    # For role=tool, references the assistant message that requested it.
    tool_name = models.CharField(max_length=64, blank=True)
    tool_payload = models.JSONField(default=dict, blank=True)
    elapsed_seconds = models.FloatField(null=True, blank=True)
    # Tokens do orquestrador (Ollama) para feedback de uso na UI.
    tokens_prompt = models.IntegerField(null=True, blank=True)
    tokens_completion = models.IntegerField(null=True, blank=True)
    # Modelo de série vencedor do comitê (ex.: "Chronos-2"), exibido como badge
    # nos detalhes — NÃO na prosa da resposta.
    forecaster_used = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:60]}"


class ChatAttachment(models.Model):
    """Arquivo anexado a uma conversa (PDF, imagem ou texto).

    Guardamos só o TEXTO extraído (não o binário) — evita configurar MEDIA e
    mantém o anexo utilizável como contexto (grounding) para o orquestrador.
    Imagens passam por OCR quando disponível; o texto extraído fica em `text`.
    """
    KIND_CHOICES = [
        ("text", "texto"),
        ("pdf", "pdf"),
        ("image", "imagem"),
    ]

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE,
                               related_name="attachments")
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default="text")
    text = models.TextField(blank=True)
    char_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind}, {self.char_count} chars)"
