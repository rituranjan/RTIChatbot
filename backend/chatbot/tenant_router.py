"""Send chat rows to the account database, and admin settings to their own database."""
from django.conf import settings

from .services.tenant_context import current_alias

TENANT_MODELS = {"conversation", "message", "visitorprofile"}
ADMIN_MODELS = {"appsetting", "errorevent", "prompttemplate", "promptversion"}


class TenantRouter:
    def db_for_read(self, model, **hints):
        admin = self._admin_db(model)
        if admin:
            return admin
        return self._route(model, hints.get("instance"))

    def db_for_write(self, model, **hints):
        admin = self._admin_db(model)
        if admin:
            return admin
        return self._route(model, hints.get("instance"))

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        name = model_name or ""
        if name in ADMIN_MODELS:
            if "admin" in settings.DATABASES:
                return db == "admin"
            return db == "default"
        if db == "admin":
            return False
        if db != "default":
            return False
        return None

    def _admin_db(self, model):
        if model._meta.app_label != "chatbot" or model._meta.model_name not in ADMIN_MODELS:
            return None
        if "admin" in settings.DATABASES:
            return "admin"
        return None

    def _route(self, model, instance):
        if model._meta.app_label != "chatbot" or model._meta.model_name not in TENANT_MODELS:
            return None
        if instance is not None:
            cached = getattr(instance._state, "fields_cache", {})
            parent = cached.get("conversation")
            parent_db = getattr(getattr(parent, "_state", None), "db", None)
            if parent_db:
                return parent_db
            own_db = instance._state.db
            if own_db:
                return own_db
        return current_alias()
