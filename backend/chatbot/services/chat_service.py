import logging

from django.conf import settings

from ..models import Message, WebSource
from .llm_service import chat_completion
from .profile_service import assert_profile
from .retrieval_service import accessible_documents, retrieve
from .sql_lookup import lookup_keywords
from .admin_settings import maybe_purge, not_found_reply
from .web_retrieve import retrieve_websites

log = logging.getLogger(__name__)


def _lookup_text(lookups):
    blocks = []
    for item in lookups:
        if item["error"]:
            blocks.append(f"Database lookup {item['name']} failed: {item['error']}")
            continue
        label = f" for {item['keyword']}" if item.get("keyword") else ""
        if not item["rows"]:
            blocks.append(f"Database lookup {item['name']}{label} returned no rows.")
            continue
        lines = [f"Database lookup {item['name']}{label}:"]
        for row in item["rows"]:
            lines.append(" | ".join(f"{key}: {value}" for key, value in row.items()))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def generate_reply(owner, conversation, user_text, strict=None, style="app"):
    """Save the user turn and answer only from uploaded files and keyword SQL."""
    if strict is None:
        strict = settings.STRICT_DOCUMENTS_DEFAULT

    assert_profile(conversation)
    try:
        maybe_purge()
    except Exception:
        log.exception("Scheduled data deletion failed")

    Message.objects.create(
        conversation=conversation, role=Message.ROLE_USER, content=user_text
    )

    sources = retrieve(owner, user_text, top_k=settings.RETRIEVAL_TOP_K)
    web_sources = retrieve_websites(owner, user_text, top_k=settings.RETRIEVAL_TOP_K)
    lookups = lookup_keywords(owner, user_text)
    has_documents = accessible_documents(owner).exists()
    has_web = (
        WebSource.objects.filter(owner=owner, enabled=True).exclude(chunk_count=0).exists()
    )
    crawling = WebSource.objects.filter(
        owner=owner, enabled=True, status=WebSource.STATUS_CRAWLING
    ).exists()

    history = list(conversation.messages.order_by("created_at").values("role", "content"))
    prior_questions = [
        {"role": "user", "content": item["content"]}
        for item in history[:-1]
        if item["role"] == Message.ROLE_USER
    ][-4:]

    answer = None
    found = bool(sources or lookups or web_sources)
    missing = not_found_reply(owner)
    if strict and not has_documents and not lookups and not has_web:
        if crawling:
            answer = "The website is still being read. Ask again in a moment."
        elif style == "widget":
            answer = missing
        else:
            answer = (
                "Upload a file, connect your database, or add a website. "
                "I only answer from those sources."
            )
    elif strict and not found:
        answer = missing
    else:
        if found:
            sections = []
            lookup_text = _lookup_text(lookups)
            if lookup_text:
                sections.append("Database results:\n" + lookup_text)
            if sources:
                sections.append(
                    "Document excerpts:\n"
                    + "\n\n".join(
                        f"[{s['document_title']}#{s['chunk_index']}]\n{s['content']}"
                        for s in sources
                    )
                )
            if web_sources:
                sections.append(
                    "Website excerpts:\n"
                    + "\n\n".join(
                        f"[{s['document_title']}#{s['chunk_index']}] {s['url']}\n{s['content']}"
                        for s in web_sources
                    )
                )
            cite = (
                "Answer in short friendly sentences a website visitor can read. "
                "Do not include citation brackets.\n"
                if style == "widget"
                else "Cite a document or website fact as [title#chunk_index]. "
                "Describe database rows in plain sentences without inventing extra rows.\n"
            )
            grounded = (
                "Answer using ONLY the database results, document excerpts, and website excerpts below. "
                "Do not use outside knowledge. "
                "If a database lookup failed or returned no rows, say that plainly.\n"
                + cite
                + "If none of these sources answer the question, reply with exactly this sentence:\n"
                + missing
                + "\n\n"
                + "\n\n".join(sections)
                + f"\n\nQuestion: {user_text}"
            )
            messages = prior_questions + [{"role": "user", "content": grounded}]
            system_prompt = (
                "You answer only from the database results, document excerpts, and website excerpts "
                "in the latest user message. Never add facts from general knowledge."
            )
        else:
            messages = prior_questions + [{"role": "user", "content": user_text}]
            system_prompt = "You are a helpful assistant."

        answer = chat_completion(messages, system_prompt=system_prompt, temperature=0)

    if not answer:
        answer = "(The model returned an empty response.)"

    msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=answer,
        sources=[
            {k: s[k] for k in ("document_id", "document_title", "chunk_index", "score")}
            for s in sources
        ]
        + [
            {
                "document_id": "",
                "document_title": f"sql:{item['name']}",
                "chunk_index": 0,
                "score": 1,
            }
            for item in lookups
        ]
        + [
            {
                "document_id": s.get("website_id") or "",
                "document_title": s["document_title"],
                "chunk_index": s["chunk_index"],
                "score": s["score"],
            }
            for s in web_sources
        ],
    )
    conversation.save(update_fields=["updated_at"])
    return msg
