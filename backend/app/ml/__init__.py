"""
Optional ML module — Case Duration Prediction & Delay Detection
===============================================================

This module predicts the expected duration of court cases and flags
cases that are unusually delayed compared to their predicted resolution
time. It is ENTIRELY OPTIONAL: if the model artifacts are not present,
or if ``ML_ENABLED=false`` in the environment, the rest of the application
continues to operate normally.

Sub-modules
-----------
config      — ML-specific settings (thresholds, paths, flags)
features    — Feature extraction from ORM objects
dataset     — Dataset assembly from the database
evaluation  — Regression metrics and time-based split
train       — Model training pipeline and artifact persistence
predict     — Inference interface with uncertainty bounds
outliers    — Delay ratio computation and severity classification

Usage
-----
The module is activated by:
    1. Setting ``ML_ENABLED=true`` in .env (or leaving it at the default).
    2. Running the Celery task  ``app.tasks.ml_train.retrain_duration_model``
       to produce the model artifacts.
    3. Optionally, triggering ``app.tasks.ml_train.run_ml_batch_inference``
       to populate the ``case_predictions`` table for all active cases.

The REST endpoint ``GET /api/v1/ml/case/{id}/prediction`` returns a
prediction with uncertainty bounds, delay ratio, and feature importance.
"""
