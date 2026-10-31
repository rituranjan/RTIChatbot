import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0013_embed_visitor_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmbedVisitorSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("visitor_id", models.CharField(max_length=64)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                (
                    "embed_bot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="visitor_sessions",
                        to="chatbot.embedbot",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embed_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="embedvisitorsession",
            constraint=models.UniqueConstraint(
                fields=("owner", "visitor_id"),
                name="chatbot_embed_session_owner_visitor",
            ),
        ),
        migrations.AddIndex(
            model_name="embedvisitorsession",
            index=models.Index(fields=["owner", "-last_seen"], name="chatbot_embed_sess_seen_idx"),
        ),
    ]
