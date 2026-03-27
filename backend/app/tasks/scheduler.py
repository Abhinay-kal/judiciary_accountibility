from celery.schedules import crontab

from app.celery_app import celery_app
from app.core.config import get_settings
from app.ingestion.config import get_ingestion_settings

_ingest_settings = get_ingestion_settings()
_ingest_interval = max(1, min(59, _ingest_settings.ingest_scheduler_interval_minutes))
_settings = get_settings()

celery_app.conf.beat_schedule = {
    "daily-ingestion": {
        "task": "app.tasks.ingestion.run_daily_ingestion",
        "schedule": crontab(minute=0, hour=2),
    },
    # ML: batch inference runs daily at 04:00 UTC (after ingestion completes)
    "daily-ml-inference": {
        "task": "app.tasks.ml_train.run_ml_batch_inference",
        "schedule": crontab(minute=0, hour=4),
    },
    # ML: full retraining runs every Monday at 03:00 UTC
    "weekly-ml-retrain": {
        "task": "app.tasks.ml_train.retrain_duration_model",
        "schedule": crontab(minute=0, hour=3, day_of_week=1),
    },
    "weekly-hearing-outcome-ml-retrain": {
        "task": "app.tasks.hearing_outcomes.retrain_hearing_outcome_model",
        "schedule": crontab(minute=30, hour=3, day_of_week=1),
    },
    # Resilient ingestion: dynamic scheduler sweeps every N minutes
    "resilient-ingestion-scheduler": {
        "task": "app.tasks.ingestion_tasks.run_ingestion_scheduler",
        "schedule": crontab(minute=f"*/{_ingest_interval}"),
    },
    # Resilient ingestion: monitor sweep runs every 15 minutes
    "resilient-ingestion-monitor": {
        "task": "app.tasks.ingestion_tasks.run_monitor_sweep_task",
        "schedule": crontab(minute="*/15"),
    },
    "ingestion-deferred-batch-jobs": {
        "task": "app.tasks.ingestion_tasks.run_deferred_batch_jobs",
        "schedule": crontab(minute=30, hour=2),
    },
    "ingestion-reprocess-dry-run": {
        "task": "app.tasks.reprocess.reprocess_raw_snapshots",
        "schedule": crontab(minute=0, hour=6),
        "args": ("parser-minimal-v1", 300, True),
    },
    "daily-hearing-outcome-reprocess": {
        "task": "app.tasks.hearing_outcomes.reprocess_hearing_outcomes",
        "schedule": crontab(minute=0, hour=5),
    },
    "daily-judge-reconcile": {
        "task": "app.tasks.judge_reconcile.reconcile_judges",
        "schedule": crontab(minute=30, hour=5),
    },
    "daily-importance-recompute": {
        "task": "app.tasks.importance_recompute.recompute_case_importance",
        "schedule": crontab(minute=0, hour=7),
        "args": (_settings.importance_daily_batch_size,),
    },
    "daily-delay-baseline-recompute": {
        "task": "app.tasks.delay_analytics.recompute_delay_baselines",
        "schedule": crontab(minute=20, hour=7),
    },
    "daily-delay-case-analytics-refresh": {
        "task": "app.tasks.delay_analytics.update_case_delay_analytics",
        "schedule": crontab(minute=45, hour=7),
        "args": (_settings.delay_update_batch_size,),
    },
    "daily-admin-population-run": {
        "task": "app.tasks.population.start_population_run",
        "schedule": crontab(minute=15, hour=3),
        "kwargs": {"trigger_type": "SCHEDULED", "reason": "daily scheduled population"},
    },
    "daily-survival-curves-recompute": {
        "task": "app.tasks.survival_analytics.recompute_survival_curves",
        "schedule": crontab(minute=15, hour=8),
    },
    "daily-survival-anomaly-flagging": {
        "task": "app.tasks.survival_analytics.flag_survival_anomalies",
        "schedule": crontab(minute=45, hour=8),
        "args": (_settings.survival_recompute_batch_size,),
    },
    "daily-dormancy-recompute": {
        "task": "app.tasks.dormancy_analytics.recompute_case_dormancy",
        "schedule": crontab(minute=20, hour=9),
        "args": (_settings.dormancy_batch_size,),
    },
}

if _settings.cache_warmup_enabled:
    celery_app.conf.beat_schedule.update(
        {
            "cache-precomputed-refresh": {
                "task": "app.tasks.cache_tasks.refresh_precomputed_cache",
                "schedule": crontab(minute="*/30"),
            },
            "cache-hot-case-warmup": {
                "task": "app.tasks.cache_tasks.warmup_hot_case_cache",
                "schedule": crontab(minute="*/20"),
                "args": (100,),
            },
        }
    )
