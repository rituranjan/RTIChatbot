from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0010_prompts_llm_gateway"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsetting",
            name="language_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="userchatsetting",
            name="preferred_language",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
