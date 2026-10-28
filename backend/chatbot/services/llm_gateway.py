"""Central routing for chat completions: plan limits, prompts, optimization, logging."""
import time
import uuid

from django.conf import settings

from ..models import LlmUsageLog
from .llm_service import LLMError
from .openrouter_service import complete_chat
from .plan_access import (
    per_request_input_cap,
    projected_limit_block,
    record_usage,
    max_output_tokens_for_request,
)
from .prompt_service import get_prompt
from .token_optimize import (
    estimate_messages,
    fit_messages_to_budget,
    optimize_grounded_sections,
    trim_user_history,
)


def complete_for_user(
    user,
    *,
    workflow,
    model,
    messages,
    system_slug=None,
    system_variables=None,
    inline_system=None,
    prompt_slug=None,
    prompt_variables=None,
    temperature=0,
):
    """
    Run one OpenRouter chat completion under the user's plan.
    Returns the same dict as complete_chat plus prompt_version and usage log id.
    """
    system_text = inline_system or ""
    prompt_version = 0
    if system_slug:
        system_text, prompt_version = get_prompt(system_slug, system_variables or {})
    elif prompt_slug:
        system_text, prompt_version = get_prompt(prompt_slug, prompt_variables or {})

    trimmed = trim_user_history(messages)
    input_cap = per_request_input_cap(user)
    trimmed, system_text = fit_messages_to_budget(trimmed, system_text, input_cap)
    estimated = estimate_messages(trimmed, system_text)

    blocked = projected_limit_block(user, estimated)
    if blocked:
        return {
            "blocked": True,
            "content": blocked,
            "usage": {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0},
            "prompt_version": prompt_version,
        }

    max_output = max_output_tokens_for_request(user)
    started = time.perf_counter()
    log_id = uuid.uuid4()
    try:
        result = complete_chat(
            trimmed,
            model=model,
            system_prompt=system_text,
            temperature=temperature,
            max_tokens=max_output,
        )
        latency = int((time.perf_counter() - started) * 1000)
        usage = result.get("usage") or {}
        record_usage(user, usage)
        LlmUsageLog.objects.create(
            id=log_id,
            user=user,
            workflow=workflow[:64],
            provider="openrouter",
            model=(model or "")[:120],
            prompt_slug=(system_slug or prompt_slug or "")[:80],
            prompt_version=prompt_version,
            estimated_input_tokens=estimated,
            actual_input_tokens=int(usage.get("input_tokens") or 0),
            max_output_tokens=max_output,
            actual_output_tokens=int(usage.get("output_tokens") or 0),
            cached_tokens=int(usage.get("cached_tokens") or 0),
            latency_ms=latency,
            success=True,
        )
        result["prompt_version"] = prompt_version
        result["log_id"] = str(log_id)
        result["blocked"] = False
        return result
    except LLMError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        LlmUsageLog.objects.create(
            id=log_id,
            user=user,
            workflow=workflow[:64],
            provider="openrouter",
            model=(model or "")[:120],
            prompt_slug=(system_slug or prompt_slug or "")[:80],
            prompt_version=prompt_version,
            estimated_input_tokens=estimated,
            actual_input_tokens=0,
            max_output_tokens=max_output,
            actual_output_tokens=0,
            cached_tokens=0,
            latency_ms=latency,
            success=False,
            error_message=str(exc)[:500],
        )
        raise


def build_grounded_user_prompt(owner, user_text, sections, style, missing_message):
    cite_slug = "chat.cite.widget" if style == "widget" else "chat.cite.app"
    cite_instruction, _ = get_prompt(cite_slug, {})
    optimized = optimize_grounded_sections(sections)
    user_prompt, _ = get_prompt(
        "chat.grounded.user",
        {
            "cite_instruction": cite_instruction,
            "not_found_message": missing_message,
            "context_sections": optimized,
            "question": user_text,
        },
    )
    return user_prompt
