import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def default_plan_days():
    return {"basic": 0, "silver": 0, "gold": 0, "diamond": 0}


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0006_admin_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsetting",
            name="plan_days",
            field=models.JSONField(default=default_plan_days),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="owner",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="embed_bot",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversations",
                to="chatbot.embedbot",
            ),
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "plan",
                    models.CharField(
                        choices=[
                            ("basic", "Basic"),
                            ("silver", "Silver"),
                            ("gold", "Gold"),
                            ("diamond", "Diamond"),
                        ],
                        default="basic",
                        max_length=16,
                    ),
                ),
                ("database_name", models.CharField(max_length=63, unique=True)),
                ("engine", models.CharField(default="sqlite", max_length=16)),
                ("ready", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True, default="")),
                ("migrated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "user profile"},
        ),
    ]
