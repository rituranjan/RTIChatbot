"""Load and cache semantic dictionary for a workspace owner."""

from django.core.cache import cache

from ...models import SemanticColumn, SemanticEngineConfig, SemanticRelationship, SemanticSynonym, SemanticTable


def _cache_key(owner_id) -> str:
    return f"semantic_dict:{owner_id}"


def invalidate_dictionary_cache(owner_id) -> None:
    cache.delete(_cache_key(owner_id))


def get_engine_config(owner):
    return (
        SemanticEngineConfig.objects.filter(owner=owner)
        .select_related("connection", "report_query", "report_query__connection")
        .first()
    )


def ensure_engine_config(owner):
    config, _ = SemanticEngineConfig.objects.get_or_create(owner=owner)
    return config


def load_dictionary(owner, use_cache=True) -> dict:
    key = _cache_key(owner.id)
    if use_cache:
        cached = cache.get(key)
        if cached:
            return cached
    tables = (
        SemanticTable.objects.filter(owner=owner, is_active=True)
        .prefetch_related("columns__synonyms")
        .order_by("table_name")
    )
    columns = []
    for table in tables:
        alias = table.table_alias or table.table_name[:1]
        for col in table.columns.filter(is_active=True):
            syns = [
                s.synonym
                for s in col.synonyms.filter(is_active=True)
                if s.synonym.strip()
            ]
            ref = f"{alias}.{col.physical_column}"
            columns.append(
                {
                    "id": str(col.id),
                    "ref": ref,
                    "table": table.table_name,
                    "alias": alias,
                    "physical": col.physical_column,
                    "sql_alias": col.sql_alias,
                    "display_name": col.display_name,
                    "data_type": col.data_type,
                    "filterable": col.filterable,
                    "sortable": col.sortable,
                    "groupable": col.groupable,
                    "aggregatable": col.aggregatable,
                    "sensitive": col.sensitive,
                    "searchable": col.searchable,
                    "synonyms": syns,
                }
            )
    relationships = list(
        SemanticRelationship.objects.filter(owner=owner, is_active=True).values(
            "source_table",
            "source_column",
            "target_table",
            "target_column",
            "join_type",
            "join_condition",
        )
    )
    payload = {"columns": columns, "relationships": relationships}
    cache.set(key, payload, timeout=300)
    return payload


def column_by_ref(dictionary: dict, ref: str):
    ref = (ref or "").strip().lower()
    for col in dictionary["columns"]:
        if col["ref"].lower() == ref:
            return col
    return None


def allowed_column_refs(dictionary: dict) -> set[str]:
    return {col["ref"].lower() for col in dictionary["columns"]}
