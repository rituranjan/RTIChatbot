"""Per-plan OpenRouter models, monthly limits, and the email sent when a limit is hit."""
import logging

from django.core.mail import get_connection, send_mail
from django.utils import timezone

from ..models import MonthlyUsage, UserChatSetting, UserProfile, default_plan_access

log = logging.getLogger(__name__)

PLAN_ORDER = ("basic", "silver", "gold", "diamond")
PLAN_LABELS = {"basic": "Basic", "silver": "Silver", "gold": "Gold", "diamond": "Diamond"}


def _whole(value, label, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if number < 0 or number > maximum:
        raise ValueError(f"{label} must be between 0 and {maximum}. Use 0 for no limit.")
    return number


def merged_access(config=None):
    from .admin_settings import load_settings, plan_schedule

    config = config or load_settings()
    saved = config.plan_access if isinstance(config.plan_access, dict) else {}
    days = plan_schedule(config)
    defaults = default_plan_access()
    result = {}
    for key in PLAN_ORDER:
        base = defaults[key]
        raw = saved.get(key) if isinstance(saved.get(key), dict) else {}
        models = []
        for item in raw.get("models") or []:
            name = str(item or "").strip()
            if name and name not in models:
                models.append(name[:120])
        raw_names = raw.get("model_names") if isinstance(raw.get("model_names"), dict) else {}
        model_names = {}
        for name in models[:40]:
            label = str(raw_names.get(name) or name).strip() or name
            model_names[name] = label[:200]
        try:
            day_value = int(raw["days"]) if "days" in raw else days[key]
        except (TypeError, ValueError, KeyError):
            day_value = days[key]

        def number(field, fallback, source=raw):
            if field not in source:
                return fallback
            try:
                return max(0, int(source.get(field) or 0))
            except (TypeError, ValueError):
                return fallback

        message = str(raw.get("limit_message") or base["limit_message"]).strip()
        lang_on = raw.get("language_enabled")
        if isinstance(lang_on, str):
            language_enabled = lang_on.strip().lower() not in ("0", "false", "no", "off")
        elif lang_on is None:
            language_enabled = bool(base.get("language_enabled", False))
        else:
            language_enabled = bool(lang_on)
        kw_on = raw.get("sql_keyword_enabled")
        if isinstance(kw_on, str):
            sql_keyword_enabled = kw_on.strip().lower() not in ("0", "false", "no", "off")
        elif kw_on is None:
            sql_keyword_enabled = bool(base.get("sql_keyword_enabled", True))
        else:
            sql_keyword_enabled = bool(kw_on)
        sem_on = raw.get("semantic_sql_enabled")
        if isinstance(sem_on, str):
            semantic_sql_enabled = sem_on.strip().lower() not in ("0", "false", "no", "off")
        elif sem_on is None:
            semantic_sql_enabled = bool(base.get("semantic_sql_enabled", True))
        else:
            semantic_sql_enabled = bool(sem_on)
        result[key] = {
            "days": max(0, min(3650, day_value)),
            "models": models[:40],
            "model_names": model_names,
            "monthly_requests": number("monthly_requests", base["monthly_requests"]),
            "input_tokens": number("input_tokens", 0),
            "output_tokens": number("output_tokens", 0),
            "cached_tokens": number("cached_tokens", 0),
            "website_max_pages": number("website_max_pages", base.get("website_max_pages", 1), raw),
            "language_enabled": language_enabled,
            "sql_keyword_enabled": sql_keyword_enabled,
            "semantic_sql_enabled": semantic_sql_enabled,
            "concurrent_users": number("concurrent_users", base.get("concurrent_users", 0), raw),
            "max_embed_domains": number("max_embed_domains", base.get("max_embed_domains", 0), raw),
            "limit_message": (message or base["limit_message"])[:2000],
        }
    return result


def clean_plan_access(incoming):
    if not isinstance(incoming, dict):
        raise ValueError("Enter settings for each plan.")
    cleaned = {}
    for key in PLAN_ORDER:
        raw = incoming.get(key)
        label = PLAN_LABELS[key]
        if not isinstance(raw, dict):
            raise ValueError(f"Enter settings for the {label} plan.")
        models = []
        for item in raw.get("models") or []:
            name = str(item or "").strip()
            if not name or name in models:
                continue
            if len(name) > 120 or any(char.isspace() for char in name):
                raise ValueError("Choose a model id such as openai/gpt-4o.")
            models.append(name)
        if len(models) > 40:
            raise ValueError("Each plan can include at most 40 models.")
        raw_names = raw.get("model_names") if isinstance(raw.get("model_names"), dict) else {}
        model_names = {}
        for name in models:
            label = str(raw_names.get(name) or name).strip() or name
            model_names[name] = label[:200]
        message = str(raw.get("limit_message") or "").strip()
        if not message:
            raise ValueError(f"Enter the limit message for the {label} plan.")
        cleaned[key] = {
            "days": _whole(raw.get("days"), f"{label} days", 3650),
            "models": models,
            "model_names": model_names,
            "monthly_requests": _whole(raw.get("monthly_requests"), f"{label} monthly requests", 1_000_000),
            "input_tokens": _whole(raw.get("input_tokens"), f"{label} input tokens", 100_000_000),
            "output_tokens": _whole(raw.get("output_tokens"), f"{label} output tokens", 100_000_000),
            "cached_tokens": _whole(raw.get("cached_tokens"), f"{label} cached tokens", 100_000_000),
            "website_max_pages": _whole(raw.get("website_max_pages"), f"{label} website RAG page limit", 10_000),
            "language_enabled": bool(raw.get("language_enabled")),
            "sql_keyword_enabled": bool(raw.get("sql_keyword_enabled", True)),
            "semantic_sql_enabled": bool(raw.get("semantic_sql_enabled", True)),
            "concurrent_users": _whole(raw.get("concurrent_users"), f"{label} concurrent users", 10_000),
            "max_embed_domains": _whole(raw.get("max_embed_domains"), f"{label} embed domains", 10_000),
            "limit_message": message[:2000],
        }
    return cleaned


def user_plan(user) -> str:
    profile = UserProfile.objects.filter(user=user).first()
    if profile and profile.plan in PLAN_ORDER:
        return profile.plan
    return "basic"


def rules_for(user) -> dict:
    return merged_access()[user_plan(user)]


def website_max_pages_for(user) -> int:
    """Max single pages in the RAG page list for this plan (0 = unlimited)."""
    return max(0, int(rules_for(user).get("website_max_pages") or 0))


def website_rag_page_count(owner) -> int:
    from ..models import WebRagPage

    return WebRagPage.objects.filter(owner=owner).count()


def assert_website_rag_quota(owner, adding: int = 1) -> None:
    from ..models import WebRagPage

    cap = website_max_pages_for(owner)
    if cap <= 0:
        return
    adding = max(1, int(adding or 1))
    count = WebRagPage.objects.filter(owner=owner).count()
    if count + adding > cap:
        label = "page" if cap == 1 else "pages"
        raise ValueError(
            f"Your plan allows {cap} RAG {label}. Remove one or ask an admin to raise the limit."
        )


def language_enabled_for(user) -> bool:
    return bool(rules_for(user).get("language_enabled"))


def sql_keyword_enabled_for(user) -> bool:
    return bool(rules_for(user).get("sql_keyword_enabled", True))


def semantic_sql_enabled_for(user) -> bool:
    return bool(rules_for(user).get("semantic_sql_enabled", True))


def concurrent_users_for(user) -> int:
    return max(0, int(rules_for(user).get("concurrent_users") or 0))


def chosen_model(user):
    """The OpenRouter model id this account chose, and the name shown in the menu."""
    if user is None or not getattr(user, "is_authenticated", True):
        return "", ""
    rules = rules_for(user)
    allowed = rules["models"]
    names = rules.get("model_names") or {}
    setting = UserChatSetting.objects.filter(user=user).first()
    chosen = (setting.selected_model if setting else "") or ""
    model_id = chosen if chosen in allowed else (allowed[0] if allowed else "")
    return model_id, (names.get(model_id) or model_id)


def model_for(user) -> str:
    return chosen_model(user)[0]


def current_usage(user) -> MonthlyUsage:
    now = timezone.localtime()
    row, _created = MonthlyUsage.objects.get_or_create(
        user=user, year=now.year, month=now.month
    )
    return row


def openrouter_key(config=None) -> str:
    from django.conf import settings

    from .admin_settings import load_settings

    config = config or load_settings()
    stored = (config.openrouter_api_key or "").strip()
    if stored:
        return stored
    return (settings.OPENROUTER_API_KEY or "").strip()


def mail_public(config) -> dict:
    raw = config.mail_settings if isinstance(config.mail_settings, dict) else {}
    try:
        port = int(raw.get("port") or 587)
    except (TypeError, ValueError):
        port = 587
    return {
        "host": str(raw.get("host") or ""),
        "port": port,
        "username": str(raw.get("username") or ""),
        "from_email": str(raw.get("from_email") or ""),
        "use_tls": bool(raw.get("use_tls", True)),
        "password_set": bool(raw.get("password")),
        "subject": str(raw.get("subject") or "Your chat plan limit was reached"),
    }


def clean_mail(incoming, config) -> dict:
    if not isinstance(incoming, dict):
        raise ValueError("Enter the mail server settings.")
    host = str(incoming.get("host") or "").strip()
    username = str(incoming.get("username") or "").strip()
    from_email = str(incoming.get("from_email") or "").strip()
    try:
        port = int(incoming.get("port") or 587)
    except (TypeError, ValueError):
        raise ValueError("Mail port must be a whole number.")
    if port < 1 or port > 65535:
        raise ValueError("Mail port must be between 1 and 65535.")
    previous = config.mail_settings if isinstance(config.mail_settings, dict) else {}
    password = str(incoming.get("password") or "")
    if not password:
        password = str(previous.get("password") or "")
    if host and not from_email:
        raise ValueError("Enter the From address used for limit emails.")
    subject = str(incoming.get("subject") or "Your chat plan limit was reached").strip()
    if not subject:
        subject = "Your chat plan limit was reached"
    return {
        "host": host[:200],
        "port": port,
        "username": username[:200],
        "password": password[:300],
        "from_email": from_email[:200],
        "use_tls": bool(incoming.get("use_tls", True)),
        "subject": subject[:200],
    }


def _reasons(user):
    """Monthly caps that block further chat. Token limits are enforced per request, not monthly."""
    rules = rules_for(user)
    usage = current_usage(user)
    if rules["monthly_requests"] > 0 and usage.requests >= rules["monthly_requests"]:
        return ["monthly requests"]
    return []


def per_request_input_cap(user) -> int:
    rules = rules_for(user)
    cap = int(rules.get("input_tokens") or 0)
    if cap > 0:
        return cap
    policy = llm_policy()
    return int(policy.get("default_max_input_tokens_per_request") or 0)


def per_request_output_cap(user) -> int:
    rules = rules_for(user)
    cap = int(rules.get("output_tokens") or 0)
    if cap > 0:
        return cap
    return int(llm_policy()["default_max_output_tokens"])


def send_limit_email(user, message, reasons) -> bool:
    from .admin_settings import load_settings

    address = (getattr(user, "email", "") or "").strip()
    if not address:
        return False
    raw = load_settings().mail_settings
    raw = raw if isinstance(raw, dict) else {}
    host = str(raw.get("host") or "").strip()
    from_email = str(raw.get("from_email") or raw.get("username") or "").strip()
    if not host or not from_email:
        log.warning("Plan limit reached for %s but outgoing mail is not configured.", user.username)
        return False
    try:
        port = int(raw.get("port") or 587)
    except (TypeError, ValueError):
        port = 587
    subject = str(raw.get("subject") or "Your chat plan limit was reached").strip()
    body = f"{message}\n\nThis month the account reached its {', '.join(reasons)}."
    try:
        connection = get_connection(
            host=host,
            port=port,
            username=str(raw.get("username") or ""),
            password=str(raw.get("password") or ""),
            use_tls=bool(raw.get("use_tls", True)),
            timeout=12,
        )
        send_mail(
            subject[:200] or "Your chat plan limit was reached",
            body,
            from_email,
            [address],
            connection=connection,
            fail_silently=False,
        )
    except Exception:
        log.exception("Could not email %s about the plan limit.", user.username)
        return False
    return True


def notify_limit(user, message, reasons) -> None:
    usage = current_usage(user)
    if usage.email_sent or not reasons:
        return
    address = (getattr(user, "email", "") or "").strip()
    if not address or send_limit_email(user, message, reasons):
        usage.email_sent = True
        usage.save(update_fields=["email_sent"])


def limit_reply(user) -> str:
    reasons = _reasons(user)
    if not reasons:
        return ""
    message = rules_for(user)["limit_message"]
    notify_limit(user, message, reasons)
    return message


def llm_policy() -> dict:
    from ..models import default_llm_policy
    from .admin_settings import load_settings

    base = default_llm_policy()
    raw = load_settings().llm_policy
    if isinstance(raw, dict):
        for key in base:
            if key in raw:
                base[key] = raw[key]
    try:
        base["default_max_output_tokens"] = max(
            1, min(8192, int(base.get("default_max_output_tokens") or 2048))
        )
    except (TypeError, ValueError):
        base["default_max_output_tokens"] = 2048
    try:
        base["default_max_input_tokens_per_request"] = max(
            0, int(base.get("default_max_input_tokens_per_request") or 0)
        )
    except (TypeError, ValueError):
        base["default_max_input_tokens_per_request"] = 0
    policy = str(base.get("missing_plan_policy") or "defaults").strip().lower()
    if policy not in ("defaults", "block"):
        policy = "defaults"
    base["missing_plan_policy"] = policy
    return base


def projected_limit_block(user, estimated_input_tokens: int) -> str:
    """Block when monthly requests are exhausted or this request still exceeds input cap after trimming."""
    blocked = limit_reply(user)
    if blocked:
        return blocked
    cap = per_request_input_cap(user)
    if cap > 0 and max(0, estimated_input_tokens) > cap:
        return rules_for(user)["limit_message"]
    return ""


def max_output_tokens_for_request(user) -> int:
    return max(1, min(8192, per_request_output_cap(user)))


def record_usage(user, usage) -> None:
    row = current_usage(user)
    row.requests += 1
    row.input_tokens += int((usage or {}).get("input_tokens") or 0)
    row.output_tokens += int((usage or {}).get("output_tokens") or 0)
    row.cached_tokens += int((usage or {}).get("cached_tokens") or 0)
    row.save(update_fields=["requests", "input_tokens", "output_tokens", "cached_tokens"])
    reasons = _reasons(user)
    if reasons:
        notify_limit(user, rules_for(user)["limit_message"], reasons)


def my_plan_payload(user) -> dict:
    from .languages import chosen_language, language_label, language_public_payload

    from .embed_domains import embed_domains_payload, max_embed_domains_for

    plan = user_plan(user)
    rules = merged_access()[plan]
    usage = current_usage(user)
    setting = UserChatSetting.objects.filter(user=user).first()
    saved_lang = (setting.preferred_language if setting else "") or ""
    return {
        "plan": plan,
        "plan_label": PLAN_LABELS[plan],
        "models": [
            {"id": model_id, "name": (rules.get("model_names") or {}).get(model_id) or model_id}
            for model_id in rules["models"]
        ],
        "selected_model": model_for(user),
        "language": language_public_payload(user),
        "selected_language": saved_lang,
        "effective_language": language_label(chosen_language(user)) if chosen_language(user) else "",
        "limits": {
            "monthly_requests": rules["monthly_requests"],
            "input_tokens": rules["input_tokens"],
            "output_tokens": rules["output_tokens"],
            "cached_tokens": rules["cached_tokens"],
            "website_max_pages": website_max_pages_for(user),
            "concurrent_users": concurrent_users_for(user),
            "max_embed_domains": max_embed_domains_for(user),
            "input_tokens_scope": "per_request",
            "output_tokens_scope": "per_request",
            "sql_keyword_enabled": bool(rules.get("sql_keyword_enabled", True)),
            "semantic_sql_enabled": bool(rules.get("semantic_sql_enabled", True)),
        },
        "usage": {
            "requests": usage.requests,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_tokens": usage.cached_tokens,
        },
        "limit_message": rules["limit_message"],
        "month": f"{usage.year}-{usage.month:02d}",
        **embed_domains_payload(user),
    }


def set_selected_model(user, model=None, preferred_language=None) -> dict:
    from .languages import validate_user_language

    row, _created = UserChatSetting.objects.get_or_create(user=user)
    updates = []
    if model is not None:
        chosen = str(model or "").strip()
        allowed = rules_for(user)["models"]
        if chosen not in allowed:
            raise ValueError("Choose one of the models assigned to this plan.")
        row.selected_model = chosen
        updates.append("selected_model")
    if preferred_language is not None:
        lang = validate_user_language(preferred_language, user=user)
        row.preferred_language = lang
        updates.append("preferred_language")
    if not updates:
        raise ValueError("Nothing to save.")
    row.save(update_fields=updates)
    return my_plan_payload(user)


def openrouter_status(user=None) -> dict:
    from django.conf import settings

    key = openrouter_key()
    model, model_name = ("", "")
    if user is not None and getattr(user, "pk", None):
        model, model_name = chosen_model(user)
    return {
        "configured": bool(key),
        "model": model,
        "model_name": model_name,
        "base_url": settings.OPENROUTER_BASE_URL,
    }
