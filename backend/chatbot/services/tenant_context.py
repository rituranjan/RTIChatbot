import threading

_state = threading.local()


def current_alias():
    return getattr(_state, "alias", None)


def set_alias(alias):
    _state.alias = alias
