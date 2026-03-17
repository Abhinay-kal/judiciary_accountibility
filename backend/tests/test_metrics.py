from app.models import Case
from app.services.metrics import compute_time_between_hearings


def test_compute_time_between_hearings_empty() -> None:
    case = Case(
        case_uid="x",
        case_number="x",
        court_id=1,
        court_level="district",
        state="Delhi",
        status="pending",
        source_url="http://example.com",
        source_fields={},
    )
    case.hearings = []
    assert compute_time_between_hearings(case) == []
