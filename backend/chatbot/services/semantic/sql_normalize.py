"""Normalize report SQL so validation and execution always see a SELECT."""

import re

_COMMENT_LINE = re.compile(r"^\s*--[^\n]*\n?", re.M)
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_WORD_SELECT = re.compile(r"\bselect\b", re.I)
_WORD_WITH = re.compile(r"\bwith\b", re.I)
_WORD_FROM = re.compile(r"\bfrom\b", re.I)


def normalize_report_sql(sql: str) -> str:
    text = (sql or "").strip().lstrip("\ufeff")
    if text.endswith(";"):
        text = text[:-1].strip()
    text = _COMMENT_BLOCK.sub("", text)
    text = _COMMENT_LINE.sub("", text)
    text = text.strip()
    if not text:
        raise ValueError("SQL query is empty.")

    collapsed = " ".join(text.lower().split())
    if collapsed.startswith("select ") or collapsed.startswith("with "):
        return text
    if collapsed.startswith("from "):
        match = _WORD_FROM.search(text)
        if match:
            return f"SELECT * {text[match.start():].lstrip()}"
    if re.match(r"^[a-z0-9_.]+\s*,", collapsed) or collapsed.startswith("a."):
        return f"SELECT {text}"

    for pattern in (_WORD_SELECT, _WORD_WITH):
        match = pattern.search(text)
        if match:
            return text[match.start() :].lstrip()

    match = _WORD_FROM.search(text)
    if match:
        return f"SELECT * {text[match.start():].lstrip()}"

    raise ValueError(
        "Report SQL must start with SELECT or FROM (FROM will be wrapped as SELECT * ...)."
    )
