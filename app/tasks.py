import asyncio

from app.ingestion.pipeline import run_ingestion
from app.worker import celery_app


@celery_app.task(name="app.tasks.ingest_seed")
def ingest_seed():
    asyncio.run(run_ingestion())
