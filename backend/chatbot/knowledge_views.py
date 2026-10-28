"""Files are handled on DocumentViewSet. This module is connections, SQL, questions, and insights."""
from datetime import datetime, time

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from .models import Conversation, DataConnection, IntakeQuestion, SqlKeywordQuery, VisitorProfile
from .serializers import (
    ConnectionTestSerializer,
    DataConnectionSerializer,
    IntakeQuestionSerializer,
    SqlKeywordQuerySerializer,
)
from .permissions import IsMenuAdmin
from .services.external_db import assert_select, run_select, test_connection
from .services.profile_service import question_key


def _clean_keywords(value):
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        parts = []
    cleaned = []
    for part in parts:
        word = str(part).strip()
        if word and word.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(word[:40])
    return cleaned[:12]


class DataConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = DataConnectionSerializer
    permission_classes = [IsMenuAdmin]

    def get_queryset(self):
        return DataConnection.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(request=ConnectionTestSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["post"])
    def test(self, request):
        engine = str(request.data.get("engine") or "")
        connection_string = str(request.data.get("connection_string") or "")
        try:
            detail = test_connection(engine, connection_string)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"ok": False, "detail": str(exc).splitlines()[0][:300]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"ok": True, "detail": detail})


class SqlKeywordQueryViewSet(viewsets.ModelViewSet):
    serializer_class = SqlKeywordQuerySerializer
    permission_classes = [IsMenuAdmin]

    def get_queryset(self):
        return SqlKeywordQuery.objects.filter(owner=self.request.user).select_related(
            "connection"
        )

    def _validate(self, request, instance=None):
        connection_id = request.data.get("connection") or (
            instance.connection_id if instance else None
        )
        connection = DataConnection.objects.filter(
            id=connection_id, owner=request.user
        ).first()
        if connection is None:
            return None, None, Response(
                {"detail": "Choose one of your database connections."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        keywords = _clean_keywords(request.data.get("keywords", instance.keywords if instance else []))
        if not keywords:
            return None, None, Response(
                {"detail": "Add at least one keyword, such as Payment or AccountNo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sql_text = str(request.data.get("sql_text") if "sql_text" in request.data else (instance.sql_text if instance else ""))
        try:
            sql_text = assert_select(sql_text)
        except ValueError as exc:
            return None, None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return connection, keywords, sql_text

    def create(self, request, *args, **kwargs):
        connection, keywords, sql_text = self._validate(request)
        if isinstance(sql_text, Response):
            return sql_text
        name = str(request.data.get("name") or "").strip()[:120]
        if not name:
            return Response({"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
        query = SqlKeywordQuery.objects.create(
            owner=request.user,
            connection=connection,
            name=name,
            keywords=keywords,
            sql_text=sql_text,
            enabled=bool(request.data.get("enabled", True)),
        )
        return Response(self.get_serializer(query).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        query = self.get_object()
        connection, keywords, sql_text = self._validate(request, query)
        if isinstance(sql_text, Response):
            return sql_text
        name = str(request.data.get("name") or query.name).strip()[:120]
        query.connection = connection
        query.keywords = keywords
        query.sql_text = sql_text
        query.name = name or query.name
        if "enabled" in request.data:
            query.enabled = bool(request.data.get("enabled"))
        query.save()
        return Response(self.get_serializer(query).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        query = self.get_object()
        keyword = ""
        if query.keywords:
            keyword = str(query.keywords[0])
        try:
            rows = run_select(
                query.connection.engine,
                query.connection.connection_string,
                query.sql_text,
                keyword=keyword,
                limit=5,
            )
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"ok": False, "detail": str(exc).splitlines()[0][:300]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"ok": True, "rows": rows})


class IntakeQuestionViewSet(viewsets.ModelViewSet):
    serializer_class = IntakeQuestionSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return IntakeQuestion.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        label = serializer.validated_data["label"].strip()
        field_key = question_key(label, serializer.validated_data.get("field_key", ""))
        position = serializer.validated_data.get("position")
        if position in (None, 0):
            position = self.get_queryset().count()
        serializer.save(owner=self.request.user, label=label, field_key=field_key, position=position)

    def perform_update(self, serializer):
        label = serializer.validated_data.get("label", serializer.instance.label).strip()
        field_key = question_key(
            label, serializer.validated_data.get("field_key", serializer.instance.field_key)
        )
        serializer.save(label=label, field_key=field_key)


def _bounds(request):
    start = parse_date(request.query_params.get("start") or "")
    end = parse_date(request.query_params.get("end") or "")
    keyword = (request.query_params.get("q") or "").strip()[:80]
    return start, end, keyword


def _apply_filters(qs, start, end, keyword):
    if start:
        qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(start, time.min)))
    if end:
        qs = qs.filter(created_at__lte=timezone.make_aware(datetime.combine(end, time.max)))
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword)
            | Q(messages__content__icontains=keyword)
            | Q(profile__answers__icontains=keyword)
        ).distinct()
    return qs


class InsightsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("start", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="YYYY-MM-DD"),
            OpenApiParameter("end", OpenApiTypes.DATE, OpenApiParameter.QUERY, description="YYYY-MM-DD"),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Keyword"),
        ]
    )
    def get(self, request):
        start, end, keyword = _bounds(request)
        qs = _apply_filters(
            Conversation.objects.filter(owner=request.user)
            .select_related("profile", "embed_bot")
            .annotate(message_count=Count("messages")),
            start,
            end,
            keyword,
        ).order_by("-created_at")[:200]

        visitors = []
        chats = []
        for conversation in qs:
            answers = {}
            try:
                answers = conversation.profile.answers or {}
            except VisitorProfile.DoesNotExist:
                answers = {}
            preview = ""
            first = conversation.messages.filter(role="user").order_by("created_at").first()
            if first:
                preview = first.content[:180]
            row = {
                "id": str(conversation.id),
                "title": conversation.title,
                "channel": "website" if conversation.embed_bot_id else "app",
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "answers": answers,
                "message_count": conversation.message_count,
                "preview": preview,
            }
            if answers:
                visitors.append(row)
            chats.append(row)
        return Response({"visitors": visitors, "chats": chats, "keyword": keyword})
