from app.core.constants import ADJOURNMENT_KEYWORDS


def detect_adjournment(outcome_text: str | None) -> tuple[bool, str | None]:
    """Detect whether a hearing outcome indicates an adjournment."""

    if not outcome_text:
        return False, None

    normalized = outcome_text.lower()
    for keyword in ADJOURNMENT_KEYWORDS:
        if keyword in normalized:
            return True, keyword
    return False, None
