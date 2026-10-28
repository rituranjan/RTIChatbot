from .acting import data_user
from .services.tenant_db import use_tenant


class TenantMiddleware:
    """Point chat, filter, and search queries at the selected account's database."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            with use_tenant(data_user(request)):
                return self.get_response(request)
        return self.get_response(request)
