"""Questions asked before a chat, and the answers stored with that chat."""
import re

from django.contrib.auth import get_user_model

from ..models import IntakeQuestion, VisitorProfile


def owner_of(conversation):
    return get_user_model().objects.get(pk=conversation.owner_id)

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def question_key(label, explicit=""):
    raw = (explicit or label or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if not raw:
        raw = "field"
    if not raw[0].isalpha():
        raw = "f_" + raw
    return raw[:40]


def public_questions(owner):
    return [
        {
            "id": str(item.id),
            "label": item.label,
            "field_key": item.field_key,
            "placeholder": item.placeholder,
            "required": item.required,
            "position": item.position,
        }
        for item in IntakeQuestion.objects.filter(owner=owner, enabled=True).order_by(
            "position", "label"
        )
    ]


def normalize_answers(owner, raw):
    questions = list(
        IntakeQuestion.objects.filter(owner=owner, enabled=True).order_by("position", "label")
    )
    incoming = raw if isinstance(raw, dict) else {}
    cleaned = {}
    missing = []
    for question in questions:
        value = str(incoming.get(question.field_key) or "").strip()[:200]
        if question.required and not value:
            missing.append(question.label)
        if value:
            cleaned[question.field_key] = value
    if missing:
        raise ValueError("Please fill in: " + ", ".join(missing))
    return cleaned


def profile_required(owner):
    return IntakeQuestion.objects.filter(owner=owner, enabled=True).exists()


def profile_answers(conversation):
    try:
        return conversation.profile.answers or {}
    except VisitorProfile.DoesNotExist:
        return None


def save_profile(conversation, raw):
    cleaned = normalize_answers(owner_of(conversation), raw)
    db = conversation._state.db or "default"
    profile, _created = VisitorProfile.objects.using(db).update_or_create(
        conversation=conversation,
        defaults={"answers": cleaned},
    )
    return profile.answers


def assert_profile(conversation):
    if not profile_required(owner_of(conversation)):
        return
    if profile_answers(conversation) is None:
        raise ValueError("Answer the questions before starting the chat.")
