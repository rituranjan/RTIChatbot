"""Read a public website and store its pages in that user's Qdrant collection."""
import logging
import re
import threading
import time
import uuid
from urllib.parse import urljoin, urlsplit

import requests
from django.db import close_old_connections

from ..models import WebPage, WebSource
from .ingestion_service import split_text
from .web_embed import embed_passages
from .web_html import html_to_text, links_from_html
from .web_urls import WebUrlError, assert_public_host, is_page_url, normalize_url, site_key
from .web_vectors import delete_website, upsert_chunks

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; ChatbotRAG/1.0)"
MAX_BYTES = 1_500_000
MAX_SITEMAPS = 40
PAGE_FLOOR = 80
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


def schedule_crawl(source_id) -> None:
    token = uuid.uuid4()
    WebSource.objects.filter(id=source_id).update(
        status=WebSource.STATUS_CRAWLING,
        error="",
        message="Starting crawl",
        crawl_token=token,
        page_count=0,
        chunk_count=0,
    )
    WebPage.objects.filter(source_id=source_id).delete()
    threading.Thread(
        target=_run,
        args=(str(source_id), str(token)),
        daemon=True,
        name=f"web-crawl-{source_id}",
    ).start()


def _run(source_id: str, token: str) -> None:
    close_old_connections()
    try:
        _crawl(source_id, token)
    except Exception as exc:  # noqa: BLE001
        log.exception("Website crawl failed")
        _finish(source_id, token, WebSource.STATUS_FAILED, error=str(exc).splitlines()[0][:500])
    finally:
        close_old_connections()


def _current(source_id, token):
    source = WebSource.objects.filter(id=source_id, crawl_token=token).first()
    return source


def _finish(source_id, token, status, error="", message=None, pages=None, chunks=None):
    source = _current(source_id, token)
    if source is None:
        return
    source.status = status
    source.error = error
    if message is not None:
        source.message = message[:300]
    if pages is not None:
        source.page_count = pages
    if chunks is not None:
        source.chunk_count = chunks
    source.save()


def _crawl(source_id: str, token: str) -> None:
    source = _current(source_id, token)
    if source is None:
        return
    start = normalize_url(source.url)
    assert_public_host(urlsplit(start).hostname)
    site = site_key(urlsplit(start).hostname)
    delete_website(source.owner_id, source.id)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    public_hosts = {}

    def host_ok(hostname: str) -> bool:
        if hostname not in public_hosts:
            try:
                assert_public_host(hostname)
                public_hosts[hostname] = True
            except WebUrlError:
                public_hosts[hostname] = False
        return public_hosts[hostname]

    queue = []
    seen = set()

    def add(url: str) -> None:
        if url in seen or not is_page_url(url):
            return
        host = urlsplit(url).hostname or ""
        if site_key(host) != site or not host_ok(host):
            return
        seen.add(url)
        queue.append(url)

    add(start)
    for url in _sitemap_urls(session, start, site, host_ok):
        add(url)

    pages = 0
    chunks = 0
    limit = max(1, min(int(source.max_pages or 300), 400))
    deadline = time.monotonic() + 900

    while queue and pages < limit and time.monotonic() < deadline:
        if _current(source_id, token) is None:
            return
        url = queue.pop(0)
        try:
            status, body, final_url = _fetch(session, url, site, host_ok)
        except Exception as exc:  # noqa: BLE001
            if url == start and pages == 0:
                raise
            log.info("Skip %s: %s", url, exc)
            continue
        if status != 200 or not body:
            continue
        for link in links_from_html(body, final_url, site):
            add(link)
        title, text = html_to_text(body)
        if len(text) < PAGE_FLOOR:
            continue
        stored = _index_page(source, final_url, title, text)
        if not stored:
            continue
        pages += 1
        chunks += stored
        WebSource.objects.filter(id=source_id, crawl_token=token).update(
            page_count=pages,
            chunk_count=chunks,
            message=f"Indexed {pages} pages, {chunks} sections",
        )
        time.sleep(0.1)

    if pages == 0:
        _finish(
            source_id,
            token,
            WebSource.STATUS_FAILED,
            error="No readable pages were found on that website.",
            message="No pages indexed",
        )
        return
    note = f"Indexed {pages} pages, {chunks} sections."
    if queue and pages >= limit:
        note = f"Indexed {pages} pages (the {limit} page limit). Raise the limit and read it again for the rest."
    _finish(
        source_id,
        token,
        WebSource.STATUS_READY,
        message=note,
        pages=pages,
        chunks=chunks,
    )


def _index_page(source, url: str, title: str, text: str) -> int:
    parts = split_text(text)
    if not parts:
        return 0
    vectors = embed_passages([f"{title}\n{part}" if title else part for part in parts])
    if len(vectors) != len(parts):
        return 0
    rows = [
        {
            "vector": vector,
            "url": url[:500],
            "title": (title or url)[:300],
            "chunk_index": index,
            "content": part,
        }
        for index, (part, vector) in enumerate(zip(parts, vectors))
    ]
    upsert_chunks(source.owner_id, source.id, rows)
    WebPage.objects.update_or_create(
        source=source,
        url=url[:500],
        defaults={"title": (title or "")[:300], "chunk_count": len(rows)},
    )
    return len(rows)


def _fetch(session, url: str, site: str, host_ok) -> tuple[int, str, str]:
    current = url
    for _ in range(5):
        host = urlsplit(current).hostname or ""
        if site_key(host) != site or not host_ok(host):
            raise WebUrlError("The page left the website.")
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


def _sitemap_urls(session, start: str, site: str, host_ok) -> list[str]:
    origin = f"{urlsplit(start).scheme}://{urlsplit(start).netloc}"
    pending = [f"{origin}/sitemap.xml"]
    pages = []
    seen_maps = set()
    while pending and len(seen_maps) < MAX_SITEMAPS and len(pages) < 2000:
        map_url = pending.pop(0)
        if map_url in seen_maps:
            continue
        seen_maps.add(map_url)
        try:
            response = session.get(map_url, timeout=(5, 20))
            response.raise_for_status()
            text = response.text[:2_000_000]
        except requests.RequestException:
            continue
        for loc in _LOC.findall(text):
            loc = loc.strip()
            try:
                cleaned = normalize_url(loc)
            except WebUrlError:
                continue
            host = urlsplit(cleaned).hostname or ""
            if site_key(host) != site or not host_ok(host):
                continue
            if cleaned.lower().endswith(".xml"):
                pending.append(cleaned)
            elif is_page_url(cleaned):
                pages.append(cleaned)
    return pages
