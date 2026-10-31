"""MySQL INFORMATION_SCHEMA discovery (review-only)."""

from ..external_db import connect, _parts


def discover_mysql(connection_string, database_name: str) -> dict:
    parts = _parts(connection_string)
    db = database_name or parts.get("database") or ""
    connection = connect("mysql", connection_string)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (db,),
        )
        tables = {}
        for table_name, column_name, data_type in cursor.fetchall():
            tables.setdefault(table_name, []).append(
                {"column": column_name, "data_type": data_type}
            )
        return {"database": db, "tables": tables}
    finally:
        connection.close()
