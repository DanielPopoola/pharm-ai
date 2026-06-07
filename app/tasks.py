import asyncio

from celery import chain

from app.ingestion.pipeline import (
    stage_embed,
    stage_embed_single,
    stage_fetch,
    stage_fetch_single,
    stage_upsert,
    stage_upsert_single,
)
from app.worker import celery_app


@celery_app.task(name="app.tasks.fetch_single_drug")
def fetch_single_drug(drug_name: str):
    asyncio.run(stage_fetch_single(drug_name))


@celery_app.task(name="app.tasks.embed_single_drug")
def embed_single_drug(drug_name: str):
    asyncio.run(stage_embed_single(drug_name))


@celery_app.task(name="app.tasks.upsert_single_drug")
def upsert_single_drug(drug_name: str):
    asyncio.run(stage_upsert_single(drug_name))


@celery_app.task(name="app.tasks.ingest_drug_on_demand")
def ingest_drug_on_demand(drug_name: str):
    pipeline = chain(
        fetch_single_drug.si(drug_name),
        embed_single_drug.si(drug_name),
        upsert_single_drug.si(drug_name),
    )
    pipeline.delay()


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
