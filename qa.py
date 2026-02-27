import re

FORBIDDEN_PATTERNS = [
    r"\bbestes\b",
    r"\bgarantiert\b",
    r"100\s*%",
]

def qa_check(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if len(t) < 80:
        return False, "Zu kurz (<80 Zeichen)."
    if len(t) > 500:
        return False, "Zu lang (>500 Zeichen)."

    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return False, f"Verbotenes Wort/Pattern gefunden: {pat}"

    return True, ""