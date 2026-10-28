"""One private database per account for chats, filters, and search."""
import re
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import connections

from ..models import Conversation, Message, UserProfile, VisitorProfile
from .tenant_context import current_alias, set_alias

PLANS = UserProfile.PLANS


def postgres_enabled() -> bool:
    return bool(getattr(settings, "TENANT_PG_HOST", "") or "")


def database_name_for(user) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (user.username or "").lower()).strip("_") or "user"
    return f"tenant_{slug[:40]}_{user.id}"


def sqlite_file(profile) -> Path:
    root = Path(getattr(settings, "TENANT_DB_DIR", Path(settings.BASE_DIR) / "tenants"))
    return root / f"{profile.database_name}.sqlite3"


def alias_for(profile) -> str:
    return f"tenant_{profile.user_id}"


def _running_test_class():
    import inspect
    import sys

    if "test" not in sys.argv:
        return None
    for frame_info in inspect.stack():
        candidate = frame_info.frame.f_locals.get("self")
        databases = getattr(candidate, "databases", None)
        if isinstance(databases, (set, frozenset)) and "default" in databases:
            return type(candidate)
    return None


def _allow_test_alias(alias: str) -> None:
    """Django's test runner blocks aliases that did not exist when the test started."""
    cls = _running_test_class()
    if cls is None:
        return
    allowed = set(cls.databases)
    allowed.add(alias)
    cls.databases = allowed


def _forget_test_alias(alias: str) -> None:
    cls = _running_test_class()
    if cls is None:
        return
    allowed = set(cls.databases)
    allowed.discard(alias)
    cls.databases = allowed


def register_database(profile) -> str:
    alias = alias_for(profile)
    config = settings.DATABASES["default"].copy()
    config["OPTIONS"] = dict(config.get("OPTIONS") or {})
    config["ATOMIC_REQUESTS"] = False
    config["CONN_MAX_AGE"] = 0
    if profile.engine == "postgresql":
        config.update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": profile.database_name,
                "USER": settings.TENANT_PG_USER,
                "PASSWORD": settings.TENANT_PG_PASSWORD,
                "HOST": settings.TENANT_PG_HOST,
                "PORT": settings.TENANT_PG_PORT,
            }
        )
    else:
        path = sqlite_file(profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        config.update(
            {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(path),
                "USER": "",
                "PASSWORD": "",
                "HOST": "",
                "PORT": "",
            }
        )
    settings.DATABASES[alias] = config
    current = getattr(connections._connections, alias, None)
    if current is not None and current.settings_dict.get("NAME") != config["NAME"]:
        current.close()
        del connections[alias]
    _allow_test_alias(alias)
    return alias


def _create_postgres(name: str) -> None:
    import psycopg2
    from psycopg2 import sql

    connection = psycopg2.connect(
        dbname=settings.TENANT_PG_MAINTENANCE_DB,
        user=settings.TENANT_PG_USER,
        password=settings.TENANT_PG_PASSWORD,
        host=settings.TENANT_PG_HOST,
        port=settings.TENANT_PG_PORT,
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name])
            if cursor.fetchone():
                return
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        connection.close()


def _drop_postgres(name: str) -> None:
    import psycopg2
    from psycopg2 import sql

    connection = psycopg2.connect(
        dbname=settings.TENANT_PG_MAINTENANCE_DB,
        user=settings.TENANT_PG_USER,
        password=settings.TENANT_PG_PASSWORD,
        host=settings.TENANT_PG_HOST,
        port=settings.TENANT_PG_PORT,
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                [name],
            )
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    finally:
        connection.close()


def ensure_schema(alias: str) -> None:
    existing = set(connections[alias].introspection.table_names())
    with connections[alias].schema_editor() as editor:
        for model in (Conversation, Message, VisitorProfile):
            if model._meta.db_table not in existing:
                editor.create_model(model)


def _stamp(model, alias, pk, created_at, updated_at=None):
    fields = {"created_at": created_at}
    if updated_at is not None:
        fields["updated_at"] = updated_at
    model.objects.using(alias).filter(pk=pk).update(**fields)


def move_chats_to_tenant(user, alias: str) -> int:
    conversations = list(
        Conversation.objects.using("default").filter(owner_id=user.id).order_by("created_at")
    )
    for conv in conversations:
        Conversation.objects.using(alias).update_or_create(
            id=conv.id,
            defaults={
                "owner_id": conv.owner_id,
                "title": conv.title,
                "embed_bot_id": conv.embed_bot_id,
                "visitor_id": conv.visitor_id,
            },
        )
        _stamp(Conversation, alias, conv.id, conv.created_at, conv.updated_at)
        for message in Message.objects.using("default").filter(conversation_id=conv.id):
            Message.objects.using(alias).update_or_create(
                id=message.id,
                defaults={
                    "conversation_id": conv.id,
                    "role": message.role,
                    "content": message.content,
                    "sources": message.sources,
                },
            )
            _stamp(Message, alias, message.id, message.created_at)
        profile = VisitorProfile.objects.using("default").filter(conversation_id=conv.id).first()
        if profile:
            VisitorProfile.objects.using(alias).update_or_create(
                id=profile.id,
                defaults={"conversation_id": conv.id, "answers": profile.answers},
            )
            _stamp(VisitorProfile, alias, profile.id, profile.created_at)
    if conversations:
        Conversation.objects.using("default").filter(owner_id=user.id).delete()
    return len(conversations)


def provision_tenant(user, plan=None) -> UserProfile:
    if plan is not None and plan not in PLANS:
        raise ValueError("Choose Basic, Silver, Gold, or Diamond.")
    profile = UserProfile.objects.filter(user=user).first()
    if profile is None:
        profile = UserProfile(user=user, database_name=database_name_for(user))
    if plan:
        profile.plan = plan
    if not profile.database_name:
        profile.database_name = database_name_for(user)
    profile.engine = "postgresql" if postgres_enabled() else "sqlite"
    try:
        if profile.engine == "postgresql":
            _create_postgres(profile.database_name)
        alias = register_database(profile)
        ensure_schema(alias)
        if not profile.migrated:
            move_chats_to_tenant(user, alias)
            profile.migrated = True
        profile.ready = True
        profile.error = ""
    except Exception as exc:
        profile.ready = False
        profile.error = str(exc).splitlines()[0][:500]
    profile.save()
    return profile


def close_alias(profile) -> None:
    alias = alias_for(profile)
    try:
        connections[alias].close()
    except Exception:
        pass
    try:
        del connections[alias]
    except Exception:
        pass
    settings.DATABASES.pop(alias, None)
    _forget_test_alias(alias)


def drop_tenant(profile) -> None:
    close_alias(profile)
    if profile.engine == "postgresql":
        if not postgres_enabled():
            raise ValueError("PostgreSQL is not configured, so the account database could not be removed.")
        _drop_postgres(profile.database_name)
        return
    path = sqlite_file(profile)
    for extra in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            extra.unlink(missing_ok=True)
        except OSError as exc:
            raise ValueError(f"Could not remove the account database: {exc}") from exc


@contextmanager
def use_tenant(user):
    previous = current_alias()
    profile = UserProfile.objects.filter(user=user).first() if user is not None else None
    if profile is not None and profile.ready:
        set_alias(register_database(profile))
    else:
        set_alias(None)
    try:
        yield current_alias()
    finally:
        set_alias(previous)
