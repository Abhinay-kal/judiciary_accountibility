from celery.schedules import crontab

from app.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "daily-ingestion": {
        "task": "app.tasks.ingestion.run_daily_ingestion",
        "schedule": crontab(minute=0, hour=2),
    },
}
