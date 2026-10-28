import logging

from django.conf import settings

from ..models import WebSource
from .web_embed import embed_query
from .web_vectors import search_websites

log = logging.getLogger(__name__)


def retrieve_websites(user, query: str, top_k=None):
    """Nearest crawled page sections from this user's own vector collection."""
    query = (query or "").strip()
    if not query:
        return []
    website_ids = list(
        WebSource.objects.filter(owner=user, enabled=True)
        .exclude(chunk_count=0)
        .values_list("id", flat=True)
    )
    if not website_ids:
        return []
    try:
        vector = embed_query(query)
        return search_websites(
            user.id,
            vector,
            [str(item) for item in website_ids],
            top_k or settings.RETRIEVAL_TOP_K,
        )
    except Exception:
        log.exception("Website search failed for user %s", user.id)
        return []
