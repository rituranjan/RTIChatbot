"""Build parameterized SELECT from intent and dictionary."""

import re

from .connection_resolver import resolve_base_select
from .sql_normalize import normalize_report_sql


def build_query(config, dictionary: dict, filters: list[dict], limit: int) -> tuple[str, tuple]:
    base_sql = normalize_report_sql(resolve_base_select(config))
    params = []
    where_parts = []
    for item in filters:
        ref = item["column"]
        op = (item.get("operator") or "=").upper()
        value = item.get("value")
        col = next((c for c in dictionary["columns"] if c["ref"].lower() == ref.lower()), None)
        if not col or not col["filterable"]:
            continue
        if op == "LIKE":
            where_parts.append(f"{ref} LIKE %s")
            params.append(value)
        else:
            where_parts.append(f"{ref} = %s")
            params.append(value)
    if where_parts:
        clause = " AND ".join(where_parts)
        if re.search(r"\bwhere\b", base_sql, re.I):
            sql = f"{base_sql} AND {clause}\nLIMIT %s"
        else:
            sql = f"{base_sql} WHERE {clause}\nLIMIT %s"
    else:
        sql = f"{base_sql}\nLIMIT %s"
    params.append(int(limit))
    return sql, tuple(params)
