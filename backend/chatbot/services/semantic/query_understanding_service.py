"""Optional LLM intent refinement using a subset of the dictionary."""

import json
import logging

from ..llm_gateway import complete_for_user
from ..plan_access import model_for

log = logging.getLogger(__name__)


def refine_intent(owner, question: str, dictionary: dict, filters: list[dict]) -> list[dict]:
    if filters:
        return filters
    model = model_for(owner)
    if not model:
        return filters
    subset = dictionary["columns"][:25]
    prompt = (
        "Return JSON only: {\"filters\":[{\"column\":\"a.pincode\",\"operator\":\"=\",\"value\":\"700053\"}]}. "
        "Use only these columns:\n"
        + json.dumps([{"ref": c["ref"], "display": c["display_name"]} for c in subset])
        + f"\nQuestion: {question}"
    )
    try:
        result = complete_for_user(
            owner,
            workflow="semantic.sql",
            model=model,
            messages=[{"role": "user", "content": prompt}],
            system_slug="chat.general.system",
            temperature=0,
        )
        text = (result.get("content") or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return filters
        data = json.loads(text[start : end + 1])
        return data.get("filters") or filters
    except Exception:
        log.exception("Semantic LLM intent failed")
        return filters
