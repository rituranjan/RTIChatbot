"""Read-only connections to a database the owner configures."""
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote, unquote, urlparse
from uuid import UUID

ENGINES = {"sqlite", "mysql", "postgresql", "mssql"}

_FORBIDDEN = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "exec",
    "execute",
    "grant",
    "revoke",
    "merge",
    "attach",
    "detach",
    "pragma",
    "copy",
    "call",
)


def assert_select(sql: str) -> str:
    """Allow one read-only SELECT. Reject anything that can change data."""
    try:
        from .semantic.sql_normalize import normalize_report_sql

        text = normalize_report_sql(sql)
    except ValueError:
        text = (sql or "").strip()
        if text.endswith(";"):
            text = text[:-1].strip()
    if not text:
        raise ValueError("SQL query is empty.")
    if ";" in text:
        raise ValueError("Use a single SELECT query.")
    lowered = " ".join(text.lower().split())
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("Only a SELECT query can run.")
    words = set(lowered.replace("(", " ").replace(")", " ").split())
    blocked = words.intersection(_FORBIDDEN)
    if blocked:
        raise ValueError(f"Only a read-only SELECT is allowed ({', '.join(sorted(blocked))}).")
    if "@keyword".count("@") and text.count("@keyword") > 1:
        raise ValueError("Use @keyword at most once.")
    return text


def _cell(value):
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, (datetime, date, Decimal, UUID)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")[:500]
    return str(value)[:500]


def _rows(cursor, limit=40):
    columns = [col[0] for col in (cursor.description or [])]
    records = []
    for record in cursor.fetchmany(limit):
        records.append({columns[i]: _cell(record[i]) for i in range(len(columns))})
    return records


def _parts(connection_string):
    raw = (connection_string or "").strip()
    if not raw:
        raise ValueError("Connection string is empty.")
    if "=" in raw and "://" not in raw.split()[0]:
        fields = {}
        for piece in raw.split(";"):
            if "=" not in piece:
                continue
            key, value = piece.split("=", 1)
            fields[key.strip().lower()] = value.strip()
        host = fields.get("server") or fields.get("data source") or fields.get("host") or ""
        port = None
        if "," in host:
            host, port_text = host.split(",", 1)
            port = int(port_text.strip() or "0") or None
        return {
            "host": host,
            "port": int(fields["port"]) if fields.get("port") else port,
            "user": fields.get("user id") or fields.get("uid") or fields.get("user") or "",
            "password": fields.get("password") or fields.get("pwd") or "",
            "database": fields.get("database") or fields.get("initial catalog") or "",
        }
    parsed = urlparse(raw)
    database = unquote((parsed.path or "").lstrip("/"))
    return {
        "host": parsed.hostname or "",
        "port": parsed.port,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


def sqlite_path(connection_string):
    """Turn the connection string saved in the UI into a file path."""
    raw = (connection_string or "").strip().strip('"').strip("'")
    lowered = raw.lower()
    for prefix in ("sqlite:///", "sqlite://", "sqllite=", "sqlite="):
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    raw = raw.replace("\\", "/").strip()
    if not raw:
        raise ValueError("SQLite connection string needs a file path.")
    if len(raw) > 2 and raw[1] == ":":
        drive = raw[0].lower()
        rest = raw[2:].lstrip("/")
        return f"/host_{drive}/{rest}" if rest else f"/host_{drive}"
    return raw


def _sqlite_tables(connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def connect(engine, connection_string):
    engine = (engine or "").strip().lower()
    if engine not in ENGINES:
        raise ValueError("Choose SQLite, MySQL, SQL Server, or PostgreSQL.")
    if engine == "sqlite":
        path = sqlite_path(connection_string)
        if not os.path.isfile(path):
            raise ValueError(f"SQLite file not found: {(connection_string or '').strip()}")
        return sqlite3.connect(f"file:{quote(path, safe='/')}?mode=ro", uri=True, timeout=8)

    parts = _parts(connection_string)
    if not parts["host"] or not parts["database"]:
        raise ValueError("Connection string needs a server and a database name.")

    if engine == "mysql":
        import pymysql

        return pymysql.connect(
            host=parts["host"],
            port=parts["port"] or 3306,
            user=parts["user"],
            password=parts["password"],
            database=parts["database"],
            connect_timeout=8,
            read_timeout=12,
            write_timeout=12,
        )
    if engine == "postgresql":
        import psycopg2

        return psycopg2.connect(
            host=parts["host"],
            port=parts["port"] or 5432,
            user=parts["user"],
            password=parts["password"],
            dbname=parts["database"],
            connect_timeout=8,
        )
    import pymssql

    return pymssql.connect(
        server=parts["host"],
        port=str(parts["port"] or 1433),
        user=parts["user"],
        password=parts["password"],
        database=parts["database"],
        login_timeout=8,
        timeout=12,
    )


def run_select(engine, connection_string, sql, keyword="", limit=40):
    statement = assert_select(sql)
    placeholder = "?" if engine == "sqlite" else "%s"
    params = ()
    if "@keyword" in statement:
        statement = statement.replace("@keyword", placeholder)
        params = (keyword,)
    connection = connect(engine, connection_string)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(statement, params)
        except sqlite3.OperationalError as exc:
            if engine == "sqlite" and "no such table" in str(exc).lower():
                names = _sqlite_tables(connection)
                shown = ", ".join(names[:40]) or "none"
                raise ValueError(
                    f"{exc}. This connection opened {sqlite_path(connection_string)}. "
                    f"Tables in that file: {shown}."
                ) from exc
            raise
        return _rows(cursor, limit=limit)
    finally:
        connection.close()


def test_connection(engine, connection_string):
    connection = connect(engine, connection_string)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        if engine == "sqlite":
            names = _sqlite_tables(connection)
            return (
                f"Connected to {sqlite_path(connection_string)}. "
                f"{len(names)} tables, including {', '.join(names[:12])}."
            )
    finally:
        connection.close()
    return "Connected."
