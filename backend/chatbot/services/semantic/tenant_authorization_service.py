"""Platform and workspace authorization for semantic SQL."""

from ...models import AppSetting
from ..plan_access import semantic_sql_enabled_for
from .connection_resolver import resolve_connection
from .dictionary_service import get_engine_config


def platform_enabled() -> bool:
    setting = AppSetting.objects.filter(pk=1).first()
    raw = (setting.semantic_sql_settings if setting else None) or {}
    return bool(raw.get("platform_enabled", True))


def workspace_authorized(owner) -> tuple[bool, str]:
    if not platform_enabled():
        return False, "Semantic SQL is disabled platform-wide."
    if not semantic_sql_enabled_for(owner):
        return False, "Your plan does not include natural-language SQL."
    config = get_engine_config(owner)
    if not config:
        return False, "Configure SQL studio for this workspace."
    if (config.chat_sql_mode or "keywords") != "semantic":
        return False, "Chat is using SQL keywords mode. Switch to Semantic Text-to-SQL on the SQL studio page."
    conn = resolve_connection(config)
    if not conn:
        return False, (
            "Choose a report SQL query on the SQL & natural language page (saved SELECT + database)."
        )
    if config.report_query_id and not config.report_query.enabled:
        return False, "The semantic report SQL query is disabled."
    return True, ""


def apply_tenant_filter(config, filters: list[dict], owner) -> list[dict]:
    column = (config.tenant_filter_column or "").strip()
    if not column:
        return filters
    extra = {"column": column, "operator": "=", "value": owner.id}
    if any(f.get("column") == column for f in filters):
        return filters
    return filters + [extra]
