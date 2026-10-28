from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .embed_views import EmbedChatView, EmbedConfigView, EmbedProfileView, MyEmbedBotView
from .knowledge_views import (
    DataConnectionViewSet,
    InsightsView,
    IntakeQuestionViewSet,
    SqlKeywordQueryViewSet,
)
from .settings_views import AdminPurgeView, AdminSettingsView
from .website_views import WebSourceViewSet
from .views import (
    ChatView,
    ConversationViewSet,
    CsrfView,
    DocumentViewSet,
    FolderSourceViewSet,
    HealthView,
    IndexingJobViewSet,
    LoginView,
    LogoutView,
    MeView,
    OllamaStatusView,
    RegisterView,
)

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("documents", DocumentViewSet, basename="document")
router.register("folder-sources", FolderSourceViewSet, basename="folder-source")
router.register("indexing-jobs", IndexingJobViewSet, basename="indexing-job")
router.register("connections", DataConnectionViewSet, basename="connection")
router.register("sql-queries", SqlKeywordQueryViewSet, basename="sql-query")
router.register("intake", IntakeQuestionViewSet, basename="intake")
router.register("websites", WebSourceViewSet, basename="website")

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("auth/csrf/", CsrfView.as_view()),
    path("chat/", ChatView.as_view()),
    path("embed/mine/", MyEmbedBotView.as_view()),
    path("embed/<uuid:bot_id>/", EmbedConfigView.as_view()),
    path("embed/<uuid:bot_id>/profile/", EmbedProfileView.as_view()),
    path("embed/<uuid:bot_id>/chat/", EmbedChatView.as_view()),
    path("insights/", InsightsView.as_view()),
    path("admin-settings/", AdminSettingsView.as_view()),
    path("admin-settings/purge/", AdminPurgeView.as_view()),
    path("system/health/", HealthView.as_view()),
    path("system/ollama/", OllamaStatusView.as_view()),
    path("", include(router.urls)),
]