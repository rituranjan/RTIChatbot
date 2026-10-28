import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0008_openrouter_plans"),
    ]

    operations = [
        migrations.CreateModel(
            name="ErrorEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("source", models.CharField(max_length=16)),
                ("path", models.CharField(blank=True, default="", max_length=500)),
                ("method", models.CharField(blank=True, default="", max_length=16)),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("message", models.TextField(blank=True, default="")),
                ("stack", models.TextField(blank=True, default="")),
                ("user_id", models.IntegerField(blank=True, null=True)),
                ("username", models.CharField(blank=True, default="", max_length=150)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("user_agent", models.CharField(blank=True, default="", max_length=400)),
                ("screenshot_path", models.CharField(blank=True, default="", max_length=500)),
            ],
            options={
                "verbose_name": "error event",
                "ordering": ["-created_at"],
            },
        ),
    ]
