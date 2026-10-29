from django.db import migrations, models


def _ensure_llm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='chatbot_llmusagelog'"
        )
        existing = {row[0] for row in cursor.fetchall()}
        if "chatbot_llm_user_created_idx" not in existing:
            cursor.execute(
                "CREATE INDEX chatbot_llm_user_created_idx "
                "ON chatbot_llmusagelog (user_id, created_at DESC)"
            )
        long_wf = "chatbot_llm_workflow_created_idx"
        short_wf = "chatbot_llm_wf_created_idx"
        if long_wf in existing:
            cursor.execute(f"DROP INDEX {long_wf}")
        if short_wf not in existing:
            cursor.execute(
                f"CREATE INDEX {short_wf} "
                "ON chatbot_llmusagelog (workflow, created_at DESC)"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("chatbot", "0011_chat_languages"),
    ]

    operations = [
        migrations.RunPython(_ensure_llm_indexes, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="llmusagelog",
                    name="chatbot_llm_workflow_created_idx",
                ),
                migrations.AddIndex(
                    model_name="llmusagelog",
                    index=models.Index(
                        fields=["workflow", "-created_at"],
                        name="chatbot_llm_wf_created_idx",
                    ),
                ),
            ],
        ),
    ]
