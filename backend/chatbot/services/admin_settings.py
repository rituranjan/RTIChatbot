"""Global retention and the per-user sentence used when nothing is found."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models import AppSetting, Conversation, Document, UserChatSetting

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


def purge_expired_data() -> dict:
    """Delete chats and uploaded files older than the configured number of days, for every user."""
    config = load_settings()
    days = int(config.retention_days or 0)
    if days < 1:
        return {"ran": False, "retention_days": 0, "conversations": 0, "documents": 0}
    cutoff = timezone.now() - timedelta(days=days)
    documents = Document.objects.filter(
        owner__isnull=False,
        folder_source__isnull=True,
        created_at__lt=cutoff,
    )
    document_count = documents.count()
    for document in documents.iterator():
        if document.file:
            document.file.delete(save=False)
        document.delete()
    conversations = Conversation.objects.filter(updated_at__lt=cutoff)
    conversation_count = conversations.count()
    conversations.delete()
    config.last_purge_at = timezone.now()
    config.save(update_fields=["last_purge_at"])
    return {
        "ran": True,
        "retention_days": days,
        "conversations": conversation_count,
        "documents": document_count,
    }


def maybe_purge() -> None:
    config = load_settings()
    if int(config.retention_days or 0) < 1:
        return
    if config.last_purge_at and timezone.now() - config.last_purge_at < PURGE_GAP:
        return
    purge_expired_data()


def settings_payload() -> dict:
    config = load_settings()
    users = []
    saved = {
        row.user_id: row.not_found_message
        for row in UserChatSetting.objects.all()
    }
    for user in get_user_model().objects.order_by("username"):
        users.append(
            {
                "id": user.id,
                "username": user.username,
                "not_found_message": saved.get(user.id, ""),
            }
        )
    return {
        "retention_days": config.retention_days,
        "not_found_message": config.not_found_message,
        "last_purge_at": config.last_purge_at,
        "users": users,
    }


def save_settings(data) -> dict:
    config = load_settings()
    if "retention_days" in data:
        try:
            days = int(data.get("retention_days"))
        except (TypeError, ValueError):
            raise ValueError("Days must be a whole number.")
        if days < 0 or days > 3650:
            raise ValueError("Days must be between 0 and 3650. Use 0 to turn deletion off.")
        config.retention_days = days
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
    return settings_payload()
