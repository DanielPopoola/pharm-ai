import logging

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ingestion import checkpoint
from app.ingestion.chunker import is_clinically_useful, parse_label_into_chunks
from app.ingestion.embedder import embed_chunks
from app.ingestion.openfda_client import fetch_label_for_drug, fetch_labels_for_class
from app.ingestion.repository import complete_job, create_job, upsert_drugs_and_chunks, verify_upsert

logger = logging.getLogger("pharmai")


async def stage_fetch() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        for therapeutic_class in settings.SEED_THERAPEUTIC_CLASSES:
            if checkpoint.labels_exist(therapeutic_class):
                logger.info("Labels checkpoint exists, skipping: %s", therapeutic_class)
                continue

            labels = await fetch_labels_for_class(
                therapeutic_class,
                client,
            )

            if not labels:
                logger.info("No labels fetched for: %s", therapeutic_class)
                continue

            checkpoint.write_labels(therapeutic_class, labels)


def _extract_chunks(labels):
    chunks_with_labels = []

    for label in labels:
        if not is_clinically_useful(label):
            logger.info(
                "Skipping low-quality label: %s",
                label.drug_name,
            )
            continue

        chunks = parse_label_into_chunks(label)

        chunks_with_labels.extend((label, chunk) for chunk in chunks)

    return chunks_with_labels


async def stage_embed() -> None:
    for therapeutic_class in settings.SEED_THERAPEUTIC_CLASSES:
        if not checkpoint.labels_exist(therapeutic_class):
            logger.warning(
                "No labels checkpoint for: %s, skipping embed",
                therapeutic_class,
            )
            continue

        if checkpoint.embeddings_exist(therapeutic_class):
            logger.info(
                "Embeddings checkpoint exists, skipping: %s",
                therapeutic_class,
            )
            continue

        labels = checkpoint.read_labels(therapeutic_class)

        chunks_with_labels = _extract_chunks(labels)

        if not chunks_with_labels:
            logger.info(
                "No clinically useful chunks found for: %s",
                therapeutic_class,
            )
            continue

        try:
            texts = [chunk.chunk_text for _, chunk in chunks_with_labels]

            embeddings = await embed_chunks(texts)

            chunks_with_embeddings = [
                (label, chunk, embedding)
                for (label, chunk), embedding in zip(
                    chunks_with_labels,
                    embeddings,
                )
            ]

            checkpoint.write_embeddings(
                therapeutic_class,
                chunks_with_embeddings,
            )

            logger.info(
                "Embedded %s chunks for %s",
                len(chunks_with_embeddings),
                therapeutic_class,
            )

        except Exception:
            logger.exception(
                "Embedding failed for therapeutic class: %s",
                therapeutic_class,
            )


async def stage_upsert() -> None:
    success = True

    for therapeutic_class in settings.SEED_THERAPEUTIC_CLASSES:
        if not checkpoint.embeddings_exist(therapeutic_class):
            logger.warning(
                "No embeddings checkpoint for: %s, skipping upsert",
                therapeutic_class,
            )
            success = False
            continue

        drugs = checkpoint.read_embeddings(therapeutic_class)

        for drug in drugs:
            try:
                rows = await upsert_drugs_and_chunks(drug)

                if not verify_upsert(rows, drug):
                    logger.error(
                        "Upsert verification failed: %s",
                        drug["drug_name"],
                    )
                    success = False
                    continue

                logger.info("Upserted: %s", drug["drug_name"])

            except Exception:
                logger.exception(
                    "Failed upsert: %s",
                    drug["drug_name"],
                )
                success = False

    if success:
        checkpoint.wipe_checkpoints()
        logger.info("All classes upserted successfully, checkpoints wiped")
    else:
        logger.warning("Some upserts failed, checkpoints preserved")


async def stage_fetch_single(drug_name: str) -> None:
    async with AsyncSessionLocal() as session:
        await create_job(session, drug_name, triggered_by="cache_miss")

    async with httpx.AsyncClient(timeout=30) as client:
        labels = await fetch_label_for_drug(drug_name, client)

    if not labels:
        raise ValueError(f"No label found on OpenFDA for: {drug_name}")

    if not is_clinically_useful(labels[0]):
        raise ValueError(f"Label for {drug_name} did not pass quality filter")

    checkpoint.write_labels(drug_name, labels)
    logger.info("Fetched and checkpointed single drug: %s", drug_name)


async def stage_embed_single(drug_name: str) -> None:
    labels = checkpoint.read_labels(drug_name)
    chunks_with_labels = _extract_chunks(labels)

    if not chunks_with_labels:
        raise ValueError(f"No usable chunks for: {drug_name}")

    texts = [chunk.chunk_text for _, chunk in chunks_with_labels]
    embeddings = await embed_chunks(texts)

    chunks_with_embeddings = [
        (label, chunk, embedding) for (label, chunk), embedding in zip(chunks_with_labels, embeddings)
    ]

    checkpoint.write_embeddings(drug_name, chunks_with_embeddings)
    logger.info("Embedded single drug: %s", drug_name)


async def stage_upsert_single(drug_name: str) -> None:
    drugs = checkpoint.read_embeddings(drug_name)

    for drug in drugs:
        rows = await upsert_drugs_and_chunks(drug)
        if not verify_upsert(rows, drug):
            raise ValueError(f"Upsert verification failed for: {drug_name}")
        logger.info("Upserted: %s", drug["drug_name"])

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT id FROM ingestion_jobs \
                WHERE drug_name = :drug_name AND status = 'running' LIMIT 1"
            ),
            {"drug_name": drug_name},
        )
        row = result.mappings().first()
        if row:
            await complete_job(session, row["id"])

    checkpoint.wipe_checkpoints()
    logger.info("Upsert complete, checkpoints wiped: %s", drug_name)
