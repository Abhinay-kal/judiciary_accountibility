from app.models import HearingOutcomeType
from app.ingestion.hearing_outcomes import parse_outcome_text


def detect_adjournment(
    outcome_text: str | None,
    *,
    parsed_outcome: HearingOutcomeType | None = None,
) -> tuple[bool, str | None]:
    """Detect whether a hearing outcome indicates an adjournment."""

    if parsed_outcome == HearingOutcomeType.ADJOURNED:
        result = parse_outcome_text(outcome_text)
        keyword = result.matched_keywords[0] if result.matched_keywords else None
        if keyword == "adjourned to":
            keyword = "adjourned"
        return True, keyword

    result = parse_outcome_text(outcome_text, allow_ml=False)
    if result.outcome_type != HearingOutcomeType.ADJOURNED:
        return False, None
    keyword = result.matched_keywords[0] if result.matched_keywords else None
    if keyword == "adjourned to":
        keyword = "adjourned"
    return True, keyword
