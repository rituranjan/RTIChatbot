"""Run the owner's saved SQL for a chat question."""
import re

from ..models import SqlKeywordQuery
from .external_db import run_select

_QUESTION_WORDS = {
    "who", "what", "how", "why", "when", "where", "which", "the", "and", "for",
    "with", "from", "that", "this", "your", "about", "does", "did", "are", "was",
    "were", "have", "has", "can", "you", "please", "tell", "give", "show", "is",
}
_SECRET = re.compile(r"password|passwd|secret|token|api_key|apikey", re.I)


def _public_rows(rows):
    cleaned = []
    for row in rows:
        visible = {key: value for key, value in row.items() if not _SECRET.search(str(key))}
        cleaned.append(visible or row)
    return cleaned


def _question_word(text):
    words = [
        word
        for word in re.findall(r"[a-z0-9_]+", (text or "").lower())
        if len(word) > 2 and word not in _QUESTION_WORDS
    ]
    return words[0] if words else ""


def lookup_keywords(owner, message, limit_queries=3):
    text = (message or "").lower()
    if not text.strip():
        return []
    queries = list(
        SqlKeywordQuery.objects.filter(owner=owner, enabled=True, connection__enabled=True)
        .select_related("connection")
        .order_by("name")
    )
    chosen = []
    for query in queries:
        keywords = [str(item).strip() for item in (query.keywords or []) if str(item).strip()]
        matched = next((word for word in keywords if word.lower() in text), "")
        if matched:
            chosen.append((query, matched))
    if not chosen:
        # A normal question such as "who is ritu" still uses the connected database.
        word = _question_word(text)
        chosen = [(query, word) for query in queries]

    found = []
    for query, matched in chosen[:limit_queries]:
        try:
            rows = _public_rows(
                run_select(
                    query.connection.engine,
                    query.connection.connection_string,
                    query.sql_text,
                    keyword=matched,
                )
            )
            found.append(
                {
                    "name": query.name,
                    "keyword": matched,
                    "rows": rows,
                    "error": "",
                }
            )
        except Exception as exc:  # noqa: BLE001
            detail = str(exc).splitlines()[0][:240]
            found.append(
                {
                    "name": query.name,
                    "keyword": matched,
                    "rows": [],
                    "error": detail or "The database lookup failed.",
                }
            )
    return found
