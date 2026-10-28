"""Estimate and trim LLM payloads while keeping facts needed to answer."""
import hashlib
import re

_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")
_QUESTION = re.compile(r"\n\nQuestion:\s*", re.I)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages(messages, system_prompt=None) -> int:
    total = estimate_tokens(system_prompt or "")
    for message in messages or []:
        total += 4 + estimate_tokens(str(message.get("content") or ""))
    return total


def _normalize(text: str) -> str:
    text = _BLANK.sub("\n\n", text or "")
    return _WS.sub(" ", text).strip()


def dedupe_passages(block: str) -> str:
    parts = [part.strip() for part in (block or "").split("\n\n") if part.strip()]
    seen = set()
    kept = []
    for part in parts:
        key = hashlib.sha256(part.encode("utf-8", errors="ignore")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        kept.append(part)
    return "\n\n".join(kept)


def trim_user_history(messages, max_turns=3):
    if not messages:
        return []
    users = [m for m in messages if m.get("role") == "user"]
    return users[-max_turns:] if users else messages[-max_turns:]


def _shrink_text(content: str, max_chars: int) -> str:
    content = content or ""
    if len(content) <= max_chars:
        return content
    match = _QUESTION.search(content)
    if match:
        head = content[: match.start()]
        tail = content[match.start() :]
        room = max(120, max_chars - len(tail) - 24)
        if len(head) > room:
            half = room // 2
            head = head[:half] + "\n…\n" + head[-half:]
        return head + tail
    half = max_chars // 2
    return content[:half] + "\n…\n" + content[-half:]


def fit_messages_to_budget(messages, system_prompt, token_budget):
    """
    Gently shorten context until the estimated input fits the per-request budget.
    Keeps the latest question and trims older excerpt text first.
    """
    if token_budget <= 0:
        return messages, system_prompt
    working = [dict(m) for m in (messages or [])]
    system = system_prompt or ""
    max_chars = token_budget * 4
    while working and estimate_messages(working, system) > token_budget:
        changed = False
        for index in range(len(working) - 1, -1, -1):
            message = working[index]
            if message.get("role") != "user":
                continue
            content = str(message.get("content") or "")
            if len(content) <= 200 and index > 0:
                working.pop(index)
                changed = True
                break
            shorter = _shrink_text(content, max(max_chars // max(len(working), 1), 280))
            if shorter != content:
                message["content"] = shorter
                changed = True
                break
        if not changed:
            break
    if system and estimate_tokens(system) > token_budget // 4:
        system = _shrink_text(system, max(200, max_chars // 6))
    return working, system


def optimize_grounded_sections(sections: str) -> str:
    return dedupe_passages(_normalize(sections))
