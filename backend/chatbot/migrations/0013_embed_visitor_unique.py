from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0012_llm_usage_index_names"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(embed_bot__isnull=False) & ~models.Q(visitor_id=""),
                fields=("embed_bot", "visitor_id"),
                name="chatbot_embed_visitor_unique",
            ),
        ),
    ]
