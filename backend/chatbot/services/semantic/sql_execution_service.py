"""Execute validated SQL with parameters."""

from ..external_db import assert_select, connect
from .dictionary_service import column_by_ref
from .sql_normalize import normalize_report_sql


def _cell(value):
    from ..external_db import _cell as ec

    return ec(value)


def _public_row(row: dict, dictionary: dict) -> dict:
    cleaned = {}
    for key, value in row.items():
        ref = None
        for col in dictionary["columns"]:
            if col["sql_alias"] == key or col["physical"] == key:
                ref = col
                break
        if ref and ref["sensitive"]:
            continue
        cleaned[key] = value
    return cleaned or row


def run_query(engine, connection_string, sql, params, dictionary, limit=40):
    statement = assert_select(normalize_report_sql(sql))
    if statement.count("%s") != len(params):
        raise ValueError("Parameter count does not match placeholders.")
    connection = connect(engine, connection_string)
    try:
        cursor = connection.cursor()
        cursor.execute(statement, params)
        columns = [col[0] for col in (cursor.description or [])]
        rows = []
        for record in cursor.fetchmany(limit):
            row = {columns[i]: _cell(record[i]) for i in range(len(columns))}
            rows.append(_public_row(row, dictionary))
        return rows
    finally:
        connection.close()
