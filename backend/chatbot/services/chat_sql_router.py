"""Which database path chat uses: keyword SQL or semantic NL-to-SQL (one at a time)."""

from .plan_access import rules_for, semantic_sql_enabled_for, sql_keyword_enabled_for
from .semantic.dictionary_service import get_engine_config
from .semantic.query_pipeline import run_semantic_query
from .semantic.tenant_authorization_service import platform_enabled, workspace_authorized
from .sql_lookup import lookup_keywords


def sql_keyword_allowed(user) -> bool:
    return sql_keyword_enabled_for(user)


def semantic_sql_allowed(user) -> bool:
    return semantic_sql_enabled_for(user)


def configured_chat_sql_mode(user) -> str:
    config = get_engine_config(user)
    if not config:
        return "keywords"
    mode = (config.chat_sql_mode or "keywords").strip().lower()
    if mode not in ("keywords", "semantic"):
        mode = "keywords"
    if mode == "semantic" and not semantic_sql_allowed(user):
        mode = "keywords" if sql_keyword_allowed(user) else "keywords"
    if mode == "keywords" and not sql_keyword_allowed(user):
        mode = "semantic" if semantic_sql_allowed(user) else "keywords"
    return mode


def resolve_db_lookups(owner, message: str) -> list:
    if not platform_enabled() and configured_chat_sql_mode(owner) == "semantic":
        pass
    mode = configured_chat_sql_mode(owner)
    if mode == "semantic" and semantic_sql_allowed(owner):
        ok, _ = workspace_authorized(owner)
        if ok:
            result = run_semantic_query(owner, message)
            if result:
                return [
                    {
                        "name": result.get("name") or "semantic",
                        "keyword": result.get("keyword") or "",
                        "rows": result.get("rows") or [],
                        "error": result.get("error") or "",
                    }
                ]
        return []
    if mode == "keywords" and sql_keyword_allowed(owner):
        return lookup_keywords(owner, message)
    return []
