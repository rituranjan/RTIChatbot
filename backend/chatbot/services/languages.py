"""Chat reply languages — India-focused list, configured in Admin settings."""
from ..models import UserChatSetting

# code, English label, native label (shown in dropdown)
CATALOG = [
    ("en", "English", "English"),
    ("hi", "Hindi", "हिन्दी"),
    ("bn", "Bengali", "বাংলা"),
    ("te", "Telugu", "తెలుగు"),
    ("mr", "Marathi", "मराठी"),
    ("ta", "Tamil", "தமிழ்"),
    ("ur", "Urdu", "اردو"),
    ("gu", "Gujarati", "ગુજરાતી"),
    ("kn", "Kannada", "ಕನ್ನಡ"),
    ("ml", "Malayalam", "മലയാളം"),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ"),
    ("or", "Odia", "ଓଡ଼ିଆ"),
    ("as", "Assamese", "অসমীয়া"),
    ("mai", "Maithili", "मैथिली"),
    ("sa", "Sanskrit", "संस्कृत"),
    ("ks", "Kashmiri", "کٲشُر"),
    ("ne", "Nepali", "नेपाली"),
    ("sd", "Sindhi", "سنڌي"),
    ("kok", "Konkani", "कोंकणी"),
    ("mni", "Manipuri", "মৈতৈলোন্"),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ"),
    ("bho", "Bhojpuri", "भोजपुरी"),
]

_CODES = {code for code, _, _ in CATALOG}


def default_language_settings():
    return {
        "enabled": True,
        "required": False,
        "default_code": "en",
        "enabled_codes": [code for code, _, _ in CATALOG],
    }


def _load_raw():
    from .admin_settings import load_settings

    raw = load_settings().language_settings
    if isinstance(raw, dict):
        return raw
    return {}


def merged_language_settings():
    base = default_language_settings()
    raw = _load_raw()
    base["enabled"] = bool(raw.get("enabled", base["enabled"]))
    base["required"] = bool(raw.get("required", base["required"]))
    default_code = str(raw.get("default_code") or base["default_code"]).strip()
    base["default_code"] = default_code if default_code in _CODES else "en"
    codes = raw.get("enabled_codes")
    if isinstance(codes, list):
        cleaned = []
        for item in codes:
            code = str(item or "").strip()
            if code in _CODES and code not in cleaned:
                cleaned.append(code)
        if cleaned:
            base["enabled_codes"] = cleaned
    return base


def clean_language_settings(incoming):
    if not isinstance(incoming, dict):
        raise ValueError("Enter language settings.")
    required = bool(incoming.get("required"))
    default_code = str(incoming.get("default_code") or "en").strip()
    if default_code not in _CODES:
        raise ValueError("Choose a valid default language.")
    codes = incoming.get("enabled_codes")
    if isinstance(incoming.get("languages"), list):
        codes = [
            str(row.get("code") or "").strip()
            for row in incoming["languages"]
            if row.get("enabled") and str(row.get("code") or "").strip() in _CODES
        ]
    if not isinstance(codes, list) or not codes:
        raise ValueError("Enable at least one language.")
    cleaned = []
    for item in codes:
        code = str(item or "").strip()
        if code in _CODES and code not in cleaned:
            cleaned.append(code)
    if not cleaned:
        raise ValueError("Enable at least one language.")
    if default_code not in cleaned:
        default_code = cleaned[0]
    return {
        "enabled": True,
        "required": required,
        "default_code": default_code,
        "enabled_codes": cleaned,
    }


def language_options_for_ui():
    settings = merged_language_settings()
    labels = {code: (english, native) for code, english, native in CATALOG}
    options = []
    for code in settings["enabled_codes"]:
        english, native = labels.get(code, (code, code))
        options.append(
            {
                "code": code,
                "label": english,
                "native_label": native,
                "display": f"{english} — {native}" if native != english else english,
            }
        )
    return options


def admin_language_editor():
    settings = merged_language_settings()
    enabled_set = set(settings["enabled_codes"])
    return {
        "enabled": settings["enabled"],
        "required": settings["required"],
        "default_code": settings["default_code"],
        "enabled_codes": settings["enabled_codes"],
        "languages": [
            {
                "code": code,
                "label": english,
                "native_label": native,
                "enabled": code in enabled_set,
            }
            for code, english, native in CATALOG
        ],
    }


def language_public_payload(user=None):
    from .plan_access import language_enabled_for

    settings = merged_language_settings()
    plan_on = language_enabled_for(user) if user is not None else False
    return {
        "enabled": plan_on,
        "required": bool(settings["required"]) if plan_on else False,
        "default_code": settings["default_code"],
        "options": language_options_for_ui() if plan_on else [],
    }


def chosen_language(user) -> str:
    """Legacy helper — prefer resolve_chat_language with an explicit chat selection."""
    return resolve_chat_language(user, None)


def resolve_chat_language(user, chat_language: str | None = None) -> str:
    """Language for this chat turn: dropdown value first, then saved preference, then default."""
    from .plan_access import language_enabled_for

    if not language_enabled_for(user):
        return ""
    settings = merged_language_settings()
    code = str(chat_language or "").strip()
    if code:
        if code not in settings["enabled_codes"]:
            raise ValueError("Choose one of the languages offered.")
        return code
    row = UserChatSetting.objects.filter(user=user).first()
    saved = ((row.preferred_language if row else "") or "").strip()
    if saved and saved in settings["enabled_codes"]:
        return saved
    if settings["required"]:
        return ""
    default = settings["default_code"]
    return default if default in settings["enabled_codes"] else ""


def language_label(code: str) -> str:
    for item_code, english, native in CATALOG:
        if item_code == code:
            return f"{english} ({native})" if native != english else english
    return code or "English"


def language_block_message(user, chat_language: str | None = None) -> str:
    from .plan_access import language_enabled_for

    settings = merged_language_settings()
    if not language_enabled_for(user) or not settings["required"]:
        return ""
    try:
        if resolve_chat_language(user, chat_language):
            return ""
    except ValueError:
        return "Choose a language from the list before chatting."
    return "Choose a language from the list before chatting."


def apply_language_to_system(system_text: str, user, chat_language: str | None = None) -> str:
    try:
        code = resolve_chat_language(user, chat_language)
    except ValueError:
        return system_text or ""
    if not code:
        return system_text or ""
    name = language_label(code)
    rule = (
        f"\n\nLanguage: Respond entirely in {name}. "
        "Match the language the user writes in when it is one of your supported reply languages. "
        "Do not switch to English unless the user asks for English."
    )
    base = (system_text or "").strip()
    return (base + rule).strip()


def validate_user_language(code: str, user=None) -> str:
    from .plan_access import language_enabled_for

    if user is not None and not language_enabled_for(user):
        return ""
    settings = merged_language_settings()
    chosen = str(code or "").strip()
    if not chosen:
        if settings["required"]:
            raise ValueError("Choose a language.")
        return ""
    if chosen not in settings["enabled_codes"]:
        raise ValueError("Choose one of the languages offered for your account.")
    return chosen
