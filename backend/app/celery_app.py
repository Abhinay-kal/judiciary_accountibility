from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("justice_tracker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue=settings.celery_task_default_queue,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="UTC",
)

celery_app.autodiscover_tasks(["app.tasks"])

# Import scheduler module so beat schedule is registered.
from app.tasks import scheduler  # noqa: E402,F401
