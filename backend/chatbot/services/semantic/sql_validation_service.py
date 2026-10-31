"""Validate generated SQL against the semantic dictionary."""

import re

from .dictionary_service import allowed_column_refs
from .sql_normalize import normalize_report_sql

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|exec|execute|call)\b",
    re.I,
)


def validate_sql(sql: str, dictionary: dict) -> str:
    text = normalize_report_sql(sql)
    if ";" in text:
        raise ValueError("Only one statement is allowed.")
    collapsed = " ".join(text.lower().split())
    if not (collapsed.startswith("select ") or collapsed.startswith("with ")):
        raise ValueError("Only SELECT is allowed.")
    if _FORBIDDEN.search(text.lower()):
        raise ValueError("Only read-only SELECT is allowed.")
    allowed = allowed_column_refs(dictionary)
    where_match = re.search(r"\bwhere\b", text, re.I)
    scan_text = text[where_match.start() :] if where_match else ""
    for match in re.finditer(r"\b([a-z]{1,3})\.([a-zA-Z_][\w]*)\b", scan_text):
        ref = f"{match.group(1)}.{match.group(2)}".lower()
        if ref not in allowed:
            raise ValueError(f"Column not in semantic dictionary: {ref}")
    return text
