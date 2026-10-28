import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0002_databaserecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmbedBot",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(default="Assistant", max_length=80)),
                (
                    "greeting",
                    models.TextField(default="Hello! How can I help you today?"),
                ),
                ("quick_replies", models.JSONField(blank=True, default=list)),
                ("accent", models.CharField(default="#2563eb", max_length=16)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embed_bots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="conversation",
            name="embed_bot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversations",
                to="chatbot.embedbot",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="visitor_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["embed_bot", "visitor_id"],
                name="chatbot_con_embed_b_6a0c1d_idx",
            ),
        ),
    ]
