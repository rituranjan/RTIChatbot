import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import chatbot.models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0016_webragpage"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="appsetting",
            name="semantic_sql_settings",
            field=models.JSONField(blank=True, default=chatbot.models.default_semantic_sql_settings),
        ),
        migrations.CreateModel(
            name="SemanticEngineConfig",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("enabled", models.BooleanField(default=False)),
                ("database_name", models.CharField(blank=True, default="", max_length=120)),
                ("base_from_sql", models.TextField(blank=True, default="")),
                ("tenant_filter_column", models.CharField(blank=True, default="", max_length=200)),
                ("max_rows", models.PositiveIntegerField(default=40)),
                ("timeout_seconds", models.PositiveIntegerField(default=12)),
                ("use_llm_understanding", models.BooleanField(default=True)),
                ("fallback_keyword_sql", models.BooleanField(default=True)),
                ("temperature", models.FloatField(default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="semantic_engines",
                        to="chatbot.dataconnection",
                    ),
                ),
                (
                    "owner",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_engine",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SemanticTable",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("database_name", models.CharField(max_length=120)),
                ("table_name", models.CharField(max_length=120)),
                ("table_alias", models.CharField(blank=True, default="", max_length=16)),
                ("display_name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_tables",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["table_name"]},
        ),
        migrations.CreateModel(
            name="SemanticColumn",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("physical_column", models.CharField(max_length=200)),
                ("sql_alias", models.CharField(blank=True, default="", max_length=200)),
                ("display_name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("data_type", models.CharField(blank=True, default="string", max_length=64)),
                ("searchable", models.BooleanField(default=True)),
                ("filterable", models.BooleanField(default=True)),
                ("sortable", models.BooleanField(default=True)),
                ("groupable", models.BooleanField(default=False)),
                ("aggregatable", models.BooleanField(default=False)),
                ("sensitive", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "semantic_table",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="columns",
                        to="chatbot.semantictable",
                    ),
                ),
            ],
            options={"ordering": ["physical_column"]},
        ),
        migrations.CreateModel(
            name="SemanticSynonym",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("synonym", models.CharField(max_length=200)),
                ("language_code", models.CharField(blank=True, default="en", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "semantic_column",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="synonyms",
                        to="chatbot.semanticcolumn",
                    ),
                ),
            ],
            options={"ordering": ["synonym"]},
        ),
        migrations.CreateModel(
            name="SemanticRelationship",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("source_table", models.CharField(max_length=120)),
                ("source_column", models.CharField(max_length=200)),
                ("target_table", models.CharField(max_length=120)),
                ("target_column", models.CharField(max_length=200)),
                ("join_type", models.CharField(default="LEFT", max_length=16)),
                ("join_condition", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_relationships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["source_table"]},
        ),
        migrations.CreateModel(
            name="SemanticExample",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("question", models.TextField()),
                ("expected_columns", models.JSONField(blank=True, default=list)),
                ("expected_filters", models.JSONField(blank=True, default=list)),
                ("expected_query_pattern", models.TextField(blank=True, default="")),
                ("language_code", models.CharField(blank=True, default="en", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_examples",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SemanticSchemaSnapshot",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("reviewed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_snapshots",
                        to="chatbot.dataconnection",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="semantictable",
            index=models.Index(fields=["owner", "database_name"], name="chatbot_sem_tbl_owner_db"),
        ),
        migrations.AddConstraint(
            model_name="semantictable",
            constraint=models.UniqueConstraint(
                fields=("owner", "database_name", "table_name"),
                name="chatbot_sem_table_owner_db_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="semanticcolumn",
            constraint=models.UniqueConstraint(
                fields=("semantic_table", "physical_column"),
                name="chatbot_sem_col_table_phys",
            ),
        ),
        migrations.AddConstraint(
            model_name="semanticsynonym",
            constraint=models.UniqueConstraint(
                fields=("semantic_column", "synonym", "language_code"),
                name="chatbot_sem_syn_col_lang",
            ),
        ),
    ]
