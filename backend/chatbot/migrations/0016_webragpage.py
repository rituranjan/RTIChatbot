import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0015_embed_allowed_domain"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebRagPage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                ("title", models.CharField(blank=True, default="", max_length=300)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "pending"),
                            ("crawling", "crawling"),
                            ("ready", "ready"),
                            ("failed", "failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("error", models.TextField(blank=True)),
                ("message", models.CharField(blank=True, default="", max_length=300)),
                ("chunk_count", models.IntegerField(default=0)),
                ("priority", models.IntegerField(default=100)),
                ("index_token", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="web_rag_pages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="webragpage",
            index=models.Index(fields=["owner", "-updated_at"], name="chatbot_ragpage_owner_u_idx"),
        ),
        migrations.AddConstraint(
            model_name="webragpage",
            constraint=models.UniqueConstraint(
                fields=("owner", "url"), name="chatbot_ragpage_owner_url_uniq"
            ),
        ),
    ]
