import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0009_error_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="appsetting",
            name="llm_policy",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="PromptTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("category", models.CharField(default="chat", max_length=64)),
                ("workflow", models.CharField(default="chat", max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("active_version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by_id", models.IntegerField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "prompt template",
                "ordering": ["category", "slug"],
            },
        ),
        migrations.CreateModel(
            name="PromptVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("content", models.TextField()),
                ("variables", models.JSONField(blank=True, default=list)),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by_id", models.IntegerField(blank=True, null=True)),
                (
                    "prompt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="chatbot.prompttemplate",
                    ),
                ),
            ],
            options={
                "verbose_name": "prompt version",
                "ordering": ["-version"],
            },
        ),
        migrations.AddConstraint(
            model_name="promptversion",
            constraint=models.UniqueConstraint(
                fields=("prompt", "version"), name="chatbot_prompt_version_unique"
            ),
        ),
        migrations.CreateModel(
            name="LlmUsageLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("workflow", models.CharField(max_length=64)),
                ("provider", models.CharField(default="openrouter", max_length=32)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("prompt_slug", models.CharField(blank=True, default="", max_length=80)),
                ("prompt_version", models.PositiveIntegerField(default=0)),
                ("estimated_input_tokens", models.PositiveIntegerField(default=0)),
                ("actual_input_tokens", models.PositiveIntegerField(default=0)),
                ("max_output_tokens", models.PositiveIntegerField(default=0)),
                ("actual_output_tokens", models.PositiveIntegerField(default=0)),
                ("cached_tokens", models.PositiveIntegerField(default=0)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("success", models.BooleanField(default=True)),
                ("error_message", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="llm_usage",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "LLM usage log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="llmusagelog",
            index=models.Index(fields=["user", "-created_at"], name="chatbot_llm_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="llmusagelog",
            index=models.Index(fields=["workflow", "-created_at"], name="chatbot_llm_workflow_created_idx"),
        ),
    ]
