"""Store backend and UI failures, with the call stack and a screenshot file."""
import logging
import traceback
import uuid
from pathlib import Path

from django.conf import settings
from rest_framework.views import exception_handler

from ..models import ErrorEvent

logger = logging.getLogger(__name__)


def _user_details(request):
    user = getattr(request, "user", None) if request is not None else None
    if user is None or not getattr(user, "is_authenticated", False):
        return None, "", ""
    return user.pk, (user.get_username() or "")[:150], (getattr(user, "email", "") or "")[:254]


def save_screenshot(upload):
    """Write a UI image onto the Docker volume and return its path."""
    if upload is None:
        return ""
    data = upload.read()
    if not data or len(data) > 2_000_000:
        return ""
    if data.startswith(b"\x89PNG"):
        suffix = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        suffix = ".webp"
    else:
        return ""
    root = Path(settings.ERROR_SCREENSHOT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return str(path)


def record_exception(request, exc, status_code=None, source="backend", screenshot_path="", message="", stack=""):
    """Persist one failure. Never raises into the request that failed."""
    try:
        if request is not None and "/api/client-errors" in (getattr(request, "path", "") or ""):
            return None
        user_id, username, email = _user_details(request)
        if exc is not None and not stack:
            stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if exc is not None and not message:
            message = str(exc)
        agent = ""
        path = ""
        method = ""
        if request is not None:
            agent = (request.META.get("HTTP_USER_AGENT") or "")[:400]
            path = (getattr(request, "path", "") or "")[:500]
            method = (getattr(request, "method", "") or "")[:16]
        return ErrorEvent.objects.create(
            source=(source or "backend")[:16],
            path=path,
            method=method,
            status_code=status_code,
            message=(message or "")[:8000],
            stack=(stack or "")[:50000],
            user_id=user_id,
            username=username,
            email=email,
            user_agent=agent,
            screenshot_path=(screenshot_path or "")[:500],
        )
    except Exception:
        logger.exception("Could not store the error event")
        return None


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and response.status_code >= 500:
        record_exception(
            context.get("request"),
            exc,
            status_code=response.status_code,
            source="backend",
        )
    return response


def record_client_error(request, message, stack, path, screenshot_path):
    user_id, username, email = _user_details(request)
    agent = (request.META.get("HTTP_USER_AGENT") or "")[:400]
    return ErrorEvent.objects.create(
        source="ui",
        path=(path or "")[:500],
        method="UI",
        message=(message or "UI error")[:8000],
        stack=(stack or "")[:50000],
        user_id=user_id,
        username=username,
        email=email,
        user_agent=agent,
        screenshot_path=(screenshot_path or "")[:500],
    )


def error_payload(row):
    return {
        "id": str(row.id),
        "created_at": row.created_at,
        "source": row.source,
        "path": row.path,
        "method": row.method,
        "status_code": row.status_code,
        "message": row.message,
        "stack": row.stack,
        "user_id": row.user_id,
        "username": row.username,
        "email": row.email,
        "screenshot_path": row.screenshot_path,
    }
