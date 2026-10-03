# Aurora responde: chat aberto (user opcional + session_key) e anexos.
# Escrita à mão (o ambiente de dev não tinha todas as deps p/ makemigrations).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orquestrador", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatthread",
            name="user",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chat_threads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="chatthread",
            name="session_key",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=40,
                help_text="Chave de sessão do dono anônimo (quando user é nulo).",
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="ChatAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("kind", models.CharField(choices=[("text", "texto"), ("pdf", "pdf"), ("image", "imagem")], default="text", max_length=8)),
                ("text", models.TextField(blank=True)),
                ("char_count", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="orquestrador.chatthread")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
