"""End-to-end semantic text-to-SQL for chat and admin test console."""

import logging

from .connection_resolver import resolve_connection
from .dictionary_service import ensure_engine_config, get_engine_config, load_dictionary
from .matcher_service import extract_filters
from .query_understanding_service import refine_intent
from .sql_execution_service import run_query
from .sql_generation_service import build_query
from .sql_validation_service import validate_sql
from .tenant_authorization_service import apply_tenant_filter, platform_enabled, workspace_authorized

log = logging.getLogger(__name__)


def semantic_enabled(owner) -> bool:
    ok, _ = workspace_authorized(owner)
    return ok


def run_semantic_query(owner, question: str) -> dict | None:
    ok, reason = workspace_authorized(owner)
    if not ok:
        return None
    config = get_engine_config(owner)
    dictionary = load_dictionary(owner)
    if not dictionary["columns"]:
        return {
            "name": "semantic",
            "keyword": "",
            "rows": [],
            "error": "Semantic dictionary is empty. Import mappings in Semantic Text-to-SQL.",
            "sql": "",
        }
    filters, clarifications = extract_filters(question, dictionary)
    if config.use_llm_understanding:
        filters = refine_intent(owner, question, dictionary, filters)
    filters = apply_tenant_filter(config, filters, owner)
    if clarifications and not filters:
        return {
            "name": "semantic",
            "keyword": "",
            "rows": [],
            "error": clarifications[0],
            "sql": "",
        }
    if not filters:
        return None
    limit = min(int(config.max_rows or 40), 200)
    try:
        sql, params = build_query(config, dictionary, filters, limit)
    except ValueError as exc:
        return {
            "name": "semantic",
            "keyword": "",
            "rows": [],
            "error": str(exc),
            "sql": "",
        }
    connection = resolve_connection(config)
    if not connection:
        return {
            "name": "semantic",
            "keyword": "",
            "rows": [],
            "error": "No database connection for semantic SQL.",
            "sql": "",
        }
    try:
        sql = validate_sql(sql, dictionary)
        rows = run_query(
            connection.engine,
            connection.connection_string,
            sql,
            params,
            dictionary,
            limit=limit,
        )
        return {
            "name": "semantic",
            "keyword": "",
            "rows": rows,
            "error": "",
            "sql": sql,
            "params": list(params),
        }
    except Exception as exc:  # noqa: BLE001
        log.info("Semantic query failed: %s", exc)
        return {
            "name": "semantic",
            "keyword": "",
            "rows": [],
            "error": str(exc).splitlines()[0][:300],
            "sql": sql,
        }


def preview_query(owner, question: str) -> dict:
    """Build SQL for the test console. Does not require the engine to be enabled."""
    config = ensure_engine_config(owner)
    dictionary = load_dictionary(owner)
    if not dictionary.get("columns"):
        return {
            "error": "Import the semantic dictionary first (Semantic Text-to-SQL → Import starter dictionary).",
            "sql": "",
            "params": [],
            "filters": [],
        }
    filters, clarifications = extract_filters(question, dictionary)
    if config.use_llm_understanding:
        filters = refine_intent(owner, question, dictionary, filters)
    filters = apply_tenant_filter(config, filters, owner)
    if clarifications and not filters:
        return {"error": clarifications[0], "sql": "", "params": [], "filters": []}
    sql = ""
    params: tuple = ()
    try:
        sql, params = build_query(config, dictionary, filters, min(int(config.max_rows or 40), 200))
        sql = validate_sql(sql, dictionary)
    except ValueError as exc:
        return {
            "error": str(exc),
            "sql": sql,
            "params": list(params),
            "filters": filters,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("Semantic preview failed")
        return {
            "error": str(exc).splitlines()[0][:300],
            "sql": sql,
            "params": list(params),
            "filters": filters,
        }
    hints = []
    if not resolve_connection(config):
        hints.append("Choose a report SQL query on SQL & natural language (saved SELECT + database).")
    if (config.chat_sql_mode or "keywords") != "semantic" and not config.enabled:
        hints.append("Set chat server mode to Semantic Text-to-SQL on the Setup tab.")
    if not platform_enabled():
        hints.append("Semantic SQL is disabled in platform settings.")
    return {
        "error": "",
        "sql": sql,
        "params": list(params),
        "filters": filters,
        "run_hint": " ".join(hints),
    }
