"""Resolve database connection and base SQL from workspace config (no hardcoded DSN)."""

from ...models import DataConnection


def resolve_connection(config) -> DataConnection | None:
    if not config:
        return None
    query = getattr(config, "report_query", None)
    if query and query.connection_id:
        conn = query.connection
        if conn and conn.enabled:
            return conn
    conn = getattr(config, "connection", None)
    if conn and conn.enabled:
        return conn
    return None


def resolve_base_select(config) -> str:
    query = getattr(config, "report_query", None)
    if query:
        if not query.enabled:
            raise ValueError("The chosen report SQL query is disabled.")
        text = (query.sql_text or "").strip().rstrip(";")
        if not text:
            raise ValueError("The report SQL query has no SQL text.")
        return text
    base = (config.base_from_sql or "").strip().rstrip(";")
    if base:
        return base
    raise ValueError(
        "Choose a saved SELECT under SQL keywords as the semantic report query "
        "(Knowledge → SQL keywords), or set optional base SQL in semantic settings."
    )


def resolve_database_name(config, connection: DataConnection | None) -> str:
    name = (config.database_name or "").strip()
    if name:
        return name
    if not connection:
        return ""
    from ..external_db import _parts

    try:
        return (_parts(connection.connection_string).get("database") or "").strip()
    except ValueError:
        return ""
