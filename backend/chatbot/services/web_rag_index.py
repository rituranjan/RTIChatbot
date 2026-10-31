"""Index a single pasted page into the user's Qdrant collection (high priority)."""
import logging
import threading
import uuid
from urllib.parse import urljoin, urlsplit

import requests
from django.db import close_old_connections

from ..models import WebRagPage
from .ingestion_service import split_text
from .web_crawl import PAGE_FLOOR, USER_AGENT
from .web_embed import embed_passages
from .web_html import html_to_text
from .web_urls import WebUrlError, assert_public_host, normalize_url, site_key
from .web_vectors import delete_website, upsert_chunks

log = logging.getLogger(__name__)

MAX_BYTES = 1_500_000


def schedule_rag_page(page_id) -> None:
    token = uuid.uuid4()
    WebRagPage.objects.filter(id=page_id).update(
        status=WebRagPage.STATUS_CRAWLING,
        error="",
        message="Indexing page",
        index_token=token,
        chunk_count=0,
    )
    thread = threading.Thread(
        target=_run,
        args=(str(page_id), str(token)),
        daemon=True,
        name=f"web-rag-page-{page_id}",
    )
    thread.start()


def _run(page_id: str, token: str) -> None:
    close_old_connections()
    try:
        _index(page_id, token)
    except Exception as exc:  # noqa: BLE001
        log.exception("RAG page index failed")
        _finish(page_id, token, WebRagPage.STATUS_FAILED, error=str(exc).splitlines()[0][:500])
    finally:
        close_old_connections()


def _current(page_id, token):
    return WebRagPage.objects.filter(id=page_id, index_token=token).first()


def _finish(page_id, token, status, error="", message=None, chunks=None, title=None):
    page = _current(page_id, token)
    if page is None:
        return
    page.status = status
    page.error = error
    if message is not None:
        page.message = message[:300]
    if chunks is not None:
        page.chunk_count = chunks
    if title is not None:
        page.title = (title or "")[:300]
    page.save()


def _index(page_id: str, token: str) -> None:
    page = _current(page_id, token)
    if page is None:
        return
    url = normalize_url(page.url)
    host = urlsplit(url).hostname or ""
    assert_public_host(host)
    delete_website(page.owner_id, page.id)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    site = site_key(host)
    status, body, final_url = _fetch(session, url, site)
    if status != 200 or not body:
        raise WebUrlError("That page could not be read.")
    title, text = html_to_text(body)
    if len(text) < PAGE_FLOOR:
        raise WebUrlError("That page did not contain enough readable text.")
    parts = split_text(text)
    if not parts:
        raise WebUrlError("That page did not contain enough readable text.")
    vectors = embed_passages([f"{title}\n{part}" if title else part for part in parts])
    if len(vectors) != len(parts):
        raise WebUrlError("Embedding failed for that page.")
    rows = [
        {
            "vector": vector,
            "url": final_url[:500],
            "title": (title or final_url)[:300],
            "chunk_index": index,
            "content": part,
            "priority": max(int(page.priority or 0), 100),
        }
        for index, (part, vector) in enumerate(zip(parts, vectors))
    ]
    upsert_chunks(page.owner_id, page.id, rows)
    _finish(
        page_id,
        token,
        WebRagPage.STATUS_READY,
        message=f"Indexed {len(rows)} sections",
        chunks=len(rows),
        title=title or final_url,
    )


def _fetch(session, url: str, site: str) -> tuple[int, str, str]:
    current = url
    for _ in range(5):
        host = urlsplit(current).hostname or ""
        if site_key(host) != site:
            raise WebUrlError("The page left the allowed host.")
        assert_public_host(host)
        response = session.get(current, allow_redirects=False, timeout=(5, 20), stream=True)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location") or ""
            response.close()
            if not location:
                raise WebUrlError("Redirect had no destination.")
            current = normalize_url(urljoin(current, location))
            continue
        body = _read_limited(response)
        content_type = response.headers.get("Content-Type", "")
        response.close()
        if "html" not in content_type.lower() and "<html" not in body[:500].lower():
            return response.status_code, "", current
        return response.status_code, body, current
    raise WebUrlError("Too many redirects.")


def _read_limited(response) -> str:
    import re

    chunks = []
    total = 0
    for block in response.iter_content(65536):
        if not block:
            continue
        total += len(block)
        if total > MAX_BYTES:
            break
        chunks.append(block)
    raw = b"".join(chunks)
    charset = "utf-8"
    match = re.search(r"charset=([\w.-]+)", response.headers.get("Content-Type", ""), re.I)
    if match:
        charset = match.group(1)
    return raw.decode(charset, errors="replace")
