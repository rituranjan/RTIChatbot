from django.core.management.base import BaseCommand

from chatbot.models import PromptTemplate, PromptVersion
from chatbot.services.prompt_service import template_variables


SEED = [
    {
        "slug": "chat.grounded.system",
        "name": "Grounded chat system",
        "category": "chat",
        "workflow": "chat",
        "description": "System instructions when answering from uploaded sources.",
        "content": (
            "You answer only from the database results, document excerpts, and website excerpts "
            "in the latest user message. Never add facts from general knowledge."
        ),
    },
    {
        "slug": "chat.general.system",
        "name": "General chat system",
        "category": "chat",
        "workflow": "chat",
        "description": "System instructions when no retrieved context is required.",
        "content": "You are a helpful assistant. Be concise and complete.",
    },
    {
        "slug": "chat.grounded.user",
        "name": "Grounded user message",
        "category": "chat",
        "workflow": "chat",
        "description": "User message template with retrieved context.",
        "content": (
            "Answer using ONLY the database results, document excerpts, and website excerpts below. "
            "Do not use outside knowledge. "
            "If a database lookup failed or returned no rows, say that plainly.\n"
            "{{cite_instruction}}"
            "If none of these sources answer the question, reply with exactly this sentence:\n"
            "{{not_found_message}}\n\n"
            "{{context_sections}}\n\nQuestion: {{question}}"
        ),
    },
    {
        "slug": "chat.cite.widget",
        "name": "Widget citation style",
        "category": "chat",
        "workflow": "chat",
        "description": "Citation rules for the embedded widget.",
        "content": (
            "Answer in short friendly sentences a website visitor can read. "
            "Do not include citation brackets.\n"
        ),
    },
    {
        "slug": "chat.cite.app",
        "name": "App citation style",
        "category": "chat",
        "workflow": "chat",
        "description": "Citation rules for the logged-in app chat.",
        "content": (
            "Cite a document or website fact as [title#chunk_index]. "
            "Describe database rows in plain sentences without inventing extra rows.\n"
        ),
    },
]


class Command(BaseCommand):
    help = "Seed default LLM prompt templates into the admin database."

    def handle(self, *args, **options):
        from django.conf import settings

        alias = "admin" if "admin" in settings.DATABASES else "default"
        created = 0
        for row in SEED:
            prompt, was_new = PromptTemplate.objects.using(alias).get_or_create(
                slug=row["slug"],
                defaults={
                    "name": row["name"],
                    "category": row["category"],
                    "workflow": row["workflow"],
                    "description": row["description"],
                    "active": True,
                    "is_default": True,
                },
            )
            if PromptVersion.objects.using(alias).filter(prompt=prompt).exists():
                continue
            PromptVersion.objects.using(alias).create(
                prompt=prompt,
                version=1,
                content=row["content"],
                variables=template_variables(row["content"]),
                note="Initial seed",
            )
            prompt.active_version = 1
            prompt.save(update_fields=["active_version"])
            created += 1 if was_new else 0
        self.stdout.write(self.style.SUCCESS(f"Prompt seed complete ({len(SEED)} templates, {created} new)."))
