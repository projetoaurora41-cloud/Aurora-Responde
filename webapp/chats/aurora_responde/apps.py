from django.apps import AppConfig


class AuroraRespondeConfig(AppConfig):
    """Aurora Responde — chat único com roteador determinístico e Jurema-7B."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "chats.aurora_responde"
    label = "orquestrador"
    verbose_name = "Aurora Responde"

    def ready(self):
        from core.registry import ChatType, register

        register(ChatType(
            key="aurora_responde",
            name="Aurora Responde",
            url_name="chat:list",
            description=(
                "Assistente conversacional único sobre violência contra crianças "
                "e adolescentes: dados SINAN/SIPIA-CT, legislação e documentação "
                "do produto, com roteador determinístico e narração via Jurema-7B."
            ),
            owner="Hernandison",
            icon="📈",
        ))
