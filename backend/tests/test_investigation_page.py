from __future__ import annotations

import io
import zipfile
from datetime import date
import pytest

from app.investigation.builder import InvestigationBuilder
from app.investigation.export import export_json_package, export_offline_archive, export_pdf_bytes
from app.investigation.snapshot import SnapshotService
from app.models import Case, CaseFeedback, DelayBaseline, Flag, Hearing, InvestigationSnapshot, Order, SurvivalCurve
from app.models.entities import FeedbackDisplayLabel, FeedbackPublicStatus, FeedbackResponderType, FeedbackVerificationMethod, HearingOutcomeType


class _Query:
    def __init__(self, items):
        self.items = list(items)

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        rows = self.items
        for key, value in kwargs.items():
            rows = [item for item in rows if getattr(item, key, None) == value]
        return _Query(rows)

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, value):
        return _Query(self.items[value:])

    def limit(self, value):
        return _Query(self.items[:value])

    def count(self):
        return len(self.items)

    def one_or_none(self):
        return self.items[0] if self.items else None

    def all(self):
        return list(self.items)


class _DB:
    def __init__(self):
        self.cases = []
        self.hearings = []
        self.orders = []
        self.flags = []
        self.baselines = []
        self.survival_curves = []
        self.feedback = []
        self.snapshots = []

    def query(self, model):
        name = model.__name__
        if name == "Case":
            return _Query(self.cases)
        if name == "Hearing":
            return _Query(self.hearings)
        if name == "Order":
            return _Query(self.orders)
        if name == "Flag":
            return _Query(self.flags)
        if name == "DelayBaseline":
            return _Query(self.baselines)
        if name == "SurvivalCurve":
            return _Query(self.survival_curves)
        if name == "CaseFeedback":
            return _Query(self.feedback)
        if name == "InvestigationSnapshot":
            return _Query(self.snapshots)
        return _Query([])

    def add(self, obj):
        if obj.__class__.__name__ == "InvestigationSnapshot":
            obj.snapshot_id = obj.snapshot_id or f"snap-{len(self.snapshots) + 1}"
            if obj.generated_at is None:
                obj.generated_at = date.today()
            self.snapshots.append(obj)

    def commit(self):
        return None


@pytest.fixture
def stub_evidence(monkeypatch):
    monkeypatch.setattr(
        "app.investigation.builder.build_hearing_evidence_bundle",
        lambda db, hearing: {
            "source_links": [f"https://source/{hearing.id}"],
            "judge_attribution": [],
        },
    )


def _build_case(case_id: int = 1) -> Case:
    return Case(
        id=case_id,
        case_uid=f"UID-{case_id}",
        case_number=f"{case_id}/2020",
        court_id=10,
        court_level="district",
        state="Delhi",
        status="pending",
        source_url="https://court.example/case",
        source_fields={},
        filing_date=date(2020, 1, 1),
        case_type="criminal",
        delay_percentile=93.0,
        case_duration_days=3400.0,
        importance_score=0.86,
        importance_confidence=0.8,
        baseline_confidence=0.72,
        baseline_level_used="state_case_type",
    )


def test_snapshot_creation_and_version_retrieval(stub_evidence):
    db = _DB()
    db.cases = [_build_case()]

    builder = InvestigationBuilder(db)
    service = SnapshotService(db)

    report = builder.build(1).to_dict()
    first = service.create_snapshot_if_changed(case_id=1, report=report, data_cutoff_date=date.today())
    assert first.version_number == 1

    second_same = service.create_snapshot_if_changed(case_id=1, report=report, data_cutoff_date=date.today())
    assert second_same.version_number == 1

    report["summary"]["narrative"] = "Narrative changed"
    second = service.create_snapshot_if_changed(case_id=1, report=report, data_cutoff_date=date.today())
    assert second.version_number == 2

    versions = service.list_versions(1)
    assert len(versions) == 2
    assert {item["version_number"] for item in versions} == {1, 2}


def test_export_correctness(stub_evidence):
    db = _DB()
    db.cases = [_build_case()]
    report = InvestigationBuilder(db).build(1).to_dict()
    snap = {
        "snapshot_id": "snap-1",
        "version_number": 1,
        "content_hash": "abc",
        "generated_at": "2026-03-17T00:00:00Z",
    }

    package = export_json_package(report, snapshot_meta=snap)
    assert package["snapshot"]["version_number"] == 1
    assert package["report"]["case_id"] == 1

    pdf = export_pdf_bytes(report, snapshot_meta=snap)
    assert pdf.startswith(b"%PDF")

    archive = export_offline_archive(report, canonical_url="/investigation/1", version_number=1, snapshot_meta=snap)
    with zipfile.ZipFile(io.BytesIO(archive), "r") as zf:
        names = set(zf.namelist())
    assert {"report.html", "report.json", "sources.txt"}.issubset(names)


def test_missing_data_handling(stub_evidence):
    db = _DB()
    case = _build_case()
    case.delay_percentile = None
    case.case_duration_days = None
    case.importance_confidence = None
    case.baseline_confidence = None
    db.cases = [case]

    report = InvestigationBuilder(db).build(1).to_dict()
    assert report["summary"]["narrative"].startswith("Delay benchmarking is currently limited")
    assert report["metrics"]["survival_summary"]["available"] is False


def test_large_case_timeline_build(stub_evidence):
    db = _DB()
    case = _build_case()
    db.cases = [case]

    hearings = []
    for i in range(1, 401):
        hearings.append(
            Hearing(
                id=i,
                case_id=1,
                date=date(2021, 1, 1),
                source="cause_list",
                outcome_type=HearingOutcomeType.ADJOURNED if i % 2 == 0 else HearingOutcomeType.HEARD,
                outcome_text="Listed",
                listing_type="Regular",
            )
        )
    for row in hearings:
        row.case = case
    db.hearings = hearings

    report = InvestigationBuilder(db).build(1).to_dict()
    assert len(report["timeline"]) >= 400


def test_right_to_respond_integration(stub_evidence):
    db = _DB()
    db.cases = [_build_case()]
    db.feedback = [
        CaseFeedback(
            id="fb-1",
            case_id=1,
            responder_type=FeedbackResponderType.GOV_AGENCY,
            responder_name="Officer",
            responder_affiliation="Agency",
            responder_contact="masked",
            responder_contact_hash="hash",
            responder_verified=True,
            responder_verification_method=FeedbackVerificationMethod.ADMIN_VERIFIED,
            verification_confidence=0.9,
            content="Official statement",
            attachments_ref=[],
            display_label=FeedbackDisplayLabel.OFFICIAL_RESPONSE,
            received_via="WEB",
            public_status=FeedbackPublicStatus.PUBLISHED,
            moderation_notes={},
            is_private=False,
        )
    ]

    report = InvestigationBuilder(db).build(1).to_dict()
    assert report["right_to_respond"]["present"] is True
    assert "Official response submitted by" in report["right_to_respond"]["responses"][0]["statement"]
