"""Allowed parent-site domains for the website embed widget."""
from urllib.parse import urlparse

from django.conf import settings

from ..models import EmbedAllowedDomain


def normalize_embed_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Enter a domain.")
    if "://" in raw:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").strip()
    else:
        host = raw.split("/")[0].split(":")[0].strip()
    host = host.lower().strip(".")
    if not host or ".." in host or " " in host or len(host) > 253:
        raise ValueError("Enter a valid domain such as www.example.com.")
    if host in ("localhost", "127.0.0.1") or host.endswith(".local"):
        return host
    if "." not in host and host != "localhost":
        raise ValueError("Enter a full domain name such as shop.example.com.")
    return host


def max_embed_domains_for(user) -> int:
    from .plan_access import rules_for

    return max(0, int(rules_for(user).get("max_embed_domains") or 0))


def list_embed_domains(user) -> list[str]:
    return list(
        EmbedAllowedDomain.objects.filter(owner=user)
        .order_by("host")
        .values_list("host", flat=True)
    )


def embed_domains_payload(user) -> dict:
    cap = max_embed_domains_for(user)
    hosts = list_embed_domains(user)
    return {
        "max_embed_domains": cap,
        "embed_domains": hosts,
        "embed_domains_remaining": None if cap == 0 else max(0, cap - len(hosts)),
    }


def save_embed_domains(user, incoming) -> list[str]:
    if not isinstance(incoming, list):
        raise ValueError("Enter domains as a list.")
    cap = max_embed_domains_for(user)
    cleaned = []
    for item in incoming:
        host = normalize_embed_host(item)
        if host not in cleaned:
            cleaned.append(host)
    if cap > 0 and len(cleaned) > cap:
        raise ValueError(f"Your plan allows at most {cap} embed domains.")
    EmbedAllowedDomain.objects.filter(owner=user).exclude(host__in=cleaned).delete()
    for host in cleaned:
        EmbedAllowedDomain.objects.get_or_create(owner=user, host=host)
    return cleaned


def _dev_host(host: str) -> bool:
    return host in ("localhost", "127.0.0.1") or host.endswith(".local")


def parent_host_from_request(request) -> str:
    raw = (
        request.headers.get("X-Embed-Parent")
        or request.query_params.get("parent")
        or request.query_params.get("site")
        or ""
    ).strip()
    if not raw and request.data:
        raw = str(request.data.get("parent_origin") or request.data.get("site") or "").strip()
    if not raw:
        referer = str(request.headers.get("Referer") or "").strip()
        if referer:
            raw = referer
    if not raw:
        return ""
    try:
        return normalize_embed_host(raw)
    except ValueError:
        return ""


def verify_embed_parent(owner, request) -> tuple[bool, str]:
    parent = parent_host_from_request(request)
    allowed = list_embed_domains(owner)
    cap = max_embed_domains_for(owner)

    if settings.DEBUG and parent and _dev_host(parent):
        return True, ""

    if cap == 0 and not allowed:
        return True, ""

    if not allowed:
        return False, "Add an allowed domain in User settings → Model before using the embed on your website."

    if not parent:
        return False, "This embed must be opened from an allowed website domain."

    if host_allowed(parent, allowed):
        return True, ""

    return False, "This website domain is not allowed to use this chatbot."


def host_allowed(parent: str, allowed: list[str]) -> bool:
    parent = normalize_embed_host(parent) if parent else ""
    for item in allowed:
        if parent == item:
            return True
        if parent.endswith(f".{item}"):
            return True
    return False
