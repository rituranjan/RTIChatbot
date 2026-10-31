"""Match natural language to dictionary columns and filter values."""

import re

_PIN = re.compile(r"\b(?:pin|pincode|postal code|postcode|zip)\b", re.I)
_MOBILE = re.compile(r"\b(?:mobile|phone|contact number)\b", re.I)
_EMAIL = re.compile(r"\b(?:email|mail id)\b", re.I)
_APP_NO = re.compile(r"\b(?:rti|application)\s*(?:number|no|id)\b", re.I)
_TRACK = re.compile(r"\btracking[\s_]*number\b|\btrackingno\b|\btracking\b", re.I)
_STATUS = re.compile(r"\b(?:pending|approved|rejected|paid|unpaid|refund)\b", re.I)
_DIGITS = re.compile(r"\b(\d{5,12})\b")
_TRACK_ID = re.compile(r"\b([A-Z]{2}\d{6,15}[A-Z0-9]{0,6})\b", re.I)
_TOKEN = re.compile(r"\b([A-Za-z0-9]{8,24})\b")
_SKIP = frozenset(
    {
        "show",
        "find",
        "details",
        "detail",
        "tracking",
        "number",
        "tracking_number",
        "applicant",
        "applicants",
        "from",
        "with",
        "the",
        "for",
    }
)
_EMAIL_VAL = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
_RTI_ID = re.compile(r"\b(RTI[\w-]+)\b", re.I)


def _find_column(dictionary, *needles):
    needles = [n.lower() for n in needles]
    for col in dictionary["columns"]:
        hay = " ".join([col["display_name"], col["sql_alias"], *col["synonyms"]]).lower()
        if any(n in hay for n in needles):
            return col
    return None


def extract_filters(question: str, dictionary: dict) -> tuple[list[dict], list[str]]:
    """Return filter clauses and clarification prompts."""
    text = (question or "").strip()
    lower = text.lower()
    filters = []
    clarifications = []

    if _EMAIL_VAL.search(text):
        col = _find_column(dictionary, "email")
        if col and col["filterable"]:
            filters.append({"column": col["ref"], "operator": "=", "value": _EMAIL_VAL.search(text).group(0)})

    pin_col = _find_column(dictionary, "postal", "pincode", "pin code")
    if pin_col and pin_col["filterable"] and _PIN.search(text):
        match = re.search(r"\b(\d{6})\b", text)
        if match:
            filters.append({"column": pin_col["ref"], "operator": "=", "value": match.group(1)})

    mobile_col = _find_column(dictionary, "mobile", "phone")
    if mobile_col and mobile_col["filterable"] and _MOBILE.search(text):
        match = re.search(r"\b(\d{10})\b", text)
        if match:
            filters.append({"column": mobile_col["ref"], "operator": "=", "value": match.group(1)})

    if _APP_NO.search(text) or _RTI_ID.search(text):
        col = _find_column(dictionary, "application number", "rti application")
        token = _RTI_ID.search(text)
        if col and col["filterable"] and token:
            filters.append({"column": col["ref"], "operator": "=", "value": token.group(1)})

    if _TRACK.search(text.replace("_", " ")) or _TRACK_ID.search(text):
        col = _find_column(dictionary, "tracking")
        if col and col["filterable"]:
            match = _TRACK_ID.search(text)
            if match:
                filters.append({"column": col["ref"], "operator": "=", "value": match.group(1)})
            else:
                for token in _TOKEN.finditer(text):
                    value = token.group(1)
                    if value.lower() in _SKIP or value.isdigit():
                        continue
                    filters.append({"column": col["ref"], "operator": "=", "value": value})
                    break
            if not any(f.get("column") == col["ref"] for f in filters):
                match = _DIGITS.search(text)
                if match:
                    filters.append({"column": col["ref"], "operator": "=", "value": match.group(1)})

    if _STATUS.search(text):
        col = _find_column(dictionary, "application status", "payment status", "refund status")
        if col and col["filterable"]:
            for word in ("pending", "approved", "rejected", "paid", "unpaid", "refund"):
                if word in lower:
                    filters.append({"column": col["ref"], "operator": "LIKE", "value": f"%{word}%"})
                    break

    name_col = _find_column(dictionary, "full name", "first name")
    if name_col and name_col["filterable"] and re.search(r"\b(named|name is|applicant)\b", lower):
        tokens = re.findall(r"[A-Za-z]{3,}", text)
        stop = {"show", "find", "applicant", "applicants", "named", "name", "with", "from", "the"}
        names = [t for t in tokens if t.lower() not in stop]
        if len(names) == 1:
            filters.append({"column": name_col["ref"], "operator": "LIKE", "value": f"%{names[0]}%"})

    if re.fullmatch(r"\d+", text.strip()) and not filters:
        clarifications.append(
            "Do you want to search by postal code, mobile number, application ID, or tracking number?"
        )

    return filters, clarifications
