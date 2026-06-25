from celery import Celery

from app.core.config import get_settings
from app.queue import apply_multi_queue_config

settings = get_settings()

celery_app = Celery(
    "justice_tracker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
apply_multi_queue_config(celery_app)

celery_app.conf.imports = (
    "app.tasks.ingestion",
    "app.tasks.hearing_outcomes",
    "app.tasks.judge_reconcile",
    "app.tasks.ml_train",
    "app.tasks.ingestion_tasks",
    "app.tasks.reprocess",
    "app.tasks.importance_recompute",
    "app.tasks.delay_analytics",
    "app.tasks.survival_analytics",
    "app.tasks.dormancy_analytics",
    "app.tasks.cache_tasks",
    "app.tasks.notifications",
    "app.tasks.population",
    "app.tasks.analytics",
)

celery_app.autodiscover_tasks(["app.tasks"])

# Import scheduler module so beat schedule is registered.
from app.tasks import scheduler  # noqa: E402,F401
