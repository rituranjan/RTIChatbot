"""Enforce per-plan concurrent embed visitors for the bot owner account."""
from datetime import timedelta

from django.utils import timezone

from ..models import EmbedVisitorSession

SESSION_TTL = timedelta(minutes=5)
BUSY_MESSAGE = "Too many people are chatting right now. Please try again in a few minutes."


def _cap(owner) -> int:
    from .plan_access import concurrent_users_for

    return concurrent_users_for(owner)


def _prune(owner_id: int) -> None:
    cutoff = timezone.now() - SESSION_TTL
    EmbedVisitorSession.objects.filter(owner_id=owner_id, last_seen__lt=cutoff).delete()


def admit_embed_visitor(owner, visitor_id: str, embed_bot=None) -> tuple[bool, str]:
    """
    Return (allowed, message). Existing visitor ids within the TTL always stay admitted.
    """
    cap = _cap(owner)
    if cap <= 0:
        return True, ""
    vid = str(visitor_id or "").strip()
    if not vid:
        return False, "Invalid visitor."

    _prune(owner.id)
    qs = EmbedVisitorSession.objects.filter(owner_id=owner.id)
    existing = qs.filter(visitor_id=vid).first()
    if existing:
        existing.last_seen = timezone.now()
        if embed_bot is not None:
            existing.embed_bot = embed_bot
        existing.save(update_fields=["last_seen", "embed_bot"])
        return True, ""

    active_count = qs.count()
    if active_count >= cap:
        return False, BUSY_MESSAGE

    EmbedVisitorSession.objects.create(
        owner_id=owner.id,
        visitor_id=vid,
        embed_bot=embed_bot,
    )
    return True, ""


def active_embed_count(owner) -> int:
    _prune(owner.id)
    return EmbedVisitorSession.objects.filter(owner_id=owner.id).count()
