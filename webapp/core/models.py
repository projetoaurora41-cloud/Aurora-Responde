"""Modelos-base abstratos reutilizáveis por qualquer tipo de chat.

São abstratos (não geram tabelas): servem de molde para que cada app de
chat herde uma estrutura consistente de conversa/mensagem. Usar é opcional.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class BaseChatThread(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="%(app_label)s_threads",
    )
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversa #{self.pk}"


class BaseChatMessage(models.Model):
    ROLE_CHOICES = [
        ("system", "system"),
        ("user", "user"),
        ("assistant", "assistant"),
        ("tool", "tool"),
    ]
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:60]}"
