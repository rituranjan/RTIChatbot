"""Create, update, and delete accounts and the database that belongs to each one."""
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from ..models import Document, UserChatSetting, UserProfile
from ..permissions import is_menu_admin
from .tenant_db import provision_tenant

User = get_user_model()
PLAN_LABELS = dict(UserProfile.PLAN_CHOICES)


def serialize_account(user, profile, not_found_message="", viewer=None) -> dict:
    plan = profile.plan if profile else ""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "plan": plan,
        "plan_label": PLAN_LABELS.get(plan, ""),
        "database_name": profile.database_name if profile else "",
        "database_engine": profile.engine if profile else "",
        "database_ready": bool(profile and profile.ready),
        "database_error": profile.error if profile else "",
        "not_found_message": not_found_message or "",
        "is_menu_admin": is_menu_admin(user),
        "can_delete": bool(viewer is not None and user.id != viewer.id and not is_menu_admin(user)),
    }


def account_row(user, viewer=None) -> dict:
    profile = UserProfile.objects.filter(user=user).first()
    setting = UserChatSetting.objects.filter(user=user).first()
    message = setting.not_found_message if setting else ""
    return serialize_account(user, profile, message, viewer)


def _clean_email(value) -> str:
    email = str(value or "").strip()
    if not email:
        return ""
    try:
        validate_email(email)
    except DjangoValidationError:
        raise ValueError("Enter a valid email address.")
    return email


def create_account(username, email, password, plan) -> dict:
    username = str(username or "").strip()
    if not username or len(username) > 150:
        raise ValueError("Enter a username.")
    if User.objects.filter(username__iexact=username).exists():
        raise ValueError("That username is already in use.")
    if len(str(password or "")) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if plan not in UserProfile.PLANS:
        raise ValueError("Choose Basic, Silver, Gold, or Diamond.")
    user = User.objects.create_user(
        username=username,
        email=_clean_email(email),
        password=password,
    )
    provision_tenant(user, plan)
    return user


def update_account(user, data) -> None:
    if "email" in data:
        user.email = _clean_email(data.get("email"))
    password = str(data.get("password") or "")
    if password:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        user.set_password(password)
    user.save()
    if data.get("plan"):
        plan = str(data.get("plan"))
        if plan not in UserProfile.PLANS:
            raise ValueError("Choose Basic, Silver, Gold, or Diamond.")
        profile = UserProfile.objects.filter(user=user).first()
        if profile is None:
            provision_tenant(user, plan)
        else:
            profile.plan = plan
            profile.save(update_fields=["plan"])
    if "not_found_message" in data:
        message = str(data.get("not_found_message") or "").strip()[:2000]
        if message:
            UserChatSetting.objects.update_or_create(
                user=user, defaults={"not_found_message": message}
            )
        else:
            UserChatSetting.objects.filter(user=user).delete()


def delete_account(user) -> None:
    if is_menu_admin(user):
        raise ValueError("The admin account cannot be deleted.")
    profile = UserProfile.objects.filter(user=user).first()
    if profile is not None:
        from .tenant_db import drop_tenant

        drop_tenant(profile)
    for document in Document.objects.filter(owner=user):
        if document.file:
            document.file.delete(save=False)
    try:
        from .web_vectors import delete_user_collection

        delete_user_collection(user.id)
    except Exception:
        pass
    user.delete()
