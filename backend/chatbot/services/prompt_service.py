"""Database-backed prompt templates with safe {{variable}} substitution."""
import re

from ..models import PromptTemplate, PromptVersion

_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

# Built-in fallbacks when the admin database has no row yet (migration/seed pending).
_BUILTIN = {
    "chat.grounded.system": (
        "You answer only from the database results, document excerpts, and website excerpts "
        "in the latest user message. Never add facts from general knowledge."
    ),
    "chat.general.system": "You are a helpful assistant. Be concise and complete.",
    "chat.grounded.user": (
        "Answer using ONLY the database results, document excerpts, and website excerpts below. "
        "Do not use outside knowledge. "
        "If a database lookup failed or returned no rows, say that plainly.\n"
        "{{cite_instruction}}"
        "If none of these sources answer the question, reply with exactly this sentence:\n"
        "{{not_found_message}}\n\n"
        "{{context_sections}}\n\nQuestion: {{question}}"
    ),
    "chat.cite.widget": (
        "Answer in short friendly sentences a website visitor can read. "
        "Do not include citation brackets.\n"
    ),
    "chat.cite.app": (
        "Cite a document or website fact as [title#chunk_index]. "
        "Describe database rows in plain sentences without inventing extra rows.\n"
    ),
}


def template_variables(content: str) -> list:
    seen = []
    for match in _VAR.finditer(content or ""):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def render_template(content: str, variables: dict) -> str:
    required = template_variables(content)
    missing = [name for name in required if name not in (variables or {})]
    if missing:
        raise ValueError(f"Missing prompt variables: {', '.join(missing)}")

    def replace(match):
        key = match.group(1)
        value = variables.get(key, "")
        return str(value)

    return _VAR.sub(replace, content or "")


def _db_alias():
    from django.conf import settings

    return "admin" if "admin" in settings.DATABASES else "default"


def get_prompt_record(slug: str) -> tuple[str, int]:
    """Return (content, version). Uses built-in fallback when inactive or missing."""
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Prompt slug is required.")
    alias = _db_alias()
    row = (
        PromptTemplate.objects.using(alias)
        .filter(slug=slug, active=True)
        .first()
    )
    if row is None:
        if slug in _BUILTIN:
            return _BUILTIN[slug], 0
        raise ValueError(f"No prompt configured for {slug}.")

    version = (
        PromptVersion.objects.using(alias)
        .filter(prompt=row, version=row.active_version)
        .first()
    )
    if version is None:
        version = PromptVersion.objects.using(alias).filter(prompt=row).order_by("-version").first()
    if version is None:
        if slug in _BUILTIN:
            return _BUILTIN[slug], 0
        raise ValueError(f"Prompt {slug} has no versions.")
    return version.content, version.version


def get_prompt(slug: str, variables=None) -> tuple[str, int]:
    content, version = get_prompt_record(slug)
    rendered = render_template(content, variables or {})
    return rendered, version


def list_prompts():
    alias = _db_alias()
    rows = PromptTemplate.objects.using(alias).all()
    payload = []
    for row in rows:
        version = (
            PromptVersion.objects.using(alias)
            .filter(prompt=row, version=row.active_version)
            .first()
        )
        payload.append(
            {
                "slug": row.slug,
                "name": row.name,
                "category": row.category,
                "workflow": row.workflow,
                "description": row.description,
                "active": row.active,
                "active_version": row.active_version,
                "content": version.content if version else "",
                "variables": template_variables(version.content if version else ""),
                "updated_at": row.updated_at,
            }
        )
    return payload


def save_prompt(slug, data, user_id=None):
    alias = _db_alias()
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Prompt slug is required.")
    content = str(data.get("content") or "").strip()
    if not content:
        raise ValueError("Prompt content cannot be empty.")
    variables = template_variables(content)
    # Validate with empty strings for preview-only vars
    preview_vars = {name: "" for name in variables}
    render_template(content, preview_vars)

    row, created = PromptTemplate.objects.using(alias).get_or_create(
        slug=slug,
        defaults={
            "name": data.get("name") or slug,
            "category": data.get("category") or "chat",
            "workflow": data.get("workflow") or "chat",
            "description": str(data.get("description") or "")[:2000],
        },
    )
    if not created:
        if "name" in data:
            row.name = str(data["name"])[:200]
        if "category" in data:
            row.category = str(data["category"])[:64]
        if "workflow" in data:
            row.workflow = str(data["workflow"])[:64]
        if "description" in data:
            row.description = str(data["description"])[:2000]
        if "active" in data:
            row.active = bool(data["active"])
    row.updated_by_id = user_id
    row.save()

    latest = (
        PromptVersion.objects.using(alias).filter(prompt=row).order_by("-version").first()
    )
    next_version = (latest.version + 1) if latest else 1
    note = str(data.get("note") or "Saved from admin")[:200]
    PromptVersion.objects.using(alias).create(
        prompt=row,
        version=next_version,
        content=content,
        variables=variables,
        note=note,
        created_by_id=user_id,
    )
    row.active_version = next_version
    row.save(update_fields=["active_version", "updated_at", "updated_by_id"])
    return list_prompts()


def activate_version(slug, version, user_id=None):
    alias = _db_alias()
    row = PromptTemplate.objects.using(alias).filter(slug=slug).first()
    if row is None:
        raise ValueError("Prompt not found.")
    if not PromptVersion.objects.using(alias).filter(prompt=row, version=version).exists():
        raise ValueError("That version does not exist.")
    row.active_version = int(version)
    row.updated_by_id = user_id
    row.save(update_fields=["active_version", "updated_by_id", "updated_at"])
    return list_prompts()


def preview_prompt(slug, variables=None):
    content, version = get_prompt_record(slug)
    vars_in = variables if isinstance(variables, dict) else {}
    merged = {name: str(vars_in.get(name, f"[{name}]")) for name in template_variables(content)}
    return {"rendered": render_template(content, merged), "version": version, "variables": list(merged)}
