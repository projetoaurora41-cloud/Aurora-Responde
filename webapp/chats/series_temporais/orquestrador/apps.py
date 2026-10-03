from django.apps import AppConfig


class OrquestradorConfig(AppConfig):
    """Chat com séries temporais retrospectiva, conduzido por orquestrador LLM."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "chats.series_temporais.orquestrador"
    label = "orquestrador"
    verbose_name = "Séries Temporais — Orquestrador"

    def ready(self):
        from core.registry import ChatType, register

        register(ChatType(
            key="series_temporais",
            name="Séries Temporais — Retrospectiva",
            url_name="chat:list",
            description=(
                "Chat conduzido por orquestrador LLM sobre séries temporais de "
                "notificações (SINAM/VIOLBR): análise retrospectiva, forecast e QA."
            ),
            owner="Hernandison",
            icon="📈",
        ))
