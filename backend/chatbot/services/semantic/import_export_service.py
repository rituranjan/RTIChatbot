"""Import bootstrap or exported dictionary JSON into a workspace."""

from django.db import transaction

from ...models import SemanticColumn, SemanticEngineConfig, SemanticRelationship, SemanticSynonym, SemanticTable
from .bootstrap_data import (
    COLUMN_SPECS,
    DEFAULT_RELATIONSHIPS,
    DEFAULT_SELECT_PREFIX,
)
from .dictionary_service import ensure_engine_config, invalidate_dictionary_cache


@transaction.atomic
def import_rti_bootstrap(owner, replace=False) -> dict:
    if replace:
        SemanticTable.objects.filter(owner=owner).delete()
        SemanticRelationship.objects.filter(owner=owner).delete()
    config = ensure_engine_config(owner)
    db_label = (config.database_name or "").strip() or "semantic"
    table_cache = {}
    created_columns = 0
    created_synonyms = 0
    for spec in COLUMN_SPECS:
        tname, alias, tdisplay, physical, sql_alias, display, dtype, sensitive, syns = spec
        table = table_cache.get(tname)
        if not table:
            table, _ = SemanticTable.objects.get_or_create(
                owner=owner,
                database_name=db_label,
                table_name=tname,
                defaults={
                    "table_alias": alias,
                    "display_name": tdisplay,
                    "description": tdisplay,
                },
            )
            table_cache[tname] = table
        col, created = SemanticColumn.objects.get_or_create(
            semantic_table=table,
            physical_column=physical,
            defaults={
                "sql_alias": sql_alias,
                "display_name": display,
                "data_type": dtype,
                "sensitive": sensitive,
            },
        )
        if created:
            created_columns += 1
        for syn in syns:
            _, syn_created = SemanticSynonym.objects.get_or_create(
                semantic_column=col,
                synonym=syn[:200],
                language_code="en",
            )
            if syn_created:
                created_synonyms += 1
    for rel in DEFAULT_RELATIONSHIPS:
        SemanticRelationship.objects.get_or_create(
            owner=owner,
            source_table=rel["source_table"],
            source_column=rel["source_column"],
            target_table=rel["target_table"],
            target_column=rel["target_column"],
            defaults={
                "join_type": rel["join_type"],
                "join_condition": rel["join_condition"],
            },
        )
    invalidate_dictionary_cache(owner.id)
    return {
        "tables": len(table_cache),
        "columns": len(COLUMN_SPECS),
        "created_columns": created_columns,
        "created_synonyms": created_synonyms,
        "select_prefix_hint": DEFAULT_SELECT_PREFIX[:80] + "...",
    }


def export_dictionary(owner) -> dict:
    from .dictionary_service import load_dictionary

    config = SemanticEngineConfig.objects.filter(owner=owner).first()
    return {
        "config": {
            "database_name": config.database_name if config else "",
            "base_from_sql": config.base_from_sql if config else "",
            "enabled": config.enabled if config else False,
        },
        "dictionary": load_dictionary(owner, use_cache=False),
    }
