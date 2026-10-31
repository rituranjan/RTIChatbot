"""URL checks for a same-site crawl. No network except the public-host lookup."""
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js",
    ".pdf", ".zip", ".gz", ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".eot",
    ".xml", ".json", ".txt", ".rss", ".atom",
}


class WebUrlError(ValueError):
    pass


def site_key(hostname: str) -> str:
    host = (hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        return host[4:]
    return host


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise WebUrlError("Enter a full http or https address, such as https://rtiguru.com/.")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
    ]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urlencode(query), ""))


def is_page_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return not any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


def assert_public_host(hostname: str) -> None:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".local"):
        raise WebUrlError("That address is not a public website.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise WebUrlError(f"Could not resolve {host}.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise WebUrlError("That address is not a public website.")


_URL_BODY = re.compile(r"https?://[^\s<>\"']+", re.I)


def extract_urls_from_paste(text: str) -> list[str]:
    """Pull http(s) URLs from free text, including URLs pasted back-to-back without spaces."""
    raw = (text or "").strip()
    if not raw:
        return []
    chunks = re.split(r"(?=https?://)", raw, flags=re.I)
    seen = set()
    urls = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _URL_BODY.match(chunk)
        if not match:
            continue
        cand = match.group(0).rstrip(".,;)")
        try:
            cleaned = normalize_url(cand)
        except WebUrlError:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        urls.append(cleaned)
    return urls
