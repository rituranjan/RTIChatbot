import os
from pathlib import Path
from threading import Thread

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import FileResponse
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from .models import (
    Conversation,
    Document,
    FolderSource,
    IndexingJob,
    Message,
)
from .serializers import (
    ChatRequestSerializer,
    ConversationSerializer,
    DocumentSerializer,
    FolderSourceSerializer,
    IndexingJobSerializer,
    LoginSerializer,
    MessageSerializer,
    ProfileBodySerializer,
    RegisterSerializer,
)
from .services.chat_service import generate_reply
from .services.profile_service import profile_answers, save_profile
from .services.folder_service import is_within_approved_root, run_indexing
from .services.ingestion_service import index_document
from .acting import data_user
from .permissions import IsMenuAdmin, is_menu_admin
from .models import UserProfile
from .services.llm_service import LLMError, provider_status


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _user_payload(user, request=None):
    profile = UserProfile.objects.filter(user=user).first()
    acting = None
    if request is not None and is_menu_admin(user):
        selected = data_user(request)
        if selected.id != user.id:
            acting = {
                "id": selected.id,
                "username": selected.username,
                "plan": "",
                "database_name": "",
            }
            selected_profile = UserProfile.objects.filter(user=selected).first()
            if selected_profile:
                acting["plan"] = selected_profile.plan
                acting["database_name"] = selected_profile.database_name
                acting["database_engine"] = selected_profile.engine
                acting["database_ready"] = selected_profile.ready
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_menu_admin": is_menu_admin(user),
        "plan": profile.plan if profile else "",
        "database_name": profile.database_name if profile else "",
        "database_engine": profile.engine if profile else "",
        "database_ready": bool(profile and profile.ready),
        "acting_as": acting,
    }


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from .services.tenant_db import provision_tenant

        provision_tenant(user, "basic")
        login(request, user)
        return Response(_user_payload(user, request), status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(_user_payload(user, request))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"status": "ok"})


class MeView(APIView):
    def get(self, request):
        return Response(_user_payload(request.user, request))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        queryset = Conversation.objects.filter(owner=data_user(self.request))
        if self.action == "list":
            queryset = queryset.filter(embed_bot__isnull=True)
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        serializer.save(owner=data_user(self.request))

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if "answers" not in request.data:
            return response
        conversation = Conversation.objects.get(id=response.data["id"])
        try:
            response.data["profile"] = save_profile(conversation, request.data.get("answers"))
        except ValueError as exc:
            conversation.delete()
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        data["messages"] = MessageSerializer(instance.messages.all(), many=True).data
        data["profile"] = profile_answers(instance)
        return Response(data)

    @extend_schema(request=ProfileBodySerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"])
    def profile(self, request, pk=None):
        conversation = self.get_object()
        try:
            answers = save_profile(conversation, request.data.get("answers"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"profile": answers})


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatView(APIView):
    @extend_schema(request=ChatRequestSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation_id = serializer.validated_data["conversation_id"]
        user_text = serializer.validated_data["message"].strip()
        if not user_text:
            return Response({"detail": "Empty message."}, status=status.HTTP_400_BAD_REQUEST)

        owner = data_user(request)
        conversation = Conversation.objects.filter(
            id=conversation_id, owner=owner
        ).first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        strict = serializer.validated_data.get("strict_documents")
        chat_language = (serializer.validated_data.get("language") or "").strip()
        try:
            msg = generate_reply(
                owner, conversation, user_text, strict=strict, style="app", chat_language=chat_language or None
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LLMError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                "message": MessageSerializer(msg).data,
                "sources": msg.sources,
            }
        )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def _validate_upload_signature(file_obj, ext):
    head = file_obj.read(8)
    file_obj.seek(0)
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        raise ValueError("File does not look like a valid PDF.")
    if ext == ".png" and not head.startswith(b"\x89PNG"):
        raise ValueError("File does not look like a valid PNG.")
    if ext in (".jpg", ".jpeg") and not head.startswith(b"\xff\xd8"):
        raise ValueError("File does not look like a valid JPEG.")


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [IsMenuAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Document.objects.filter(
            owner=data_user(self.request)
        ).order_by("-created_at")

    def get_object(self):
        obj = Document.objects.filter(id=self.kwargs.get("pk")).first()
        if obj is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        if obj.owner_id != data_user(self.request).id and not obj.is_shared:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        if obj.is_shared and self.request.method == "DELETE":
            raise PermissionDenied("Shared documents cannot be deleted.")
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={201: DocumentSerializer},
    )
    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST
            )

        ext = Path(file.name).suffix.lower()
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            return Response(
                {"detail": f"File type {ext} is not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            return Response(
                {"detail": f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            _validate_upload_signature(file, ext)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        title = os.path.basename(file.name)[:255]
        doc = Document.objects.create(
            owner=data_user(request),
            title=title,
            file=file,
            file_type=ext.lstrip("."),
            size=file.size,
            status=Document.STATUS_PROCESSING,
        )

        try:
            index_document(doc)
            doc.status = Document.STATUS_READY
            doc.error = ""
        except Exception as exc:  # noqa: BLE001
            doc.status = Document.STATUS_FAILED
            doc.error = str(exc)[:1000]
        doc.save()

        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        doc = self.get_object()
        if doc.is_shared:
            raise PermissionDenied("Shared documents cannot be renamed.")
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"detail": "Title is required."}, status=status.HTTP_400_BAD_REQUEST)
        doc.title = title[:255]
        doc.save(update_fields=["title", "updated_at"])
        return Response(DocumentSerializer(doc).data)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        doc = self.get_object()
        if not doc.file:
            return Response({"detail": "This file has no download."}, status=status.HTTP_404_NOT_FOUND)
        name = doc.title or "download"
        if doc.file_type and not name.lower().endswith("." + doc.file_type.lower()):
            name = f"{name}.{doc.file_type}"
        return FileResponse(doc.file.open("rb"), as_attachment=True, filename=name)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_shared:
            raise PermissionDenied("Shared documents cannot be deleted.")
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def reindex(self, request, pk=None):
        doc = self.get_object()
        if doc.is_shared:
            raise PermissionDenied("Shared documents cannot be reindexed by users.")
        doc.status = Document.STATUS_PROCESSING
        doc.save(update_fields=["status"])
        try:
            index_document(doc)
            doc.status = Document.STATUS_READY
            doc.error = ""
        except Exception as exc:  # noqa: BLE001
            doc.status = Document.STATUS_FAILED
            doc.error = str(exc)[:1000]
        doc.save()
        return Response(DocumentSerializer(doc).data)


# ---------------------------------------------------------------------------
# Folder sources + indexing jobs
# ---------------------------------------------------------------------------

class FolderSourceViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSourceSerializer
    permission_classes = [IsMenuAdmin]

    def get_queryset(self):
        return FolderSource.objects.all().order_by("name")

    def perform_create(self, serializer):
        root = Path(serializer.validated_data["root_path"]).resolve()
        if not is_within_approved_root(root):
            raise ValidationError(
                {"root_path": "Path is not within an approved root directory."}
            )
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if "root_path" in serializer.validated_data:
            root = Path(serializer.validated_data["root_path"]).resolve()
            if not is_within_approved_root(root):
                raise ValidationError(
                    {"root_path": "Path is not within an approved root directory."}
                )
        serializer.save()

    @action(detail=True, methods=["post"])
    def index(self, request, pk=None):
        source = self.get_object()
        job = IndexingJob.objects.create(
            folder_source=source, status=IndexingJob.STATUS_PENDING
        )

        def _run():
            run_indexing(job, index_document)

        Thread(target=_run, daemon=True).start()

        return Response(
            IndexingJobSerializer(job).data, status=status.HTTP_202_ACCEPTED
        )


class IndexingJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IndexingJobSerializer
    permission_classes = [IsMenuAdmin]

    def get_queryset(self):
        return IndexingJob.objects.all().order_by("-started_at")


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class OllamaStatusView(APIView):
    def get(self, request):
        from .acting import data_user

        status_payload = provider_status(data_user(request))
        status_payload["embedding_model"] = status_payload.get("embedding_model")
        return Response(status_payload)