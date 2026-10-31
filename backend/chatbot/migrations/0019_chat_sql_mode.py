import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0018_semantic_report_query"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticengineconfig",
            name="chat_sql_mode",
            field=models.CharField(
                choices=[("keywords", "keywords"), ("semantic", "semantic")],
                default="keywords",
                max_length=16,
            ),
        ),
    ]
