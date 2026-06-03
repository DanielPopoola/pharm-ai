from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "pharmai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.beat_schedule = {
    "seed-ingestion-daily": {
        "task": "app.tasks.ingest_seed",
        "schedule": crontab(hour=2, minute=0),
    }
}

celery_app.conf.timezone = "UTC"
