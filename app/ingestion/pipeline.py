import asyncio
import logging

import httpx

from app.core.config import settings
from app.ingestion import checkpoint
from app.ingestion.chunker import is_clinically_useful, parse_label_into_chunks
from app.ingestion.embedder import embed_chunks
from app.ingestion.openfda_client import fetch_labels_for_class
from app.ingestion.repository import upsert_drugs_and_chunks, verify_upsert

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


async def _embed_label(label):
    if not is_clinically_useful(label):
        logger.info("Skipping low-quality label: %s", label.drug_name)
        return []

    chunks = parse_label_into_chunks(label)
    if not chunks:
        return []

    texts = [c.chunk_text for c in chunks]

    embeddings = await embed_chunks(texts)

    return [(label, chunk, embedding) for chunk, embedding in zip(chunks, embeddings)]


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

        all_embeddings = []

        for label in labels:
            try:
                result = await _embed_label(label)
                all_embeddings.extend(result)

                await asyncio.sleep(60 / settings.EMBEDDING_RPM_LIMIT)

            except Exception:
                logger.exception(
                    "Embedding failed for drug: %s",
                    label.drug_name,
                )
                continue

        if all_embeddings:
            checkpoint.write_embeddings(
                therapeutic_class,
                all_embeddings,
            )


async def stage_upsert() -> None:
    success = True

    for therapeutic_class in settings.SEED_THERAPEUTIC_CLASSES:
        if not checkpoint.embeddings_exist(therapeutic_class):
            logger.warning(
                "No embeddings checkpoint for: %s, skipping upsert",
                therapeutic_class,
            )
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
