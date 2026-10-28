"""Turn a crawled HTML page into text and same-site links."""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .web_urls import is_page_url, normalize_url, site_key

_SPACE = re.compile(r"[ \t]+")


def html_to_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "canvas"]):
        tag.decompose()
    title = ""
    if soup.title:
        title = _SPACE.sub(" ", soup.title.get_text(" ", strip=True)).strip()[:300]
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines = []
    for line in root.get_text("\n", strip=True).splitlines():
        cleaned = _SPACE.sub(" ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return title, "\n".join(lines)[:30000]


def links_from_html(html: str, page_url: str, site: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    found = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(page_url, href)
        try:
            cleaned = normalize_url(absolute)
        except ValueError:
            continue
        host = urlsplit(cleaned).hostname or ""
        if site_key(host) != site or not is_page_url(cleaned) or cleaned in seen:
            continue
        seen.add(cleaned)
        found.append(cleaned)
    return found
