from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SwaggerDocsView(TemplateView):
    template_name = "swagger_ui.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["schema_url"] = "/api/schema/"
        return context


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path("api/docs/", SwaggerDocsView.as_view(), name="swagger-ui"),
    path("api/", include("chatbot.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]