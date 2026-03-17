from app.services.adjournment import detect_adjournment


def test_detect_adjournment_positive() -> None:
    is_adjournment, reason = detect_adjournment("Matter adjourned to next week")
    assert is_adjournment is True
    assert reason == "adjourned"


def test_detect_adjournment_negative() -> None:
    is_adjournment, reason = detect_adjournment("Arguments heard and reserved")
    assert is_adjournment is False
    assert reason is None
