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
