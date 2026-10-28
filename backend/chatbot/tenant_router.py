"""Send chat rows to the account database selected for this request."""
from .services.tenant_context import current_alias

TENANT_MODELS = {"conversation", "message", "visitorprofile"}


class TenantRouter:
    def db_for_read(self, model, **hints):
        return self._route(model, hints.get("instance"))

    def db_for_write(self, model, **hints):
        return self._route(model, hints.get("instance"))

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "default":
            return None
        return False

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
