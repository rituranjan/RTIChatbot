import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0004_knowledge"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebSource",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("url", models.URLField(max_length=500)),
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
                ("page_count", models.IntegerField(default=0)),
                ("chunk_count", models.IntegerField(default=0)),
                ("max_pages", models.IntegerField(default=300)),
                ("crawl_token", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="web_sources",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="WebPage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                ("title", models.CharField(blank=True, default="", max_length=300)),
                ("chunk_count", models.IntegerField(default=0)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pages",
                        to="chatbot.websource",
                    ),
                ),
            ],
            options={
                "ordering": ["url"],
            },
        ),
        migrations.AddIndex(
            model_name="websource",
            index=models.Index(fields=["owner", "-updated_at"], name="chatbot_web_owner_u_idx"),
        ),
        migrations.AddConstraint(
            model_name="webpage",
            constraint=models.UniqueConstraint(
                fields=("source", "url"), name="chatbot_webpage_source_url"
            ),
        ),
    ]
