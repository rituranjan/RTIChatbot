"""Global retention and the per-user sentence used when nothing is found."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models import AppSetting, Conversation, Document, UserChatSetting, UserProfile
from .tenant_db import postgres_enabled, register_database

DEFAULT_NOT_FOUND = "I could not find that in your uploaded files or websites."
PURGE_GAP = timedelta(hours=6)


def load_settings() -> AppSetting:
    row, _ = AppSetting.objects.get_or_create(
        pk=1,
        defaults={"not_found_message": DEFAULT_NOT_FOUND},
    )
    return row


def not_found_reply(owner) -> str:
    custom = ""
    setting = UserChatSetting.objects.filter(user=owner).first()
    if setting:
        custom = (setting.not_found_message or "").strip()
    if custom:
        return custom[:2000]
    global_message = (load_settings().not_found_message or "").strip()
    return global_message[:2000] or DEFAULT_NOT_FOUND


def plan_schedule(config=None) -> dict:
    config = config or load_settings()
    saved = config.plan_days if isinstance(config.plan_days, dict) else {}
    schedule = {"basic": 0, "silver": 0, "gold": 0, "diamond": 0}
    for key in schedule:
        try:
            schedule[key] = max(0, int(saved.get(key) or 0))
        except (TypeError, ValueError):
            schedule[key] = 0
    return schedule


def _positive_days(config) -> bool:
    if int(config.retention_days or 0) >= 1:
        return True
    return any(days >= 1 for days in plan_schedule(config).values())


def _delete_documents(owner_ids, cutoff) -> int:
    documents = Document.objects.filter(
        owner_id__in=owner_ids,
        folder_source__isnull=True,
        created_at__lt=cutoff,
    )
    count = documents.count()
    for document in documents.iterator():
        if document.file:
            document.file.delete(save=False)
        document.delete()
    return count


def _delete_chats(user, cutoff) -> int:
    aliases = ["default"]
    profile = UserProfile.objects.filter(user=user).first()
    if profile is not None and profile.ready:
        aliases.append(register_database(profile))
    removed = 0
    seen = set()
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        conversations = Conversation.objects.using(alias).filter(owner_id=user.id, updated_at__lt=cutoff)
        removed += conversations.count()
        conversations.delete()
    return removed


def purge_expired_data() -> dict:
    """Delete old chats and uploaded files. Each plan has its own number of days."""
    config = load_settings()
    if not _positive_days(config):
        return {"ran": False, "retention_days": 0, "conversations": 0, "documents": 0}
    schedule = plan_schedule(config)
    profiles = list(UserProfile.objects.select_related("user"))
    profile_ids = {profile.user_id for profile in profiles}
    conversation_count = 0
    document_count = 0
    for profile in profiles:
        days = schedule.get(profile.plan, 0)
        if days < 1:
            continue
        cutoff = timezone.now() - timedelta(days=days)
        conversation_count += _delete_chats(profile.user, cutoff)
        document_count += _delete_documents([profile.user_id], cutoff)
    legacy_days = int(config.retention_days or 0)
    if legacy_days >= 1:
        cutoff = timezone.now() - timedelta(days=legacy_days)
        legacy_users = list(
            get_user_model().objects.exclude(pk__in=profile_ids).values_list("pk", flat=True)
        )
        if legacy_users:
            conversations = Conversation.objects.using("default").filter(
                owner_id__in=legacy_users, updated_at__lt=cutoff
            )
            conversation_count += conversations.count()
            conversations.delete()
            document_count += _delete_documents(legacy_users, cutoff)
    config.last_purge_at = timezone.now()
    config.save(update_fields=["last_purge_at"])
    return {
        "ran": True,
        "retention_days": legacy_days,
        "conversations": conversation_count,
        "documents": document_count,
        "plans": schedule,
    }


def maybe_purge() -> None:
    config = load_settings()
    if not _positive_days(config):
        return
    if config.last_purge_at and timezone.now() - config.last_purge_at < PURGE_GAP:
        return
    purge_expired_data()


def settings_payload(viewer=None) -> dict:
    from .accounts import serialize_account

    config = load_settings()
    messages = {
        row.user_id: row.not_found_message
        for row in UserChatSetting.objects.all()
    }
    profiles = {row.user_id: row for row in UserProfile.objects.all()}
    users = [
        serialize_account(user, profiles.get(user.id), messages.get(user.id, ""), viewer)
        for user in get_user_model().objects.order_by("username")
    ]
    return {
        "retention_days": config.retention_days,
        "plans": plan_schedule(config),
        "database_mode": "postgresql" if postgres_enabled() else "sqlite",
        "not_found_message": config.not_found_message,
        "last_purge_at": config.last_purge_at,
        "users": users,
    }


def save_settings(data, viewer=None) -> dict:
    config = load_settings()
    if "retention_days" in data:
        try:
            days = int(data.get("retention_days"))
        except (TypeError, ValueError):
            raise ValueError("Days must be a whole number.")
        if days < 0 or days > 3650:
            raise ValueError("Days must be between 0 and 3650. Use 0 to turn deletion off.")
        config.retention_days = days
    if "plans" in data:
        incoming = data.get("plans")
        if not isinstance(incoming, dict):
            raise ValueError("Enter a number of days for each plan.")
        schedule = plan_schedule(config)
        for key in schedule:
            if key not in incoming:
                continue
            try:
                days = int(incoming.get(key))
            except (TypeError, ValueError):
                raise ValueError("Days must be a whole number.")
            if days < 0 or days > 3650:
                raise ValueError("Days must be between 0 and 3650. Use 0 to turn deletion off.")
            schedule[key] = days
        config.plan_days = schedule
    if "not_found_message" in data:
        message = str(data.get("not_found_message") or "").strip()
        if not message:
            raise ValueError("Enter the sentence to show when no information is found.")
        config.not_found_message = message[:2000]
    config.save()

    users = data.get("users")
    if isinstance(users, list):
        known = {user.id: user for user in get_user_model().objects.all()}
        for item in users:
            if not isinstance(item, dict):
                continue
            try:
                user_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            user = known.get(user_id)
            if user is None:
                continue
            message = str(item.get("not_found_message") or "").strip()[:2000]
            if message:
                UserChatSetting.objects.update_or_create(
                    user=user, defaults={"not_found_message": message}
                )
            else:
                UserChatSetting.objects.filter(user=user).delete()
    return settings_payload(viewer)
