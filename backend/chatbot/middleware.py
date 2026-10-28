from .acting import data_user
from .services.error_log import record_exception
from .services.tenant_db import use_tenant


class ErrorRecordMiddleware:
    """Keep the call stack when a request fails before an API response is built."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        record_exception(request, exception, status_code=500, source="backend")
        return None


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
