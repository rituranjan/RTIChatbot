import re

from django.conf import settings
from django.db.models import Q

from ..models import Document, DocumentChunk
from .ingestion_service import cosine, unpack_vector
from .llm_service import LLMError, embed_text


def accessible_documents(user):
    """Documents this user may search: their uploads and enabled shared folders."""
    return Document.objects.filter(
        Q(owner=user) | Q(folder_source__isnull=False, folder_source__enabled=True)
    ).filter(status=Document.STATUS_READY)


_QUESTION_WORDS = {
    "who", "what", "how", "why", "when", "where", "which", "the", "and", "for",
    "with", "from", "that", "this", "your", "about", "does", "did", "are", "was",
    "were", "have", "has", "can", "you", "please", "tell", "give", "show",
}


def _keyword_score(query: str, content: str) -> float:
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", query.lower())
        if len(word) > 2 and word not in _QUESTION_WORDS
    ]
    if not words or not content:
        return 0.0
    hits = sum(
        1 for word in words if re.search(rf"\b{re.escape(word)}\b", content.lower())
    )
    return hits / len(words)


def retrieve(user, query: str, top_k=None, document_ids=None):
    """Return the best matching chunks, plus their neighbors, for this user."""
    top_k = top_k or settings.RETRIEVAL_TOP_K
    query = (query or "").strip()
    if not query:
        return []

    docs = accessible_documents(user)
    if document_ids:
        docs = docs.filter(id__in=document_ids)
    if not docs.exists():
        return []

    qvec = []
    try:
        qvec = embed_text(query) or []
    except LLMError:
        qvec = []

    chunks = list(
        DocumentChunk.objects.filter(document__in=docs).select_related("document")
    )
    by_key = {(chunk.document_id, chunk.chunk_index): chunk for chunk in chunks}

    scored = []
    for chunk in chunks:
        vec = unpack_vector(chunk.embedding)
        embed_score = cosine(qvec, vec) if qvec and vec else 0.0
        score = embed_score + (0.25 * _keyword_score(query, chunk.content))
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    seeds = scored[:top_k]
    if not seeds:
        return []

    # Neighboring chunks often hold the rest of a sentence that was split.
    chosen = {}
    for score, chunk in seeds:
        for offset in (-1, 0, 1):
            key = (chunk.document_id, chunk.chunk_index + offset)
            neighbor = by_key.get(key)
            if neighbor is None:
                continue
            previous = chosen.get(key)
            if previous is None or score > previous[0]:
                chosen[key] = (score if offset == 0 else score - 0.01, neighbor)

    ranked = sorted(chosen.values(), key=lambda item: item[0], reverse=True)[:12]
    best_score = ranked[0][0]
    floor = max(0.45, best_score - 0.2)
    ranked = [item for item in ranked if item[0] >= floor] or ranked[:3]
    ordered = sorted(
        ranked,
        key=lambda item: (item[1].document.title, item[1].chunk_index),
    )

    results = []
    for score, chunk in ordered:
        results.append(
            {
                "score": round(float(score), 4),
                "document_id": str(chunk.document_id),
                "document_title": chunk.document.title,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "page": chunk.page,
            }
        )
    return results
