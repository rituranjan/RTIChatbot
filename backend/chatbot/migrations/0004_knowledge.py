import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0003_embedbot"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataConnection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                (
                    "engine",
                    models.CharField(
                        choices=[
                            ("sqlite", "SQLite"),
                            ("mysql", "MySQL"),
                            ("postgresql", "PostgreSQL"),
                            ("mssql", "SQL Server"),
                        ],
                        max_length=16,
                    ),
                ),
                ("connection_string", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_connections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SqlKeywordQuery",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("keywords", models.JSONField(blank=True, default=list)),
                ("sql_text", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="queries",
                        to="chatbot.dataconnection",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sql_queries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="IntakeQuestion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("label", models.CharField(max_length=80)),
                ("field_key", models.CharField(max_length=40)),
                ("placeholder", models.CharField(blank=True, default="", max_length=120)),
                ("required", models.BooleanField(default=True)),
                ("position", models.IntegerField(default=0)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intake_questions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["position", "label"],
            },
        ),
        migrations.AddConstraint(
            model_name="intakequestion",
            constraint=models.UniqueConstraint(
                fields=("owner", "field_key"), name="chatbot_intake_owner_key"
            ),
        ),
        migrations.CreateModel(
            name="VisitorProfile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("answers", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to="chatbot.conversation",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
