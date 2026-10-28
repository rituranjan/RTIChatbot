from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from chatbot.models import AppSetting


class Command(BaseCommand):
    help = "Create the admin settings database and copy global settings into it once."

    def handle(self, *args, **options):
        if "admin" not in settings.DATABASES:
            self.stdout.write("Admin settings stay on the main database in this environment.")
            return
        try:
            call_command("migrate", database="admin", interactive=False, verbosity=1)
        except Exception as exc:
            self.stderr.write(f"Admin migrate could not finish ({exc}). Creating the settings tables directly.")
        self._create_tables()
        self._copy_settings()

    def _create_tables(self):
        from django.db import connections

        from chatbot.models import ErrorEvent, PromptTemplate, PromptVersion

        existing = set(connections["admin"].introspection.table_names())
        with connections["admin"].schema_editor() as editor:
            for model in (AppSetting, ErrorEvent, PromptTemplate, PromptVersion):
                if model._meta.db_table not in existing:
                    editor.create_model(model)

    def _copy_settings(self):
        if AppSetting.objects.using("admin").filter(pk=1).exists():
            self.stdout.write("Admin and global settings are already in their own database.")
            return
        source = None
        try:
            source = AppSetting.objects.using("default").filter(pk=1).first()
        except Exception:
            source = None
        if source is None:
            AppSetting.objects.using("admin").create(pk=1)
            self.stdout.write(self.style.SUCCESS("Created the admin settings database."))
            return
        values = {}
        for field in source._meta.concrete_fields:
            if field.primary_key:
                continue
            values[field.attname] = getattr(source, field.attname)
        try:
            AppSetting.objects.using("admin").create(pk=1, **values)
        except Exception:
            raise CommandError("Could not copy global settings into the admin database.") from None
        self.stdout.write(self.style.SUCCESS("Copied global settings into the admin database."))
