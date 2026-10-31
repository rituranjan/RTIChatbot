from rest_framework import serializers

from .models import (
    DataConnection,
    SemanticColumn,
    SemanticEngineConfig,
    SemanticExample,
    SemanticRelationship,
    SemanticSynonym,
    SemanticTable,
)


class SemanticEngineConfigSerializer(serializers.ModelSerializer):
    connection_name = serializers.CharField(source="connection.name", read_only=True, allow_null=True)
    report_query_name = serializers.CharField(source="report_query.name", read_only=True, allow_null=True)

    class Meta:
        model = SemanticEngineConfig
        fields = (
            "enabled",
            "connection",
            "connection_name",
            "report_query",
            "report_query_name",
            "database_name",
            "base_from_sql",
            "tenant_filter_column",
            "max_rows",
            "timeout_seconds",
            "use_llm_understanding",
            "fallback_keyword_sql",
            "temperature",
            "chat_sql_mode",
            "updated_at",
        )

    def validate(self, attrs):
        report = attrs.get("report_query")
        if report is None and "report_query" in attrs and attrs["report_query"] is None:
            pass
        elif report:
            from .acting import data_user

            owner = data_user(self.context["request"])
            if report.owner_id != owner.id:
                raise serializers.ValidationError({"report_query": "Choose a query from this workspace."})
            attrs["connection"] = report.connection
        mode = attrs.get("chat_sql_mode")
        if mode == "semantic":
            attrs["enabled"] = True
        elif mode == "keywords":
            attrs["enabled"] = False
        return attrs


class SemanticSynonymSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemanticSynonym
        fields = ("id", "synonym", "language_code", "is_active")
        read_only_fields = ("id",)


class SemanticColumnSerializer(serializers.ModelSerializer):
    synonyms = SemanticSynonymSerializer(many=True, read_only=True)

    class Meta:
        model = SemanticColumn
        fields = (
            "id",
            "physical_column",
            "sql_alias",
            "display_name",
            "description",
            "data_type",
            "searchable",
            "filterable",
            "sortable",
            "groupable",
            "aggregatable",
            "sensitive",
            "is_active",
            "synonyms",
        )
        read_only_fields = ("id",)


class SemanticTableSerializer(serializers.ModelSerializer):
    columns = SemanticColumnSerializer(many=True, read_only=True)

    class Meta:
        model = SemanticTable
        fields = (
            "id",
            "database_name",
            "table_name",
            "table_alias",
            "display_name",
            "description",
            "is_active",
            "columns",
        )
        read_only_fields = ("id",)


class SemanticTableWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemanticTable
        fields = (
            "database_name",
            "table_name",
            "table_alias",
            "display_name",
            "description",
            "is_active",
        )


class SemanticColumnWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemanticColumn
        fields = (
            "physical_column",
            "sql_alias",
            "display_name",
            "description",
            "data_type",
            "searchable",
            "filterable",
            "sortable",
            "groupable",
            "aggregatable",
            "sensitive",
            "is_active",
        )


class SemanticRelationshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemanticRelationship
        fields = (
            "id",
            "source_table",
            "source_column",
            "target_table",
            "target_column",
            "join_type",
            "join_condition",
            "is_active",
        )
        read_only_fields = ("id",)


class SemanticExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SemanticExample
        fields = (
            "id",
            "question",
            "expected_columns",
            "expected_filters",
            "expected_query_pattern",
            "language_code",
            "is_active",
        )
        read_only_fields = ("id",)


class SemanticTestQuerySerializer(serializers.Serializer):
    question = serializers.CharField(max_length=4000)


class SemanticDiscoverSerializer(serializers.Serializer):
    connection = serializers.UUIDField(required=False)
    database_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
