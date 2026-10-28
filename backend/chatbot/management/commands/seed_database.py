from django.core.management.base import BaseCommand

from django.contrib.auth import get_user_model

from chatbot.embed_views import ensure_embed_bot
from chatbot.services.database_service import ensure_sample_records


class Command(BaseCommand):
    help = "Insert sample database rows that are not already stored."

    def handle(self, *args, **options):
        created = ensure_sample_records()
        if created:
            self.stdout.write(self.style.SUCCESS(f"Inserted {created} database records."))
        else:
            self.stdout.write("Database records already present.")
        User = get_user_model()
        admin, _created = User.objects.get_or_create(
            username="RRGupta",
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("H@ppy123")
        admin.save()
        ensure_embed_bot(admin)
        self.stdout.write("Menu admin RRGupta is ready.")
        owner = User.objects.order_by("id").first()
        if owner:
            bot = ensure_embed_bot(owner)
            self.stdout.write(f"Embed bot {bot.id}")
