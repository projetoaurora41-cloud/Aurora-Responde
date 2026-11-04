# Modelo de série vencedor (badge nos detalhes), sem citar na prosa.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orquestrador", "0003_chatmessage_tokens"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="forecaster_used",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
