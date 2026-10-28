from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level permission: only the owner may access the record."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "owner_id", None) == request.user.id


MENU_ADMIN_USERNAME = "RRGupta"


def is_menu_admin(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.username == MENU_ADMIN_USERNAME
    )


class IsMenuAdmin(BasePermission):
    """Knowledge and website-embed settings belong to the menu admin only."""

    def has_permission(self, request, view):
        return is_menu_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.user and request.user.is_staff)