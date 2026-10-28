import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chatbot", "0005_website"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppSetting",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ("retention_days", models.PositiveIntegerField(default=0)),
                (
                    "not_found_message",
                    models.TextField(
                        default="I could not find that in your uploaded files or websites."
                    ),
                ),
                ("last_purge_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"verbose_name": "app setting"},
        ),
        migrations.CreateModel(
            name="UserChatSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("not_found_message", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_setting",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "user chat setting"},
        ),
    ]
