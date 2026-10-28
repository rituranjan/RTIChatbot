import time
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ErrorEvent
from .permissions import IsMenuAdmin
from .services.error_log import error_payload, record_client_error, save_screenshot

_HITS = {}


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


def _allowed(ip):
    now = time.time()
    recent = [stamp for stamp in _HITS.get(ip, []) if now - stamp < 60]
    if len(recent) >= 30:
        _HITS[ip] = recent
        return False
    recent.append(now)
    _HITS[ip] = recent
    return True


class ClientErrorView(APIView):
    """The browser reports a UI failure and an optional screenshot."""

    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ip = request.META.get("REMOTE_ADDR") or "unknown"
        if not _allowed(ip):
            return Response({"detail": "Too many error reports."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        message = str(request.data.get("message") or "").strip()
        stack = str(request.data.get("stack") or "")
        path = str(request.data.get("path") or "")
        if not message and not stack:
            return Response({"detail": "Missing error details."}, status=status.HTTP_400_BAD_REQUEST)
        screenshot = save_screenshot(request.FILES.get("screenshot"))
        row = record_client_error(request, message, stack, path, screenshot)
        return Response({"id": str(row.id), "stored": True}, status=status.HTTP_201_CREATED)


class ErrorEventListView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        rows = ErrorEvent.objects.all()[:100]
        return Response({"errors": [error_payload(row) for row in rows]})


class ErrorScreenshotView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request, error_id):
        row = ErrorEvent.objects.filter(pk=error_id).first()
        if row is None or not row.screenshot_path:
            return Response({"detail": "Screenshot not found."}, status=status.HTTP_404_NOT_FOUND)
        path = Path(row.screenshot_path).resolve()
        root = Path(settings.ERROR_SCREENSHOT_DIR).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return Response({"detail": "Screenshot not found."}, status=status.HTTP_404_NOT_FOUND)
        content_type = "image/png"
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        elif path.suffix.lower() == ".webp":
            content_type = "image/webp"
        return FileResponse(path.open("rb"), content_type=content_type)
