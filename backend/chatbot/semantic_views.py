from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .acting import data_user
from .models import AppSetting, SemanticColumn, SemanticEngineConfig, SemanticExample, SemanticRelationship, SemanticSynonym, SemanticTable
from .permissions import IsMenuAdmin
from .semantic_serializers import (
    SemanticColumnSerializer,
    SemanticColumnWriteSerializer,
    SemanticEngineConfigSerializer,
    SemanticExampleSerializer,
    SemanticRelationshipSerializer,
    SemanticSynonymSerializer,
    SemanticTableSerializer,
    SemanticTableWriteSerializer,
    SemanticDiscoverSerializer,
    SemanticTestQuerySerializer,
)
from .services.plan_access import semantic_sql_enabled_for, sql_keyword_enabled_for
from .services.semantic.connection_resolver import resolve_connection, resolve_database_name
from .services.semantic.dictionary_service import ensure_engine_config, invalidate_dictionary_cache, load_dictionary
from .services.semantic.import_export_service import export_dictionary, import_rti_bootstrap
from .services.semantic.query_pipeline import preview_query, run_semantic_query
from .services.semantic.schema_discovery_service import discover_mysql
from .services.semantic.tenant_authorization_service import platform_enabled, workspace_authorized


def _owner(request):
    return data_user(request)


class SemanticEngineView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        config = ensure_engine_config(_owner(request))
        return Response(
            {
                "platform_enabled": platform_enabled(),
                "config": SemanticEngineConfigSerializer(config).data,
                "column_count": len(load_dictionary(_owner(request)).get("columns") or []),
                "plan": {
                    "sql_keyword_enabled": sql_keyword_enabled_for(_owner(request)),
                    "semantic_sql_enabled": semantic_sql_enabled_for(_owner(request)),
                },
            }
        )

    def patch(self, request):
        config = ensure_engine_config(_owner(request))
        serializer = SemanticEngineConfigSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_dictionary_cache(_owner(request).id)
        return Response(SemanticEngineConfigSerializer(config).data)


class SemanticPlatformSettingsView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        setting = AppSetting.objects.filter(pk=1).first()
        return Response((setting.semantic_sql_settings if setting else {}) or {})

    def patch(self, request):
        setting, _ = AppSetting.objects.get_or_create(pk=1)
        raw = setting.semantic_sql_settings if isinstance(setting.semantic_sql_settings, dict) else {}
        raw.update(request.data if isinstance(request.data, dict) else {})
        setting.semantic_sql_settings = raw
        setting.save(update_fields=["semantic_sql_settings"])
        return Response(raw)


class SemanticTableViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMenuAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SemanticTable.objects.filter(owner=_owner(self.request)).prefetch_related("columns__synonyms")

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return SemanticTableWriteSerializer
        return SemanticTableSerializer

    def perform_create(self, serializer):
        serializer.save(owner=_owner(self.request))
        invalidate_dictionary_cache(_owner(self.request).id)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_dictionary_cache(_owner(self.request).id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_dictionary_cache(_owner(self.request).id)


class SemanticColumnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMenuAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SemanticColumn.objects.filter(semantic_table__owner=_owner(self.request)).prefetch_related(
            "synonyms"
        )

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return SemanticColumnWriteSerializer
        return SemanticColumnSerializer

    def create(self, request, *args, **kwargs):
        table_id = request.data.get("semantic_table")
        table = SemanticTable.objects.filter(id=table_id, owner=_owner(request)).first()
        if not table:
            return Response({"detail": "Table not found."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SemanticColumnWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        col = SemanticColumn.objects.create(semantic_table=table, **serializer.validated_data)
        invalidate_dictionary_cache(_owner(request).id)
        return Response(SemanticColumnSerializer(col).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_dictionary_cache(_owner(self.request).id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_dictionary_cache(_owner(self.request).id)


class SemanticSynonymViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMenuAdmin]
    serializer_class = SemanticSynonymSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SemanticSynonym.objects.filter(semantic_column__semantic_table__owner=_owner(self.request))

    def create(self, request, *args, **kwargs):
        col_id = request.data.get("semantic_column")
        col = SemanticColumn.objects.filter(id=col_id, semantic_table__owner=_owner(request)).first()
        if not col:
            return Response({"detail": "Column not found."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = SemanticSynonym.objects.create(semantic_column=col, **serializer.validated_data)
        invalidate_dictionary_cache(_owner(request).id)
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_dictionary_cache(_owner(self.request).id)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_dictionary_cache(_owner(self.request).id)


class SemanticRelationshipViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMenuAdmin]
    serializer_class = SemanticRelationshipSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SemanticRelationship.objects.filter(owner=_owner(self.request))

    def perform_create(self, serializer):
        serializer.save(owner=_owner(self.request))

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class SemanticExampleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsMenuAdmin]
    serializer_class = SemanticExampleSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return SemanticExample.objects.filter(owner=_owner(self.request))

    def perform_create(self, serializer):
        serializer.save(owner=_owner(self.request))


class SemanticBootstrapView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request):
        replace = bool(request.data.get("replace"))
        result = import_rti_bootstrap(_owner(request), replace=replace)
        return Response(result)


class SemanticExportView(APIView):
    permission_classes = [IsMenuAdmin]

    def get(self, request):
        return Response(export_dictionary(_owner(request)))


class SemanticPreviewView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request):
        body = SemanticTestQuerySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        owner = _owner(request)
        question = body.validated_data["question"]
        preview = preview_query(owner, question)
        ok, auth_reason = workspace_authorized(owner)
        if ok and not preview.get("error"):
            run = run_semantic_query(owner, question)
            preview["rows"] = (run or {}).get("rows") or []
            preview["run_error"] = (run or {}).get("error") or ""
        else:
            preview["rows"] = []
            if preview.get("error"):
                preview["run_error"] = preview["error"]
            elif not ok:
                preview["run_error"] = auth_reason
            else:
                preview["run_error"] = preview.get("run_error") or ""

        http_status = status.HTTP_200_OK
        if preview.get("error") or preview.get("run_error"):
            http_status = status.HTTP_400_BAD_REQUEST
        return Response(preview, status=http_status)


class SemanticDiscoverView(APIView):
    permission_classes = [IsMenuAdmin]

    def post(self, request):
        body = SemanticDiscoverSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        config = ensure_engine_config(_owner(request))
        conn = resolve_connection(config)
        if body.validated_data.get("connection"):
            from .models import DataConnection

            conn = DataConnection.objects.filter(
                id=body.validated_data["connection"], owner=_owner(request)
            ).first()
        if not conn or conn.engine != "mysql":
            return Response(
                {"detail": "Discovery requires a MySQL connection."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        db_name = body.validated_data.get("database_name") or resolve_database_name(config, conn)
        payload = discover_mysql(conn.connection_string, db_name)
        return Response(payload)
