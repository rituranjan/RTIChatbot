"""Admin CRUD for websites. Crawling writes that user's Qdrant collection."""
from urllib.parse import urlsplit

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import WebSource
from .acting import data_user
from .permissions import IsMenuAdmin
from .serializers import WebSourceSerializer
from .services.web_crawl import schedule_crawl
from .services.web_urls import WebUrlError, assert_public_host, normalize_url
from .services.web_vectors import delete_website


def _max_pages(value, default=300):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, 400))


def _public_url(value):
    url = normalize_url(value or "")
    assert_public_host(urlsplit(url).hostname)
    return url


class WebSourceViewSet(viewsets.ModelViewSet):
    serializer_class = WebSourceSerializer
    permission_classes = [IsMenuAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WebSource.objects.filter(owner=data_user(self.request)).prefetch_related("pages")

    def create(self, request, *args, **kwargs):
        try:
            url = _public_url(request.data.get("url"))
        except WebUrlError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        name = str(request.data.get("name") or "").strip()[:200] or urlsplit(url).hostname
        owner = data_user(request)
        source = WebSource.objects.create(
            owner=owner,
            name=name,
            url=url,
            enabled=_enabled(request.data, True),
            max_pages=_max_pages(request.data.get("max_pages"), 300),
        )
        schedule_crawl(source.id)
        source.refresh_from_db()
        return Response(self.get_serializer(source).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        source = self.get_object()
        url = source.url
        recrawl = False
        if "url" in request.data:
            try:
                url = _public_url(request.data.get("url"))
            except WebUrlError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            recrawl = url != source.url
        name = str(request.data.get("name") or source.name).strip()[:200]
        source.name = name or source.name
        source.url = url
        if "enabled" in request.data:
            source.enabled = _enabled(request.data, source.enabled)
        if "max_pages" in request.data:
            source.max_pages = _max_pages(request.data.get("max_pages"), source.max_pages)
        source.save()
        if recrawl:
            schedule_crawl(source.id)
            source.refresh_from_db()
        return Response(self.get_serializer(source).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        source = self.get_object()
        try:
            delete_website(source.owner_id, source.id)
        except Exception:
            pass
        source.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def recrawl(self, request, pk=None):
        source = self.get_object()
        schedule_crawl(source.id)
        source.refresh_from_db()
        return Response(self.get_serializer(source).data)


def _enabled(data, default):
    if "enabled" not in data:
        return default
    value = data.get("enabled")
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)
