from django.apps import AppConfig


class GuardrailsConfig(AppConfig):
    """Proteções de entrada/saída e limites do Aurora Responde.

    Stub até o pacote real da frente de segurança ser dropado em
    ``webapp/guardrails/``. Ver ``docs/guardrails_integracao.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "guardrails"
    verbose_name = "Aurora — Guardrails"
