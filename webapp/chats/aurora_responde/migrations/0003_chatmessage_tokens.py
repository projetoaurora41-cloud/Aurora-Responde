# Feedback de tokens: guarda prompt/completion tokens por resposta do assistente.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orquestrador", "0002_open_chat_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="tokens_prompt",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="tokens_completion",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
