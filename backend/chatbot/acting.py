"""The account whose chats, files, and database settings the request should use."""
from django.contrib.auth import get_user_model

from .permissions import is_menu_admin

SESSION_KEY = "acting_user_id"


def data_user(request):
    """Menu admin can work inside another account. Everyone else uses their own."""
    user = request.user
    if not is_menu_admin(user):
        return user
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return user
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return user
    other = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    return other or user


def set_acting_user(request, user):
    if user is None or user.id == request.user.id:
        request.session.pop(SESSION_KEY, None)
        return
    request.session[SESSION_KEY] = user.id


def clear_acting_user(request, user_id):
    raw = request.session.get(SESSION_KEY)
    if raw is not None and str(raw) == str(user_id):
        request.session.pop(SESSION_KEY, None)
