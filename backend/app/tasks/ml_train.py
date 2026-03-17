"""Celery tasks for ML model lifecycle management.

Tasks
-----
retrain_duration_model
    Trains (or retrains) the case-duration prediction model from the current
    database of disposed cases.  Saves versioned artifacts to disk.
    Intended schedule: weekly (every Monday at 03:00 UTC).

run_ml_batch_inference
    Runs the trained predictor over all non-disposed active cases and updates
    the ``case_predictions`` table with fresh delay flags.
    Intended schedule: daily after ingestion (at 04:00 UTC).

Both tasks are gated by ``ML_ENABLED`` and fail gracefully rather than
raising unhandled exceptions so that they never block the Celery worker queue.
"""
from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ml_train.retrain_duration_model",
    bind=True,
    max_retries=0,  # Do not retry — retraining with stale data is not useful
)
def retrain_duration_model(self) -> dict:
    """Weekly batch retraining of the case duration prediction model.

    Returns a summary dict with ``status``, ``version``, ``best_model``,
    ``metrics``, ``train_size``, and ``val_size`` on success.
    """
    from app.ml.config import get_ml_settings
    from app.ml.train import ModelTrainer

    ml_cfg = get_ml_settings()
    if not ml_cfg.ml_enabled:
        logger.info("ML_ENABLED=false — skipping model retraining")
        return {"status": "skipped", "reason": "ML_ENABLED=false"}

    db = SessionLocal()
    try:
        trainer = ModelTrainer()
        result = trainer.train(db)
        logger.info("Model retraining complete: %s", result)
        # Reload the singleton predictor so live endpoints immediately pick up
        # the new model without a process restart.
        from app.ml.predict import get_predictor

        get_predictor().reload()
        return {"status": "success", **result}
    except Exception as exc:
        logger.exception("Model retraining failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.ml_train.run_ml_batch_inference",
    bind=True,
    max_retries=1,
)
def run_ml_batch_inference(self) -> dict:
    """Daily batch inference: score all active cases for predicted delay.

    Populates / refreshes the ``case_predictions`` table.  Safe to run
    multiple times — existing rows are updated in-place.
    """
    from app.ml.config import get_ml_settings
    from app.ml.outliers import flag_delayed_cases
    from app.ml.predict import get_predictor

    ml_cfg = get_ml_settings()
    if not ml_cfg.ml_enabled:
        return {"status": "skipped", "reason": "ML_ENABLED=false"}

    predictor = get_predictor()
    db = SessionLocal()
    try:
        flagged = flag_delayed_cases(db, predictor)
        return {"status": "success", "flagged_count": len(flagged)}
    except Exception as exc:
        logger.exception("Batch ML inference failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
