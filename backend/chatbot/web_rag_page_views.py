"""CRUD for single-page RAG entries (paste URLs)."""
from urllib.parse import urlsplit

from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .acting import data_user
from .models import WebRagPage
from .permissions import IsMenuAdmin
from .serializers import WebRagPageSerializer
from .services.plan_access import assert_website_rag_quota, website_max_pages_for, website_rag_page_count
from .services.web_rag_index import schedule_rag_page
from .services.web_urls import WebUrlError, assert_public_host, extract_urls_from_paste, normalize_url
from .services.web_vectors import delete_website


def _enabled(data, default):
    if "enabled" not in data:
        return default
    value = data.get("enabled")
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)


def _public_url(value):
    url = normalize_url(value or "")
    assert_public_host(urlsplit(url).hostname)
    return url


class WebRagPageViewSet(viewsets.ModelViewSet):
    serializer_class = WebRagPageSerializer
    permission_classes = [IsMenuAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WebRagPage.objects.filter(owner=data_user(self.request))

    def create(self, request, *args, **kwargs):
        try:
            url = _public_url(request.data.get("url"))
        except WebUrlError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        owner = data_user(request)
        try:
            assert_website_rag_quota(owner, adding=1)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            page = WebRagPage.objects.create(
                owner=owner,
                url=url,
                enabled=_enabled(request.data, True),
            )
        except IntegrityError:
            return Response({"detail": "That page is already in your list."}, status=status.HTTP_400_BAD_REQUEST)
        schedule_rag_page(page.id)
        page.refresh_from_db()
        return Response(self.get_serializer(page).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        page = self.get_object()
        if "enabled" in request.data:
            page.enabled = _enabled(request.data, page.enabled)
        page.save()
        return Response(self.get_serializer(page).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        page = self.get_object()
        try:
            delete_website(page.owner_id, page.id)
        except Exception:
            pass
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def reindex(self, request, pk=None):
        page = self.get_object()
        schedule_rag_page(page.id)
        page.refresh_from_db()
        return Response(self.get_serializer(page).data)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        paste = str(request.data.get("paste") or request.data.get("text") or "").strip()
        urls = extract_urls_from_paste(paste)
        if not urls and request.data.get("url"):
            try:
                urls = [_public_url(request.data.get("url"))]
            except WebUrlError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not urls:
            return Response(
                {"detail": "Paste one or more http(s) addresses."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner = data_user(request)
        existing = set(WebRagPage.objects.filter(owner=owner).values_list("url", flat=True))
        validated = []
        invalid = []
        for raw in urls:
            try:
                url = _public_url(raw)
                validated.append(url)
            except WebUrlError as exc:
                invalid.append({"url": raw, "error": str(exc)})

        new_urls = []
        duplicates = []
        for url in validated:
            if url in existing:
                duplicates.append(url)
                continue
            new_urls.append(url)

        cap = website_max_pages_for(owner)
        used = website_rag_page_count(owner)
        if cap > 0:
            room = max(0, cap - used)
            over_limit = new_urls[room:]
            new_urls = new_urls[:room]
        else:
            over_limit = []

        created_rows = []
        for url in new_urls:
            try:
                page = WebRagPage.objects.create(owner=owner, url=url, enabled=True)
            except IntegrityError:
                duplicates.append(url)
                continue
            schedule_rag_page(page.id)
            page.refresh_from_db()
            created_rows.append(page)

        payload = {
            "created": self.get_serializer(created_rows, many=True).data,
            "duplicates": duplicates,
            "over_limit": over_limit,
            "invalid": invalid,
            "limit": cap,
            "used": used + len(created_rows),
        }
        if not created_rows and (duplicates or over_limit or invalid):
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_201_CREATED if created_rows else status.HTTP_200_OK)
