from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Base compartilhada por todos os tipos de chat do projeto Aurora.

    Fornece: modelos-base abstratos de conversa, o registry de tipos de chat
    (usado pela home), a home/landing e a autenticação (login/signup).
    Cada pesquisador cria seu próprio app de chat e o registra aqui.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Aurora — Core"
