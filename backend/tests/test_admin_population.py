from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.admin_population import (
    TriggerPopulationRequest,
    get_population_run,
    list_population_runs,
    trigger_population_run,
)
from app.ingestion.models import POPULATION_RUNNING, PopulationRun, PopulationSourceRun


class _Query:
    def __init__(self, items):
        self._items = list(items)
        self._offset = 0
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def count(self):
        return len(self._items)

    def offset(self, value: int):
        self._offset = value
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        sliced = self._items[self._offset :]
        if self._limit is not None:
            sliced = sliced[: self._limit]
        return sliced


class _DB:
    def __init__(self, runs=None, source_runs=None):
        self.runs = list(runs or [])
        self.source_runs = list(source_runs or [])

    def query(self, model):
        if model is PopulationRun:
            return _Query(self.runs)
        if model is PopulationSourceRun:
            return _Query(self.source_runs)
        return _Query([])


def _run(run_id: str, status: str = "QUEUED"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=1,
        run_id=run_id,
        trigger_type="MANUAL",
        status=status,
        admin_id=1,
        reason="manual",
        started_at=now,
        finished_at=None,
        total_sources=2,
        completed_sources=1,
        successful_sources=1,
        failed_sources=0,
        records_processed=10,
        records_failed=1,
        diagnostics={"k": "v"},
    )


def _source_run(source_name: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=101,
        source_id=5,
        population_run_id=1,
        source_name=source_name,
        status="RUNNING",
        task_id="task-1",
        records_processed=5,
        records_failed=0,
        error_summary=None,
        diagnostics={},
        started_at=now,
        finished_at=None,
    )


def test_trigger_population_returns_existing_run_when_active(monkeypatch):
    db = _DB(runs=[_run("run-active", status=POPULATION_RUNNING)])

    response = trigger_population_run(
        TriggerPopulationRequest(admin_id=1, reason="test", priority=6),
        db,
    )

    assert response["status"] == "already_running"
    assert response["run_id"] == "run-active"


def test_trigger_population_queues_new_run(monkeypatch):
    db = _DB(runs=[])

    class _AsyncResult:
        id = "task-123"

    def _apply_async(**kwargs):
        assert kwargs["queue"] == "ingestion"
        return _AsyncResult()

    monkeypatch.setattr(
        "app.api.routes.admin_population.start_population_run.apply_async",
        _apply_async,
    )

    response = trigger_population_run(
        TriggerPopulationRequest(admin_id=1, reason="start", priority=5),
        db,
    )

    assert response == {"status": "queued", "run_id": response["run_id"], "task_id": "task-123"}


def test_list_population_runs_returns_serialized_payload():
    db = _DB(runs=[_run("run-1", status="PARTIAL")])

    payload = list_population_runs(db, status=None, limit=20, offset=0)

    assert payload["total"] == 1
    assert payload["items"][0]["run_id"] == "run-1"
    assert payload["items"][0]["status"] == "PARTIAL"


def test_get_population_run_not_found_raises_404():
    db = _DB(runs=[])

    with pytest.raises(HTTPException) as exc:
        get_population_run("missing-run", db)

    assert exc.value.status_code == 404


def test_get_population_run_returns_sources():
    db = _DB(runs=[_run("run-xyz", status="RUNNING")], source_runs=[_source_run("ecourts")])

    payload = get_population_run("run-xyz", db)

    assert payload["run"]["run_id"] == "run-xyz"
    assert payload["sources"][0]["source_name"] == "ecourts"
