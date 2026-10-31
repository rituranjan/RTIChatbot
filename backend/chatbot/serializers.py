from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Conversation,
    DataConnection,
    Document,
    FolderSource,
    IndexingJob,
    IntakeQuestion,
    Message,
    SqlKeywordQuery,
    WebPage,
    WebRagPage,
    WebSource,
)

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "role", "content", "sources", "created_at")
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ("id", "title", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class DocumentSerializer(serializers.ModelSerializer):
    is_shared = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "file_type",
            "status",
            "error",
            "size",
            "is_shared",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class FolderSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FolderSource
        fields = (
            "id",
            "name",
            "root_path",
            "extensions",
            "max_size_mb",
            "enabled",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class IndexingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndexingJob
        fields = (
            "id",
            "folder_source",
            "status",
            "files_total",
            "files_indexed",
            "files_failed",
            "message",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class DataConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataConnection
        fields = (
            "id",
            "name",
            "engine",
            "connection_string",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class SqlKeywordQuerySerializer(serializers.ModelSerializer):
    connection_name = serializers.CharField(source="connection.name", read_only=True)

    class Meta:
        model = SqlKeywordQuery
        fields = (
            "id",
            "connection",
            "connection_name",
            "name",
            "keywords",
            "sql_text",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "connection_name", "created_at", "updated_at")


class IntakeQuestionSerializer(serializers.ModelSerializer):
    field_key = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = IntakeQuestion
        fields = (
            "id",
            "label",
            "field_key",
            "placeholder",
            "required",
            "position",
            "enabled",
        )
        read_only_fields = ("id",)


class WebPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebPage
        fields = ("id", "url", "title", "chunk_count")
        read_only_fields = fields


class WebSourceSerializer(serializers.ModelSerializer):
    pages = WebPageSerializer(many=True, read_only=True)

    class Meta:
        model = WebSource
        fields = (
            "id",
            "name",
            "url",
            "enabled",
            "status",
            "error",
            "message",
            "page_count",
            "chunk_count",
            "max_pages",
            "pages",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "error",
            "message",
            "page_count",
            "chunk_count",
            "pages",
            "created_at",
            "updated_at",
        )


class WebRagPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebRagPage
        fields = (
            "id",
            "url",
            "title",
            "enabled",
            "status",
            "error",
            "message",
            "chunk_count",
            "priority",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "title",
            "status",
            "error",
            "message",
            "chunk_count",
            "priority",
            "created_at",
            "updated_at",
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class ConnectionTestSerializer(serializers.Serializer):
    engine = serializers.ChoiceField(choices=["sqlite", "mysql", "mssql", "postgresql"])
    connection_string = serializers.CharField()


class ProfileBodySerializer(serializers.Serializer):
    answers = serializers.JSONField()


class EmbedChatBodySerializer(serializers.Serializer):
    visitor_id = serializers.CharField()
    message = serializers.CharField()
    language = serializers.CharField(required=False, allow_blank=True, default="")


class EmbedProfileBodySerializer(serializers.Serializer):
    visitor_id = serializers.CharField()
    answers = serializers.JSONField()


class EmbedUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    greeting = serializers.CharField(required=False)
    accent = serializers.CharField(required=False)
    quick_replies = serializers.ListField(child=serializers.CharField(), required=False)


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    message = serializers.CharField()
    language = serializers.CharField(required=False, allow_blank=True, default="")
    stream = serializers.BooleanField(required=False, default=False)
    strict_documents = serializers.BooleanField(required=False, allow_null=True, default=None)