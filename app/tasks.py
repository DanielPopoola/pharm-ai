import asyncio

from celery import chain

from app.ingestion.pipeline import stage_embed, stage_fetch, stage_upsert
from app.worker import celery_app


@celery_app.task(name="app.tasks.fetch_labels")
def fetch_labels():
    asyncio.run(stage_fetch())


@celery_app.task(name="app.tasks.embed_labels")
def embed_labels():
    asyncio.run(stage_embed())


@celery_app.task(name="app.tasks.upsert_to_db")
def upsert_to_db():
    asyncio.run(stage_upsert())


@celery_app.task(name="app.tasks.ingest_seed")
def ingest_seed():
    pipeline = chain(
        fetch_labels.si(),
        embed_labels.si(),
        upsert_to_db.si(),
    )
    pipeline.delay()
