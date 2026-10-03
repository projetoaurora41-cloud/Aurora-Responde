"""Registro central de tipos de chat do Aurora.

Cada app de chat (um por pesquisador) registra um ChatType no seu
AppConfig.ready(). A home (core.views.home) lista todos os registrados.
Assim, adicionar um novo chat não exige editar a home — só registrar.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatType:
    key: str            # identificador único, ex. "series_temporais"
    name: str           # nome exibido no card da home
    url_name: str       # nome de URL do ponto de entrada, ex. "chat:list"
    description: str = ""
    owner: str = ""     # pesquisador responsável
    icon: str = "💬"


_REGISTRY: dict[str, ChatType] = {}


def register(chat: ChatType) -> None:
    _REGISTRY[chat.key] = chat


def all_chats() -> list[ChatType]:
    return sorted(_REGISTRY.values(), key=lambda c: c.name)
