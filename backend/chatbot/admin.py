from django.contrib import admin

from .models import (
    Conversation,
    DatabaseRecord,
    EmbedBot,
    Document,
    DocumentChunk,
    FolderSource,
    IndexingJob,
    Message,
    WebSource,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "title", "updated_at")
    search_fields = ("title", "owner__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    search_fields = ("content",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "folder_source", "status", "created_at")
    list_filter = ("status", "file_type")
    search_fields = ("title",)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "chunk_index", "created_at")


@admin.register(FolderSource)
class FolderSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "root_path", "enabled", "created_at")
    list_filter = ("enabled",)


@admin.register(EmbedBot)
class EmbedBotAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "enabled", "created_at")
    search_fields = ("name", "greeting")


@admin.register(DatabaseRecord)
class DatabaseRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "created_at")
    list_filter = ("category",)
    search_fields = ("title", "content", "category")


@admin.register(WebSource)
class WebSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "url", "status", "page_count", "updated_at")
    list_filter = ("status", "enabled")
    search_fields = ("name", "url")


@admin.register(IndexingJob)
class IndexingJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "folder_source",
        "status",
        "files_total",
        "files_indexed",
        "files_failed",
        "started_at",
    )
    list_filter = ("status",)