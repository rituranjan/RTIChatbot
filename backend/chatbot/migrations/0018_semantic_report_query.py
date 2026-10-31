import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0017_semantic_sql"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticengineconfig",
            name="report_query",
            field=models.ForeignKey(
                blank=True,
                help_text="Canonical SELECT from SQL keywords; uses that query's database connection.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="semantic_reports",
                to="chatbot.sqlkeywordquery",
            ),
        ),
    ]
