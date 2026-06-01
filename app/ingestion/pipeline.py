import logging

import httpx

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ingestion.chunker import parse_label_into_chunks
from app.ingestion.embedder import embed_chunks
from app.ingestion.openfda_client import (
    fetch_label_for_drug,
    fetch_labels_for_class,
)
from app.ingestion.repository import (
    complete_job,
    create_job,
    fail_job,
    upsert_drugs_and_chunks,
)

logger = logging.getLogger("pharmai")


async def run_ingestion(drug_name: str | None = None):
    async with AsyncSessionLocal() as session:
        job_id = await create_job(
            session=session,
            drug_name=drug_name or "seed",
            triggered_by="seed" if not drug_name else "cache_miss",
        )

        try:
            labels = await _fetch_labels(drug_name)

            chunks = _build_chunks(labels)

            if not chunks:
                logger.info("No chunks generated; finishing early")
                await complete_job(session, job_id)
                return

            texts = [c.chunk_text for _, c in chunks]
            embeddings = await embed_chunks(texts)

            await upsert_drugs_and_chunks(session, chunks, embeddings)

            await complete_job(session, job_id)

            logger.info(
                "Ingestion complete: %s drugs, %s chunks",
                len({label.drug_name for label, _ in chunks}),
                len(chunks),
            )

        except Exception as e:
            await fail_job(session, job_id, str(e))
            logger.exception("Ingestion failed")
            raise


async def _fetch_labels(drug_name: str | None):
    async with httpx.AsyncClient(timeout=30) as client:
        if drug_name:
            return await fetch_label_for_drug(drug_name, client)

        labels = []
        for therapeutic_class in settings.SEED_THERAPEUTIC_CLASSES:
            batch = await fetch_labels_for_class(therapeutic_class, client)
            labels.extend(batch)

        return labels


def _build_chunks(labels):
    chunks = []

    for label in labels:
        for chunk in parse_label_into_chunks(label):
            chunks.append((label, chunk))

    return chunks
