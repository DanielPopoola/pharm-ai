import os

from celery import Celery

celery_app = Celery(
    "pharmai",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
)
