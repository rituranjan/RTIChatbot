"""Chat completions through OpenRouter. Embeddings stay on the configured provider."""
import time

import requests
from django.conf import settings

from .llm_service import LLMError
from .plan_access import openrouter_key

_catalog = {"at": 0.0, "items": [], "key": ""}


def complete_chat(messages, model, system_prompt=None, temperature=0, max_tokens=None):
    key = openrouter_key()
    if not key:
        raise LLMError("OpenRouter is not configured. Add the API key in Admin settings.")
    if not model:
        raise LLMError("Choose a model in Account, then Model. An admin assigns the models for each plan.")
    payload = []
    if system_prompt:
        payload.append({"role": "system", "content": system_prompt})
    for message in messages:
        payload.append({"role": message["role"], "content": message["content"]})
    url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
    body = {"model": model, "messages": payload, "temperature": temperature}
    if max_tokens is not None and int(max_tokens) > 0:
        body["max_tokens"] = int(max_tokens)
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
    except requests.Timeout as exc:
        raise LLMError("OpenRouter request timed out.") from exc
    except requests.RequestException as exc:
        raise LLMError(f"OpenRouter request failed: {exc}") from exc
    if response.status_code >= 400:
        detail = (response.text or "")[:300]
        raise LLMError(f"OpenRouter request failed ({response.status_code}): {detail}")
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError("OpenRouter returned a response that was not JSON.") from exc
    content = ""
    choices = data.get("choices") or []
    if choices:
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
    usage = data.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") if isinstance(details, dict) else 0
    return {
        "content": content,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "cached_tokens": int(cached or usage.get("cached_tokens") or 0),
        },
    }


def list_models(query=""):
    """Live OpenRouter catalog. The admin picks from this list; nothing is hardcoded."""
    key = openrouter_key()
    if not key:
        raise LLMError("OpenRouter is not configured. Add the API key in Admin settings.")
    now = time.time()
    fingerprint = key[-12:]
    if (
        now - _catalog["at"] > 600
        or not _catalog["items"]
        or _catalog.get("key") != fingerprint
    ):
        url = f"{settings.OPENROUTER_BASE_URL}/models"
        try:
            response = requests.get(
                url,
                params={"limit": 500},
                headers={"Authorization": f"Bearer {key}"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise LLMError(f"OpenRouter model list failed: {exc}") from exc
        if response.status_code >= 400:
            detail = (response.text or "")[:300]
            raise LLMError(f"OpenRouter model list failed ({response.status_code}): {detail}")
        try:
            body = response.json()
        except ValueError as exc:
            raise LLMError("OpenRouter model list was not JSON.") from exc
        items = []
        seen = set()
        for row in (body or {}).get("data") or []:
            model_id = str(row.get("id") or "").strip()
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            context = row.get("context_length")
            try:
                context = int(context) if context else None
            except (TypeError, ValueError):
                context = None
            items.append(
                {
                    "id": model_id,
                    "name": str(row.get("name") or model_id),
                    "context_length": context,
                }
            )
        items.sort(key=lambda item: item["name"].lower())
        _catalog["at"] = now
        _catalog["key"] = fingerprint
        _catalog["items"] = items
    needle = (query or "").strip().lower()
    rows = _catalog["items"]
    if needle:
        rows = [
            row
            for row in rows
            if needle in row["id"].lower() or needle in row["name"].lower()
        ]
    return rows[:500]
