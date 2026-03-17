from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin_hearings
from app.db.session import get_db
from app.main import app
from app.models import JudgeAssignmentRole
from app.services.judge_resolution import (
    build_assignments_from_bench,
    candidate_lookup,
    normalize_name,
    parse_bench_string,
    phonetic_key,
    raw_bench_snapshot_id,
    resolve_judge,
)


def test_normalize_name_strips_honorifics_and_punctuation() -> None:
    assert normalize_name("Hon'ble Mr. Justice A.B. Sharma") == "a b sharma"
    assert normalize_name("JUSTICE C.D. Rao, J.") == "c d rao"


def test_phonetic_key_stable_for_similar_names() -> None:
    assert phonetic_key("A.B. Sharma") == phonetic_key("AB Sharma")


class _FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return list(self.items)

    def first(self):
        return self.items[0] if self.items else None


class _FakeDB:
    def __init__(self, registry_entries=None):
        self.registry_entries = registry_entries or []
        self.added = []

    def query(self, model):
        return _FakeQuery(self.registry_entries)

    def add(self, obj):
        self.added.append(obj)
        if hasattr(obj, "judge_id") and obj not in self.registry_entries:
            self.registry_entries.append(obj)

    def flush(self):
        return None


def _registry(judge_id: str, name: str, court_id: int | None = None):
    return SimpleNamespace(
        judge_id=judge_id,
        canonical_name=name,
        phonetic_keys={"keys": [phonetic_key(name)]},
        court_id=court_id,
        first_seen=datetime(2020, 1, 1),
        last_seen=datetime(2030, 1, 1),
        known_designations={"values": []},
        is_provisional=False,
        name_variants={"variants": [name]},
    )


def test_candidate_lookup_and_scoring() -> None:
    db = _FakeDB(
        registry_entries=[
            _registry("j-1", "a b sharma", court_id=10),
            _registry("j-2", "c d rao", court_id=10),
        ]
    )
    candidates = candidate_lookup(
        db,
        court_id=10,
        normalized_name=normalize_name("Hon'ble Mr. Justice A.B. Sharma"),
        phonetic=phonetic_key("A.B. Sharma"),
        hearing_date=datetime(2026, 3, 17),
    )
    assert candidates
    assert candidates[0].judge_id == "j-1"
    assert candidates[0].score > 0.8


def test_resolve_judge_returns_no_match_when_empty_registry() -> None:
    db = _FakeDB(registry_entries=[])
    result = resolve_judge(
        db,
        raw_name="Justice Unknown",
        court_id=11,
        hearing_date=datetime(2026, 3, 17),
    )
    assert result.judge_id is None


@pytest.mark.parametrize(
    "bench",
    [
        "Hon'ble Mr. Justice A.B. Sharma",
        "Coram: A.B. Sharma, C.D. Rao, E.F. Kaur, JJ.",
        "Single bench of Justice X",
        "Division bench of Justices X & Y",
        "Hon'ble Justice N. Venkataraman and Justice P. Sinha",
        "Coram: Justice A. Banerjee / Justice B. Khan",
        "A.B. Sharma, J.",
        "Coram: Dr. Justice M. Ali",
        "Justice A. K. Singh, Justice R. P. Rai",
        "JUSTICE R.S. Chauhan",
        "Hon'ble Chief Justice P. Rao",
        "Coram - Justice A; Justice B",
        "Justice X, J. & Justice Y, J.",
        "Bench: Justice Lakshmi Narayan",
        "Coram: Justice K. Thomas and Justice P. Mathew",
        "Justice A.B.C. Dsouza",
        "Justice M N Rao",
        "Coram: Hon'ble Mr. Justice A.B. Sharma",
        "Bench not constituted",
        "Coram: न्यायमूर्ति ए.बी. शर्मा",
        "Justice X & Justice Y & Justice Z",
        "Hon. Justice A, Justice B",
        "Coram: A. Sharma, JJ.",
        "A.B. Sharma and C.D. Rao",
        "Justice K. Ramaswamy",
        "Coram: Justice P, Justice Q, Justice R",
        "Division Bench: Justice X and Justice Y",
        "Single Bench: Justice A",
        "Justice A/B Justice B",
        "Coram: Justice A | Justice B",
    ],
)
def test_parse_bench_string_examples(bench: str) -> None:
    tokens = parse_bench_string(bench)
    if "Bench not constituted" in bench:
        assert tokens == []
    else:
        assert all(token.raw_name for token in tokens)


def test_multi_judge_bench_assignments_preserve_order() -> None:
    db = _FakeDB(registry_entries=[])
    assignments = build_assignments_from_bench(
        db,
        raw_bench="Coram: Hon'ble Mr. Justice A.B. Sharma, Justice C.D. Rao, Justice E.F. Kaur",
        court_id=10,
        source_name="high_court",
        hearing_date=date(2026, 3, 17),
    )
    assert len(assignments) >= 3
    assert [item.sequence_index for item in assignments] == sorted(item.sequence_index for item in assignments)
    assert assignments[0].is_presiding is True


def test_bench_change_updates_provenance_snapshot() -> None:
    bench_cause_list = "Coram: Justice A.B. Sharma, Justice C.D. Rao"
    bench_order_pdf = "Coram: Justice A.B. Sharma, Justice E.F. Kaur"
    assert raw_bench_snapshot_id(bench_cause_list) != raw_bench_snapshot_id(bench_order_pdf)


@pytest.fixture
def client_assign_override(monkeypatch):
    hearing = SimpleNamespace(id=20, is_deleted=False)
    assignment = SimpleNamespace(
        assignment_id="a-1",
        judge_name_raw="Justice A.B. Sharma",
        role=JudgeAssignmentRole.PRESIDING,
        attribution_confidence=1.0,
        judge_id="reg-1",
    )

    class FakeQuery:
        def __init__(self, item=None):
            self.item = item

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.item

    class FakeDB:
        def __init__(self):
            self.added = []

        def get(self, model, item_id):
            model_name = getattr(model, "__name__", "")
            if model_name == "Hearing" and item_id == 20:
                return hearing
            if model_name == "JudgeRegistry" and item_id == "reg-1":
                return SimpleNamespace(judge_id="reg-1", canonical_name="a b sharma")
            return None

        def query(self, model):
            model_name = getattr(model, "__name__", "")
            if model_name == "JudgeAssignment":
                return FakeQuery(assignment)
            return FakeQuery(None)

        def add(self, obj):
            self.added.append(obj)

        def flush(self):
            return None

        def commit(self):
            return None

    fake_db = FakeDB()

    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(admin_hearings, "invalidate_namespace", lambda _key: None)

    client = TestClient(app)
    try:
        yield client, fake_db
    finally:
        app.dependency_overrides.clear()


def test_manual_assign_override_writes_audit(client_assign_override) -> None:
    client, fake_db = client_assign_override
    response = client.post(
        "/api/v1/admin/hearings/20/assign-judge",
        json={
            "judge_registry_id": "reg-1",
            "role": "PRESIDING",
            "explanation": "Verified from signed order sheet",
            "admin_id": 17,
            "sequence_index": 0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["judge_registry_id"] == "reg-1"
    assert payload["role"] == "PRESIDING"
    assert any(getattr(item, "action", "") == "manual_assign" for item in fake_db.added)
